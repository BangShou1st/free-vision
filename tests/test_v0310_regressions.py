import io
import json
import tempfile
import unittest
from pathlib import Path


CANONICAL_REPOSITORY = "https://github.com/BangShou1st/free-vision"
CANONICAL_BRANCH = "main"
MIN_RELEASE_VERSION = (0, 3, 10)


class CanonicalSourceMetadataTests(unittest.TestCase):
    def test_source_metadata_matches_runtime_and_canonical_repository(self):
        from free_vision import __version__

        root = Path(__file__).resolve().parents[1]
        metadata = json.loads((root / "source.json").read_text(encoding="utf-8"))

        self.assertGreaterEqual(
            tuple(int(part) for part in __version__.split(".")),
            MIN_RELEASE_VERSION,
        )
        self.assertEqual(metadata["name"], "free-vision")
        self.assertEqual(metadata["repository"], CANONICAL_REPOSITORY)
        self.assertEqual(metadata["branch"], CANONICAL_BRANCH)
        self.assertEqual(metadata["version"], __version__)

    def test_runtime_payload_contains_source_metadata(self):
        from free_vision.install import iter_payload_files

        root = Path(__file__).resolve().parents[1]
        relative = {
            path.relative_to(root).as_posix()
            for path in iter_payload_files(root)
        }
        self.assertIn("source.json", relative)

    def test_installer_copies_source_metadata(self):
        from free_vision import __version__
        from free_vision.install import install_skill

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "skills" / "free-vision"
            install_skill(root, destination)
            installed = json.loads(
                (destination / "source.json").read_text(encoding="utf-8")
            )
            self.assertEqual(installed["repository"], CANONICAL_REPOSITORY)
            self.assertEqual(installed["branch"], CANONICAL_BRANCH)
            self.assertEqual(installed["version"], __version__)

    def test_installer_output_exposes_canonical_source(self):
        from free_vision.install import main

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            out = io.StringIO()
            err = io.StringIO()
            rc = main(
                ["--dest", str(Path(td) / "skills"), "--dry-run"],
                source_root=root,
                home=Path(td),
                project_dir=Path(td),
                stdout=out,
                stderr=err,
            )
            self.assertEqual(rc, 0, err.getvalue())
            self.assertIn(CANONICAL_REPOSITORY, out.getvalue())
            self.assertIn(CANONICAL_BRANCH, out.getvalue())


class AgentUpdateSourceContractTests(unittest.TestCase):
    def test_skill_names_canonical_source_and_forbids_repository_guessing(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "SKILL.md").read_text(encoding="utf-8")
        lower = text.lower()

        self.assertIn(CANONICAL_REPOSITORY, text)
        self.assertIn("source.json", text)
        self.assertIn("do not search", lower)
        self.assertIn("do not guess", lower)
        self.assertIn("not a git", lower)
        self.assertIn("scripts/install.py", lower)
        self.assertIn("--force", lower)
        self.assertIn("scripts/zcode.py setup", lower)
        self.assertIn("scripts/zcode.py status", lower)

    def test_readme_prominently_names_official_repository(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "README.md").read_text(encoding="utf-8")
        first_section = text[:1500]
        self.assertIn(CANONICAL_REPOSITORY, first_section)
        self.assertIn("官方仓库", first_section)


if __name__ == "__main__":
    unittest.main()
