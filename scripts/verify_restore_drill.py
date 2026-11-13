"""Prepare and verify local-only disaster-recovery fixtures without paid providers."""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import psycopg
from fastapi.testclient import TestClient
from PIL import Image
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from restore_protocol_fixture import run_cost_review_fixture

from visual_platform.api.main import create_app
from visual_platform.core.identity import hash_password
from visual_platform.core.settings import Settings
from visual_platform.db.pool import open_pool
from visual_platform.db.result import required_row
from visual_platform.domain.provider_pricing import SupplierPriceVersion, canonical_price
from visual_platform.domain.schemas import QuoteRequest, canonical_hash
from visual_platform.providers.authorization import (
    ProviderAuthorization,
    SmokeAuthorization,
    UnitSmokeAuthorization,
    canonical_authorization,
)
from visual_platform.providers.fake import DurableFakeProvider
from visual_platform.providers.pipeline import BASELINE_ENDPOINTS
from visual_platform.services.backup import require
from visual_platform.services.config_backup import validate_configuration
from visual_platform.services.detection_delivery import (
    approve_detection_delivery,
    detection_delivery_context,
)
from visual_platform.services.provider_budget import (
    provider_budget_snapshot,
    provider_quote_review,
    register_provider_budget,
)
from visual_platform.services.provider_pricing import (
    publish_supplier_price,
    supplier_price_context,
    supplier_task_costs,
)
from visual_platform.services.quotes import hash_data
from visual_platform.services.rule_operations import publish_rule
from visual_platform.storage.s3 import S3Storage, StorageError
from visual_platform.worker.runner import Worker

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="command", required=True)
prepare = sub.add_parser("prepare")
prepare.add_argument("--profile-dir", type=Path, default=ROOT / ".local")
verify = sub.add_parser("verify")
verify.add_argument("--profile-dir", type=Path, required=True)
verify.add_argument("--restore-result", type=Path, required=True)
cleanup = sub.add_parser("cleanup")
cleanup.add_argument("--profile-dir", type=Path, default=ROOT / ".local")
marker = sub.add_parser("marker")
marker.add_argument("--profile-dir", type=Path, default=ROOT / ".local")
for command in (prepare, verify, cleanup, marker):
    command.add_argument("--state", type=Path, required=True)
args = p.parse_args()
profile = json.loads((args.profile_dir.resolve() / "runtime.json").read_text())
require(profile["PROVIDER_PROFILE"] == "offline", "offline profile required")
require(
    all(
        urlsplit(profile[key]).hostname in ("127.0.0.1", "localhost")
        for key in (
            "APP_ORIGIN",
            "API_DATABASE_URL",
            "AUTH_DATABASE_URL",
            "ADMIN_DATABASE_URL",
            "WORKER_DATABASE_URL",
            "S3_ENDPOINT",
        )
    ),
    "drill fixtures require an explicit loopback profile",
)
settings = Settings(
    profile["API_DATABASE_URL"],
    profile["AUTH_DATABASE_URL"],
    Path(profile["JWT_PRIVATE_KEY_FILE"]).read_text(),
    Path(profile["JWT_PUBLIC_KEY_FILE"]).read_text(),
    profile["APP_ORIGIN"],
    False,
    profile["S3_ENDPOINT"],
    profile["S3_ACCESS_KEY"],
    profile["S3_SECRET_KEY"],
    profile["S3_BUCKET"],
    profile["S3_REGION"],
)


def login(client, state):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": state["email"], "password": state["password"]},
        headers={"origin": profile["APP_ORIGIN"]},
    )
    require(response.status_code == 200, "drill login failed")
    return {"origin": profile["APP_ORIGIN"], "x-csrf-token": client.cookies["visual_csrf"]}


def task(client, body, headers):
    q = client.post("/api/v1/quotes", json=body, headers=headers)
    require(q.status_code == 201, "drill quote failed")
    r = client.post(
        "/api/v1/tasks",
        json={**body, "quote_id": q.json()["quote_id"]},
        headers={**headers, "idempotency-key": str(uuid4())},
    )
    require(r.status_code == 201, "drill task failed")
    return r.json()["id"]


