"""Qwen composition freezes a new identity, never silently reuses BFL execution scope."""

import base64
import copy
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import httpx
from test_runtime import runtime_document

from visual_platform.providers.contract import ProviderUncertain
from visual_platform.providers.runtime import (
    ProviderRuntime,
    credential_fingerprint,
    offline_runtime,
)


def qwen_runtime_document():
    document = runtime_document()
    document["schema_version"] = 2
    document["generate"].update(
        provider="aliyun_bailian",
        model="qwen-image-3.0",
        endpoint_origin="https://ws-synthetic.cn-beijing.maas.aliyuncs.com",
        credential_fingerprint=credential_fingerprint("synthetic-qwen"),
    )
    return document


class QwenRuntimeContracts(unittest.IsolatedAsyncioTestCase):
    async def test_qwen_factory_scope_and_reconstructed_unknown_cost_are_bound(self):
        calls = []

        def route(request):
            calls.append(request)
            return httpx.Response(
                200, json={"output": {"task_id": "synthetic-task", "task_status": "PENDING"}}
            )

        runtime = ProviderRuntime.model_validate(qwen_runtime_document(), strict=True)
        with tempfile.TemporaryDirectory() as folder:
            async with offline_runtime(
                runtime,
                Path(folder),
                generate_key="synthetic-qwen",
                detect_key="synthetic-hubway",
                generate_transport=httpx.MockTransport(route),
                detect_transport=httpx.MockTransport(route),
            ) as provider:
                binding = runtime.execution_binding()
                provider.verify_execution_scope(binding)
                self.assertTrue(
                    binding["provider_endpoints"]["generate"].endswith(
                        "/aigc/image-generation/generation"
                    )
                )
                self.assertEqual(binding["provider_models"]["generate"], "qwen-image-3.0")
                for field in (
                    "provider_models",
                    "provider_endpoints",
                    "provider_runtime_sha256",
                    "provider_accounts",
                ):
                    mutated = copy.deepcopy(binding)
                    mutated.pop(field)
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        provider.verify_execution_scope(mutated)
                from visual_platform.providers.qwen_image import QwenImageRequest

                intent = uuid4()
                payload = QwenImageRequest(
                    prompt="synthetic edit",
                    width=512,
                    height=512,
                    images=[base64.b64encode(b"\x89PNG\r\n\x1a\nsynthetic").decode()],
                ).model_dump()
                receipt = await provider.submit_generate(intent, payload)
                attempt = {
                    "id": str(intent),
                    "provider_id": receipt.provider_id,
                    "response_digest": receipt.response_digest,
                    "polling_url_private": receipt.polling_url,
                }
                observation = provider.observation("generate", attempt)
                self.assertIsNone(observation["provider_cost"])
                self.assertNotIn("bfl_credit", str(observation))
                with self.assertRaises(ProviderUncertain):
                    provider.observation("generate", {**attempt, "response_digest": "f" * 64})
                self.assertEqual(len(calls), 1)

    async def test_schema_model_region_and_credentials_cannot_be_implicitly_mixed(self):
        for change in (
            "legacy_schema",
            "legacy_provider",
            "wrong_model",
            "foreign_region",
            "secret",
        ):
            document = qwen_runtime_document()
            if change == "legacy_schema":
                document["schema_version"] = 1
            elif change == "legacy_provider":
                document["generate"]["provider"] = "bfl"
            elif change == "wrong_model":
                document["generate"]["model"] = "qwen-image-3.0-pro"
            elif change == "foreign_region":
                document["generate"]["endpoint_origin"] = (
                    "https://ws-synthetic.ap-southeast-1.maas.aliyuncs.com"
                )
            else:
                document["generate"]["api_key"] = "synthetic"
            with self.subTest(change=change), self.assertRaises(ValueError):
                ProviderRuntime.model_validate(document, strict=True)
        runtime = ProviderRuntime.model_validate(qwen_runtime_document(), strict=True)
        mock = httpx.MockTransport(lambda _: httpx.Response(503))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "must-not-exist"
            for key, transport in (("synthetic-qwen", None), ("synthetic-bfl", mock)):
                with self.assertRaises(ValueError):
                    async with offline_runtime(
                        runtime,
                        target,
                        generate_key=key,
                        detect_key="synthetic-hubway",
                        generate_transport=transport,
                        detect_transport=mock,
                    ):
                        self.fail("unreviewed execution must not activate")
                self.assertFalse(target.exists())
