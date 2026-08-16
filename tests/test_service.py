import os
import tempfile
import unittest
from unittest.mock import patch

from free_vision.types import MediaInput, ModelCandidate, VisionError


CANDIDATES = [
    ModelCandidate("first", "First", 0, 0),
    ModelCandidate("second", "Second", 0, 0),
]


class FakeProvider:
    def __init__(self, behavior):
        self.behavior = behavior

    def analyze(self, model, media, task):
        action = self.behavior[model]
        if isinstance(action, Exception):
            raise action
        return action


class BatchRejectingProvider:
    def __init__(self, *, batch_status=400):
        self.batch_status = batch_status
        self.calls = []

    def analyze(self, model, media, task):
        self.calls.append((model, [item.source for item in media], task))
        if len(media) > 1:
            raise VisionError(
                "provider_request_failed",
                "provider rejected multi-image batch",
                status=self.batch_status,
            )
        return f"evidence for {media[0].source}"


class ServiceTests(unittest.TestCase):
    def test_falls_back_to_second_model(self):
        from free_vision.service import analyze

        provider = FakeProvider({"first": VisionError("provider_request_failed", "temporary", status=500), "second": "done"})
        result = analyze(
            ["a.png"],
            "task",
            config_loader=lambda: type("C", (), {"api_key": "secret"})(),
            discovery=lambda refresh=False: CANDIDATES,
            resolver=lambda source: MediaInput(source, "image/png", b"x"),
            provider_factory=lambda key: provider,
        )
        self.assertEqual(result.model, "second")
        self.assertEqual([a.status for a in result.attempts], ["failed", "success"])

    def test_auth_failure_stops_without_trying_next_model(self):
        from free_vision.service import analyze

        provider = FakeProvider({"first": VisionError("provider_request_failed", "unauthorized", status=401), "second": "should not run"})
        with self.assertRaises(VisionError) as ctx:
            analyze(
                ["a.png"],
                "task",
                config_loader=lambda: type("C", (), {"api_key": "secret"})(),
                discovery=lambda refresh=False: CANDIDATES,
                resolver=lambda source: MediaInput(source, "image/png", b"x"),
                provider_factory=lambda key: provider,
            )
        self.assertEqual(ctx.exception.code, "authentication_failed")
        self.assertEqual(len(ctx.exception.attempts), 1)

    def test_all_models_failed_contains_safe_attempts(self):
        from free_vision.service import analyze

        provider = FakeProvider({
            "first": VisionError("provider_request_failed", "one", status=500),
            "second": VisionError("provider_request_failed", "two", status=429),
        })
        with self.assertRaises(VisionError) as ctx:
            analyze(
                ["a.png"],
                "task",
                config_loader=lambda: type("C", (), {"api_key": "secret"})(),
                discovery=lambda refresh=False: CANDIDATES,
                resolver=lambda source: MediaInput(source, "image/png", b"x"),
                provider_factory=lambda key: provider,
            )
        self.assertEqual(ctx.exception.code, "all_models_failed")
        self.assertEqual([a.model for a in ctx.exception.attempts], ["first", "second"])

    def test_forced_model_must_be_free_vision_candidate(self):
        from free_vision.service import analyze

        with self.assertRaises(VisionError) as ctx:
            analyze(
                ["a.png"],
                "task",
                model="paid-model",
                config_loader=lambda: type("C", (), {"api_key": "secret"})(),
                discovery=lambda refresh=False: CANDIDATES,
                resolver=lambda source: MediaInput(source, "image/png", b"x"),
                provider_factory=lambda key: FakeProvider({}),
            )
        self.assertEqual(ctx.exception.code, "model_not_eligible")

    def test_multi_image_batch_rejection_falls_back_to_each_image(self):
        from free_vision.service import analyze

        provider = BatchRejectingProvider(batch_status=400)
        result = analyze(
            ["a.png", "b.png"],
            "compare the screenshots",
            config_loader=lambda: type("C", (), {"api_key": "secret"})(),
            discovery=lambda refresh=False: [CANDIDATES[0]],
            resolver=lambda source: MediaInput(source, "image/png", b"x"),
            provider_factory=lambda key: provider,
        )

        self.assertEqual(
            [call[1] for call in provider.calls],
            [["a.png", "b.png"], ["a.png"], ["b.png"]],
        )
        self.assertIn("[Image 1]", result.result)
        self.assertIn("evidence for a.png", result.result)
        self.assertIn("[Image 2]", result.result)
        self.assertIn("evidence for b.png", result.result)
        self.assertEqual(result.attempts[-1].status, "success")
        self.assertEqual(result.attempts[-1].reason, "multi_image_compat_fallback")

    def test_multi_image_rate_limit_does_not_fan_out_requests(self):
        from free_vision.service import analyze

        provider = BatchRejectingProvider(batch_status=429)
        with self.assertRaises(VisionError) as ctx:
            analyze(
                ["a.png", "b.png"],
                "compare the screenshots",
                config_loader=lambda: type("C", (), {"api_key": "secret"})(),
                discovery=lambda refresh=False: [CANDIDATES[0]],
                resolver=lambda source: MediaInput(source, "image/png", b"x"),
                provider_factory=lambda key: provider,
            )

        self.assertEqual(ctx.exception.code, "all_models_failed")
        self.assertEqual([call[1] for call in provider.calls], [["a.png", "b.png"]])


if __name__ == "__main__":
    unittest.main()
