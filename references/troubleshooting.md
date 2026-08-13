# Free Vision Troubleshooting

## Skill is not discovered by the Agent

Verify that the installed directory contains:

```text
<skills-root>/free-vision/SKILL.md
```

Restart or refresh the Agent client after installing. If the client does not scan the chosen shared directory, use its native Skill installer or client-specific Skill root.

## `missing_api_key`

First determine whether the host has a genuinely secure secret-to-process channel.

If the host can deliver the secret through a non-TTY stdin pipe or hidden PTY/process-input channel without exposing the key in shell/tool-visible source, conversational setup is allowed. Never echo the key.

If the host has **no secure hidden channel**, do not ask the user to paste a key and then invent a transport. In particular, this is **not a secure stdin** workaround:

```text
python -c "key=...; subprocess.run(..., input=key)"
```

The child receives stdin, but the secret is already present in shell/tool-visible Python source. Do not use temporary key files, temporary scripts, argv, `echo KEY | ...`, or tool-visible environment assignment commands either.

Use the local hidden prompt instead:

```text
python <SKILL_DIR>/scripts/configure.py set --pretty
```

After configuration, verify with:

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
python <SKILL_DIR>/scripts/selftest.py --pretty
```

## `authentication_failed`

The current or candidate key was rejected with HTTP 401/403. For a change-key attempt, the candidate was not saved and the previous local key remains unchanged.

Request a new key only after confirming that the host has a secure secret-input channel. Otherwise use the local hidden prompt above.

## `environment_key_active`

An environment variable (`OPENCODE_API_KEY` or `FREE_VISION_OPENCODE_API_KEY`) currently wins over the local config file. Free Vision intentionally refuses to pretend that saving a different local key would change the active credential.

The environment variable must be changed or unset in the host environment before a conversational local replacement can become active.

## Check configuration without revealing a key

```text
python <SKILL_DIR>/scripts/configure.py status --pretty
```

This reports configuration presence and active source only.

## Run full diagnosis

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
```

Doctor stages are configuration, discovery, authentication, and a real vision probe using the same bundled PNG asset as the self-test. Discovery/network/no-free-model failures are intentionally kept separate from credential failures.

## Run deterministic end-to-end self-test

```text
python <SKILL_DIR>/scripts/selftest.py --pretty
```

This uses Free Vision's bundled test image. For ordinary installation verification, do not create a Playwright/browser screenshot or another temporary image just to test the Skill.

## Clear the local key

```text
python <SKILL_DIR>/scripts/configure.py clear --pretty
```

This does not alter environment variables. If one remains active, the returned status still reports Free Vision as configured.

## Windows / terminal output looks garbled

Current builds emit machine-readable JSON using ASCII-safe JSON escapes, so the raw JSON no longer depends on the console using GBK, cp936, or UTF-8. Do not add `PYTHONIOENCODING=utf-8` as a normal Free Vision workaround. Parse the JSON normally; escaped Unicode values decode back to the original text.

If an older installation still needs an encoding environment workaround, update/reinstall Free Vision first.

## Windows path is rejected as a URL

Current builds recognize both:

```text
C:\Users\me\Desktop\test.png
C:/Users/me/Desktop/test.png
```

If an older installation reports `unsupported_url_scheme`, reinstall the latest build.

## `model_discovery_failed`

The machine running the Skill must reach OpenCode Zen and models.dev over HTTPS. Check DNS, firewall, proxy, and TLS interception. Do not assume this means the API key is invalid.

## `no_free_vision_models`

Free model availability changes. Configuration may be perfectly valid even when no current zero-cost image model qualifies. Retry later.

## `all_models_failed`

Eligible models were found but the live vision probe failed. Keep the existing key unless doctor specifically reports `authentication_failed`.

## Verify an installation manually

From a directory other than the Skill directory:

```text
python <SKILL_DIR>/scripts/vision.py --help
python <SKILL_DIR>/scripts/configure.py status --pretty
python <SKILL_DIR>/scripts/doctor.py --pretty
python <SKILL_DIR>/scripts/selftest.py --pretty
```
