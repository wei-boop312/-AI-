"""Private review and publication of supplier price evidence; no paid transport."""

import hashlib
import json
from uuid import UUID

import psycopg

from visual_platform.db.result import required_row
from visual_platform.domain.provider_pricing import (
    SupplierPriceVersion,
    canonical_price,
    estimate_supplier_cost,
)
from visual_platform.services.rule_operations import assert_operator


def publish_supplier_price(
    dsn: str,
    storage,
    price: SupplierPriceVersion,
    evidence: bytes,
    operation: UUID,
    reason: str,
    *,
    evidence_reviewed: bool = False,
):
    if not evidence_reviewed:
        raise ValueError("explicit_price_evidence_review_required")
    if (
        not 0 < len(evidence) <= 20 * 1024 * 1024
        or hashlib.sha256(evidence).hexdigest() != price.evidence_sha256
    ):
        raise ValueError("price_evidence_mismatch")
    if not reason.strip() or len(reason) > 4000:
        raise ValueError("invalid_price_review")
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
    canonical = canonical_price(price)
    digest = hashlib.sha256(canonical).hexdigest()
    key = "private/supplier-price/" + str(operation) + "/" + price.evidence_sha256
    version = storage.put_immutable(key, evidence, "application/octet-stream")
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        identity = required_row(
            connection.execute(
                "SELECT ops.publish_supplier_price(%s,%s,%s,%s,%s,%s,%s)",
                (canonical.decode(), digest, storage.bucket, key, version, operation, reason),
            )
        )[0]
    return str(identity)


def supplier_price_context(dsn: str, identity: UUID):
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        result = required_row(
            connection.execute("SELECT ops.supplier_price_context(%s)", (identity,))
        )[0]
    if result is None:
        raise ValueError("supplier_price_not_found")
    return result


def estimate_reviewed_price(dsn: str, identity: UUID, quantities: dict, **scope):
    reviewed = supplier_price_context(dsn, identity)
    price = SupplierPriceVersion.model_validate_json(json.dumps(reviewed["document"]))
    if hashlib.sha256(canonical_price(price)).hexdigest() != reviewed["document_sha256"]:
        raise ValueError("supplier_price_document_mismatch")
    return estimate_supplier_cost(price, quantities, **scope)


def supplier_task_costs(dsn: str, task: UUID):
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        return required_row(connection.execute("SELECT ops.supplier_task_costs(%s)", (task,)))[0]
