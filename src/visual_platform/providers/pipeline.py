"""Protocol composition, enabled only with explicit offline HTTP mock transports."""

import asyncio
import hashlib
import struct
from uuid import UUID

from visual_platform.providers.bfl import BflRequest
from visual_platform.providers.contract import ProviderPending, ProviderUncertain, Receipt


class ProtocolProvider:
    execution_profile = "offline_protocol_mock"
    report_profile = "offline_protocol_mock"

    def __init__(self, bfl, gemini):
        if not bfl.offline_transport or not gemini.offline_transport:
            raise ValueError(
                "protocol pipeline requires explicit offline MockTransport on both suppliers"
            )
        self.bfl = bfl
        self.gemini = gemini

    def prepare_generate(self, generation, source):
        return BflRequest.from_canonical(generation, source).model_dump()

    async def submit_generate(self, intent, payload):
        return await asyncio.to_thread(self.bfl.submit, intent, BflRequest.model_validate(payload))

    async def retrieve_image(self, attempt):
        receipt = Receipt(
            attempt["provider_id"], attempt["response_digest"], attempt["polling_url_private"]
        )
        poll = await asyncio.to_thread(self.bfl.poll, receipt)
        if poll.status != "Ready":
            raise ProviderPending("existing BFL result pending")
        return await asyncio.to_thread(self.bfl.fetch_result, poll)

    async def submit_detect(self, intent, final):
        if len(final) < 24 or not final.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("final PNG required")
        width, height = struct.unpack(">II", final[16:24])
        return await self.gemini.submit(
            intent,
            final,
            expected_sha256=hashlib.sha256(final).hexdigest(),
            width=width,
            height=height,
        )

    def fetch_facts(self, identity):
        return self.gemini.fetch_facts(identity)

    def observation(self, step, attempt):
        if step == "generate":
            try:
                record = self.bfl.receipt_record(UUID(attempt["id"]))
            except ProviderUncertain:
                return {
                    "transport": "offline_mock",
                    "response_digest": attempt["response_digest"],
                    "provider_cost": None,
                    "source": "known_db_receipt_private_cost_metadata_unavailable",
                }
            return {
                "transport": "offline_mock",
                "response_digest": record["response_digest"],
                "provider_cost": record["cost"],
            }
        record = self.gemini.fetch_facts(attempt["provider_id"])
        return {
            "transport": "offline_mock",
            "response_digest": record["response_digest"],
            "usage": record["usage"],
            "cost": record["cost"],
            "final_sha256": record["final_sha256"],
            "sdk_version": record["sdk_version"],
        }
