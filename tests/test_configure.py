import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ConfigureCliTests(unittest.TestCase):
    def test_status_json_reports_source_without_secret(self):
        from free_vision.configure import main
        from free_vision.config import save_api_key

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
            save_api_key("file-secret")
            out = io.StringIO()
            rc = main(["status"], stdout=out)

        payload = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["active_source"], "file")
        self.assertTrue(payload["has_local_key"])
        self.assertNotIn("file-secret", out.getvalue())

    def test_set_reads_key_from_stdin_validates_then_saves(self):
        from free_vision.configure import main

        saved = []
        out = io.StringIO()
        rc = main(
            ["set", "--stdin"],
            stdin=io.StringIO("new-secret\n"),
            stdout=out,
            inspector=lambda: type("S", (), {"has_environment_key": False})(),
            validator=lambda **kwargs: {
                "ok": True,
                "configuration": {"status": "ok", "source": "candidate"},
                "discovery": {"status": "ok", "models": 1},
                "authentication": {"status": "ok"},
                "vision": {"status": "ok", "model": "mimo-v2.5-free"},
            },
            saver=lambda key: saved.append(key) or Path("config.json"),
        )

        payload = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(saved, ["new-secret"])
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["doctor"]["vision"]["model"], "mimo-v2.5-free")
        self.assertEqual(payload["doctor"]["configuration"]["source"], "file")
        self.assertNotIn("new-secret", out.getvalue())

    def test_set_stdin_consumes_one_line_without_waiting_for_eof(self):
        from free_vision.configure import main

        class LineOnlyInput:
            def readline(self):
                return "line-secret\n"

        saved = []
        out = io.StringIO()
        rc = main(
            ["set", "--stdin"],
            stdin=LineOnlyInput(),
            stdout=out,
            inspector=lambda: type("S", (), {"has_environment_key": False})(),
            validator=lambda **kwargs: {
                "ok": True,
                "configuration": {"status": "ok", "source": "candidate"},
                "discovery": {"status": "ok", "models": 1},
                "authentication": {"status": "ok"},
                "vision": {"status": "ok", "model": "mimo-v2.5-free"},
            },
            saver=lambda key: saved.append(key) or Path("config.json"),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(saved, ["line-secret"])

    def test_failed_candidate_validation_preserves_existing_file_key(self):
        from free_vision.configure import main
        from free_vision.config import load_config, save_api_key

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
            save_api_key("old-secret")
            out = io.StringIO()
            rc = main(
                ["set", "--stdin"],
                stdin=io.StringIO("bad-new-secret\n"),
                stdout=out,
                validator=lambda **kwargs: {
                    "ok": False,
                    "configuration": {"status": "ok", "source": "candidate"},
                    "discovery": {"status": "ok", "models": 1},
                    "authentication": {"status": "failed"},
                    "vision": {"status": "failed"},
                    "error": {"code": "authentication_failed", "message": "rejected"},
                },
            )
            current = load_config().api_key

        payload = json.loads(out.getvalue())
        self.assertEqual(rc, 1)
        self.assertFalse(payload["saved"])
        self.assertEqual(payload["error"]["code"], "authentication_failed")
        self.assertEqual(current, "old-secret")
        self.assertNotIn("bad-new-secret", out.getvalue())
        self.assertNotIn("old-secret", out.getvalue())

    def test_environment_key_blocks_local_replacement(self):
        from free_vision.configure import main

        out = io.StringIO()
        rc = main(
            ["set", "--stdin"],
            stdin=io.StringIO("unused-secret\n"),
            stdout=out,
            inspector=lambda: type("S", (), {"has_environment_key": True, "active_source": "env:OPENCODE_API_KEY"})(),
        )
        payload = json.loads(out.getvalue())
        self.assertEqual(rc, 1)
        self.assertEqual(payload["error"]["code"], "environment_key_active")
        self.assertNotIn("unused-secret", out.getvalue())

    def test_clear_removes_local_key_but_reports_remaining_environment_source(self):
        from free_vision.configure import main

        states = iter([
            type("S", (), {"configured": True, "active_source": "env:OPENCODE_API_KEY", "has_environment_key": True, "has_local_key": True, "config_path": "x"})(),
            type("S", (), {"configured": True, "active_source": "env:OPENCODE_API_KEY", "has_environment_key": True, "has_local_key": False, "config_path": "x"})(),
        ])
        out = io.StringIO()
        rc = main(
            ["clear"],
            stdout=out,
            inspector=lambda: next(states),
            clearer=lambda: True,
        )
        payload = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertTrue(payload["removed_local_key"])
        self.assertEqual(payload["active_source"], "env:OPENCODE_API_KEY")
        self.assertTrue(payload["configured"])


class DoctorCliTests(unittest.TestCase):
    def test_doctor_cli_writes_json(self):
        from free_vision.doctor_cli import main

        out = io.StringIO()
        rc = main(
            ["--pretty"],
            stdout=out,
            doctor=lambda **kwargs: {
                "ok": True,
                "configuration": {"status": "ok", "source": "file"},
                "discovery": {"status": "ok", "models": 1},
                "authentication": {"status": "ok"},
                "vision": {"status": "ok", "model": "mimo-v2.5-free"},
            },
        )
        payload = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
