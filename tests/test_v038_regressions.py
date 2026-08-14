import ast
import io
import json
import tempfile
import unittest
from pathlib import Path


class ReleaseIntegrityTests(unittest.TestCase):
    def test_release_python_sources_are_utf8_and_parse(self):
        names = sorted(
            path
            for pattern in ("gateway*.py", "zcode*.py")
            for path in Path("free_vision").glob(pattern)
        )
        for path in names:
            with self.subTest(path=path.as_posix()):
                source = path.read_bytes().decode("utf-8")
                ast.parse(source, filename=str(path))


class ExistingProviderChainTests(unittest.TestCase):
    def test_setup_adopts_existing_provider_base_url_and_preserves_key(self):
        from free_vision.zcode import ZCodeGatewayConfig, load_gateway_config, save_gateway_config
        from free_vision.zcode_cli import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zdir = root / ".zcode" / "v2"
            zdir.mkdir(parents=True)
            provider_id = "64322738-6381-44f3-a704-dacddbbefb08"
            upstream = "http://127.0.0.1:18991/zen/v1"
            config_path = zdir / "config.json"
            config_path.write_text(
                json.dumps({"provider": {provider_id: {
                    "enabled": True,
                    "kind": "openai-compatible",
                    "models": [{"id": "deepseek-v4-flash-free"}],
                    "options": {"baseURL": upstream, "apiKey": "existing-provider-secret"},
                }}}),
                encoding="utf-8",
            )
            (zdir / "bots-model-cache.v2.json").write_text('{"workspaceConfigOptions":{}}', encoding="utf-8")
            state_path = root / "gateway.json"
            save_gateway_config(ZCodeGatewayConfig("https://opencode.ai/zen/v1"), path=state_path)
            out = io.StringIO()
            rc = main([
                "setup", "--zcode-config", str(config_path),
                "--provider-id", provider_id,
                "--model", "deepseek-v4-flash-free",
                "--no-start", "--no-autostart",
            ], stdout=out, config_path=state_path, platform_name="posix")
            payload = json.loads(out.getvalue())
            self.assertEqual(rc, 0)
            self.assertTrue(payload["zcode_connected"])
            self.assertEqual(payload["upstream_base_url"], upstream)
            provider = json.loads(config_path.read_text(encoding="utf-8"))["provider"][provider_id]
            self.assertEqual(provider["options"]["baseURL"], "http://127.0.0.1:8765/v1")
            self.assertEqual(provider["options"]["apiKey"], "existing-provider-secret")
            managed = load_gateway_config(path=state_path)
            self.assertEqual(managed.upstream_base_url, upstream)
            self.assertNotIn("existing-provider-secret", state_path.read_text(encoding="utf-8"))


class GatewayIdentityTests(unittest.TestCase):
    def test_gateway_current_requires_matching_version_and_upstream(self):
        from free_vision import __version__
        from free_vision.zcode import ZCodeGatewayConfig, gateway_matches_config

        config = ZCodeGatewayConfig("http://127.0.0.1:18991/zen/v1")
        good = {
            "service": "free-vision-zcode-gateway",
            "version": __version__,
            "upstream_base_url": config.upstream_base_url,
        }
        self.assertTrue(gateway_matches_config(good, config))
        stale = dict(good, upstream_base_url="https://opencode.ai/zen/v1")
        self.assertFalse(gateway_matches_config(stale, config))


class ReleaseContractTests(unittest.TestCase):
    def test_version_and_reference_contract(self):
        from free_vision import __version__

        self.assertGreaterEqual(tuple(int(part) for part in __version__.split('.')), (0, 3, 8))
        text = Path("references/zcode.md").read_text(encoding="utf-8").lower()
        for needle in ("existing base url", "upstream", "preserve", "api key", "gateway_current"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