def run_worker(task_id, mode="success", broken=False):
    class ArchiveOutage(S3Storage):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def fail(*args, **kwargs):
                raise StorageError("controlled archive outage")

            self.client.put_object = fail

    async def run():
        pool = await open_pool(profile["WORKER_DATABASE_URL"], "app_worker")
        storage = (ArchiveOutage if broken else S3Storage)(settings)
        try:
            return await Worker(
                pool, storage, DurableFakeProvider(Path(profile["FAKE_PROVIDER_DIR"]), mode=mode)
            ).run(task_id)
        finally:
            await pool.close()
            storage.close()

    return asyncio.run(run())


def admin(query, values):
    with psycopg.connect(profile["ADMIN_DATABASE_URL"]) as c:
        return required_row(c.execute(query, values))[0]


def register_drill_budget(quote_identity, snapshot, uid, *, unit_budget=False):
    instant = datetime.now(timezone.utc)
    scope: ProviderAuthorization = SmokeAuthorization.model_validate_json(
        json.dumps(
            {
                "authorization_id": str(uuid4()),
                "user_id": str(uid),
                "product_id": snapshot["product_id"],
                "source_asset_version_id": snapshot["source_asset_version_id"],
                "quote_input_sha256": hash_data(snapshot),
                "authorized_by": "synthetic offline recovery review",
                "authorized_at": instant.isoformat(),
                "expires_at": (instant + timedelta(hours=1)).isoformat(),
                "source_path": "restore-fixture.png",
                "source_sha256": snapshot["_execution"]["source_sha256"],
                "generation": snapshot["generation"],
                "targets": snapshot["targets"],
                "generate_ceiling": "0.10",
                "detect_ceiling": "0.02",
                "total_ceiling": "0.12",
            }
        )
    )
    if unit_budget:
        data = scope.model_dump(mode="json")
        for field in ("currency", "generate_ceiling", "detect_ceiling", "total_ceiling"):
            data.pop(field)
        data.update(
            schema_version=3,
            step_budgets={
                "generate": {"currency": "BFL_CREDIT", "ceiling": "0.10"},
                "detect": {"currency": "HUBWAY_BALANCE_UNIT", "ceiling": "0.02"},
            },
            currency_totals=[
                {"currency": "BFL_CREDIT", "ceiling": "0.10"},
                {"currency": "HUBWAY_BALANCE_UNIT", "ceiling": "0.02"},
            ],
        )
        scope = UnitSmokeAuthorization.model_validate_json(json.dumps(data))
    digest = hashlib.sha256(canonical_authorization(scope)).hexdigest()
    identity = register_provider_budget(
        profile["ADMIN_DATABASE_URL"],
        quote_identity,
        scope,
        digest,
        uuid4(),
        "synthetic restore budget",
    )
    return scope, digest, identity


