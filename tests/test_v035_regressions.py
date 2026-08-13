import importlib.util
import io
import json
import struct
import unittest
from pathlib import Path

from free_vision.types import Attempt, ConfigStatus, VisionResult

ROOT = Path(__file__).resolve().parents[1]


def assert_ascii(testcase, text):
    testcase.assertTrue(text)
    testcase.assertTrue(all(ord(ch) < 128 for ch in text), repr(text))


class WindowsJsonContractTests(unittest.TestCase):
    def test_write_json_is_ascii_safe_and_round_trips_unicode(self):
        from free_vision.output import write_json

        out = io.StringIO()
        payload = {"text": "商品 ¥459 😀"}
        write_json(out, payload, pretty=True)
        raw = out.getvalue()

        assert_ascii(self, raw)
        self.assertEqual(json.loads(raw), payload)

    def test_vision_cli_output_is_ascii_safe(self):
        from free_vision.cli import main

        out = io.StringIO()
        result = VisionResult(
            "opencode",
            "mimo-v2.5-free",
            "商品 ¥459 😀",
            ["shot.png"],
            [Attempt("mimo-v2.5-free", "success")],
        )
        rc = main(["shot.png"], analyzer=lambda *args, **kwargs: result, stdout=out)
        self.assertEqual(rc, 0)
        assert_ascii(self, out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["result"], result.result)

    def test_doctor_cli_output_is_ascii_safe(self):
        from free_vision.doctor_cli import main

        out = io.StringIO()
        report = {"ok": True, "vision": {"detail": "价格 ¥459 😀"}}
        self.assertEqual(main([], stdout=out, doctor=lambda **kwargs: report), 0)
        assert_ascii(self, out.getvalue())
        self.assertEqual(json.loads(out.getvalue()), report)

    def test_configure_cli_output_is_ascii_safe(self):
        from free_vision.configure import main

        out = io.StringIO()
        status = ConfigStatus(True, "file", False, True, "C:/用户/¥😀/config.json")
        self.assertEqual(main(["status"], stdout=out, inspector=lambda: status), 0)
        assert_ascii(self, out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["config_path"], status.config_path)


class BundledAssetTests(unittest.TestCase):
    def test_selftest_asset_helper_exposes_valid_png(self):
        spec = importlib.util.find_spec("free_vision.assets")
        self.assertIsNotNone(spec, "free_vision.assets module is missing")
        if spec is None:
            return
        from free_vision.assets import load_selftest_image, selftest_image_path

        path = selftest_image_path()
        data = load_selftest_image()
        self.assertTrue(path.is_file())
        self.assertEqual(data, path.read_bytes())
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertGreaterEqual(width, 64)
        self.assertGreaterEqual(height, 48)

    def test_installer_payload_contains_asset_and_selftest_script(self):
        from free_vision.install import iter_payload_files

        rel = {p.relative_to(ROOT).as_posix() for p in iter_payload_files(ROOT)}
        self.assertIn("free_vision/assets/selftest.png", rel)
        self.assertIn("scripts/selftest.py", rel)


class DoctorAssetReuseTests(unittest.TestCase):
    def test_doctor_uses_shared_selftest_asset_instead_of_embedded_base64(self):
        source = (ROOT / "free_vision" / "doctor.py").read_text(encoding="utf-8")
        self.assertNotIn("_PROBE_PNG", source)
        self.assertNotIn("import base64", source)
        self.assertIn("load_selftest_image", source)


class SelftestCommandTests(unittest.TestCase):
    def test_selftest_runs_normal_analyzer_on_bundled_asset(self):
        spec = importlib.util.find_spec("free_vision.selftest")
        self.assertIsNotNone(spec, "free_vision.selftest module is missing")
        if spec is None:
            return
        from free_vision.assets import selftest_image_path
        from free_vision.selftest import run_selftest

        seen = {}

        def analyzer(images, task, **kwargs):
            seen["images"] = images
            seen["task"] = task
            return VisionResult(
                "opencode",
                "mimo-v2.5-free",
                "I see the bundled test card.",
                list(images),
                [Attempt("mimo-v2.5-free", "success")],
            )

        payload = run_selftest(analyzer=analyzer)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["selftest"])
        self.assertEqual(seen["images"], [str(selftest_image_path())])
        self.assertTrue(seen["task"])

    def test_selftest_cli_emits_json(self):
        spec = importlib.util.find_spec("free_vision.selftest_cli")
        self.assertIsNotNone(spec, "free_vision.selftest_cli module is missing")
        if spec is None:
            return
        from free_vision.selftest_cli import main

        out = io.StringIO()
        rc = main([], stdout=out, runner=lambda: {"ok": True, "selftest": True, "result": "ok"})
        self.assertEqual(rc, 0)
        assert_ascii(self, out.getvalue())
        self.assertTrue(json.loads(out.getvalue())["selftest"])


class AgentStabilityContractTests(unittest.TestCase):
    def test_skill_uses_bundled_selftest_and_forbids_shell_visible_secret_pipe(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("scripts/selftest.py --pretty", text)
        self.assertIn("python -c", text)
        self.assertIn("not a secure stdin", text)
        self.assertIn("playwright", text)
        self.assertIn("temporary image", text)

    def test_readme_uses_bundled_selftest_for_acceptance(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("scripts/selftest.py --pretty", text)
        self.assertIn("python -c", text)
        self.assertIn("Playwright", text)


if __name__ == "__main__":
    unittest.main()
