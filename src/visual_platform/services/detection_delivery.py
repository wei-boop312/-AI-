"""Approve local manual-review delivery without manufacturing a provider receipt."""

from uuid import UUID

import psycopg

from visual_platform.db.result import required_row
from visual_platform.services.rule_operations import assert_operator


def detection_delivery_context(dsn: str, task: UUID):
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        return required_row(
            connection.execute("SELECT ops.detection_delivery_context(%s)", (task,))
        )[0]


def approve_detection_delivery(
    dsn: str,
    task: UUID,
    attempt: UUID,
    final_sha256: str,
    operation: UUID,
    reason: str,
    evidence: str,
) -> str:
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        return str(
            required_row(
                connection.execute(
                    "SELECT ops.approve_detection_manual_delivery(%s,%s,%s,%s,%s,%s)",
                    (task, attempt, final_sha256, operation, reason, evidence),
                )
            )[0]
        )
