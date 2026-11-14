"""Prepare a new audited protocol rehearsal quote; never mutate the original quote."""

import copy
import hashlib
import json
from uuid import UUID, uuid5

import psycopg

from visual_platform.db.result import required_row
from visual_platform.providers.runtime import ProviderRuntime
from visual_platform.services.rule_operations import assert_operator

NAMESPACE = UUID("b2bf2e62-cfa1-4d41-a267-96bcb09ae73c")


def runtime_snapshot(source, runtime):
    document = copy.deepcopy(source["input_snapshot"])
    document["_execution"].update(runtime.execution_binding())
    document["_execution"].update(
        provider_profile="offline_protocol_mock",
        provider_model="flux-3-image-protocol-mock",
        price_version="trial-protocol-mock-v1",
    )
    return document


def prepare_runtime_quote(dsn, user, source_quote, runtime, reviewed_sha256, operation, reason):
    runtime = ProviderRuntime.model_validate(runtime.model_dump(mode="json"), strict=True)
    if reviewed_sha256 != runtime.digest():
        raise ValueError("runtime_configuration_not_reviewed")
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        source = required_row(
            connection.execute("SELECT ops.runtime_quote_source(%s,%s)", (user, source_quote))
        )[0]
    snapshot = runtime_snapshot(source, runtime)
    canonical = json.dumps(
        snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    identity = uuid5(NAMESPACE, str(operation))
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        identity = required_row(
            connection.execute(
                "SELECT ops.prepare_runtime_quote(%s,%s,%s,%s,%s,%s,%s)",
                (user, source_quote, identity, canonical, digest, operation, reason),
            )
        )[0]
    return {
        "quote_id": str(identity),
        "input_sha256": digest,
        "runtime_sha256": runtime.digest(),
        "profile": "offline_protocol_mock",
        "paid_calls": 0,
        "execution_enabled": False,
    }
