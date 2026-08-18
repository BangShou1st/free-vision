# Tool-Generated Screenshot Fallback Design

## Goal

Make Free Vision automatically continue a task when a browser/automation tool produces a screenshot path even if textual or structured extraction is empty. The motivating case is `(no output)` plus `Browser screenshot saved to: C:\...\result.png` and empty `Structured content`.

## Behavior

1. Treat accessible image paths exposed by relevant tool results in the current task as image activation signals, not only images mentioned in the user's message.
2. If textual/structured extraction is empty or insufficient but a screenshot exists, do not stop at `(no output)` or conclude that the page has no content.
3. Preserve the user's original task; do not replace it with a generic `describe this image` prompt.
4. If multiple relevant screenshot paths are exposed, preserve their tool-result order and use the existing multi-image analysis flow.
5. Native-vision precedence remains unchanged for Agent-driven use.

## ZCode provider-boundary fallback

The ZCode gateway must handle this path even when the host does not re-select the Free Vision Skill after a tool call. Before forwarding a chat-completions request, it scans tool-result messages for fixed `Browser screenshot saved to:` / `Screenshot saved to:` lines, analyzes trusted screenshot artifacts, and appends `[Free Vision visual evidence]` to the tool result.

The visual task is based on the latest preceding user message so the original requested outcome remains primary.

## Local-file safety boundary

Tool output is not sufficient authority to read an arbitrary local path. Automatic gateway reading is allowed only when all conditions are true:

- the message is a tool result (`role == tool` or has `tool_call_id`);
- the path comes from a fixed screenshot-saved line;
- the path is absolute and resolves to a real file;
- the resolved file stays inside the current user's `~/.zcode/cli/artifacts/` tree, including after symlink resolution;
- the suffix is `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`.

Ordinary user text containing the same phrase and paths outside that tree must not trigger local-file reading.

## Components

- `free_vision/gateway_transform.py`: extract trusted screenshot artifacts, derive the latest user task, call the existing analyzer/cache, and append evidence.
- `free_vision/gateway_handler_request.py`: run tool-screenshot transformation before normal image-url adaptive fallback and forward the transformed payload.
- `free_vision/gateway_handler.py`: allow an artifact root to be injected for deterministic tests; production defaults to the current user's ZCode artifact tree.
- `SKILL.md`: describe Agent-level tool-result activation and the ZCode safety-scoped automatic path.
- `README.md` / `CHANGELOG.md`: document the behavior and release.

No filesystem watcher, background browser parser, arbitrary file interceptor, or new dependency is introduced. Existing provider routing, secret handling, media limits, and installer replacement behavior remain unchanged.

## Versioning

Release version becomes `0.3.11`. `free_vision.__version__` and `source.json.version` must match.

## Verification

Regression coverage must include trusted artifact transformation, latest-user-task preservation, multiple screenshot order, user-message non-triggering, outside-artifact-root rejection, gateway forwarding without an `image_url`, Skill/documentation contracts, and forward-compatible source-version metadata.