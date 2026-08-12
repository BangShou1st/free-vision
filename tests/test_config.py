import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ConfigTests(unittest.TestCase):
    def test_primary_environment_key_wins(self):
        from free_vision.config import load_config

        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "OPENCODE_API_KEY": "primary",
                "FREE_VISION_OPENCODE_API_KEY": "secondary",
                "XDG_CONFIG_HOME": td,
            },
            clear=True,
        ):
            self.assertEqual(load_config().api_key, "primary")

    def test_secondary_environment_key_beats_file(self):
        from free_vision.config import load_config

        with tempfile.TemporaryDirectory() as td:
            config_dir = Path(td) / "free-vision"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({"opencode_api_key": "file-key"}))
            with patch.dict(
                os.environ,
                {"FREE_VISION_OPENCODE_API_KEY": "secondary", "XDG_CONFIG_HOME": td},
                clear=True,
            ):
                self.assertEqual(load_config().api_key, "secondary")

    def test_file_key_is_loaded(self):
        from free_vision.config import load_config

        with tempfile.TemporaryDirectory() as td:
            config_dir = Path(td) / "free-vision"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({"opencode_api_key": "file-key"}))
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
                self.assertEqual(load_config().api_key, "file-key")

    def test_missing_key_raises_stable_error(self):
        from free_vision.config import load_config
        from free_vision.types import VisionError

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
            with self.assertRaises(VisionError) as ctx:
                load_config()
        self.assertEqual(ctx.exception.code, "missing_api_key")
        self.assertNotIn("Bearer", str(ctx.exception))

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_save_api_key_uses_private_permissions(self):
        from free_vision.config import config_path, save_api_key

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
            path = save_api_key("secret-value")
            self.assertEqual(path, config_path())
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            data = json.loads(path.read_text())
            self.assertEqual(data["opencode_api_key"], "secret-value")


if __name__ == "__main__":
    unittest.main()

class ConfigLifecycleTests(unittest.TestCase):
    def test_inspect_config_reports_active_environment_source_without_secret(self):
        from free_vision.config import inspect_config

        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {"OPENCODE_API_KEY": "top-secret", "XDG_CONFIG_HOME": td},
            clear=True,
        ):
            status = inspect_config()

        self.assertTrue(status.configured)
        self.assertEqual(status.active_source, "env:OPENCODE_API_KEY")
        self.assertTrue(status.has_environment_key)
        self.assertFalse(status.has_local_key)
        self.assertNotIn("top-secret", repr(status))

    def test_inspect_config_reports_file_when_no_environment_key(self):
        from free_vision.config import inspect_config, save_api_key

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
            save_api_key("file-secret")
            status = inspect_config()

        self.assertEqual(status.active_source, "file")
        self.assertTrue(status.has_local_key)
        self.assertFalse(status.has_environment_key)

    def test_clear_saved_api_key_removes_only_local_key(self):
        from free_vision.config import clear_saved_api_key, inspect_config, save_api_key

        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {"OPENCODE_API_KEY": "env-secret", "XDG_CONFIG_HOME": td},
            clear=True,
        ):
            save_api_key("file-secret")
            self.assertTrue(clear_saved_api_key())
            status = inspect_config()

        self.assertTrue(status.configured)
        self.assertEqual(status.active_source, "env:OPENCODE_API_KEY")
        self.assertFalse(status.has_local_key)

    def test_clear_saved_api_key_is_idempotent(self):
        from free_vision.config import clear_saved_api_key

        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True):
            self.assertFalse(clear_saved_api_key())
