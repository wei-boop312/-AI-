import tempfile
import unittest
from pathlib import Path

import httpx

from visual_platform.providers.bfl import BflProvider
from visual_platform.providers.gemini import GeminiProvider
from visual_platform.providers.pipeline import ProtocolProvider


class ProtocolActivationContracts(unittest.IsolatedAsyncioTestCase):
    async def test_live_transports_cannot_activate_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            bfl = BflProvider("offline-test-key", Path(directory) / "bfl")
            gemini = GeminiProvider("offline-test-key", Path(directory) / "gemini")
            try:
                with self.assertRaises(ValueError):
                    ProtocolProvider(bfl, gemini)
            finally:
                bfl.close()
                await gemini.aclose()

    async def test_mixed_transport_cannot_activate_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            bfl = BflProvider(
                "offline-test-key",
                Path(directory) / "bfl",
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
            )
            gemini = GeminiProvider("offline-test-key", Path(directory) / "gemini")
            try:
                with self.assertRaises(ValueError):
                    ProtocolProvider(bfl, gemini)
            finally:
                bfl.close()
                await gemini.aclose()
