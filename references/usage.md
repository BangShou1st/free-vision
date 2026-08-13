# Free Vision Usage Reference

## Preserve the user's working directory

Invoke `scripts/vision.py` by its absolute path inside the installed Skill, but keep the agent's original working directory. This lets relative image paths continue to refer to the user's project rather than to the Skill installation directory.

## Task shaping

Pass the user's real visual objective to `--task`.

Good:

```text
--task "Find the error message, the failing field, and any visible status indicators."
```

Avoid turning every request into a generic description. A targeted task usually produces less irrelevant output and better evidence for the main agent.

## Local paths

Windows PowerShell/CMD:

```text
python <SKILL_DIR>/scripts/vision.py "C:\Users\me\Desktop\test.png" --task "Describe the page and extract product names and prices."
```

macOS/Linux:

```text
python <SKILL_DIR>/scripts/vision.py /tmp/test.png --task "Read the terminal error and surrounding context."
```

Relative path from the user's current project:

```text
python <SKILL_DIR>/scripts/vision.py ./artifacts/screenshot.png --task "Explain the visible regression."
```

## HTTP/HTTPS URLs

```text
python <SKILL_DIR>/scripts/vision.py "https://example.com/image.png" --task "Describe the diagram and extract its labels."
```

The CLI downloads and validates the image before inference, so the upstream model does not need to fetch the URL itself.

## Multiple images

```text
python <SKILL_DIR>/scripts/vision.py before.png after.png --task "Compare layout, text, and button state between these screenshots."
```

All images are sent in one multimodal request so the vision model can compare them directly.

## Model inspection

List currently eligible zero-cost vision models:

```text
python <SKILL_DIR>/scripts/vision.py --list-models --pretty
```

Force a fresh discovery lookup:

```text
python <SKILL_DIR>/scripts/vision.py --list-models --refresh-models --pretty
```

## Built-in installation self-test

After installation and configuration, use the bundled deterministic test image:

```text
python <SKILL_DIR>/scripts/selftest.py --pretty
```

This is the normal end-to-end acceptance test. Do not create a Playwright/browser screenshot or another temporary image merely to test whether Free Vision works. The bundled self-test uses the normal image-analysis service, current free-model discovery, provider, fallback, and machine JSON output.

## Consuming JSON

Free Vision's machine-readable CLI output is ASCII-safe JSON. Unicode text is represented with standard JSON escapes when necessary; after `json.loads`, the semantic value is the original Unicode text.

Success fields:

- `ok`: `true`
- `provider`: provider identifier
- `model`: model actually used
- `result`: visual evidence text
- `media`: input sources
- `attempts`: safe fallback history

Use `result` as evidence, then answer naturally. Do not expose the full JSON unless requested.

## Conversational configuration lifecycle

Free Vision configuration is meant to be triggered by natural language, but only when the host has a genuinely secure secret-to-process channel.

### First setup

The Agent runs:

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
```

If the result is `missing_api_key`, first determine whether the host can deliver the secret to the child process without serializing the key into command/source text, argv, temporary files/scripts, logs, or tool-visible environment assignments.

If a true secure non-TTY pipe exists, conversational setup may use:

```text
python <SKILL_DIR>/scripts/configure.py set --stdin --pretty
```

If the host has a hidden PTY/process-input channel, run:

```text
python <SKILL_DIR>/scripts/configure.py set --pretty
```

and feed the pending key through that hidden channel.

`python -c "key=...; subprocess.run(..., input=key)"` is **not a secure stdin** workaround. Although the child receives stdin, the key has already been serialized into shell/tool-visible Python source. The same rule applies to PowerShell or Bash source strings.

If the host has no secure hidden channel, do not ask the user to paste a key for automated setup. Ask the user to run locally:

```text
python <SKILL_DIR>/scripts/configure.py set --pretty
```

Then continue with:

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
python <SKILL_DIR>/scripts/selftest.py --pretty
```

Do not put a key in a command argument, construct `echo KEY | ...`, write a temporary key file, or create a temporary script containing the key.

### Change key

For requests like “换一下 Free Vision 的 key”, apply the same secure-channel check first. Candidate validation happens before persistence, so a failed candidate does not replace the old local key.

### Status

```text
python <SKILL_DIR>/scripts/configure.py status --pretty
```

Use `active_source`, `has_environment_key`, and `has_local_key` to explain configuration without revealing secret material.

### Clear

```text
python <SKILL_DIR>/scripts/configure.py clear --pretty
```

If `active_source` still points to `env:...`, tell the user that an environment key remains active.

### Repair

Run doctor first. Request a key only for `missing_api_key` or `authentication_failed`, and only after confirming a secure secret channel exists. Keep existing configuration for discovery, no-free-model, network, rate-limit, and other provider failures. Do not patch installed Free Vision source during normal repair.
