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

## Consuming JSON

Success fields:

- `ok`: `true`
- `provider`: provider identifier
- `model`: model actually used
- `result`: visual evidence text
- `media`: input sources
- `attempts`: safe fallback history

Use `result` as evidence, then answer naturally. Do not expose the full JSON unless requested.

## Conversational configuration lifecycle

Free Vision configuration is meant to be triggered by natural language, not memorized shell commands.

### First setup

The Agent runs:

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
```

If the result is `missing_api_key`, it explains that the next key message enters the conversation context, asks the user to send the key alone, and enters `WAITING_FOR_API_KEY`.

After the next message, the Agent starts:

```text
python <SKILL_DIR>/scripts/configure.py set --stdin --pretty
```

and provides the pending key through process stdin. Do not put a key in a command argument or construct `echo KEY | ...`.

### Change key

For requests like “换一下 Free Vision 的 key”, use the same flow but conceptual state `WAITING_FOR_NEW_API_KEY`. Candidate validation happens before persistence, so a failed candidate does not replace the old local key.

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

Run doctor first. Request a key only for `missing_api_key` or `authentication_failed`. Keep existing configuration for discovery, no-free-model, network, rate-limit, and other provider failures.
