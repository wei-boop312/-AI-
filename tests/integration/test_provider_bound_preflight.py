"""Read-only Ops snapshot review against actual PG; model transports remain mock."""

import json
from uuid import uuid4

from bailian_pricing_fixture import BailianPricingFixture

from visual_platform.providers.authorization import BailianSmokeAuthorization
from visual_platform.providers.bailian_connection import BailianConnection
from visual_platform.services.provider_preflight import load_bound_review, review_bound_scope
from visual_platform.services.runtime_quote import revoke_runtime_configuration


class BoundProviderPreflightTests(BailianPricingFixture):
    def review_scope(self, quote, scope):
        bundle = load_bound_review(
            self.operator_dsn, self.user, quote, self.qwen_runtime.digest(), scope.authorization_id
        )
        connection = BailianConnection(
            endpoint_origin=self.qwen_runtime.generate.endpoint_origin,
            credential_fingerprint=self.qwen_runtime.generate.credential_fingerprint,
        )
        return review_bound_scope(
            scope, self.qwen_runtime, connection, bundle, allow_offline_fixture=True
        )

    def test_actual_read_only_snapshot_binds_budget_prices_and_prediction_without_calls_or_holds(
        self,
    ):
        quote, _, reviewed = self.qwen_review()
        self.bind_qwen(quote, reviewed["input_snapshot"])
        scope = BailianSmokeAuthorization.model_validate_json(json.dumps(self.qwen_scope_data))
        before = self.snapshot()
        result = self.review_scope(quote, scope)
        self.assertTrue(result["scope_checks_passed"], result["failures"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls, [])
        self.assertFalse(result["execution_enabled"])
        revoke_runtime_configuration(
            self.operator_dsn,
            self.qwen_runtime.digest(),
            uuid4(),
            "synthetic revoke before spending",
        )
        self.assertIn("registered_runtime_active", self.review_scope(quote, scope)["failures"])

    def test_preflight_rejects_budget_already_used_by_a_completed_task(self):
        task = self.qwen_task()
        scope = BailianSmokeAuthorization.model_validate_json(json.dumps(self.qwen_scope_data))
        quote = self.snapshot()["quote_id"]
        self.assertEqual(self.run_qwen(task), "succeeded")
        result = self.review_scope(quote, scope)
        self.assertFalse(result["scope_checks_passed"])
        self.assertIn("unused_open_budget", result["failures"])
        self.assertEqual((self.post_count("bailian"), self.post_count("gemini")), (1, 1))
