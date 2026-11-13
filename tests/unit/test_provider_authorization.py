import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image

from visual_platform.imaging.normalize import normalize
from visual_platform.providers.authorization import load_authorization, verify_sample


class ProviderAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.path = self.root / "review.json"
        image = BytesIO()
        Image.new("RGB", (256, 256), "white").save(image, format="PNG")
        self.image = normalize(image.getvalue())
        (self.root / "sample.png").write_bytes(self.image)
        self.now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
        self.data = {
            "authorization_id": str(uuid4()),
            "authorized_by": "review fixture, not spending permission",
            "authorized_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(hours=1)).isoformat(),
            "source_path": "sample.png",
            "source_sha256": hashlib.sha256(self.image).hexdigest(),
            "generation": {
                "type": "scene",
                "prompt": "Review fixture",
                "protection_mode": "pixel_exact",
                "regions": [
                    {
                        "source_x": 0,
                        "source_y": 0,
                        "width": 1,
                        "height": 1,
                        "target_x": 0,
                        "target_y": 0,
                    }
                ],
                "output": {"width": 256, "height": 256, "format": "png"},
            },
            "targets": [
                {
                    "platform": "amazon",
                    "marketplace": "US",
                    "category": "test",
                    "image_type": "MAIN",
                }
            ],
            "generate_ceiling": "0.10",
            "detect_ceiling": "0.02",
            "total_ceiling": "0.12",
        }

    def load(self, data=None, now=None):
        self.path.write_text(json.dumps(self.data if data is None else data))
        return load_authorization(self.path, now=now or self.now)

    async def test_canonical_sample_is_verified_in_isolated_decoder(self):
        scope, digest = self.load()
        sample = await verify_sample(scope, self.path)
        self.assertEqual(sample, {"sha256": scope.source_sha256, "width": 256, "height": 256})
        self.assertEqual(len(digest), 64)

    def test_request_and_cost_changes_change_review_digest(self):
        _, original = self.load()
        changed = copy.deepcopy(self.data)
        changed["generation"]["prompt"] = "Different request"
        self.assertNotEqual(original, self.load(changed)[1])
        changed = {**self.data, "total_ceiling": "0.13"}
        self.assertNotEqual(original, self.load(changed)[1])

    def test_duplicate_targets_cannot_expand_reviewed_scope(self):
        with self.assertRaisesRegex(ValueError, "duplicate targets"):
            self.load({**self.data, "targets": self.data["targets"] * 2})

    def test_duplicate_fields_are_rejected_before_model_validation(self):
        self.path.write_text('{"max_generate_calls":1,"max_generate_calls":2}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_authorization(self.path, now=self.now)

    def test_limits_models_extra_fields_and_types_cannot_expand_scope(self):
        for key, value in (
            ("max_generate_calls", 2),
            ("max_detect_calls", 2),
            ("max_generate_calls", True),
            ("schema_version", True),
            ("bfl_model", "other"),
            ("gemini_model", "other"),
            ("api_key", "fixture-not-a-real-key"),
            ("currency", "CNY"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.load({**self.data, key: value})

    def test_ceilings_are_exact_positive_decimal_strings_and_cover_both_calls(self):
        for value in (0.1, True, "0", "-1", "NaN", "Infinity", "1e2", "01", "0.0000001", "1000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load({**self.data, "generate_ceiling": value})
        with self.assertRaises(ValueError):
            self.load({**self.data, "total_ceiling": "0.119999"})

    def test_validity_is_utc_bounded_and_exclusive_at_expiry(self):
        for changed in (
            {"authorized_at": "2026-11-13T12:00:00"},
            {"authorized_at": "2026-11-13T20:00:00+08:00"},
            {"expires_at": (self.now + timedelta(hours=25)).isoformat()},
            {"expires_at": self.now.isoformat()},
            {"authorized_at": (self.now + timedelta(minutes=1)).isoformat()},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.load({**self.data, **changed})
        with self.assertRaises(ValueError):
            self.load(now=self.now + timedelta(hours=1))

    async def test_changed_or_malformed_sample_cannot_use_reviewed_scope(self):
        scope, _ = self.load()
        (self.root / "sample.png").write_bytes(b"not the reviewed image")
        with self.assertRaisesRegex(ValueError, "reviewed hash"):
            await verify_sample(scope, self.path)
        data = {**self.data, "source_sha256": hashlib.sha256(b"not the reviewed image").hexdigest()}
        scope, _ = self.load(data)
        with self.assertRaises(ValueError):
            await verify_sample(scope, self.path)

    async def test_protected_output_must_preserve_source_dimensions(self):
        data = copy.deepcopy(self.data)
        data["generation"]["output"]["width"] = 512
        scope, _ = self.load(data)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            await verify_sample(scope, self.path)

    def test_oversized_configuration_is_rejected(self):
        self.path.write_bytes(b" " * 65537)
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            load_authorization(self.path, now=self.now)

    def test_cli_without_preflight_cannot_execute_even_with_missing_config(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, str(root / "scripts/provider_smoke.py"), "--config", str(self.path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 3)
        report = json.loads(result.stdout)
        self.assertEqual(report["result"], "WAITING_EXTERNAL")
        self.assertEqual(report["paid_calls"], 0)

    def test_cli_diagnostics_do_not_echo_secret_config_fields(self):
        root = Path(__file__).resolve().parents[2]
        secret = "private-fixture-do-not-print"
        self.path.write_text(json.dumps({**self.data, "api_key": secret}))
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/provider_smoke.py"),
                "--config",
                str(self.path),
                "--preflight",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "PREFLIGHT_REJECTED")
