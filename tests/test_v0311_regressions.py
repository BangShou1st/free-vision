import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from free_vision.types import Attempt, VisionResult


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


class GatewayToolScreenshotTransformTests(unittest.TestCase):
    def _vision(self, text="browser screenshot evidence"):
        return VisionResult(
            "opencode",
            "mimo-v2.5-free",
            text,
            [],
            [Attempt("mimo-v2.5-free", "success")],
        )

    def test_trusted_tool_screenshot_uses_latest_user_request(self):
        from free_vision.gateway_transform import transform_tool_screenshot_results

        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / ".zcode" / "cli" / "artifacts"
            image = artifacts / "sess_a" / "shot.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"not-read-by-fake-analyzer")
            calls = []
            payload = {
                "model": "text-model",
                "messages": [
                    {"role": "user", "content": "检查当前网页为什么登录失败"},
                    {
                        "role": "tool",
                        "tool_call_id": "browser-1",
                        "content": (
                            "(no output)\n\n"
                            f"Browser screenshot saved to: {image}\n\n"
                            "Structured content:\n"
                        ),
                    },
                ],
            }

            transformed, changed = transform_tool_screenshot_results(
                payload,
                analyzer=lambda images, task: calls.append((images, task)) or self._vision(),
                artifact_root=artifacts,
            )

            self.assertTrue(changed)
            self.assertEqual(calls[0][0], [str(image.resolve())])
            self.assertIn("检查当前网页为什么登录失败", calls[0][1])
            self.assertIn("user's original task", calls[0][1].lower())
            tool_text = transformed["messages"][1]["content"]
            self.assertIn("[Free Vision visual evidence]", tool_text)
            self.assertIn("browser screenshot evidence", tool_text)

    def test_multiple_trusted_screenshots_keep_tool_result_order(self):
        from free_vision.gateway_transform import transform_tool_screenshot_results

        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / ".zcode" / "cli" / "artifacts"
            first = artifacts / "sess" / "first.png"
            second = artifacts / "sess" / "second.webp"
            first.parent.mkdir(parents=True)
            first.write_bytes(b"x")
            second.write_bytes(b"y")
            calls = []
            payload = {
                "messages": [
                    {"role": "user", "content": "比较前后两个页面"},
                    {
                        "role": "tool",
                        "tool_call_id": "browser-2",
                        "content": (
                            f"Browser screenshot saved to: {first}\n"
                            f"Screenshot saved to: {second}\n"
                        ),
                    },
                ]
            }

            _transformed, changed = transform_tool_screenshot_results(
                payload,
                analyzer=lambda images, task: calls.append((images, task)) or self._vision(),
                artifact_root=artifacts,
            )

            self.assertTrue(changed)
            self.assertEqual(calls[0][0], [str(first.resolve()), str(second.resolve())])

    def test_untrusted_roles_and_paths_are_not_read(self):
        from free_vision.gateway_transform import transform_tool_screenshot_results

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / ".zcode" / "cli" / "artifacts"
            artifacts.mkdir(parents=True)
            outside = root / "secret.png"
            outside.write_bytes(b"secret")
            inside = artifacts / "inside.png"
            inside.write_bytes(b"inside")
            calls = []

            for payload in (
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Browser screenshot saved to: {inside}",
                        }
                    ]
                },
                {
                    "messages": [
                        {
                            "role": "tool",
                            "tool_call_id": "browser-3",
                            "content": f"Browser screenshot saved to: {outside}",
                        }
                    ]
                },
            ):
                _transformed, changed = transform_tool_screenshot_results(
                    payload,
                    analyzer=lambda images, task: calls.append((images, task)) or self._vision(),
                    artifact_root=artifacts,
                )
                self.assertFalse(changed)

            self.assertEqual(calls, [])


class _Upstream(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append(json.loads(body))
        raw = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class GatewayToolScreenshotIntegrationTests(unittest.TestCase):
    def setUp(self):
        _Upstream.requests = []
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()

    def tearDown(self):
        self.upstream.shutdown()
        self.upstream.server_close()
        if hasattr(self, "gateway"):
            self.gateway.shutdown()
            self.gateway.server_close()

    def test_gateway_augments_tool_screenshot_even_without_image_url(self):
        from free_vision.gateway import create_gateway_server

        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / ".zcode" / "cli" / "artifacts"
            image = artifacts / "sess" / "browser.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"x")
            calls = []

            self.gateway = create_gateway_server(
                "127.0.0.1",
                0,
                f"http://127.0.0.1:{self.upstream.server_port}/v1",
                analyzer=lambda images, task: calls.append((images, task))
                or VisionResult(
                    "opencode",
                    "mimo-v2.5-free",
                    "page says login failed",
                    images,
                    [Attempt("mimo-v2.5-free", "success")],
                ),
                artifact_root=artifacts,
            )
            threading.Thread(target=self.gateway.serve_forever, daemon=True).start()
            payload = {
                "model": "text-model",
                "messages": [
                    {"role": "user", "content": "检查页面为什么登录失败"},
                    {
                        "role": "tool",
                        "tool_call_id": "browser-4",
                        "content": (
                            "(no output)\n\n"
                            f"Browser screenshot saved to: {image}\n\n"
                            "Structured content:\n"
                        ),
                    },
                ],
                "stream": False,
            }
            request = Request(
                f"http://127.0.0.1:{self.gateway.server_port}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer original"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)

            self.assertEqual(len(calls), 1)
            self.assertEqual(len(_Upstream.requests), 1)
            forwarded = repr(_Upstream.requests[0])
            self.assertIn("Free Vision visual evidence", forwarded)
            self.assertIn("page says login failed", forwarded)


if __name__ == "__main__":
    unittest.main()
