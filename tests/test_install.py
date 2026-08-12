import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InstallDestinationTests(unittest.TestCase):
    def test_default_user_install_uses_cross_client_agents_directory(self):
        from free_vision.install import resolve_install_destination

        home = Path('/fake/home')
        self.assertEqual(
            resolve_install_destination('agents', 'user', home=home),
            home / '.agents' / 'skills' / 'free-vision',
        )

    def test_project_install_uses_project_agents_directory(self):
        from free_vision.install import resolve_install_destination

        project = Path('/workspace/project')
        self.assertEqual(
            resolve_install_destination('agents', 'project', home=Path('/home/u'), project_dir=project),
            project / '.agents' / 'skills' / 'free-vision',
        )

    def test_opencode_and_claude_targets_use_compatibility_directories(self):
        from free_vision.install import resolve_install_destination

        home = Path('/home/u')
        project = Path('/workspace/project')
        self.assertEqual(
            resolve_install_destination('opencode', 'user', home=home),
            home / '.config' / 'opencode' / 'skills' / 'free-vision',
        )
        self.assertEqual(
            resolve_install_destination('opencode', 'project', home=home, project_dir=project),
            project / '.opencode' / 'skills' / 'free-vision',
        )
        self.assertEqual(
            resolve_install_destination('claude', 'user', home=home),
            home / '.claude' / 'skills' / 'free-vision',
        )
        self.assertEqual(
            resolve_install_destination('claude', 'project', home=home, project_dir=project),
            project / '.claude' / 'skills' / 'free-vision',
        )

    def test_custom_destination_appends_skill_name_unless_already_named(self):
        from free_vision.install import resolve_install_destination

        self.assertEqual(
            resolve_install_destination('agents', 'user', home=Path('/home/u'), dest=Path('/custom/skills')),
            Path('/custom/skills/free-vision'),
        )
        self.assertEqual(
            resolve_install_destination('agents', 'user', home=Path('/home/u'), dest=Path('/custom/free-vision')),
            Path('/custom/free-vision'),
        )


class PayloadTests(unittest.TestCase):
    def test_payload_contains_runtime_files_and_excludes_development_files(self):
        from free_vision.install import iter_payload_files

        root = Path(__file__).resolve().parents[1]
        rel = {path.relative_to(root).as_posix() for path in iter_payload_files(root)}

        self.assertIn('SKILL.md', rel)
        self.assertIn('scripts/vision.py', rel)
        self.assertIn('scripts/onboard.py', rel)
        self.assertIn('scripts/configure.py', rel)
        self.assertIn('scripts/doctor.py', rel)
        self.assertIn('free_vision/media.py', rel)
        self.assertNotIn('scripts/install.py', rel)
        self.assertFalse(any(item.startswith('tests/') for item in rel))
        self.assertFalse(any(item.startswith('docs/') for item in rel))
        self.assertFalse(any('__pycache__' in item or item.endswith('.pyc') for item in rel))


