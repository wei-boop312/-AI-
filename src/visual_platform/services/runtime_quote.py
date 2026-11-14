"""Prepare a new audited protocol rehearsal quote; never mutate the original quote."""

import copy
import hashlib
import json
from uuid import UUID, uuid5

import psycopg

from visual_platform.db.result import required_row
from visual_platform.providers.qwen_image import checked_dimensions
from visual_platform.providers.runtime import ProviderRuntime
from visual_platform.services.rule_operations import assert_operator

NAMESPACE = UUID("b2bf2e62-cfa1-4d41-a267-96bcb09ae73c")


def register_runtime_configuration(dsn, runtime, reviewed_sha256, operation, reason):
    runtime = ProviderRuntime.model_validate(runtime.model_dump(mode="json"), strict=True)
    if runtime.digest() != reviewed_sha256:
        raise ValueError("runtime_configuration_not_reviewed")
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        identity = required_row(
            connection.execute(
                "SELECT ops.register_provider_runtime(%s,%s,%s,%s)",
                (runtime.canonical().decode(), runtime.digest(), operation, reason),
            )
        )[0]
    return str(identity)


def registered_runtime_context(dsn, digest):
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        context = required_row(
            connection.execute("SELECT ops.provider_runtime_context(%s)", (digest,))
        )[0]
    if context is None:
        raise ValueError("runtime_configuration_not_registered")
    runtime = ProviderRuntime.model_validate(context["document"], strict=True)
    if runtime.digest() != digest or context["document_sha256"] != digest:
        raise ValueError("stored_runtime_configuration_mismatch")
    return context


def revoke_runtime_configuration(dsn, digest, operation, reason):
    with psycopg.connect(dsn) as connection:
        assert_operator(connection)
        identity = required_row(
            connection.execute(
                "SELECT ops.revoke_provider_runtime(%s,%s,%s)", (digest, operation, reason)
            )
        )[0]
    return str(identity)


def runtime_snapshot(source, runtime):
    document = copy.deepcopy(source["input_snapshot"])
    if runtime.schema_version == 2:
        output = document["generation"]["output"]
        checked_dimensions(output["width"], output["height"])
    document["_execution"].update(runtime.execution_binding())
    document["_execution"].update(
        provider_profile="offline_protocol_mock",
        provider_model=runtime.generate.model + "-protocol-mock",
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
