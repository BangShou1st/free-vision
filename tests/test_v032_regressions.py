import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from free_vision.types import Config, ModelCandidate


CANDIDATES = [ModelCandidate("mimo-v2.5-free", "MiMo", 0, 0, provider_id="opencode")]


class FakeProvider:
    def __init__(self):
        self.calls = []

    def analyze(self, model, media, task):
        self.calls.append((model, media, task))
        return "VISION_OK"


class DoctorProbeRegressionTests(unittest.TestCase):
    def test_probe_png_has_normal_dimensions(self):
        from free_vision.doctor import _PROBE_PNG

        self.assertEqual(_PROBE_PNG[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", _PROBE_PNG[16:24])
        self.assertGreater(width, 1)
        self.assertGreater(height, 1)

    def test_doctor_passes_embedded_probe_bytes_to_provider(self):
        from free_vision.doctor import _PROBE_PNG, run_doctor

        provider = FakeProvider()
        report = run_doctor(
            config_loader=lambda: (Config("secret"), "file"),
            discovery=lambda refresh=False: CANDIDATES,
            provider_factory=lambda key: provider,
        )

        self.assertTrue(report["ok"])
        media = provider.calls[0][1][0]
        self.assertEqual(media.source, "<free-vision-doctor>")
        self.assertEqual(media.mime_type, "image/png")
        self.assertEqual(media.data, _PROBE_PNG)


class XdgPathRegressionTests(unittest.TestCase):
    def test_config_path_uses_xdg_without_calling_home(self):
        from free_vision.config import config_path

        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"XDG_CONFIG_HOME": td}, clear=True
        ), patch.object(Path, "home", side_effect=AssertionError("Path.home should not be called")):
            self.assertEqual(config_path(), Path(td) / "free-vision" / "config.json")

    def test_cache_path_uses_xdg_without_calling_home(self):
        from free_vision.discovery import cache_path

        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"XDG_CACHE_HOME": td}, clear=True
        ), patch.object(Path, "home", side_effect=AssertionError("Path.home should not be called")):
            self.assertEqual(cache_path(), Path(td) / "free-vision" / "models.json")


class AgentContractRegressionTests(unittest.TestCase):
    @staticmethod
    def _skill_text():
        return (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8").lower()

    def test_image_presence_activates_without_keywords(self):
        text = self._skill_text()
        self.assertIn("image presence is sufficient activation evidence", text)
        self.assertIn("do not require explicit vision keywords", text)
        self.assertIn("attachment", text)
        self.assertIn(".png", text)
        self.assertIn("http", text)

    def test_native_vision_takes_precedence(self):
        text = self._skill_text()
        self.assertIn("can already inspect the image directly", text)
        self.assertIn("do not invoke free vision", text)

    def test_image_only_turn_uses_context_then_default_description(self):
        text = self._skill_text()
        self.assertIn("recent conversation context", text)
        self.assertIn("detailed visual description", text)
        self.assertIn("visible text", text)
        self.assertIn("ui state", text)

    def test_normal_repair_forbids_host_side_source_patching(self):
        text = self._skill_text()
        self.assertIn("never modify installed free vision source code", text)
        self.assertIn("installation, setup, doctor, or repair", text)

    def test_readme_fallback_uses_bundled_installer(self):
        text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("python scripts/install.py --dest <SKILL_ROOT> --force", text)
        self.assertIn("不要把整个开发仓库直接复制到最终 Skill 目录", text)


if __name__ == "__main__":
    unittest.main()
