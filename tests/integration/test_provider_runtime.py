"""Real PG budget/Worker/S3 with frozen runtime configuration; provider HTTP is mock."""

import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
from provider_budget_fixture import ProviderBudgetFixture

from visual_platform.db.pool import open_pool
from visual_platform.providers.runtime import (
    ProviderRuntime,
    credential_fingerprint,
    offline_runtime,
)
from visual_platform.services.provider_budget import provider_quote_review
from visual_platform.services.runtime_quote import prepare_runtime_quote, runtime_snapshot
from visual_platform.storage.s3 import S3Storage
from visual_platform.worker.runner import Worker


class ProviderRuntimeTests(ProviderBudgetFixture):
    def source_quote(self):
        body = {
            "product_id": self.product,
            "source_asset_version_id": self.version,
            "generation": {
                "type": "scene",
                "prompt": "offline runtime preparation",
                "output": {"width": 256, "height": 256, "format": "png"},
                "protection_mode": "none",
                "regions": [],
            },
            "targets": [
                {
                    "platform": "amazon",
                    "marketplace": "US",
                    "category": "generic",
                    "image_type": "MAIN",
                }
            ],
        }
        response = self.client.post("/api/v1/quotes", json=body, headers=self.write_headers())
        self.assertEqual(response.status_code, 201, response.text)
        return UUID(response.json()["quote_id"]), body

    def prepare(
        self, source, runtime=None, operation=None, reason="synthetic runtime quote review"
    ):
        runtime = runtime or self.runtime()
        return prepare_runtime_quote(
            self.operator_dsn,
            self.user,
            source,
            runtime,
            runtime.digest(),
            operation or uuid4(),
            reason,
        )

    def runtime(self, version="synthetic-v1"):
        data = json.loads(Path("ops/provider-runtime.example.json").read_text())
        data["version"] = version
        for index, name in enumerate(("generate", "detect"), start=1):
            data[name]["merchant_fingerprint"] = str(index) * 64
            data[name]["billing_group"] = "synthetic-runtime-group"
            data[name]["credential_fingerprint"] = credential_fingerprint(
                "offline-bfl" if name == "generate" else "offline-hubway"
            )
        return ProviderRuntime.model_validate(data, strict=True)

    def run_configured(self, task, runtime):
        async def run():
            async with offline_runtime(
                runtime,
                Path(self.folder.name) / "configured",
                generate_key="offline-bfl",
                detect_key="offline-hubway",
                generate_transport=httpx.MockTransport(self.bfl_route),
                detect_transport=httpx.MockTransport(self.gemini_route),
            ) as provider:
                pool = await open_pool(self.worker_dsn, "app_worker")
                storage = S3Storage(self.settings)
                try:
                    return await Worker(pool, storage, provider).run(task)
                finally:
                    storage.close()
                    await pool.close()

        return asyncio.run(run())

    def test_frozen_runtime_drives_actual_pipeline_and_single_budgeted_charge(self):
        runtime = self.runtime()
        task = self.submit(self.bind, execution_updates=runtime.execution_binding())
        self.assertEqual(self.run_configured(task, runtime), "succeeded")
        self.assertEqual((self.post_count("bfl"), self.post_count("gemini")), (1, 1))
        self.assertTrue(any("https://hubway.cc/v1beta/models/" in url for _, _, url in self.calls))
        result = self.client.get("/api/v1/tasks/" + task).json()
        self.assertEqual(result["status"], "succeeded")
        balance = self.client.get("/api/v1/credits/balance").json()
        self.assertEqual((balance["reserved"], balance["spent_total"]), (0, 16))

    def test_changed_configuration_rejects_before_any_intent_or_post(self):
        task = self.submit(self.bind, execution_updates=self.runtime().execution_binding())
        self.assertEqual(self.run_configured(task, self.runtime("synthetic-v2")), "failed")
        self.assertEqual((self.post_count("bfl"), self.post_count("gemini")), (0, 0))
        balance = self.client.get("/api/v1/credits/balance").json()
        self.assertEqual(
            (balance["available"], balance["reserved"], balance["spent_total"]), (100, 0, 0)
        )

    def test_changed_runtime_after_known_receipt_preserves_freeze_without_resubmit(self):
        runtime = self.runtime()
        task = self.submit(self.bind, execution_updates=runtime.execution_binding())
        self.pending = True
        self.assertEqual(self.run_configured(task, runtime), "retryable")
        self.assertEqual(self.run_configured(task, self.runtime("synthetic-v2")), "stopped")
        self.assertEqual((self.post_count("bfl"), self.post_count("gemini")), (1, 0))
        result = self.client.get("/api/v1/tasks/" + task).json()
        self.assertEqual(result["status"], "uncertain")
        balance = self.client.get("/api/v1/credits/balance").json()
        self.assertEqual(
            (balance["available"], balance["reserved"], balance["spent_total"]), (84, 16, 0)
        )

    def test_audited_preparation_uses_real_api_quote_budget_worker_and_s3_without_owner_writes(
        self,
    ):
        source, body = self.source_quote()
        before = self.client.get("/api/v1/credits/balance").json()
        runtime = self.runtime()
        prepared = self.prepare(source, runtime)
        self.assertEqual(self.client.get("/api/v1/credits/balance").json(), before)
        quote = UUID(prepared["quote_id"])
        review = provider_quote_review(self.operator_dsn, self.user, quote)
        self.assertEqual(review["input_snapshot"]["generation"], body["generation"])
        self.assertEqual(review["input_sha256"], prepared["input_sha256"])
        self.assertEqual(
            review["input_snapshot"]["_execution"]["provider_runtime_sha256"], runtime.digest()
        )
        self.bind(quote, review["input_snapshot"])
        response = self.client.post(
            "/api/v1/tasks",
            json={**body, "quote_id": str(quote)},
            headers={**self.write_headers(), "idempotency-key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.run_configured(response.json()["id"], runtime), "succeeded")
        self.assertEqual((self.post_count("bfl"), self.post_count("gemini")), (1, 1))

    def test_concurrent_operation_replays_one_quote_even_after_source_consumed(self):
        source, body = self.source_quote()
        operation = uuid4()
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(lambda _: self.prepare(source, operation=operation), range(8))
            )
        self.assertEqual(len({row["quote_id"] for row in results}), 1)
        response = self.client.post(
            "/api/v1/tasks",
            json={**body, "quote_id": str(source)},
            headers={**self.write_headers(), "idempotency-key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.prepare(source, operation=operation), results[0])
        with self.assertRaises(psycopg.Error):
            self.prepare(source, operation=operation, reason="changed review")
        with self.assertRaises(psycopg.Error):
            self.prepare(source)
        with psycopg.connect(self.owner) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM ops.audit_events WHERE request_id=%s", (operation,)
                ).fetchone()[0],
                1,
            )

    def test_sql_cannot_change_business_models_null_endpoints_or_inject_credentials(self):
        source, _ = self.source_quote()
        with psycopg.connect(self.operator_dsn) as c:
            context = c.execute(
                "SELECT ops.runtime_quote_source(%s,%s)", (self.user, source)
            ).fetchone()[0]
        for change in ("prompt", "model", "null_endpoint", "secret"):
            document = runtime_snapshot(context, self.runtime())
            if change == "prompt":
                document["generation"]["prompt"] = "unreviewed business edit"
            elif change == "model":
                document["_execution"]["provider_models"]["generate"] = "another-model"
            elif change == "null_endpoint":
                document["_execution"]["provider_endpoints"]["detect"] = None
            else:
                document["_execution"]["provider_accounts"]["detect"]["api_key"] = (
                    "synthetic-forbidden"
                )
            raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
            with (
                self.subTest(change=change),
                psycopg.connect(self.operator_dsn) as c,
                self.assertRaises(psycopg.Error),
            ):
                c.execute(
                    "SELECT ops.prepare_runtime_quote(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        self.user,
                        source,
                        uuid4(),
                        raw,
                        hashlib.sha256(raw.encode()).hexdigest(),
                        uuid4(),
                        "synthetic negative",
                    ),
                )
        with self.assertRaises(psycopg.Error):
            prepare_runtime_quote(
                self.operator_dsn,
                uuid4(),
                source,
                self.runtime(),
                self.runtime().digest(),
                uuid4(),
                "wrong user",
            )
        for dsn in (self.worker_dsn, self.settings.api_database_url):
            with psycopg.connect(dsn) as c, self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute("SELECT ops.runtime_quote_source(%s,%s)", (self.user, source))
