import json
import unittest
from pathlib import Path


RELEASE_VERSION = "0.3.11"


class ToolGeneratedScreenshotContractTests(unittest.TestCase):
    def test_skill_recognizes_current_task_tool_result_screenshots(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "SKILL.md").read_text(encoding="utf-8")
        lower = text.lower()

        for needle in (
            "current task",
            "tool result",
            "tool-generated screenshot",
            "browser screenshot saved to",
            "(no output)",
            "structured content",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, lower)

        self.assertIn("do not stop", lower)
        self.assertIn("accessible", lower)

    def test_skill_preserves_original_user_task_for_tool_screenshot_fallback(self):
        root = Path(__file__).resolve().parents[1]
        lower = (root / "SKILL.md").read_text(encoding="utf-8").lower()

        self.assertIn("user's original task", lower)
        self.assertIn("--task", lower)
        self.assertIn("generic", lower)
        self.assertIn("describe this image", lower)

    def test_skill_handles_multiple_tool_generated_screenshots_in_order(self):
        root = Path(__file__).resolve().parents[1]
        lower = (root / "SKILL.md").read_text(encoding="utf-8").lower()

        self.assertIn("multiple", lower)
        self.assertIn("screenshot", lower)
        self.assertIn("task order", lower)
        self.assertIn("image [image ...]", lower)

    def test_release_metadata_is_v0311(self):
        from free_vision import __version__

        root = Path(__file__).resolve().parents[1]
        metadata = json.loads((root / "source.json").read_text(encoding="utf-8"))

        self.assertEqual(__version__, RELEASE_VERSION)
        self.assertEqual(metadata["version"], RELEASE_VERSION)

    def test_readme_documents_no_output_screenshot_fallback(self):
        root = Path(__file__).resolve().parents[1]
        lower = (root / "README.md").read_text(encoding="utf-8").lower()

        self.assertIn("(no output)", lower)
        self.assertIn("browser screenshot saved to", lower)
        self.assertIn("structured content", lower)
        self.assertIn("原始任务", lower)


if __name__ == "__main__":
    unittest.main()
