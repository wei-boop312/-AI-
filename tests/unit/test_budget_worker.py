import unittest
from uuid import uuid4

import asyncpg

from visual_platform.worker.runner import Worker


class BudgetWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_known_budget_denial_stops_before_transport_and_requests_safe_refund(self):
        for reason in [
            "provider_budget_expired",
            "provider_budget_blocked",
            "provider_budget_scope_mismatch",
            "provider_budget_exhausted",
        ]:
            calls = []
            worker = Worker(None, None, object(), owner="fixture-worker")

            async def database(query, *args):
                calls.append((query, args))
                if "app.record_intent" in query:
                    raise asyncpg.RaiseError(reason)
                self.assertIn("app.fail_task", query)

            worker.db = database
            task = uuid4()
            with self.subTest(reason=reason):
                self.assertFalse(await worker.submit(task, 1, "generate", {"fixture": True}))
                self.assertEqual(len(calls), 2)
                self.assertEqual(
                    calls[1][1], (task, "fixture-worker", 1, "provider_budget_denied", False)
                )

    async def test_other_database_errors_do_not_request_refund_or_invoke_transport(self):
        calls = []
        worker = Worker(None, None, object())

        async def database(query, *args):
            calls.append(query)
            raise asyncpg.RaiseError("unrelated_database_error")

        worker.db = database
        with self.assertRaises(asyncpg.RaiseError):
            await worker.submit(uuid4(), 1, "generate", {})
        self.assertEqual(len(calls), 1)

    async def test_known_cost_review_cannot_refund_a_previously_paid_step(self):
        worker = Worker(None, None, object(), owner="fixture-worker")
        calls = []

        async def database(query, *args):
            calls.append((query, args))
            if "record_intent" in query:
                raise asyncpg.RaiseError("provider_budget_cost_review_required")

        worker.db = database
        task = uuid4()
        self.assertFalse(await worker.submit(task, 1, "detect", b"final"))
        self.assertEqual(
            calls[-1][1], (task, "fixture-worker", 1, "provider_cost_review_required", True)
        )
        self.assertEqual(len(calls), 2)

    async def test_price_expiry_refunds_only_when_no_prior_supplier_attempt_exists(self):
        for attempts in [[], [{"id": "known-receipt"}]]:
            worker = Worker(None, None, object(), owner="fixture-worker")
            calls = []

            async def database(query, *args):
                calls.append((query, args))
                if "record_intent" in query:
                    raise asyncpg.RaiseError("provider_price_expired")

            async def context(*args):
                return {"attempts": attempts}

            worker.db = database
            worker.context = context
            self.assertFalse(await worker.submit(uuid4(), 1, "generate", {}))
            self.assertEqual(calls[-1][1][-1], bool(attempts))
            self.assertEqual(len(calls), 2)
