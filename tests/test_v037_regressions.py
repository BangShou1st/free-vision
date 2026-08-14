import json
import signal
import tempfile
import unittest
from pathlib import Path


class V037ManagedOverlayTests(unittest.TestCase):
    def _fixture(self, root: Path):
        zdir = root / '.zcode' / 'v2'
        zdir.mkdir(parents=True)
        provider_id = '64322738-6381-44f3-a704-dacddbbefb08'
        original = {
            'enabled': True,
            'name': 'Console Free Model',
            'models': [{'id': 'deepseek-v4-flash-free'}],
            'metadata': {'source': 'console'},
        }
        config = zdir / 'config.json'
        cache = zdir / 'bots-model-cache.v2.json'
        config.write_text(json.dumps({'provider': {provider_id: original}}), encoding='utf-8')
        cache.write_text(json.dumps({'workspaceConfigOptions': {}}), encoding='utf-8')
        return config, cache, provider_id, original

    def test_uuid_provider_without_base_url_is_reversibly_overlaid(self):
        from free_vision.zcode import ZCodeGatewayConfig, connect_zcode_provider, restore_zcode_provider
        with tempfile.TemporaryDirectory() as td:
            config_path, cache_path, provider_id, original = self._fixture(Path(td))
            before_cache = json.loads(cache_path.read_text(encoding='utf-8'))
            cfg = ZCodeGatewayConfig()
            state = connect_zcode_provider(
                cfg,
                zcode_config_path=config_path,
                provider_id=provider_id,
                model_id='deepseek-v4-flash-free',
            )
            self.assertTrue(state.connected)
            self.assertTrue(state.managed_overlay)
            saved = json.loads(config_path.read_text(encoding='utf-8'))['provider'][provider_id]
            self.assertEqual(saved['kind'], 'openai-compatible')
            self.assertEqual(saved['apiFormat'], 'openai-chat-completions')
            self.assertEqual(saved['options']['baseURL'], cfg.gateway_base_url)
            self.assertEqual(saved['options']['apiKey'], 'free-vision-local')
            self.assertNotIn('secret', json.dumps(state.to_dict()).lower())
            self.assertTrue(restore_zcode_provider(cfg, connection=state))
            restored = json.loads(config_path.read_text(encoding='utf-8'))
            self.assertEqual(restored['provider'][provider_id], original)
            self.assertEqual(json.loads(cache_path.read_text(encoding='utf-8')), before_cache)

    def test_overlay_refuses_existing_provider_credential(self):
        from free_vision.zcode import ZCodeAdapterError, ZCodeGatewayConfig, connect_zcode_provider
        with tempfile.TemporaryDirectory() as td:
            config_path, _, provider_id, _ = self._fixture(Path(td))
            root = json.loads(config_path.read_text(encoding='utf-8'))
            root['provider'][provider_id]['token'] = 'account-secret'
            config_path.write_text(json.dumps(root), encoding='utf-8')
            before = config_path.read_text(encoding='utf-8')
            with self.assertRaisesRegex(ZCodeAdapterError, 'credential'):
                connect_zcode_provider(
                    ZCodeGatewayConfig(),
                    zcode_config_path=config_path,
                    provider_id=provider_id,
                    model_id='deepseek-v4-flash-free',
                )
            self.assertEqual(config_path.read_text(encoding='utf-8'), before)

    def test_overlay_refuses_unknown_or_non_free_model(self):
        from free_vision.zcode import ZCodeAdapterError, ZCodeGatewayConfig, connect_zcode_provider
        with tempfile.TemporaryDirectory() as td:
            config_path, _, provider_id, _ = self._fixture(Path(td))
            state = connect_zcode_provider(
                ZCodeGatewayConfig(), zcode_config_path=config_path, provider_id=provider_id
            )
            self.assertFalse(state.connected)
            self.assertTrue(state.manual_action_required)
            with self.assertRaisesRegex(ZCodeAdapterError, 'free OpenCode model'):
                connect_zcode_provider(
                    ZCodeGatewayConfig(),
                    zcode_config_path=config_path,
                    provider_id=provider_id,
                    model_id='glm-5.2',
                )


class V037GatewayBoundaryTests(unittest.TestCase):
    def test_opencode_forwarding_replaces_placeholder_with_free_vision_key(self):
        from free_vision.gateway import _forward_request_headers
        result = _forward_request_headers(
            {'Authorization': 'Bearer free-vision-local'},
            'https://opencode.ai/zen/v1/chat/completions',
            api_key_loader=lambda: 'real-free-vision-key',
        )
        self.assertEqual(result['Authorization'], 'Bear real-free-vision-key')
        self.assertNotIn('free-vision-local', repr(result))

    def test_health_reports_version_and_old_gateway_is_replaced(self):
        from free_vision import __version__
        from free_vision.zcode import ZCodeGatewayConfig, start_gateway_process
        health = iter([
            {'service': 'free-vision-zcode-gateway', 'pid': 19972},
            None,
            {'service': 'free-vision-zcode-gateway', 'pid': 22001, 'version': __version__},
        ])
        kills = []

        class Process:
            def poll(self): return None
            def terminate(self): raise AssertionError('new process should become healthy')

        pid = start_gateway_process(
            config=ZCodeGatewayConfig(),
            config_path=Path('gateway.json'),
            skill_dir=Path('skill'),
            health_checker=lambda cfg: next(health),
            kill=lambda pid, sig: kills.append((pid, sig)),
            popen=lambda *args, **kwargs: Process(),
            sleep=lambda seconds: None,
        )
        self.assertEqual(kills, [(19972, signal.SIGTERM)])
        self.assertEqual(pid, 22001)


class V037WindowsStartupTests(unittest.TestCase):
    def test_user_startup_launcher_contains_no_api_key(self):
        from free_vision.zcode import install_windows_autostart, remove_windows_autostart
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            startup = root / 'Startup'
            skill = root / 'skill'
            skill.mkdir()
            state = root / 'zcode-gateway.json'
            path = Path(install_windows_autostart(
                skill_dir=skill,
                config_path=state,
                startup_dir=startup,
                python_executable='C:/Python/python.exe',
            ))
            text = path.read_text(encoding='utf-8')
            self.assertIn('free_vision.gateway_cli', text)
            self.assertNotIn('api', text.lower())
            self.assertTrue(remove_windows_autostart(path=path))
            self.assertFalse(path.exists())


class V037ReleaseContractTests(unittest.TestCase):
    def test_version_and_zcode_reference_contract(self):
        from free_vision import __version__
        self.assertEqual(__version__, '0.3.7')
        text = Path('references/zcode.md').read_text(encoding='utf-8').lower()
        for needle in ('--provider-id', '--model', 'do not guess', 'placeholder', 'gateway_current', 'startup'):
            self.assertIn(needle, text)


if __name__ == '__main__':
    unittest.main()
