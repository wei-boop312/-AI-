"""Actual PG/S3 review of synthetic visual prices, without enabling execution."""

import hashlib
import json
from uuid import UUID, uuid4

import psycopg
from supplier_pricing_fixture import SupplierPricingFixture

from visual_platform.services.provider_pricing import supplier_price_context


class QwenVisionPriceReviewTests(SupplierPricingFixture):
    def vision_price(self):
        return self.document(
            schema_version=3,
            provider="aliyun_bailian_vision",
            model="qwen3.8-flash",
            endpoint_origin="https://ws-synthetic.cn-beijing.maas.aliyuncs.com",
            currency="CNY",
            rates=[
                {"measure": "input_tokens", "amount": "0.8", "per": 1000000},
                {"measure": "cached_input_tokens", "amount": "0.1", "per": 1000000},
                {"measure": "output_tokens", "amount": "2.7", "per": 1000000},
            ],
        )

    def test_private_price_review_replays_without_balance_or_model_requests(self):
        price = self.vision_price()
        before = self.client.get("/api/v1/credits/balance").json()
        operation = uuid4()
        _, identity = self.publish(price, operation)
        self.assertEqual(self.publish(price, operation)[1], identity)
        context = supplier_price_context(self.operator_dsn, UUID(identity))
        self.assertEqual(context["document"], price.model_dump(mode="json"))
        self.assertTrue(context["evidence_archived"])
        self.assertFalse(context["actual_spending_verified"])
        self.assertEqual(self.client.get("/api/v1/credits/balance").json(), before)
        self.assertEqual(self.calls, [])

    def test_database_independently_rejects_mismatched_identity_and_meter_sets(self):
        valid = self.vision_price().model_dump(mode="json")
        for patch in (
            {"schema_version": 2},
            {"model": "gemini-3.8-flash"},
            {"currency": "USD"},
            {"endpoint_origin": "https://hubway.cc"},
            {"rates": valid["rates"][:-1]},
            {
                "rates": valid["rates"]
                + [{"measure": "thinking_tokens", "amount": "2.7", "per": 1000000}]
            },
        ):
            canonical = json.dumps({**valid, **patch}, sort_keys=True, separators=(",", ":"))
            with self.subTest(patch=patch), psycopg.connect(self.operator_dsn) as connection:
                with self.assertRaisesRegex(
                    psycopg.errors.RaiseException, "invalid_supplier_price"
                ):
                    connection.execute(
                        "SELECT ops.publish_supplier_price(%s,%s,%s,%s,%s,%s,%s)",
                        (
                            canonical,
                            hashlib.sha256(canonical.encode()).hexdigest(),
                            "synthetic-evidence",
                            "private/synthetic",
                            None,
                            uuid4(),
                            "synthetic negative",
                        ),
                    )
        self.assertEqual(self.calls, [])
