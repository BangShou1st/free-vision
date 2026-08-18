# Tool-Generated Screenshot Fallback Design

## Goal

Make Free Vision automatically usable when the current task produces a tool-generated screenshot path even if the tool returns little or no textual/structured content. The motivating case is a browser result such as `(no output)` plus `Browser screenshot saved to: C:\...\result.png` and empty `Structured content`.

## Behavior

1. Treat accessible image paths exposed by relevant tool results in the current task as image activation signals, not only images mentioned in the user's message.
2. Browser, Playwright, screenshot, automation, and similar tool artifacts qualify when they expose a local `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp` path or another image URL/path already supported by the media resolver.
3. If textual/structured extraction is empty or insufficient but a screenshot exists, do not stop at `(no output)` or conclude that the page has no content. Invoke Free Vision on the screenshot.
4. Preserve the user's original task as `--task`; do not replace it with a generic `describe this image` request. Add only minimal context that the image is a tool-generated screenshot when useful.
5. If multiple relevant screenshot paths are exposed, pass all of them to Free Vision in their task order so the existing multi-image flow can compare them.
6. Native-vision precedence remains unchanged: if the host/model can already inspect the screenshot directly, Free Vision should not duplicate that work.

## Scope

This is primarily an Agent Skill behavior change in `SKILL.md` plus human-facing documentation and regression contracts. No host-specific browser parser, filesystem watcher, or background interception service is added. Existing Free Vision media resolution, provider routing, ZCode gateway behavior, secret handling, and installer mechanics stay unchanged.

## Versioning

Release version becomes `0.3.11`. `free_vision.__version__` and `source.json.version` must match.

## Verification

Regression tests must assert that `SKILL.md` explicitly covers current-task tool results, tool-generated screenshot paths, empty/no-output browser results, preservation of the original user task, and multiple screenshots. Existing source metadata/version contracts must remain valid after the version bump.