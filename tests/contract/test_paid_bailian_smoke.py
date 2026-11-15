"""Explicit mocks for the separate paid experiment; tests never enable live network."""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from qwen_fixture import canonical_png

from visual_platform.providers.bailian_connection import BailianConnection
from visual_platform.providers.gemini import fallback
from visual_platform.providers.runtime import credential_fingerprint
from visual_platform.services.paid_bailian_smoke import (
    MODEL,
    VISION_MODEL,
    PaidSmokeScope,
    SingleRound,
    download_url,
    sha,
)


class PaidBailianSmokeContracts(unittest.TestCase):
    def test_documented_accelerated_result_host_is_allowed_but_lookalikes_are_not(self):
        url = "https://dashscope-a717.oss-accelerate.aliyuncs.com/image.png?synthetic=1"
        self.assertEqual(download_url(url), url)
        for invalid in (
            url.replace("aliyuncs.com", "aliyuncs.com.evil.invalid"),
            url.replace("https://", "http://"),
            url.replace("https://", "https://user:secret@"),
            url.replace("dashscope-a717", "arbitrary-bucket"),
            url + "#secret",
        ):
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                download_url(invalid)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source.png"
        self.png = canonical_png(512, 512)
        self.source.write_bytes(self.png)
        self.key = "synthetic-smoke-secret"
        self.connection = BailianConnection(
            endpoint_origin="https://ws-synthetic.cn-beijing.maas.aliyuncs.com",
            credential_fingerprint=credential_fingerprint(self.key),
        )
        now = datetime.now(timezone.utc)
        self.scope = PaidSmokeScope.model_validate_json(
            json.dumps(
                {
                    "authorization_id": str(uuid4()),
                    "authorization_ref": "user_20261115_bailian_test",
                    "authorized_at": (now - timedelta(seconds=1)).isoformat(),
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "connection_sha256": self.connection.digest(),
                    "source_path": str(self.source),
                    "source_sha256": sha(self.png),
                    "original_path": str(self.source),
                    "original_sha256": sha(self.png),
                    "generation": {
                        "type": "white_background",
                        "prompt": "Synthetic product; preserve the region.",
                        "output": {"width": 512, "height": 512, "format": "png"},
                        "protection_mode": "pixel_exact",
                        "regions": [
                            {
                                "source_x": 0,
                                "source_y": 0,
                                "width": 32,
                                "height": 32,
                                "target_x": 0,
                                "target_y": 0,
                            }
                        ],
                    },
                }
            )
        )
        self.calls = []
        self.timeout_step = None
        self.changed_price = False

    def route(self, request):
        self.calls.append(request)
        if request.method == "GET" and request.url.path == "/api/v1/models":
            model = request.url.params["model"]
            rates = (
                {
                    "qima_input_1k": "0.02",
                    "qima_input_2k": "0.02",
                    "qima_output_1k": "0.18",
                    "qima_output_2k": "0.18",
                }
                if model == MODEL
                else {"input_token": "0.8", "output_token": "2.7", "input_token_cache": "0.1"}
            )
            if self.changed_price:
                rates[next(iter(rates))] = "5"
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "output": {
                        "models": [
                            {
                                "model": model,
                                "prices": [
                                    {
                                        "range_name": "Default",
                                        "prices": [
                                            {
                                                "type": name,
                                                "price": value,
                                                "price_unit": "每张"
                                                if model == MODEL
                                                else "每百万tokens",
                                                "time_band": "standard",
                                            }
                                            for name, value in rates.items()
                                        ],
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
        if request.method == "POST":
            payload = json.loads(request.content)
            step = "generation" if payload["model"] == MODEL else "detection"
            if self.timeout_step == step:
                raise httpx.ReadTimeout(self.key, request=request)
            if step == "generation":
                self.assertEqual(payload["parameters"]["n"], 1)
                return httpx.Response(
                    200,
                    json={"output": {"task_id": "synthetic-paid-smoke", "task_status": "PENDING"}},
                )
            self.assertEqual(payload["max_tokens"], 8192)
            self.assertFalse(payload["enable_thinking"])
            self.assertNotIn("tools", payload)
            facts = fallback(512, 512, "synthetic_mock_not_real_analysis")
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-synthetic-smoke",
                    "model": VISION_MODEL,
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": facts.model_dump_json()},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 8,
                        "total_tokens": 20,
                        "prompt_tokens_details": {"cached_tokens": 3},
                        "completion_tokens_details": {"reasoning_tokens": 0},
                    },
                },
            )
        if request.url.path.startswith("/api/v1/tasks/"):
            return httpx.Response(
                200,
                json={
                    "output": {
                        "task_id": "synthetic-paid-smoke",
                        "task_status": "SUCCEEDED",
                        "choices": [
                            {
                                "finish_reason": "stop",
                                "message": {
                                    "role": "assistant",
                                    "content": [
                                        {
                                            "image": "https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/synthetic.png?Expires=1"
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                    "usage": {
                        "output_width": 512,
                        "output_height": 512,
                        "input_image_count": 1,
                        "output_image_count": 1,
                        "input_image_type": "qima_input_1k",
                        "output_image_type": "qima_output_1k",
                    },
                },
            )
        self.assertEqual(request.url.host, "dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com")
        self.assertNotIn("authorization", request.headers)
        return httpx.Response(200, content=self.png, headers={"content-type": "image/png"})

    def runner(self, **changes):
        return SingleRound(
            self.scope,
            self.connection,
            self.key,
            self.folder,
            transport=httpx.MockTransport(self.route),
            sleeper=lambda _: None,
            **changes,
        )

    def posts(self):
        return [request for request in self.calls if request.method == "POST"]

    def test_one_round_preserves_pixels_bounds_prices_and_never_claims_mock_as_real(self):
        report = self.runner().run()
        self.assertEqual(report["result"], "SINGLE_ROUND_COMPLETED", report)
        self.assertEqual(len(self.posts()), 2)
        self.assertEqual(report["paid_posts_attempted"], 0)
        self.assertEqual(report["mock_posts_attempted"], 2)
        self.assertFalse(report["real_model_output_exists"])
        self.assertFalse(report["actual_spending_verified"])
        self.assertTrue(report["pixel_exact_passed"])
        self.assertEqual(report["total_reference_estimate_cny"], "0.20002910")
        replay = self.runner(resume=True).run()
        self.assertEqual(replay["result"], "SINGLE_ROUND_COMPLETED", replay)
        self.assertEqual(len(self.posts()), 2)
        self.assertEqual(sha(self.source.read_bytes()), self.scope.source_sha256)
        self.assertNotIn(self.key, json.dumps(report))

    def test_generation_timeout_is_unknown_and_no_fresh_or_resume_run_resubmits(self):
        self.timeout_step = "generation"
        for changes in ({}, {}, {"resume": True}):
            report = self.runner(**changes).run()
            self.assertEqual(report["result"], "STOPPED_REQUIRES_REVIEW")
            self.assertNotIn(self.key, json.dumps(report))
        self.assertEqual(len(self.posts()), 1)

    def test_detection_timeout_retains_generation_and_blocks_second_detection_post(self):
        self.timeout_step = "detection"
        self.assertEqual(self.runner().run()["result"], "STOPPED_REQUIRES_REVIEW")
        self.assertEqual(self.runner(resume=True).run()["result"], "STOPPED_REQUIRES_REVIEW")
        self.assertEqual(len(self.posts()), 2)

    def test_price_change_or_source_change_stops_before_paid_intent(self):
        self.changed_price = True
        self.assertEqual(self.runner().run()["result"], "STOPPED_REQUIRES_REVIEW")
        self.assertFalse((self.folder / "generation.intent").exists())
        self.changed_price = False
        self.source.write_bytes(b"changed")
        self.assertEqual(self.runner().run()["result"], "STOPPED_REQUIRES_REVIEW")
        self.assertEqual(self.posts(), [])

    def test_mutated_cached_wire_is_rejected_without_resubmission(self):
        self.assertEqual(self.runner().run()["result"], "SINGLE_ROUND_COMPLETED")
        (self.folder / "generation.body").write_bytes(b"{}")
        report = self.runner(resume=True).run()
        self.assertEqual(report["result"], "STOPPED_REQUIRES_REVIEW")
        self.assertEqual(len(self.posts()), 2)

    def test_default_transport_and_mixed_live_mock_and_boolean_limits_reject(self):
        with self.assertRaises(ValueError):
            SingleRound(self.scope, self.connection, self.key, self.folder)
        with self.assertRaises(ValueError):
            SingleRound(
                self.scope,
                self.connection,
                self.key,
                self.folder,
                live=True,
                transport=httpx.MockTransport(self.route),
            )
        with self.assertRaises(ValueError):
            PaidSmokeScope.model_validate({**self.scope.model_dump(), "max_generate_calls": True})
        script = Path(__file__).resolve().parents[2] / "scripts/bailian_paid_smoke.py"
        process = subprocess.run(
            [sys.executable, str(script), "--scope", "missing-secret-scope.json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(process.returncode, 3)
        self.assertEqual(json.loads(process.stdout)["result"], "PAID_SMOKE_NOT_REQUESTED")
        self.assertEqual(self.calls, [])