if args.command == "prepare":
    require(
        args.state.resolve().is_relative_to(ROOT / "work") and not args.state.exists(),
        "new private drill state required",
    )
    uid = uuid4()
    state: dict[str, Any] = {
        "user_id": str(uid),
        "email": "restore-" + uuid4().hex + "@example.invalid",
        "password": uuid4().hex + uuid4().hex,
        "tasks": {},
    }
    admin(
        "SELECT app.create_private_user(%s,%s,'backup restore drill',%s)",
        (uid, state["email"], hash_password(state["password"])),
    )
    admin("SELECT app.grant_credits(%s,%s,200,'offline restore fixture credits')", (uid, uuid4()))
    storage = S3Storage(settings)
    evidence = (
        b"Offline synthetic rule archive for backup restoration; not current platform policy."
    )
    try:
        now = datetime.now(timezone.utc)
        price_evidence = b"Synthetic supplier price backup fixture; no actual monetary rates."
        price = SupplierPriceVersion.model_validate_json(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "bfl",
                    "model": "flux-3-image",
                    "endpoint_origin": "https://api.bfl.ai",
                    "merchant_fingerprint": "a" * 64,
                    "billing_group": "offline-restore-fixture",
                    "version": "restore-" + uuid4().hex,
                    "currency": "BFL_CREDIT",
                    "valid_from": (now - timedelta(minutes=1)).isoformat(),
                    "valid_until": (now + timedelta(hours=1)).isoformat(),
                    "evidence_kind": "offline_fixture",
                    "evidence_sha256": hashlib.sha256(price_evidence).hexdigest(),
                    "complete_meter_coverage": True,
                    "rates": [{"measure": "bfl_credit", "amount": "1", "per": 1}],
                }
            )
        )
        state["supplier_price_id"] = publish_supplier_price(
            profile["ADMIN_DATABASE_URL"],
            storage,
            price,
            price_evidence,
            uuid4(),
            "synthetic price archive for independent restore",
            evidence_reviewed=True,
        )
        state["supplier_price_sha256"] = hashlib.sha256(canonical_price(price)).hexdigest()
        state["supplier_price_evidence_sha256"] = hashlib.sha256(price_evidence).hexdigest()
        vision_data = price.model_dump(mode="json")
        vision_data.update(
            provider="gemini",
            model="gemini-3.8-flash",
            endpoint_origin="https://generativelanguage.googleapis.com",
            currency="HUBWAY_BALANCE_UNIT",
            version="restore-vision-" + uuid4().hex,
            rates=[{"measure": "input_tokens", "amount": "1", "per": 1000000}],
        )
        vision_price = SupplierPriceVersion.model_validate_json(json.dumps(vision_data))
        state["vision_price_id"] = publish_supplier_price(
            profile["ADMIN_DATABASE_URL"],
            storage,
            vision_price,
            price_evidence,
            uuid4(),
            "synthetic detection unit price for unused restore budget",
            evidence_reviewed=True,
        )
        state["vision_price_sha256"] = hashlib.sha256(canonical_price(vision_price)).hexdigest()
        rule = publish_rule(
            profile["ADMIN_DATABASE_URL"],
            storage,
            {
                "platform": "amazon",
                "marketplace": "US",
                "category": "backup-synthetic",
                "image_type": "MAIN",
                "version": "backup-" + uuid4().hex,
                "evidence_status": "unverified",
                "evidence_sha256": hashlib.sha256(evidence).hexdigest(),
                "config": {},
            },
            evidence,
            uuid4(),
            "archive synthetic backup rule fixture",
        )
    finally:
        storage.close()
    state["rule_id"] = rule["rule_id"]
    with TestClient(create_app(settings)) as client:
        headers = login(client, state)
        state["old_access"] = client.cookies["visual_access"]
        product = client.post(
            "/api/v1/products",
            json={"name": "restore synthetic product", "category": "backup-synthetic"},
            headers=headers,
        )
        require(product.status_code == 201, "drill product failed")
        state["product_id"] = product.json()["id"]
        stream = BytesIO()
        Image.new("RGB", (256, 256), (201, 15, 35)).save(stream, "PNG")
        data = stream.getvalue()
        intent = client.post(
            "/api/v1/assets/upload-intents",
            json={
                "product_id": state["product_id"],
                "filename": "restore.png",
                "mime": "image/png",
                "size": len(data),
            },
            headers=headers,
        ).json()
        require(
            httpx.put(intent["upload_url"], content=data, headers=intent["headers"]).status_code
            == 200,
            "drill upload failed",
        )
        complete = client.post(
            "/api/v1/assets/upload-intents/" + intent["intent_id"] + "/complete", headers=headers
        )
        require(complete.status_code == 200, "drill normalize failed")
        source = complete.json()
        appearance = client.post(
            "/api/v1/products/" + state["product_id"] + "/appearances",
            json={"name": "restore appearance", "config": {"colors": ["red"]}},
            headers=headers,
        )
        require(appearance.status_code == 201, "drill appearance failed")
        body = {
            "product_id": state["product_id"],
            "source_asset_version_id": source["version_id"],
            "appearance_profile_id": appearance.json()["id"],
            "generation": {
                "type": "scene",
                "prompt": "offline backup fixture",
                "output": {"width": 256, "height": 256, "format": "png"},
                "protection_mode": "pixel_exact",
                "regions": [
                    {
                        "source_x": 0,
                        "source_y": 0,
                        "width": 4,
                        "height": 4,
                        "target_x": 8,
                        "target_y": 8,
                    }
                ],
            },
            "targets": [
                {
                    "platform": "amazon",
                    "marketplace": "US",
                    "category": "backup-synthetic",
                    "image_type": "MAIN",
                }
            ],
        }
        state["tasks"]["completed"] = task(client, body, headers)
        require(
            run_worker(state["tasks"]["completed"]) == "succeeded", "drill completed task failed"
        )
        report = client.get("/api/v1/tasks/" + state["tasks"]["completed"] + "/compliance").json()
        state["report_sha256"] = report["report_sha256"]
        state["final_sha256"] = report["final_sha256"]
        admin(
            "SELECT app.review_check(%s,%s,%s,%s,%s,%s,%s)",
            (
                state["tasks"]["completed"],
                report["id"],
                uuid4(),
                uid,
                "approved",
                "synthetic fixture manual review",
                Jsonb(["local:restore-drill"]),
            ),
        )
        state["tasks"]["known"] = task(client, body, headers)
        require(
            run_worker(state["tasks"]["known"], broken=True) == "retryable",
            "known-id outage fixture failed",
        )
        known = admin("SELECT ops.task_details(%s)", (state["tasks"]["known"],))
        state["known_receipt_id"] = known["receipts"][0]["id"]
        state["tasks"]["unknown"] = task(client, body, headers)
        require(
            run_worker(state["tasks"]["unknown"], "uncertain") == "stopped",
            "unknown fixture failed",
        )
        state["tasks"]["degraded"] = task(client, body, headers)
        require(
            run_worker(state["tasks"]["degraded"], "detect_uncertain") == "stopped",
            "detection unknown fixture failed",
        )
        context = detection_delivery_context(
            profile["ADMIN_DATABASE_URL"], UUID(state["tasks"]["degraded"])
        )
        state["detection_review"] = {
            "attempt": context["detect_attempt"]["id"],
            "sha256": context["final"]["sha256"],
            "operation": str(uuid4()),
            "reason": "reviewed offline final before backup",
        }
        review = state["detection_review"]
        state["detection_decision"] = approve_detection_delivery(
            profile["ADMIN_DATABASE_URL"],
            UUID(state["tasks"]["degraded"]),
            UUID(review["attempt"]),
            review["sha256"],
            UUID(review["operation"]),
            review["reason"],
            review["sha256"],
        )
        state["tasks"]["queued"] = task(client, body, headers)
        quoted_cost = client.post("/api/v1/quotes", json=body, headers=headers)
        require(quoted_cost.status_code == 201, "cost-review source quote failed")
        with psycopg.connect(profile["API_DATABASE_URL"]) as connection:
            connection.execute("SELECT set_config('app.user_id',%s,true)", (str(uid),))
            cost_snapshot = required_row(
                connection.execute(
                    "SELECT input_snapshot FROM app.quotes WHERE id=%s",
                    (quoted_cost.json()["quote_id"],),
                )
            )[0]
            cost_accounts = {
                "generate": {
                    "merchant_fingerprint": price.merchant_fingerprint,
                    "billing_group": price.billing_group,
                }
            }
            cost_snapshot["_execution"].update(
                provider_profile="offline_protocol_mock",
                provider_model="flux-3-image-protocol-mock",
                price_version="trial-protocol-mock-v1",
                provider_accounts=cost_accounts,
                provider_endpoints=BASELINE_ENDPOINTS,
                provider_price_versions={
                    "generate": {
                        "id": state["supplier_price_id"],
                        "document_sha256": state["supplier_price_sha256"],
                    }
                },
            )
            cost_quote = uuid4()
            connection.execute(
                "SELECT app.create_quote(%s,%s,%s,%s::jsonb,%s::jsonb)",
                (
                    cost_quote,
                    canonical_hash(QuoteRequest.model_validate(body)),
                    hash_data(cost_snapshot),
                    json.dumps(cost_snapshot),
                    json.dumps(cost_snapshot["_execution"]["rules"]),
                ),
            )
        _, _, state["cost_review_budget_id"] = register_drill_budget(cost_quote, cost_snapshot, uid)
        cost_created = client.post(
            "/api/v1/tasks",
            json={**body, "quote_id": str(cost_quote)},
            headers={**headers, "idempotency-key": str(uuid4())},
        )
        require(cost_created.status_code == 201, "cost-review task failed")
        state["tasks"]["cost_review"] = cost_created.json()["id"]
        cost_run = run_cost_review_fixture(
            profile, settings, UUID(state["tasks"]["cost_review"]), cost_accounts
        )
        require(
            cost_run["result"] == "stopped" and cost_run["posts"] == {"generate": 1, "detect": 0},
            "incomparable cost did not stop next synthetic paid step",
        )
        state["cost_review_costs"] = supplier_task_costs(
            profile["ADMIN_DATABASE_URL"], UUID(state["tasks"]["cost_review"])
        )
        require(
            len(state["cost_review_costs"]["estimates"]) == 1
            and state["cost_review_costs"]["estimates"][0]["currency"] == "BFL_CREDIT"
            and state["cost_review_costs"]["estimates"][0]["ceiling_state"] == "unknown",
            "cost-review estimate fixture invalid",
        )
        state["balance"] = client.get("/api/v1/credits/balance").json()
        require(
            (
                state["balance"]["available"],
                state["balance"]["reserved"],
                state["balance"]["spent_total"],
            )
            == (104, 80, 16),
            "fixture balance mismatch",
        )
    # Keep one reviewed, unused quote in the snapshot: it may have been consumed
    # after backup, so restore must revoke it even though no task existed then.
    with TestClient(create_app(settings)) as client:
        headers = login(client, state)
        quotation = client.post("/api/v1/quotes", json=body, headers=headers)
        require(quotation.status_code == 201, "unused budget quote source failed")
    with psycopg.connect(profile["API_DATABASE_URL"]) as c:
        c.execute("SELECT set_config('app.user_id',%s,true)", (str(uid),))
        snapshot = required_row(
            c.execute(
                "SELECT input_snapshot FROM app.quotes WHERE id=%s", (quotation.json()["quote_id"],)
            )
        )[0]
        snapshot["_execution"].update(
            provider_profile="offline_protocol_mock",
            provider_model="flux-3-image-protocol-mock",
            price_version="trial-protocol-mock-v1",
            provider_endpoints=BASELINE_ENDPOINTS,
            provider_accounts={
                step: {
                    "merchant_fingerprint": price.merchant_fingerprint,
                    "billing_group": price.billing_group,
                }
                for step in ("generate", "detect")
            },
            provider_price_versions={
                "generate": {
                    "id": state["supplier_price_id"],
                    "document_sha256": state["supplier_price_sha256"],
                },
                "detect": {
                    "id": state["vision_price_id"],
                    "document_sha256": state["vision_price_sha256"],
                },
            },
        )
        quote_identity = uuid4()
        c.execute(
            "SELECT app.create_quote(%s,%s,%s,%s::jsonb,%s::jsonb)",
            (
                quote_identity,
                canonical_hash(QuoteRequest.model_validate(body)),
                hash_data(snapshot),
                json.dumps(snapshot),
                json.dumps(snapshot["_execution"]["rules"]),
            ),
        )
    scope, digest, state["budget_authorization_id"] = register_drill_budget(
        quote_identity, snapshot, uid, unit_budget=True
    )
    state["budget_quote_id"] = str(quote_identity)
    state["budget_scope_sha256"] = digest
    require(
        provider_budget_snapshot(profile["ADMIN_DATABASE_URL"], scope.authorization_id)["state"]
        == "open",
        "source authorization not open",
    )
    before_budget = provider_budget_snapshot(profile["ADMIN_DATABASE_URL"], scope.authorization_id)
    state["unit_limits"] = before_budget["limits_by_currency"]
    state["step_limits"] = before_budget["step_limits"]
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(state))
    print("Prepared isolated restore fixtures; private state retained in work.")
