import io
import json
import unittest

from free_vision.types import Attempt, ModelCandidate, VisionError, VisionResult


class CliTests(unittest.TestCase):
    def test_list_models_emits_json_without_api_key(self):
        from free_vision.cli import main

        out = io.StringIO()
        code = main(
            ["--list-models"],
            discovery=lambda refresh=False: [ModelCandidate("mimo-v2.5-free", "MiMo V2.5 Free", 0, 0)],
            stdout=out,
        )
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["models"][0]["id"], "mimo-v2.5-free")

    def test_analysis_emits_success_json(self):
        from free_vision.cli import main

        out = io.StringIO()
        result = VisionResult("opencode", "mimo-v2.5-free", "error dialog", ["shot.png"], [Attempt("mimo-v2.5-free", "success")])
        calls = []

        def analyzer(images, task, *, model=None, refresh_models=False):
            calls.append((images, task, model, refresh_models))
            return result

        code = main(["shot.png", "--task", "read it"], analyzer=analyzer, stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["result"], "error dialog")
        self.assertEqual(calls[0], (["shot.png"], "read it", None, False))

    def test_runtime_error_emits_error_json(self):
        from free_vision.cli import main

        out = io.StringIO()

        def analyzer(*args, **kwargs):
            raise VisionError("missing_api_key", "configure key")

        code = main(["shot.png"], analyzer=analyzer, stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "missing_api_key")

    def test_missing_media_is_usage_error_json(self):
        from free_vision.cli import main

        out = io.StringIO()
        code = main([], stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"]["code"], "usage_error")

    def test_refresh_flag_reaches_discovery(self):
        from free_vision.cli import main

        out = io.StringIO()
        seen = []

        def discovery(refresh=False):
            seen.append(refresh)
            return [ModelCandidate("m", "M", 0, 0)]

        code = main(["--list-models", "--refresh-models"], discovery=discovery, stdout=out)
        self.assertEqual(code, 0)
        self.assertEqual(seen, [True])


if __name__ == "__main__":
    unittest.main()
