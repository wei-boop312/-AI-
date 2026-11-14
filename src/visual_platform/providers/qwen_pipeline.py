"""Explicit Qwen+Gemini offline composition; never substitutes for legacy BFL tasks."""

from uuid import UUID

from visual_platform.providers.contract import ProviderUncertain
from visual_platform.providers.pipeline import ProtocolProvider
from visual_platform.providers.qwen_image import MODEL, QwenImageProvider, QwenImageRequest


class QwenProtocolProvider(ProtocolProvider):
    generation_model = MODEL
    request_type = QwenImageRequest

    def __init__(self, qwen, gemini, *, merchant_accounts, runtime_sha256):
        if not isinstance(qwen, QwenImageProvider) or runtime_sha256 is None:
            raise ValueError("qwen_composition_requires_explicit_bound_runtime")
        super().__init__(
            qwen, gemini, merchant_accounts=merchant_accounts, runtime_sha256=runtime_sha256
        )

    def observation(self, step, attempt):
        if step != "generate":
            return super().observation(step, attempt)
        try:
            record = self.bfl.receipt_record(UUID(attempt["id"]))
        except ProviderUncertain:
            return {
                "transport": "offline_mock",
                "response_digest": attempt["response_digest"],
                "provider_cost": None,
                "source": "qwen_local_submit_evidence_unavailable",
            }
        if (
            record["provider_id"] != attempt["provider_id"]
            or record["response_digest"] != attempt["response_digest"]
            or record["polling_url"] != attempt["polling_url_private"]
        ):
            raise ProviderUncertain("Qwen receipt does not match frozen attempt")
        return {
            "transport": "offline_mock",
            "response_digest": record["response_digest"],
            "provider_cost": None,
            "source": record["source"],
        }
