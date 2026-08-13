# Free Vision v0.3.5 Stability Hardening Design

Date: 2026-08-13

## Goal

Close the remaining host-boundary problems observed in real Claude and Hermes acceptance runs without adding host-specific branches or changing provider/model discovery behavior.

The release should make installation testing deterministic, machine-readable output encoding-independent, and secret-handling guidance unambiguous.

## Confirmed problems

### 1. JSON output is still host-encoding dependent

v0.3.4 tries to emit Unicode directly when the current stdout encoding can represent the characters, and only falls back to `ensure_ascii=True` when encoding would fail.

That does not solve the Claude case: Chinese text is valid cp936, so Python writes cp936 bytes successfully, while the host tool may decode those bytes as UTF-8. The result is mojibake rather than `UnicodeEncodeError`.

The root issue is therefore not "characters that cp936 cannot encode". It is that machine-readable JSON currently depends on both producer and consumer agreeing on terminal encoding.

### 2. Installation self-test is not deterministic

Claude created a Playwright screenshot to test Free Vision end-to-end. This introduces unnecessary browser/network/tool dependencies and temporary-file cleanup into a Skill that should test itself.

Free Vision already has a tiny embedded doctor probe, but it is not a visible reusable runtime asset and there is no dedicated end-to-end self-test command for Agents.

### 3. Secret transport wording still admits a false-positive interpretation

Claude treated this as a "secure stdin pipe":

`python -c "key='...'; subprocess.run(..., input=key, ...)"`

The child process does receive a pipe, but the secret is still serialized into a shell/tool-visible source command. This violates the intended security model even though the final child transport is stdin.

The Skill must distinguish "a secure host-provided secret-to-process channel" from "a pipe manufactured by embedding the secret in shell-visible code".

## Design

### A. Encoding-independent JSON contract

All machine-readable JSON produced by Free Vision CLI surfaces will use ASCII-safe JSON serialization unconditionally:

- `ensure_ascii=True`
- pretty-printing behavior remains unchanged
- JSON schema and semantic values remain unchanged

This applies to:

- `vision.py`
- `doctor.py`
- `configure.py`

The main Agent parses JSON normally and receives the original Unicode strings after decoding JSON escapes. Users normally see the Agent's natural-language answer, so human readability of raw internal JSON is not a product requirement.

This deliberately removes stdout encoding detection from `free_vision/output.py`.

### B. Built-in reusable test image

Add one deterministic PNG runtime asset at:

`free_vision/assets/selftest.png`

The image should be large enough for OpenCode Zen, high contrast, and contain simple stable visual content suitable for a general description task. The self-test must not require OCR exact-match assertions; success is defined as a real multimodal request completing with non-empty model output.

Because the installer already recursively copies `free_vision/`, the binary asset will automatically be included in installed runtime payloads.

### C. Dedicated self-test command

Add:

`python <SKILL_DIR>/scripts/selftest.py --pretty`

The command will:

1. use the existing configured key and model discovery;
2. analyze the bundled `free_vision/assets/selftest.png`;
3. use normal Free Vision service/provider behavior and fallback;
4. return machine-readable JSON containing provider, model, result, media/test marker, and attempts;
5. never create or delete temporary screenshots.

A self-test is an end-to-end product check, not a replacement for `doctor` diagnostics. `doctor` remains the structured configuration/auth/discovery probe.

### D. Reuse the same image in doctor

Replace the separate base64 doctor image constant with the bundled self-test PNG bytes. Doctor keeps its current task (`VISION_OK`) and current setup timeout/candidate controls.

This removes duplicated image fixtures and guarantees the same validated image dimensions are used by both diagnostics and the visible end-to-end self-test.

### E. Installation/Agent flow

After installation:

1. run doctor;
2. if already configured and healthy, run bundled self-test;
3. if key is missing, configure using only a genuinely secure host-provided input path;
4. run doctor again if needed;
5. run bundled self-test;
6. report READY.

Agents must not generate a browser screenshot, create a temporary image, or depend on Playwright for Free Vision acceptance unless the user explicitly asks to test a specific real page/image.

### F. Secret transport contract

Clarify in `SKILL.md` and README:

A secure conversational setup channel means the host itself can deliver the already-received secret to the child process without serializing the secret into:

- shell command text;
- `python -c` / PowerShell / Bash source;
- command-line arguments;
- temporary files;
- temporary scripts;
- tool-visible environment assignment commands;
- logs.

Specifically, `python -c "key='...'; subprocess.run(..., input=key)"` is NOT an acceptable secure stdin path.

If no true hidden/secure process-input path exists, the Agent must not ask the user to paste a new key for automated setup. It should instruct the user to run:

`python <SKILL_DIR>/scripts/configure.py set --pretty`

and then continue doctor/self-test after the user completes that local hidden prompt.

The existing regular-file stdin rejection remains in place.

## Out of scope

- host-specific Claude/Hermes code paths;
- changes to OpenCode Zen provider logic, UA behavior, discovery, cache policy, or model selection;
- GUI configuration;
- clipboard-based key handling;
- local OCR or local vision models;
- exact OCR assertions against the self-test image.

## Testing

TDD coverage must include:

1. JSON output is ASCII-only for Chinese, `¥`, and emoji while `json.loads` reconstructs the original values.
2. `vision`, `doctor`, and `configure` all use the same output contract.
3. bundled self-test asset exists, has a supported PNG signature, and is included by installer payload enumeration.
4. doctor loads the bundled asset rather than a separate embedded base64 fixture.
5. self-test command performs an end-to-end analysis using the bundled asset and returns normal Free Vision result structure.
6. Skill documentation explicitly rejects `python -c`/shell-visible secret serialization even when the child receives stdin.
7. install/first-run documentation instructs Agents to use the bundled self-test instead of creating temporary screenshots.
8. full existing suite remains green; compileall, shell syntax, and diff checks pass.

## Acceptance criteria

A fresh Claude/Hermes-style installation should require no browser-generated test image and no `PYTHONIOENCODING` workaround.

Expected product flow:

`install -> doctor -> configure if needed -> bundled selftest -> READY`

For a real user image afterward:

`image present -> native vision if available, otherwise Free Vision -> main Agent natural-language answer`
