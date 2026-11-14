"""Real PG budget/Worker/S3 with frozen runtime configuration; provider HTTP is mock."""

import asyncio
import json
from pathlib import Path

import httpx
from provider_budget_fixture import ProviderBudgetFixture

from visual_platform.db.pool import open_pool
from visual_platform.providers.runtime import (
    ProviderRuntime,
    credential_fingerprint,
    offline_runtime,
)
from visual_platform.storage.s3 import S3Storage
from visual_platform.worker.runner import Worker


class ProviderRuntimeTests(ProviderBudgetFixture):
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
