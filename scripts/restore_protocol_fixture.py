"""Loopback-only restore fixture with hardwired MockTransports and synthetic credentials."""

import asyncio
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from PIL import Image

from visual_platform.db.pool import open_pool
from visual_platform.providers.bfl import BflProvider
from visual_platform.providers.gemini import GeminiProvider
from visual_platform.providers.pipeline import ProtocolProvider
from visual_platform.storage.s3 import S3Storage
from visual_platform.worker.runner import Worker


def run_cost_review_fixture(profile, settings, task_id, accounts, *, detect_success=False):
    if profile.get("PROVIDER_PROFILE") != "offline" or any(
        urlsplit(profile[key]).hostname not in ("localhost", "127.0.0.1")
        for key in ("WORKER_DATABASE_URL", "S3_ENDPOINT")
    ):
        raise ValueError("restore protocol fixture requires explicit offline loopback profile")
    posts = {"generate": 0, "detect": 0}
    provider_id = "restore-" + str(UUID(str(task_id)))
    stream = BytesIO()
    Image.new("RGB", (256, 256), (160, 190, 210)).save(stream, "PNG")
    png = stream.getvalue()

    def generation(request):
        if request.method == "POST":
            posts["generate"] += 1
            return httpx.Response(
                200,
                json={
                    "id": provider_id,
                    "polling_url": "https://api.eu2.bfl.ai/v1/get_result?id=" + provider_id,
                    "cost": 0.06,
                },
            )
        if request.url.host == "delivery.eu2.bfl.ai":
            return httpx.Response(200, content=png, headers={"content-type": "image/png"})
        return httpx.Response(
            200,
            json={
                "status": "Ready",
                "result": {"sample": "https://delivery.eu2.bfl.ai/restore-synthetic"},
            },
        )

    def detection(request):
        if request.method == "POST":
            posts["detect"] += 1
        if detect_success:
            facts = {
                "schema_version": 1,
                "analysis_complete": True,
                "image_width": 256,
                "image_height": 256,
                "text_items": [],
                "logo_items": [],
                "watermark_items": [],
                "background": {"classification": "non_white", "confidence": 0.9},
                "product_extent": None,
                "uncertainties": [],
            }
            return httpx.Response(
                200,
                json={
                    "modelVersion": "gemini-3.8-flash",
                    "responseId": "restore-synthetic-detection",
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": [{"text": json.dumps(facts)}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "cachedContentTokenCount": 2,
                        "candidatesTokenCount": 20,
                        "thoughtsTokenCount": 3,
                        "toolUsePromptTokenCount": 0,
                        "totalTokenCount": 33,
                    },
                },
            )
        return httpx.Response(
            500,
            json={"error": "controlled detector must remain blocked by incomparable price unit"},
        )

    async def run():
        directory = Path(profile["FAKE_PROVIDER_DIR"]) / "protocol-restore" / str(task_id)
        bfl = BflProvider(
            "offline-restore-fixture", directory / "bfl", transport=httpx.MockTransport(generation)
        )
        gemini = GeminiProvider(
            "offline-restore-fixture",
            directory / "gemini",
            transport=httpx.MockTransport(detection),
        )
        pool = None
        storage = None
        try:
            pool = await open_pool(profile["WORKER_DATABASE_URL"], "app_worker")
            storage = S3Storage(settings)
            provider = ProtocolProvider(bfl, gemini, merchant_accounts=accounts)
            return await Worker(pool, storage, provider).run(task_id)
        finally:
            if pool is not None:
                await pool.close()
            if storage is not None:
                storage.close()
            bfl.close()
            await gemini.aclose()

    result = asyncio.run(run())
    return {"result": result, "posts": posts, "paid_calls": 0}