elif args.command == "marker":
    state = json.loads(args.state.read_text())
    with TestClient(create_app(settings)) as client:
        headers = login(client, state)
        response = client.post(
            "/api/v1/products",
            json={"name": "post-backup marker", "category": "backup-synthetic"},
            headers=headers,
        )
        require(response.status_code == 201, "marker failed")
        state["post_snapshot_product_id"] = response.json()["id"]
    args.state.write_text(json.dumps(state))
    print("Post-snapshot marker created.")
elif args.command == "verify":
    state = json.loads(args.state.read_text())
    result = json.loads(args.restore_result.read_text())
    configuration = result.get("configuration_restore", {})
    require(
        configuration.get("status") == "verified_snapshot_restored"
        and configuration.get("applied_to_runtime") is False,
        "configuration snapshot restoration proof missing",
    )
    config_root = Path(configuration["output"])
    config_manifest = json.loads((config_root / "application.json").read_text())
    verified_config = validate_configuration(config_root, config_manifest)
    require(
        all(
            configuration[key] == verified_config[key]
            for key in ("application_commit", "files_verified", "snapshot_sha256")
        ),
        "restored configuration version or checksum differs",
    )
    with TestClient(create_app(settings)) as client:
        require(client.get("/api/v1/health/ready").status_code == 200, "restored API not ready")
        require(
            client.get(
                "/api/v1/auth/me", headers={"cookie": "visual_access=" + state["old_access"]}
            ).status_code
            == 401,
            "old access accepted",
        )
        client.cookies.clear()
        headers = login(client, state)
        budget = provider_budget_snapshot(
            profile["ADMIN_DATABASE_URL"], UUID(state["budget_authorization_id"])
        )
        require(
            budget["state"] == "blocked"
            and budget["scope_sha256"] == state["budget_scope_sha256"]
            and budget["holds"] == []
            and budget["schema_version"] == 3
            and budget["limits_by_currency"] == state["unit_limits"]
            and budget["step_limits"] == state["step_limits"]
            and all(
                budget[key] is None
                for key in (
                    "currency",
                    "total_ceiling",
                    "reserved_ceiling_total",
                    "known_estimate_subtotal",
                )
            ),
            "restored unused authorization not revoked",
        )
        require(
            result.get("provider_budgets_revoked", 0) >= 1,
            "restore did not report budget revocation",
        )
        review = provider_quote_review(
            profile["ADMIN_DATABASE_URL"], UUID(state["user_id"]), UUID(state["budget_quote_id"])
        )
        snapshot = review["input_snapshot"]
        business = {
            k: snapshot[k]
            for k in (
                "product_id",
                "source_asset_version_id",
                "appearance_profile_id",
                "generation",
                "targets",
            )
            if k in snapshot and snapshot[k] is not None
        }
        probe = client.post(
            "/api/v1/tasks",
            json={**business, "quote_id": state["budget_quote_id"]},
            headers={**headers, "Idempotency-Key": str(uuid4())},
        )
        require(probe.status_code == 201, "restore budget probe task failed")
        probe_id = probe.json()["id"]
        probe_owner = "restore-budget-" + uuid4().hex
        with psycopg.connect(profile["WORKER_DATABASE_URL"]) as c:
            claim = required_row(
                c.execute("SELECT ops.claim_task(%s,%s)", (probe_id, probe_owner))
            )[0]
        try:
            with psycopg.connect(profile["WORKER_DATABASE_URL"]) as c:
                c.execute(
                    "SELECT app.record_intent(%s,%s,%s,'generate',%s)",
                    (probe_id, probe_owner, claim["fencing_token"], "a" * 64),
                )
        except psycopg.errors.RaiseException as error:
            require(
                str(error).splitlines()[0] == "provider_budget_blocked",
                "unexpected restore budget rejection",
            )
        else:
            raise ValueError("restored authorization permitted a new intent")
        with psycopg.connect(profile["WORKER_DATABASE_URL"]) as c:
            c.execute(
                "SELECT app.fail_task(%s,%s,%s,'restore_budget_probe',false)",
                (probe_id, probe_owner, claim["fencing_token"]),
            )
        require(
            provider_budget_snapshot(
                profile["ADMIN_DATABASE_URL"], UUID(state["budget_authorization_id"])
            )["holds"]
            == [],
            "restore probe left a monetary reservation",
        )
        require(
            client.get("/api/v1/products/" + state["post_snapshot_product_id"]).status_code == 404,
            "post-snapshot marker unexpectedly restored",
        )
        require(
            client.get("/api/v1/credits/balance").json() == state["balance"],
            "restored frozen wallet mismatch",
        )
        restored_price = supplier_price_context(
            profile["ADMIN_DATABASE_URL"], UUID(state["supplier_price_id"])
        )
        require(
            restored_price["document_sha256"] == state["supplier_price_sha256"],
            "supplier price version changed on restore",
        )
        pointer = admin(
            "SELECT jsonb_build_object('key',evidence_object_key,'version',evidence_storage_version_id) FROM ops.supplier_price_versions WHERE id=%s",
            (state["supplier_price_id"],),
        )
        private_storage = S3Storage(settings)
        try:
            archive, _, _ = private_storage.get(pointer["key"], version=pointer["version"])
            require(
                hashlib.sha256(archive).hexdigest() == state["supplier_price_evidence_sha256"],
                "supplier price archive not restored",
            )
        finally:
            private_storage.close()
        report = client.get("/api/v1/tasks/" + state["tasks"]["completed"] + "/compliance").json()
        require(
            report["report_sha256"] == state["report_sha256"]
            and report["final_sha256"] == state["final_sha256"]
            and report["effective_source"] == "human_review",
            "restored report/review mismatch",
        )
        download = client.get(
            "/api/v1/tasks/" + state["tasks"]["completed"] + "/download", follow_redirects=False
        )
        image = httpx.get(download.headers["location"]).content
        require(
            hashlib.sha256(image).hexdigest() == state["final_sha256"],
            "restored final download mismatch",
        )
        with Image.open(BytesIO(image)) as final:
            require(
                final.convert("RGB").crop((8, 8, 12, 12)).tobytes()
                == Image.new("RGB", (4, 4), (201, 15, 35)).tobytes(),
                "restored protection pixels mismatch",
            )
        for key in ("queued", "known", "unknown", "degraded", "cost_review"):
            require(
                client.get("/api/v1/tasks/" + state["tasks"][key]).json()["status"] == "uncertain",
                "pending task not quarantined",
            )
        require(
            run_worker(state["tasks"]["queued"]) == "not_claimed"
            and run_worker(state["tasks"]["unknown"]) == "not_claimed",
            "restored unresolved task was claimed",
        )
        restored_costs = supplier_task_costs(
            profile["ADMIN_DATABASE_URL"], UUID(state["tasks"]["cost_review"])
        )
        require(
            restored_costs == state["cost_review_costs"]
            and not restored_costs["actual_spending_verified"],
            "restored cost estimate history changed",
        )
        cost_budget = provider_budget_snapshot(
            profile["ADMIN_DATABASE_URL"], UUID(state["cost_review_budget_id"])
        )
        require(
            cost_budget["state"] == "blocked"
            and cost_budget["blocked_for_cost_review"]
            and cost_budget["known_estimate_subtotal"] is None
            and not cost_budget["actual_spending_verified"],
            "restored nominal estimate was converted or budget reopened",
        )
        require(
            run_worker(state["tasks"]["cost_review"]) == "not_claimed",
            "restored cost-review task escaped quarantine",
        )
        cost_details = admin("SELECT ops.task_details(%s)", (state["tasks"]["cost_review"],))
        require(
            len(cost_details["attempts"]) == 1
            and cost_details["attempts"][0]["step"] == "generate",
            "restored cost-review task submitted another model",
        )
        before = admin("SELECT ops.task_details(%s)", (state["tasks"]["known"],))
        require(
            len([a for a in before["attempts"] if a["step"] == "generate"]) == 1,
            "generation attempt mismatch",
        )
        admin(
            "SELECT ops.reconcile_task(%s,%s,%s,%s,%s,%s)",
            (
                state["tasks"]["known"],
                uuid4(),
                "resume",
                state["known_receipt_id"],
                "source workers were fenced before snapshot; original generation receipt verified",
                "a" * 64,
            ),
        )
        require(
            run_worker(state["tasks"]["known"]) == "succeeded",
            "restored known result recovery failed",
        )
        after = admin("SELECT ops.task_details(%s)", (state["tasks"]["known"],))
        require(
            len([a for a in after["attempts"] if a["step"] == "generate"]) == 1,
            "generation resubmitted after restore",
        )
        review = state["detection_review"]
        degraded_id = UUID(state["tasks"]["degraded"])
        require(run_worker(degraded_id) == "not_claimed", "restored approval bypassed quarantine")
        original = detection_delivery_context(profile["ADMIN_DATABASE_URL"], degraded_id)[
            "decision"
        ]
        replayed = approve_detection_delivery(
            profile["ADMIN_DATABASE_URL"],
            degraded_id,
            UUID(review["attempt"]),
            review["sha256"],
            UUID(review["operation"]),
            review["reason"],
            review["sha256"],
        )
        require(
            str(replayed) == str(state["detection_decision"])
            and run_worker(degraded_id) == "not_claimed",
            "old review replay resumed restored task",
        )
        approve_detection_delivery(
            profile["ADMIN_DATABASE_URL"],
            degraded_id,
            UUID(review["attempt"]),
            review["sha256"],
            uuid4(),
            "new review of restored final; local delivery only",
            review["sha256"],
        )
        require(run_worker(degraded_id) == "succeeded", "restored local delivery failed")
        reviewed = detection_delivery_context(profile["ADMIN_DATABASE_URL"], degraded_id)
        require(
            reviewed["decision"] == original
            and reviewed["detect_attempt"]["status"] == "uncertain"
            and reviewed["detect_attempt"]["provider_id"] is None
            and not reviewed["supplier_cost_verified"],
            "restored delivery changed immutable review or supplier outcome",
        )
        degraded_report = client.get(f"/api/v1/tasks/{degraded_id}/compliance").json()
        require(
            degraded_report["detection_degraded"]
            and degraded_report["auto_overall"] == "manual_review",
            "restored report lost degradation notice",
        )
        downloaded = client.get(f"/api/v1/tasks/{degraded_id}/download", follow_redirects=False)
        final_bytes = httpx.get(downloaded.headers["location"]).content
        require(
            hashlib.sha256(final_bytes).hexdigest() == review["sha256"],
            "restored degraded final changed",
        )
        transactions = client.get("/api/v1/credits/transactions").json()["items"]
        require(
            len(
                [
                    row
                    for row in transactions
                    if row["task_id"] == str(degraded_id) and row["type"] == "charge"
                ]
            )
            == 1,
            "restored degraded delivery did not charge exactly once",
        )
        final_balance = client.get("/api/v1/credits/balance").json()
        require(
            (final_balance["available"], final_balance["reserved"], final_balance["spent_total"])
            == (104, 48, 48),
            "post-recovery wallet mismatch",
        )
    result["verification"] = {
        "api_ready": True,
        "old_access_rejected": True,
        "post_snapshot_marker_absent": True,
        "completed_report_review_and_download_hash_preserved": True,
        "pixel_protection_preserved": True,
        "supplier_price_archive_preserved": True,
        "provider_budget_revoked_before_new_intent": True,
        "unit_limits_preserved_without_cross_unit_total": True,
        "five_fixture_tasks_quarantined": True,
        "cost_estimate_history_and_review_block_preserved": True,
        "detection_delivery_requires_new_review_after_restore": True,
        "detection_supplier_unknown_and_final_hash_preserved": True,
        "detection_delivery_one_charge": True,
        "unknown_and_queued_cannot_submit": True,
        "known_id_recovered_without_new_generate": True,
        "balance_at_snapshot": state["balance"],
        "balance_after_two_safe_recoveries": final_balance,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    result["configuration_restore"] = {
        key: value for key, value in result["configuration_restore"].items() if key != "output"
    }
    (ROOT / "docs/evidence/backup-restore-drill.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print("Restore API, artifacts, quarantine and known-id recovery verified.")
else:
    state = json.loads(args.state.read_text())
    with TestClient(create_app(settings)) as client:
        headers = login(client, state)
        require(
            client.post(
                "/api/v1/tasks/" + state["tasks"]["queued"] + "/cancel", headers=headers
            ).status_code
            == 200,
            "source fixture cancel failed",
        )
        outcome = run_worker(state["tasks"]["known"])
        require(
            outcome in ("succeeded", "not_claimed")
            and client.get("/api/v1/tasks/" + state["tasks"]["known"]).json()["status"]
            == "succeeded",
            "source fixture safe finish failed",
        )
        degraded = run_worker(state["tasks"]["degraded"])
        require(
            degraded in ("succeeded", "not_claimed")
            and client.get("/api/v1/tasks/" + state["tasks"]["degraded"]).json()["status"]
            == "succeeded",
            "source detection delivery finish failed",
        )
        cost_state = client.get("/api/v1/tasks/" + state["tasks"]["cost_review"]).json()
        if cost_state["status"] != "failed":
            operation = state.setdefault("cost_cleanup_operation_id", str(uuid4()))
            args.state.write_text(json.dumps(state))
            admin(
                "SELECT ops.reconcile_task(%s,%s,'fail',NULL,%s,%s)",
                (
                    state["tasks"]["cost_review"],
                    UUID(operation),
                    "offline cost-review fixture cannot deliver; release internal credits only",
                    "b" * 64,
                ),
            )
        unknown = client.get("/api/v1/tasks/" + state["tasks"]["unknown"]).json()
        if unknown["status"] != "failed":
            operation = state.setdefault("cleanup_operation_id", str(uuid4()))
            args.state.write_text(json.dumps(state))
            admin(
                "SELECT ops.reconcile_task(%s,%s,%s,NULL,%s,%s)",
                (
                    state["tasks"]["unknown"],
                    UUID(operation),
                    "fail",
                    "offline restore fixture closed; internal credits released",
                    "a" * 64,
                ),
            )
        require(
            client.get("/api/v1/credits/balance").json()["reserved"] == 0,
            "source cleanup left reserved credits",
        )
    print("Source fixture pending balances closed through normal API/operations.")
