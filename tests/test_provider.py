import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from free_vision.types import MediaInput, VisionError


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ProviderTests(unittest.TestCase):
    def test_builds_multimodal_chat_completions_payload(self):
        from free_vision.provider import OpenCodeProvider

        calls = []

        def post_json(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"choices": [{"message": {"content": "I see an error dialog."}}]}

        provider = OpenCodeProvider("secret", post_json=post_json)
        media = [MediaInput("a.png", "image/png", b"\x89PNG\r\n\x1a\n")]
        result = provider.analyze("mimo-v2.5-free", media, "Read the screenshot")

        self.assertEqual(result, "I see an error dialog.")
        url, payload, headers, _ = calls[0]
        self.assertTrue(url.endswith("/chat/completions"))
        self.assertEqual(payload["model"], "mimo-v2.5-free")
        content = payload["messages"][0]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "Read the screenshot"})
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_zen_provider_uses_opencode_user_agent_by_default(self):
        from free_vision.http import post_json
        from free_vision.provider import OpenCodeProvider

        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["user_agent"] = request.get_header("User-agent")
            seen["authorization"] = request.get_header("Authorization")
            return FakeHttpResponse({"choices": [{"message": {"content": "ok"}}]})

        def zen_post_json(url, payload, *, headers, timeout):
            return post_json(url, payload, headers=headers, timeout=timeout, opener=opener)

        with patch.dict(os.environ, {}, clear=True):
            provider = OpenCodeProvider("secret", post_json=zen_post_json)
            provider.analyze("mimo-v2.5-free", [MediaInput("x", "image/png", b"x")], "task")

        self.assertTrue(seen["url"].endswith("/chat/completions"))
        self.assertEqual(seen["user_agent"], "opencode/1.18.16")
        self.assertEqual(seen["authorization"], "Bearer secret")

    def test_zen_provider_user_agent_can_be_overridden_by_environment(self):
        from free_vision.provider import OpenCodeProvider

        calls = []

        def post_json(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"choices": [{"message": {"content": "ok"}}]}

        with patch.dict(os.environ, {"ZEN_USER_AGENT": "opencode/0.0.0"}):
            provider = OpenCodeProvider("secret", post_json=post_json)
            provider.analyze("mimo-v2.5-free", [MediaInput("x", "image/png", b"x")], "task")

        self.assertEqual(calls[0][2]["User-Agent"], "opencode/0.0.0")

    def test_generic_post_json_keeps_free_vision_user_agent(self):
        from free_vision.http import post_json

        seen = {}

        def opener(request, timeout):
            seen["user_agent"] = request.get_header("User-agent")
            return FakeHttpResponse({"ok": True})

        post_json("https://example.com/api", {"hello": "world"}, opener=opener)

        self.assertEqual(seen["user_agent"], "free-vision/0.1")
        self.assertNotEqual(seen["user_agent"], "opencode/1.18.16")

    def test_parses_list_content_response(self):
        from free_vision.provider import OpenCodeProvider

        provider = OpenCodeProvider(
            "secret",
            post_json=lambda *a, **k: {
                "choices": [{"message": {"content": [{"type": "text", "text": "part one"}, {"text": "part two"}]}}]
            },
        )
        result = provider.analyze("model", [MediaInput("x", "image/png", b"x")], "task")
        self.assertEqual(result, "part one\npart two")

    def test_malformed_response_raises_stable_error(self):
        from free_vision.provider import OpenCodeProvider

        provider = OpenCodeProvider("secret", post_json=lambda *a, **k: {"choices": []})
        with self.assertRaises(VisionError) as ctx:
            provider.analyze("model", [MediaInput("x", "image/png", b"x")], "task")
        self.assertEqual(ctx.exception.code, "invalid_provider_response")

    def test_http_post_json_maps_http_status_without_leaking_secret(self):
        from free_vision.http import post_json

        def opener(request, timeout):
            raise HTTPError(request.full_url, 401, "Unauthorized secret-value", hdrs=None, fp=io.BytesIO(b"secret-value"))

        with self.assertRaises(VisionError) as ctx:
            post_json(
                "https://example.com/v1/chat/completions",
                {"hello": "world"},
                headers={"Authorization": "Bearer secret-value"},
                opener=opener,
            )
        self.assertEqual(ctx.exception.status, 401)
        self.assertNotIn("secret-value", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
