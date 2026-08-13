import io
import json
import unittest
from pathlib import Path

from free_vision.types import Attempt, ConfigStatus, VisionResult


def cp936_stream():
    raw = io.BytesIO()
    text = io.TextIOWrapper(raw, encoding="cp936", errors="strict", newline="")
    return raw, text


def read_stream(raw, text):
    text.flush()
    return raw.getvalue().decode("cp936")


class WindowsJsonOutputTests(unittest.TestCase):
    def test_vision_cli_falls_back_to_ascii_escaped_json_on_cp936(self):
        from free_vision.cli import main

        raw, out = cp936_stream()
        result = VisionResult(
            "opencode",
            "mimo-v2.5-free",
            "商品 ¥459 😀",
            ["shot.png"],
            [Attempt("mimo-v2.5-free", "success")],
        )

        rc = main(["shot.png"], analyzer=lambda *args, **kwargs: result, stdout=out)
        payload = json.loads(read_stream(raw, out))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["result"], "商品 ¥459 😀")

    def test_doctor_cli_falls_back_to_ascii_escaped_json_on_cp936(self):
        from free_vision.doctor_cli import main

        raw, out = cp936_stream()
        report = {"ok": True, "vision": {"status": "ok", "detail": "价格 ¥459 😀"}}

        rc = main([], stdout=out, doctor=lambda **kwargs: report)
        payload = json.loads(read_stream(raw, out))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["vision"]["detail"], "价格 ¥459 😀")

    def test_configure_cli_falls_back_to_ascii_escaped_json_on_cp936(self):
        from free_vision.configure import main

        raw, out = cp936_stream()
        status = ConfigStatus(
            configured=True,
            active_source="file",
            has_environment_key=False,
            has_local_key=True,
            config_path="C:/Users/用户/¥😀/config.json",
        )

        rc = main(["status"], stdout=out, inspector=lambda: status)
        payload = json.loads(read_stream(raw, out))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["config_path"], status.config_path)


class SecretTransportContractTests(unittest.TestCase):
    def test_skill_forbids_temp_secret_files_and_scripts_when_host_lacks_safe_stdin(self):
        text = Path("SKILL.md").read_text(encoding="utf-8").lower()

        self.assertIn("no secure stdin", text)
        self.assertIn("configure.py set --pretty", text)
        self.assertIn("do not create a temporary file", text)
        self.assertIn("do not create a temporary script", text)
        self.assertIn("do not ask the user to paste the key into chat", text)

    def test_readme_documents_manual_hidden_input_fallback(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("没有安全 stdin", text)
        self.assertIn("不要创建临时 Key 文件", text)
        self.assertIn("configure.py set", text)


if __name__ == "__main__":
    unittest.main()
