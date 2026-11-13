"""Native PG/S3 policy publishing and rule-only report version tests."""

import hashlib
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import UUID, uuid4

import httpx
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from test_offline_pipeline import PipelineFixture

from visual_platform.core.identity import hash_password
from visual_platform.services.rule_operations import publish_rule, recheck_report
from visual_platform.storage.s3 import S3Storage


class RuleOperationsTests(PipelineFixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_role = "rules_" + uuid4().hex
        password = secrets.token_urlsafe(32)
        with psycopg.connect(cls.owner) as c:
            c.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(cls.admin_role), sql.Literal(password))
            )
            c.execute(sql.SQL("GRANT ops_admin TO {}").format(sql.Identifier(cls.admin_role)))
        u = urlsplit(cls.owner)
        cls.admin_dsn = urlunsplit(
            (
                u.scheme,
                quote(cls.admin_role)
                + ":"
                + quote(password)
                + "@"
                + u.hostname
                + ":"
                + str(u.port or 5432),
                u.path,
                u.query,
                u.fragment,
            )
        )

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.owner) as c:
            c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(cls.admin_role)))
        super().tearDownClass()

    def doc(self, **values):
        return {
            "platform": "amazon",
            "marketplace": "US",
            "category": "generic",
            "image_type": "MAIN",
            "version": "test-" + uuid4().hex,
            "evidence_status": "unverified",
            "config": {},
            **values,
        }

    def publish(self, document=None, operation=None, storage=None, evidence=None):
        own = storage is None
        storage = storage or S3Storage(self.settings)
        try:
            return publish_rule(
                self.admin_dsn,
                storage,
                document or self.doc(),
                evidence,
                operation or uuid4(),
                "synthetic integration rule; no claim of current policy",
                evidence_reviewed=True,
            )
        finally:
            if own:
                storage.close()

    def recheck(self, task, source, rules, operation=None, storage=None):
        own = storage is None
        storage = storage or S3Storage(self.settings)
        try:
            return recheck_report(
                self.admin_dsn,
                storage,
                UUID(task),
                UUID(source),
                [UUID(x) for x in rules],
                operation or uuid4(),
                "re-evaluate existing facts; no provider call",
            )
        finally:
            if own:
                storage.close()

    def test_publish_concurrent_idempotent_immutable_and_restricted(self):
        doc = self.doc(category="test-" + uuid4().hex)
        operation = uuid4()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.publish(doc, operation), range(4)))
        self.assertEqual(len({r["rule_id"] for r in results}), 1)
        identity = results[0]["rule_id"]
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.publish(doc)
        with self.assertRaises(psycopg.errors.RaiseException):
            self.publish({**doc, "config": {"max_bytes": 1}}, operation)
        with psycopg.connect(self.owner) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM ops.audit_events WHERE request_id=%s", (operation,)
                ).fetchone()[0],
                1,
            )
            with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                c.execute("UPDATE app.platform_rules SET config='{}' WHERE id=%s", (identity,))
        with psycopg.connect(self.owner) as c:
            c.execute("SET SESSION AUTHORIZATION app_api")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute(
                    "SELECT ops.publish_rule(%s,%s,NULL,NULL,NULL,%s)",
                    (uuid4(), Jsonb(doc), "forbidden"),
                )

    def test_verified_requires_real_archive_hash_and_private_storage(self):
        evidence = b"Synthetic archived document for integration testing only; not platform policy."
        doc = self.doc(
            category="synthetic-" + uuid4().hex,
            evidence_status="verified",
            source_urls=["https://sellercentral.amazon.com/help/synthetic-test"],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            evidence_sha256=hashlib.sha256(evidence).hexdigest(),
        )
        with self.assertRaises(ValueError):
            self.publish(doc, evidence=b"wrong")
        with self.assertRaises(ValueError):
            self.publish(doc)
        operation = uuid4()
        identity = self.publish(doc, operation, evidence=evidence)["rule_id"]
        self.assertEqual(self.publish(doc, operation, evidence=evidence)["rule_id"], identity)
        with psycopg.connect(self.owner) as c:
            row = c.execute(
                "SELECT evidence_object_key,evidence_sha256 FROM app.platform_rules WHERE id=%s",
                (identity,),
            ).fetchone()
        self.assertEqual(row[1], hashlib.sha256(evidence).hexdigest())
        unsigned = self.settings.s3_endpoint + "/" + self.settings.s3_bucket + "/" + row[0]
        self.assertEqual(httpx.get(unsigned, timeout=10).status_code, 403)

    def test_recheck_versions_keep_original_review_charge_and_provider_attempts(self):
        task = self.submit()
        self.assertEqual(self.run_worker(task), "succeeded")
        original = self.client.get("/api/v1/tasks/" + task + "/compliance").json()
        balance = self.client.get("/api/v1/credits/balance").json()
        intents = len(list(Path(self.folder.name).glob("*.intent")))
        identity = self.publish()["rule_id"]
        operation = uuid4()
        args = (task, original["id"], [identity], operation)
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: self.recheck(*args), range(3)))
        check = results[0]["check_id"]
        self.assertEqual(len({x["check_id"] for x in results}), 1)
        self.assertEqual(self.client.get("/api/v1/tasks/" + task + "/compliance").json(), original)
        versions = self.client.get("/api/v1/tasks/" + task + "/compliance/versions").json()["items"]
        self.assertEqual(len(versions), 2)
        self.assertEqual(sum(x["is_original"] for x in versions), 1)
        revised = self.client.get(
            "/api/v1/tasks/" + task + "/compliance", params={"check_id": check}
        ).json()
        self.assertEqual(revised["final_sha256"], original["final_sha256"])
        self.assertEqual(revised["facts"], original["facts"])
        self.assertEqual(revised["rule_snapshots"][0]["rule_id"], identity)
        url = self.client.get(
            "/api/v1/tasks/" + task + "/report/download",
            params={"check_id": check},
            follow_redirects=False,
        ).headers["location"]
        data = httpx.get(url, timeout=10).content
        report = json.loads(data)
        self.assertEqual(hashlib.sha256(data).hexdigest(), revised["report_sha256"])
        self.assertEqual(report["recomputed_from_check_id"], original["id"])
        self.assertEqual(self.client.get("/api/v1/credits/balance").json(), balance)
        self.assertEqual(len(list(Path(self.folder.name).glob("*.intent"))), intents)
        with psycopg.connect(self.admin_dsn) as c:
            c.execute(
                "SELECT app.review_check(%s,%s,%s,%s,%s,%s,%s)",
                (
                    task,
                    check,
                    uuid4(),
                    self.user,
                    "approved",
                    "synthetic reviewer decision",
                    Jsonb([]),
                ),
            )
        self.assertEqual(
            self.client.get(
                "/api/v1/tasks/" + task + "/compliance", params={"check_id": check}
            ).json()["effective_source"],
            "human_review",
        )
        self.assertEqual(
            self.client.get("/api/v1/tasks/" + task + "/compliance").json()["effective_source"],
            "automatic",
        )
        self.assertEqual(
            len(
                self.client.get(
                    "/api/v1/tasks/" + task + "/compliance/reviews", params={"check_id": check}
                ).json()["items"]
            ),
            1,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/tasks/" + task + "/compliance", params={"check_id": str(uuid4())}
            ).status_code,
            404,
        )
        with psycopg.connect(self.owner) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM ops.audit_events WHERE request_id=%s", (operation,)
                ).fetchone()[0],
                1,
            )

    def test_known_cross_user_versions_and_downloads_are_hidden(self):
        task = self.submit()
        self.run_worker(task)
        source = self.client.get("/api/v1/tasks/" + task + "/compliance").json()["id"]
        check = self.recheck(task, source, [self.publish()["rule_id"]])["check_id"]
        other = uuid4()
        email = str(other) + "@test.invalid"
        with psycopg.connect(self.owner) as c:
            c.execute("SET SESSION AUTHORIZATION ops_admin")
            c.execute(
                "SELECT app.create_private_user(%s,%s,'other',%s)",
                (other, email, hash_password(self.password)),
            )
        self.email = email
        self.login()
        for suffix in [
            "/compliance/versions",
            "/compliance?check_id=" + check,
            "/report/download?check_id=" + check,
            "/compliance/reviews?check_id=" + check,
        ]:
            self.assertEqual(
                self.client.get(
                    "/api/v1/tasks/" + task + suffix, follow_redirects=False
                ).status_code,
                404,
            )

    def test_database_guards_reject_incomplete_and_mismatched_pass_results(self):
        rule = {
            "platform": "amazon",
            "marketplace": "US",
            "image_type": "MAIN",
            "version": "synthetic",
            "evidence_status": "verified",
            "config": {"complete_rule_set": True, "require_identity_review": False},
        }
        result = {
            "platform": "amazon",
            "marketplace": "US",
            "image_type": "MAIN",
            "rule_version": "synthetic",
            "status": "compliant",
            "reasons": [],
        }
        facts = {"analysis_complete": True, "uncertainties": []}

        def guard(rules, results, sampling=False):
            with psycopg.connect(self.owner) as c:
                return c.execute(
                    "SELECT app.rule_result_can_pass(%s,%s,%s,%s)",
                    (Jsonb(facts), Jsonb(rules), Jsonb(results), sampling),
                ).fetchone()[0]

        self.assertTrue(guard([rule], [result]))
        self.assertFalse(guard([], []))
        self.assertFalse(guard([rule], [result], True))
        self.assertFalse(guard([{**rule, "config": {}}], [result]))
        self.assertFalse(guard([rule], [{**result, "rule_version": "wrong"}]))
        self.assertFalse(guard([rule], [{**result, "reasons": [{"code": "needs_review"}]}]))
        task = self.submit()
        self.run_worker(task)
        source = self.client.get("/api/v1/tasks/" + task + "/compliance").json()["id"]
        identity = self.publish()["rule_id"]
        with psycopg.connect(self.admin_dsn) as c:
            with self.assertRaises(psycopg.errors.RaiseException):
                c.execute(
                    "SELECT ops.record_recheck(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s)",
                    (
                        task,
                        source,
                        [UUID(identity)],
                        uuid4(),
                        uuid4(),
                        Jsonb([result]),
                        "compliant",
                        "a" * 64,
                        self.settings.s3_bucket,
                        "fake-report",
                        "attempted invalid pass",
                    ),
                )

    def test_scope_mismatch_and_corrupt_storage_never_append(self):
        task = self.submit()
        self.run_worker(task)
        source = self.client.get("/api/v1/tasks/" + task + "/compliance").json()["id"]
        wrong = self.publish(self.doc(marketplace="UK"))["rule_id"]
        with self.assertRaises(psycopg.errors.RaiseException):
            self.recheck(task, source, [wrong])
        identity = self.publish()["rule_id"]

        class CorruptStorage(S3Storage):
            def get(self, *args, **kwargs):
                return b"corrupt", "application/json", None

        storage = CorruptStorage(self.settings)
        try:
            with self.assertRaises(ValueError):
                self.recheck(task, source, [identity], storage=storage)
        finally:
            storage.close()
        self.assertEqual(
            len(self.client.get("/api/v1/tasks/" + task + "/compliance/versions").json()["items"]),
            1,
        )

    def test_cli_unverified_publish_and_no_sensitive_exception(self):
        path = Path(self.folder.name) / "rule.json"
        path.write_text(json.dumps(self.doc()), encoding="utf-8")
        env = {
            **os.environ,
            "ADMIN_DATABASE_URL": self.admin_dsn,
            "S3_ENDPOINT": self.settings.s3_endpoint,
            "S3_ACCESS_KEY": self.settings.s3_access_key,
            "S3_SECRET_KEY": self.settings.s3_secret_key,
            "S3_BUCKET": self.settings.s3_bucket,
        }
        command = [
            sys.executable,
            "scripts/rules.py",
            "publish",
            "--document",
            str(path),
            "--operation-id",
            str(uuid4()),
            "--reason",
            "CLI synthetic fixture",
        ]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["evidence_status"], "unverified")
        evidence = b"CLI synthetic archived evidence, not actual platform policy."
        evidence_path = Path(self.folder.name) / "evidence.bin"
        evidence_path.write_bytes(evidence)
        doc = self.doc(
            category="cli-synthetic-" + uuid4().hex,
            evidence_status="verified",
            source_urls=["https://sellercentral.amazon.com/help/synthetic-test"],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            evidence_sha256=hashlib.sha256(evidence).hexdigest(),
        )
        path.write_text(json.dumps(doc), encoding="utf-8")
        verified_command = command.copy()
        verified_command[verified_command.index("--operation-id") + 1] = str(uuid4())
        verified_command += ["--evidence-file", str(evidence_path)]
        missing_attestation = subprocess.run(
            verified_command, env=env, capture_output=True, text=True, timeout=15
        )
        self.assertNotEqual(missing_attestation.returncode, 0)
        verified = subprocess.run(
            verified_command + ["--attest-evidence-reviewed"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)["evidence_status"], "verified")
        path.write_text('{"password":"sensitive-do-not-echo"}', encoding="utf-8")
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sensitive-do-not-echo", result.stderr)
