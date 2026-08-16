import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class RuntimeDirectoryTests(unittest.TestCase):
    def test_gateway_command_uses_absolute_installed_launcher(self):
        from free_vision.zcode_state import gateway_command
        skill = Path("/tmp/home/.zcode/skills/free-vision")
        state = Path("/tmp/home/.config/free-vision/zcode-gateway.json")
        command = gateway_command(skill_dir=skill, config_path=state, python_executable="python")
        self.assertEqual(command[0], "python")
        self.assertEqual(Path(command[1]), skill.resolve() / "scripts" / "zcode_gateway.py")
        self.assertEqual(command[2:], ["--config", str(state)])

    def test_start_gateway_process_uses_config_parent_as_cwd(self):
        from free_vision import __version__
        from free_vision.zcode_process import start_gateway_process
        from free_vision.zcode_types import ZCodeGatewayConfig
        calls = []
        class Process:
            def poll(self): return None
            def terminate(self): pass
        state = Path("/tmp/home/.config/free-vision/zcode-gateway.json")
        upstream = "http://127.0.0.1:18991/zen/v1"
        health_calls = iter([None, {"service":"free-vision-zcode-gateway","pid":1234,"version":__version__,"upstream_base_url":upstream}])
        def health(_config): return next(health_calls)
        def popen(command, **kwargs): calls.append((command, kwargs)); return Process()
        pid = start_gateway_process(config=ZCodeGatewayConfig(upstream), config_path=state, skill_dir=Path("/tmp/home/.zcode/skills/free-vision"), popen=popen, health_checker=health, sleep=lambda _n: None, python_executable="python")
        self.assertEqual(pid, 1234)
        self.assertEqual(Path(calls[0][1]["cwd"]), state.resolve().parent)
        self.assertNotIn("/.zcode/skills/free-vision", calls[0][1]["cwd"].replace("\\", "/"))


class WindowsStartupTests(unittest.TestCase):
    def test_startup_uses_runtime_dir_and_absolute_launcher_without_secret(self):
        from free_vision.zcode_state import install_windows_autostart
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / "skill"
            launcher = skill / "scripts" / "zcode_gateway.py"
            launcher.parent.mkdir(parents=True)
            launcher.write_text("# launcher\n", encoding="utf-8")
            state = root / "config" / "free-vision" / "zcode-gateway.json"
            startup = root / "startup"
            path = Path(install_windows_autostart(skill_dir=skill, config_path=state, python_executable="python.exe", startup_dir=startup))
            text = path.read_text(encoding="utf-8")
            self.assertIn(str(state.resolve().parent), text)
            self.assertIn(str(launcher.resolve()), text)
            self.assertNotIn(f'cd /d "{skill}"', text)
            self.assertNotIn("apiKey", text)
            self.assertNotIn("Bearer ", text)


