import io
import unittest
from pathlib import Path

from free_vision.types import MediaInput, ModelCandidate, VisionError


class TtyInput:
    def isatty(self):
        return True

    def readline(self):
        raise AssertionError("TTY --stdin must not call readline because that can echo secrets")


class ConfigureAgentInputTests(unittest.TestCase):
    def _healthy_report(self):
        return {
            "ok": True,
            "configuration": {"status": "ok", "source": "candidate"},
            "discovery": {"status": "ok", "models": 1},
            "authentication": {"status": "ok"},
            "vision": {"status": "ok", "model": "mimo-v2.5-free"},
        }

    def test_tty_stdin_uses_hidden_input_instead_of_readline(self):
        from free_vision.configure import main

        prompts = []
        out = io.StringIO()
        rc = main(
            ["set", "--stdin"],
            stdin=TtyInput(),
            stdout=out,
            inspector=lambda: type("S", (), {"has_environment_key": False})(),
            validator=lambda **kwargs: self._healthy_report(),
            saver=lambda key: Path("config.json"),
            hidden_input=lambda prompt: prompts.append(prompt) or "new-secret",
        )

        self.assertEqual(rc, 0)
        self.assertEqual(len(prompts), 1)
        self.assertNotIn("new-secret", out.getvalue())

    def test_candidate_validation_uses_one_bounded_probe(self):
        from free_vision.configure import main

        seen = {}

        def validator(**kwargs):
            seen.update(kwargs)
            return self._healthy_report()

        rc = main(
            ["set", "--stdin"],
            stdin=io.StringIO("new-secret\n"),
            stdout=io.StringIO(),
            inspector=lambda: type("S", (), {"has_environment_key": False})(),
            validator=validator,
            saver=lambda key: Path("config.json"),
        )

        self.assertEqual(rc, 0)
        self.assertEqual(seen["max_candidates"], 1)
        self.assertEqual(seen["probe_timeout"], 45)


class DoctorBoundedProbeTests(unittest.TestCase):
    def test_doctor_limits_candidate_probe_count(self):
        from free_vision.doctor import run_doctor

        candidates = [
            ModelCandidate("first-free", "first", 0, 0, None, "opencode"),
            ModelCandidate("second-free", "second", 0, 0, None, "opencode"),
        ]
        calls = []

        class Provider:
            def analyze(self, model, media, task):
                calls.append(model)
                raise VisionError("provider_request_failed", "failed", status=500)

        report = run_doctor(
            api_key="secret",
            discovery=lambda **kwargs: candidates,
            provider_factory=lambda key: Provider(),
            max_candidates=1,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(calls, ["first-free"])
        self.assertEqual(len(report["vision"]["attempts"]), 1)

    def test_doctor_passes_probe_timeout_when_requested(self):
        from free_vision.doctor import run_doctor

        seen = {}

        class Provider:
            def analyze(self, model, media, task, *, timeout=120):
                seen["timeout"] = timeout
                return "VISION_OK"

        report = run_doctor(
            api_key="secret",
            discovery=lambda **kwargs: [ModelCandidate("mimo-v2.5-free", "mimo", 0, 0, None, "opencode")],
            provider_factory=lambda key: Provider(),
            probe_timeout=45,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(seen["timeout"], 45)


class ProviderTimeoutTests(unittest.TestCase):
    def test_provider_forwards_custom_timeout(self):
        from free_vision.provider import OpenCodeProvider

        seen = {}

        def post_json(url, payload, *, headers, timeout):
            seen["timeout"] = timeout
            return {"choices": [{"message": {"content": "ok"}}]}

        provider = OpenCodeProvider("secret", post_json=post_json)
        provider.analyze(
            "mimo-v2.5-free",
            [MediaInput("x", "image/png", b"x")],
            "task",
            timeout=45,
        )
        self.assertEqual(seen["timeout"], 45)


class AgentSecretInputContractTests(unittest.TestCase):
    def test_skill_uses_hidden_input_for_pty_hosts(self):
        text = Path("SKILL.md").read_text(encoding="utf-8")
        self.assertIn("PTY", text)
        self.assertIn("configure.py set --pretty", text)
        self.assertIn("hidden", text.lower())
        self.assertIn("do not use an echoing pty", text.lower())


if __name__ == "__main__":
    unittest.main()
