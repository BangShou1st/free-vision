import io
import json
import unittest
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
