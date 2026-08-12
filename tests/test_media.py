import io
import tempfile
import unittest
from pathlib import Path

from free_vision.types import VisionError


PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 16
GIF = b"GIF89a" + b"x" * 16
WEBP = b"RIFF" + (20).to_bytes(4, "little") + b"WEBP" + b"x" * 16


class FakeResponse:
    def __init__(self, data: bytes, content_type: str = "application/octet-stream"):
        self._stream = io.BytesIO(data)
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(data))}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class MediaTests(unittest.TestCase):
    def test_detects_supported_signatures(self):
        from free_vision.media import detect_mime

        self.assertEqual(detect_mime(PNG), "image/png")
        self.assertEqual(detect_mime(JPEG), "image/jpeg")
        self.assertEqual(detect_mime(GIF), "image/gif")
        self.assertEqual(detect_mime(WEBP), "image/webp")

    def test_local_image_is_loaded(self):
        from free_vision.media import resolve_media

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shot.png"
            path.write_bytes(PNG)
            media = resolve_media(str(path), max_bytes=1024)
        self.assertEqual(media.mime_type, "image/png")
        self.assertEqual(media.data, PNG)
        self.assertIn("base64,", media.data_uri)

    def test_rejects_invalid_image(self):
        from free_vision.media import resolve_media

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.png"
            path.write_bytes(b"not-an-image")
            with self.assertRaises(VisionError) as ctx:
                resolve_media(str(path), max_bytes=1024)
        self.assertEqual(ctx.exception.code, "unsupported_media")

    def test_windows_drive_paths_are_classified_as_local(self):
        from free_vision.media import classify_source

        self.assertEqual(classify_source(r"C:\Users\32962\Desktop\test.png"), "local")
        self.assertEqual(classify_source("C:/Users/32962/Desktop/test.png"), "local")

    def test_rejects_unsupported_url_scheme(self):
        from free_vision.media import resolve_media

        with self.assertRaises(VisionError) as ctx:
            resolve_media("ftp://example.com/a.png")
        self.assertEqual(ctx.exception.code, "unsupported_url_scheme")

    def test_remote_image_download_is_bounded(self):
        from free_vision.media import resolve_media

        def opener(request, timeout):
            return FakeResponse(PNG + b"z" * 128, "image/png")

        with self.assertRaises(VisionError) as ctx:
            resolve_media("https://example.com/a.png", max_bytes=32, opener=opener)
        self.assertEqual(ctx.exception.code, "media_too_large")

    def test_remote_image_download_succeeds(self):
        from free_vision.media import resolve_media

        def opener(request, timeout):
            return FakeResponse(PNG, "image/png")

        media = resolve_media("https://example.com/a.png", max_bytes=1024, opener=opener)
        self.assertEqual(media.source, "https://example.com/a.png")
        self.assertEqual(media.mime_type, "image/png")
        self.assertEqual(media.data, PNG)


if __name__ == "__main__":
    unittest.main()
