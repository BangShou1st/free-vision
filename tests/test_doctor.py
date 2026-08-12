import unittest

from free_vision.types import Config, ModelCandidate, VisionError


CANDIDATES = [ModelCandidate("mimo-v2.5-free", "MiMo", 0, 0, provider_id="opencode")]


class FakeProvider:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []

    def analyze(self, model, media, task):
        self.calls.append((model, media, task))
        if isinstance(self.behavior, Exception):
            raise self.behavior
        return self.behavior


class DoctorTests(unittest.TestCase):
    def test_success_reports_all_stages_and_model(self):
        from free_vision.doctor import run_doctor

        provider = FakeProvider("VISION_OK")
        report = run_doctor(
            config_loader=lambda: (Config("secret"), "file"),
            discovery=lambda refresh=False: CANDIDATES,
            provider_factory=lambda key: provider,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["configuration"], {"status": "ok", "source": "file"})
        self.assertEqual(report["discovery"]["status"], "ok")
        self.assertEqual(report["authentication"]["status"], "ok")
        self.assertEqual(report["vision"]["status"], "ok")
        self.assertEqual(report["vision"]["model"], "mimo-v2.5-free")
        self.assertNotIn("secret", repr(report))
        self.assertEqual(provider.calls[0][1][0].mime_type, "image/png")

    def test_missing_key_stops_before_discovery(self):
        from free_vision.doctor import run_doctor

        called = []

        def missing():
            raise VisionError("missing_api_key", "missing")

        report = run_doctor(config_loader=missing, discovery=lambda refresh=False: called.append(True))

        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "missing_api_key")
        self.assertEqual(report["configuration"]["status"], "failed")
        self.assertEqual(report["discovery"]["status"], "skipped")
        self.assertFalse(called)

    def test_authentication_failure_is_not_mislabeled_as_network(self):
        from free_vision.doctor import run_doctor

        provider = FakeProvider(VisionError("provider_request_failed", "no", status=401))
        report = run_doctor(
            config_loader=lambda: (Config("bad-secret"), "file"),
            discovery=lambda refresh=False: CANDIDATES,
            provider_factory=lambda key: provider,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "authentication_failed")
        self.assertEqual(report["authentication"]["status"], "failed")
        self.assertEqual(report["vision"]["status"], "failed")
        self.assertNotIn("bad-secret", repr(report))

    def test_discovery_failure_keeps_authentication_unknown(self):
        from free_vision.doctor import run_doctor

        def fail(refresh=False):
            raise VisionError("model_discovery_failed", "network")

        report = run_doctor(
            config_loader=lambda: (Config("secret"), "file"),
            discovery=fail,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "model_discovery_failed")
        self.assertEqual(report["discovery"]["status"], "failed")
        self.assertEqual(report["authentication"]["status"], "unknown")
        self.assertEqual(report["vision"]["status"], "skipped")

    def test_no_free_models_is_preserved(self):
        from free_vision.doctor import run_doctor

        def fail(refresh=False):
            raise VisionError("no_free_vision_models", "none")

        report = run_doctor(
            config_loader=lambda: (Config("secret"), "file"),
            discovery=fail,
        )
        self.assertEqual(report["error"]["code"], "no_free_vision_models")

    def test_candidate_key_validation_does_not_read_active_config(self):
        from free_vision.doctor import run_doctor

        keys = []
        report = run_doctor(
            api_key="candidate-secret",
            source="candidate",
            config_loader=lambda: (_ for _ in ()).throw(AssertionError("must not load active config")),
            discovery=lambda refresh=False: CANDIDATES,
            provider_factory=lambda key: keys.append(key) or FakeProvider("VISION_OK"),
        )

        self.assertTrue(report["ok"])
        self.assertEqual(keys, ["candidate-secret"])
        self.assertEqual(report["configuration"]["source"], "candidate")
        self.assertNotIn("candidate-secret", repr(report))


if __name__ == "__main__":
    unittest.main()
