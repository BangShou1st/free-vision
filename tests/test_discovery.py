import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from free_vision.types import VisionError


ZEN = {
    "object": "list",
    "data": [
        {"id": "mimo-v2.5-free"},
        {"id": "vision-free-b"},
        {"id": "text-free"},
        {"id": "deprecated-vision-free"},
        {"id": "paid-vision"},
    ],
}

MODELS_DEV = {
    "opencode": {
        "id": "opencode",
        "name": "OpenCode",
        "models": {
            "mimo-v2.5-free": {
                "name": "MiMo V2.5 Free",
                "cost": {"input": 0, "output": 0},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            },
            "vision-free-b": {
                "name": "Vision B",
                "cost": {"input": 0.0, "output": 0.0},
                "modalities": {"input": ["image", "text"], "output": ["text"]},
            },
            "text-free": {
                "name": "Text Free",
                "cost": {"input": 0, "output": 0},
                "modalities": {"input": ["text"], "output": ["text"]},
            },
            "deprecated-vision-free": {
                "name": "Old Vision",
                "status": "deprecated",
                "cost": {"input": 0, "output": 0},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            },
            "paid-vision": {
                "name": "Paid Vision",
                "cost": {"input": 0.1, "output": 0},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            },
            "not-live": {
                "name": "Not Live",
                "cost": {"input": 0, "output": 0},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            },
        },
    },
    "other-provider": {
        "name": "Other",
        "models": {
            "text-free": {
                "name": "Duplicate Vision Elsewhere",
                "cost": {"input": 0, "output": 0},
                "modalities": {"input": ["image"], "output": ["text"]},
            }
        },
    },
}


class DiscoveryTests(unittest.TestCase):
    def test_extract_candidates_intersects_live_free_vision_models(self):
        from free_vision.discovery import extract_candidates

        candidates = extract_candidates(ZEN, MODELS_DEV)
        self.assertEqual([c.model_id for c in candidates], ["mimo-v2.5-free", "vision-free-b"])
        self.assertTrue(all(c.input_cost == 0 and c.output_cost == 0 for c in candidates))

    def test_extract_candidates_accepts_api_list_provider_shape(self):
        from free_vision.discovery import extract_candidates

        payload = [{"id": "opencode", "name": "OpenCode", "models": MODELS_DEV["opencode"]["models"]}]
        candidates = extract_candidates(ZEN, payload)
        self.assertEqual([c.model_id for c in candidates], ["mimo-v2.5-free", "vision-free-b"])

    def test_discover_candidates_caches_successful_result(self):
        from free_vision.discovery import discover_candidates

        calls = []

        def fetch_json(url, **kwargs):
            calls.append(url)
            return ZEN if "opencode.ai" in url else MODELS_DEV

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CACHE_HOME": td}, clear=True):
            first = discover_candidates(fetch_json=fetch_json)
            second = discover_candidates(fetch_json=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
            self.assertEqual([c.model_id for c in first], [c.model_id for c in second])
            self.assertEqual(len(calls), 2)
            cache = Path(td) / "free-vision" / "models.json"
            self.assertTrue(cache.is_file())

    def test_refresh_bypasses_cache(self):
        from free_vision.discovery import cache_path, discover_candidates

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CACHE_HOME": td}, clear=True):
            path = cache_path()
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"created_at": time.time(), "candidates": []}))
            calls = []

            def fetch_json(url, **kwargs):
                calls.append(url)
                return ZEN if "opencode.ai" in url else MODELS_DEV

            result = discover_candidates(refresh=True, fetch_json=fetch_json)
            self.assertEqual(len(calls), 2)
            self.assertEqual(result[0].model_id, "mimo-v2.5-free")

    def test_discovery_failure_without_cache_is_stable(self):
        from free_vision.discovery import discover_candidates

        def fail(*args, **kwargs):
            raise OSError("network down")

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CACHE_HOME": td}, clear=True):
            with self.assertRaises(VisionError) as ctx:
                discover_candidates(fetch_json=fail)
        self.assertEqual(ctx.exception.code, "model_discovery_failed")


if __name__ == "__main__":
    unittest.main()