class InstallBehaviorTests(unittest.TestCase):
    def _make_source(self, root: Path) -> Path:
        source = root / 'source'
        (source / 'scripts').mkdir(parents=True)
        (source / 'free_vision').mkdir()
        (source / 'references').mkdir()
        (source / 'agents').mkdir()
        (source / 'SKILL.md').write_text('---\nname: free-vision\ndescription: test\n---\n', encoding='utf-8')
        (source / 'scripts' / 'vision.py').write_text('print("vision")\n', encoding='utf-8')
        (source / 'scripts' / 'vision.sh').write_text('#!/bin/sh\n', encoding='utf-8')
        (source / 'scripts' / 'onboard.py').write_text('print("setup")\n', encoding='utf-8')
        (source / 'scripts' / 'configure.py').write_text('print("configure")\n', encoding='utf-8')
        (source / 'scripts' / 'doctor.py').write_text('print("doctor")\n', encoding='utf-8')
        (source / 'scripts' / 'install.py').write_text('print("installer")\n', encoding='utf-8')
        (source / 'free_vision' / '__init__.py').write_text('', encoding='utf-8')
        (source / 'references' / 'usage.md').write_text('usage', encoding='utf-8')
        (source / 'agents' / 'openai.yaml').write_text('interface: {}\n', encoding='utf-8')
        (source / 'tests').mkdir()
        (source / 'tests' / 'test_x.py').write_text('bad', encoding='utf-8')
        return source

    def test_install_rejects_source_missing_conversational_config_scripts(self):
        from free_vision.install import InstallError, install_skill

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._make_source(root)
            (source / 'scripts' / 'doctor.py').unlink()
            with self.assertRaises(InstallError) as ctx:
                install_skill(source, root / 'dest' / 'free-vision')
            self.assertIn('scripts/doctor.py', str(ctx.exception))

    def test_install_copies_filtered_payload(self):
        from free_vision.install import install_skill

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._make_source(root)
            destination = root / 'dest' / 'free-vision'
            result = install_skill(source, destination)

            self.assertEqual(result.destination, destination)
            self.assertTrue((destination / 'SKILL.md').is_file())
            self.assertTrue((destination / 'scripts' / 'vision.py').is_file())
            self.assertTrue((destination / 'references' / 'usage.md').is_file())
            self.assertTrue((destination / 'scripts' / 'configure.py').is_file())
            self.assertTrue((destination / 'scripts' / 'doctor.py').is_file())
            self.assertFalse((destination / 'scripts' / 'install.py').exists())
            self.assertFalse((destination / 'tests').exists())

    def test_installed_runtime_runs_from_an_unrelated_working_directory(self):
        from free_vision.install import install_skill

        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / 'skills' / 'free-vision'
            install_skill(source, destination)
            unrelated = root / 'work'
            unrelated.mkdir()
            proc = subprocess.run(
                [sys.executable, str(destination / 'scripts' / 'vision.py'), '--help'],
                cwd=unrelated,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('Analyze images with free OpenCode Zen vision models', proc.stdout)

    def test_existing_install_requires_force(self):
        from free_vision.install import InstallError, install_skill

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._make_source(root)
            destination = root / 'free-vision'
            destination.mkdir()
            (destination / 'old.txt').write_text('old', encoding='utf-8')
            with self.assertRaises(InstallError):
                install_skill(source, destination)
            self.assertTrue((destination / 'old.txt').is_file())

    def test_force_replaces_existing_install(self):
        from free_vision.install import install_skill

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._make_source(root)
            destination = root / 'free-vision'
            destination.mkdir()
            (destination / 'old.txt').write_text('old', encoding='utf-8')
            result = install_skill(source, destination, force=True)

            self.assertTrue(result.replaced)
            self.assertFalse((destination / 'old.txt').exists())
            self.assertTrue((destination / 'SKILL.md').is_file())

    def test_dry_run_has_no_filesystem_side_effects(self):
        from free_vision.install import install_skill

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._make_source(root)
            destination = root / 'free-vision'
            result = install_skill(source, destination, dry_run=True)

            self.assertTrue(result.dry_run)
            self.assertFalse(destination.exists())
            self.assertGreater(len(result.files), 0)


class SkillMetadataTests(unittest.TestCase):
    def test_skill_frontmatter_is_host_neutral_and_trigger_rich(self):
        text = (Path(__file__).resolve().parents[1] / 'SKILL.md').read_text(encoding='utf-8')
        frontmatter = text.split('---', 2)[1].lower()
        self.assertIn('name: free-vision', frontmatter)
        self.assertIn('local', frontmatter)
        self.assertIn('http', frontmatter)
        self.assertIn('screenshot', frontmatter)
        self.assertNotIn('codex', frontmatter)

    def test_skill_requires_user_task_passthrough_and_natural_language_answer(self):
        text = (Path(__file__).resolve().parents[1] / 'SKILL.md').read_text(encoding='utf-8').lower()
        self.assertIn("user's actual", text)
        self.assertIn('--task', text)
        self.assertIn('natural-language', text)
        self.assertIn('skill directory', text)

    def test_skill_defines_conversational_configuration_lifecycle(self):
        text = (Path(__file__).resolve().parents[1] / 'SKILL.md').read_text(encoding='utf-8').lower()
        self.assertIn('waiting_for_api_key', text)
        self.assertIn('change-key', text)
        self.assertIn('clear-key', text)
        self.assertIn('doctor', text)
        self.assertIn('conversation context', text)
        self.assertIn('stdin', text)
        self.assertIn('do not echo', text)
        self.assertIn('old key', text)


class InstallCliTests(unittest.TestCase):
    def test_cli_default_installs_to_agents_user_directory(self):
        from free_vision.install import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = InstallBehaviorTests()._make_source(root)
            home = root / 'home'
            out, err = io.StringIO(), io.StringIO()
            code = main([], source_root=source, home=home, project_dir=root / 'project', stdout=out, stderr=err)
            destination = home / '.agents' / 'skills' / 'free-vision'
            self.assertEqual(code, 0)
            self.assertTrue((destination / 'SKILL.md').is_file())
            self.assertIn(str(destination), out.getvalue())
            self.assertEqual(err.getvalue(), '')

    def test_cli_project_and_custom_dest_are_resolved(self):
        from free_vision.install import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = InstallBehaviorTests()._make_source(root)
            project = root / 'project'
            custom = root / 'custom-skills'
            out, err = io.StringIO(), io.StringIO()
            code = main(['--scope', 'project', '--target', 'opencode', '--dry-run'], source_root=source, home=root / 'home', project_dir=project, stdout=out, stderr=err)
            self.assertEqual(code, 0)
            self.assertIn(str(project / '.opencode' / 'skills' / 'free-vision'), out.getvalue())
            self.assertFalse((project / '.opencode').exists())

            out = io.StringIO()
            code = main(['--dest', str(custom), '--dry-run'], source_root=source, home=root / 'home', project_dir=project, stdout=out, stderr=err)
            self.assertEqual(code, 0)
            self.assertIn(str(custom / 'free-vision'), out.getvalue())

    def test_cli_existing_destination_returns_human_error(self):
        from free_vision.install import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = InstallBehaviorTests()._make_source(root)
            home = root / 'home'
            destination = home / '.agents' / 'skills' / 'free-vision'
            destination.mkdir(parents=True)
            out, err = io.StringIO(), io.StringIO()
            code = main([], source_root=source, home=home, project_dir=root, stdout=out, stderr=err)
            self.assertEqual(code, 1)
            self.assertIn('--force', err.getvalue())

    def test_script_entrypoint_works_outside_source_directory(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            custom = Path(td) / 'skills'
            proc = subprocess.run(
                [sys.executable, str(root / 'scripts' / 'install.py'), '--dest', str(custom), '--dry-run'],
                cwd=Path(td),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(str(custom / 'free-vision'), proc.stdout)


if __name__ == '__main__':
    unittest.main()