class ZCodeForceInstallTests(unittest.TestCase):
    def _minimal_source(self, root: Path) -> Path:
        (root / "free_vision").mkdir(parents=True)
        (root / "scripts").mkdir(parents=True)
        (root / "SKILL.md").write_text("# Free Vision\n", encoding="utf-8")
        (root / "free_vision" / "__init__.py").write_text('__version__ = "0.3.9"\n', encoding="utf-8")
        for name in ("vision.py", "onboard.py", "configure.py", "doctor.py", "selftest.py", "zcode.py"):
            (root / "scripts" / name).write_text("# script\n", encoding="utf-8")
        return root

    def test_force_zcode_install_runs_preflight_before_replacement(self):
        from free_vision import install as install_mod
        self.assertTrue(hasattr(install_mod, "_prepare_zcode_force_replace"), "v0.3.9 requires a ZCode force-update preflight")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = self._minimal_source(root / "src"); home = root / "home"; dest = home / ".zcode" / "skills" / "free-vision"
            dest.mkdir(parents=True); (dest / "old.txt").write_text("old", encoding="utf-8")
            events = []; real_install = install_mod.install_skill
            def preflight(destination): events.append(("preflight", Path(destination))); return True
            def wrapped_install(*args, **kwargs): events.append(("install", Path(args[1]))); return real_install(*args, **kwargs)
            with mock.patch.object(install_mod, "_prepare_zcode_force_replace", side_effect=preflight), mock.patch.object(install_mod, "install_skill", side_effect=wrapped_install):
                rc = install_mod.main(["--target", "zcode", "--force"], source_root=source, home=home, stdout=io.StringIO(), stderr=io.StringIO())
            self.assertEqual(rc, 0)
            self.assertEqual(events[0], ("preflight", dest.resolve()))
            self.assertEqual(events[1], ("install", dest.resolve()))

    def test_stop_helper_never_kills_unknown_service(self):
        from free_vision import install as install_mod
        self.assertTrue(hasattr(install_mod, "_stop_managed_gateway_for_update"), "v0.3.9 requires identity-gated gateway stopping")
        killed = []
        result = install_mod._stop_managed_gateway_for_update(health={"service":"some-other-service","pid":8765}, kill=lambda pid,sig: killed.append((pid,sig)))
        self.assertFalse(result); self.assertEqual(killed, [])

    def test_stop_helper_signals_only_identified_free_vision_gateway(self):
        from free_vision import install as install_mod
        self.assertTrue(hasattr(install_mod, "_stop_managed_gateway_for_update"))
        killed = []
        result = install_mod._stop_managed_gateway_for_update(health={"service":"free-vision-zcode-gateway","pid":4242}, kill=lambda pid,sig: killed.append((pid,sig)))
        self.assertTrue(result); self.assertEqual(len(killed),1); self.assertEqual(killed[0][0],4242)


class InstallerPayloadTests(unittest.TestCase):
    def test_runtime_payload_includes_absolute_gateway_launcher(self):
        from free_vision.install import iter_payload_files
        root = Path.cwd()
        rel = {path.relative_to(root).as_posix() for path in iter_payload_files(root)}
        self.assertIn("scripts/zcode_gateway.py", rel)


class InstallerIdentityTests(unittest.TestCase):
    def test_health_url_from_state_rejects_non_loopback_host(self):
        from free_vision import install as install_mod
        self.assertTrue(hasattr(install_mod, "_health_url_from_state"))
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "zcode-gateway.json"
            state.write_text('{"host":"example.com","port":8765}', encoding="utf-8")
            self.assertIsNone(install_mod._health_url_from_state(state))

    def test_health_url_from_state_uses_only_saved_loopback_host_and_port(self):
        from free_vision import install as install_mod
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "zcode-gateway.json"
            state.write_text('{"host":"127.0.0.1","port":9876}', encoding="utf-8")
            self.assertEqual(install_mod._health_url_from_state(state), "http://127.0.0.1:9876/health")

    def test_invalid_pid_is_not_signaled(self):
        from free_vision import install as install_mod
        killed = []
        for pid in (None, 0, -1, "123"):
            with self.subTest(pid=pid):
                result = install_mod._stop_managed_gateway_for_update(
                    health={"service":"free-vision-zcode-gateway","pid":pid},
                    kill=lambda process_id, sig: killed.append((process_id, sig)),
                )
                self.assertFalse(result)
        self.assertEqual(killed, [])


class ExternalUpstreamOwnershipTests(unittest.TestCase):
    def test_runtime_modules_do_not_manage_known_external_proxy_process(self):
        for path in (
            Path("free_vision/zcode_state.py"),
            Path("free_vision/zcode_health.py"),
            Path("free_vision/zcode_process.py"),
            Path("free_vision/install.py"),
        ):
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("opencode-ua-proxy", text)
            self.assertNotIn("18991", text)


class ReleaseContractTests(unittest.TestCase):
    def test_version_and_reference_contract(self):
        from free_vision import __version__
        self.assertGreaterEqual(tuple(int(part) for part in __version__.split('.')), (0, 3, 9))
        text = Path("references/zcode.md").read_text(encoding="utf-8").lower()
        for needle in ("runtime cwd", "external upstream", "does not start", "does not stop", "force update"):
            self.assertIn(needle, text)

if __name__ == "__main__": unittest.main()