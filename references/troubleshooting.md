# Free Vision Troubleshooting

## Skill is not discovered by the Agent

Verify that the installed directory contains:

```text
<skills-root>/free-vision/SKILL.md
```

Restart or refresh the Agent client after installing. If the client does not scan the chosen shared directory, use its native Skill installer or client-specific Skill root.

## `missing_api_key`

Preferred Agent flow:

1. Explain that sending a key puts it in the current conversation context.
2. Ask the user to send the key in the next message by itself.
3. Enter `WAITING_FOR_API_KEY`.
4. Run `scripts/configure.py set --stdin --pretty` and feed the key through process stdin.
5. Never echo the key.

Manual private-terminal alternative:

```text
python <SKILL_DIR>/scripts/configure.py set
```

## `authentication_failed`

The current or candidate key was rejected with HTTP 401/403. For a change-key attempt, the candidate was not saved and the previous local key remains unchanged.

Ask for a new key only after explaining the conversation-context caveat.

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

Doctor stages are configuration, discovery, authentication, and a real vision probe. Discovery/network/no-free-model failures are intentionally kept separate from credential failures.

## Clear the local key

```text
python <SKILL_DIR>/scripts/configure.py clear --pretty
```

This does not alter environment variables. If one remains active, the returned status still reports Free Vision as configured.

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
```
