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


if __name__ == "__main__":
    unittest.main()
