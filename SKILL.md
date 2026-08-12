---
name: free-vision
description: Use when an agent needs to inspect, understand, read, analyze, compare, or answer questions about images available as local file paths or HTTP/HTTPS URLs, or when the user wants to set up, change, check, repair, or clear Free Vision configuration. Handles screenshots, UI states and errors, scanned text, diagrams, charts, photos, multiple images, and conversational OpenCode API-key lifecycle management.
---

# Free Vision

Free Vision is a visual evidence tool for Agents. The vision model should **see**; the main Agent should still **reason and answer**.

Resolve the **Skill directory** from this `SKILL.md`. Never assume the current working directory is the Skill directory. Keep the user's working directory unchanged so relative image paths keep their original meaning.

## Visual tasks

Use this Skill whenever the user's task depends on image contents and an image is available as:

- a local path, including Windows drive paths; or
- an `http://` / `https://` image URL.

Invoke:

```text
python <SKILL_DIR>/scripts/vision.py IMAGE [IMAGE ...] --task "USER VISUAL TASK"
```

Use the user's actual visual question as `--task`; do not replace a specific request with a generic description prompt.

On success, read JSON `result` as visual evidence, continue reasoning with the main Agent, and give a natural-language answer. Do not dump raw JSON unless requested.

## Configuration intents

Treat configuration as a permanent Free Vision capability, not only an installation step. Recognize natural-language intents such as:

- **setup** — configure Free Vision when no key exists;
- **change-key** — replace the saved OpenCode API key;
- **status** — inspect whether a key is configured and which source is active;
- **doctor** — test whether Free Vision currently works;
- **clear-key** — remove the locally saved key;
- **repair** — diagnose first, then request a new key only if configuration/authentication requires one.

Examples include “配置 Free Vision”, “换一下 Free Vision 的 key”, “检查这个视觉 Skill 能不能用”, “Free Vision 最近不能用了”, “重新配置 OpenCode Key”, and “删除 Free Vision 的 Key”.

### Status

Run:

```text
python <SKILL_DIR>/scripts/configure.py status --pretty
```

Never reveal a complete or partial API key. Report only whether a key exists and the active source.

### Doctor / repair

Run doctor **before** asking for a replacement key when the user says Free Vision is broken:

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
```

Interpret results:

- `missing_api_key` → request a key;
- `authentication_failed` → request a replacement key;
- `model_discovery_failed` → explain network/metadata discovery failure; do not blame the key;
- `no_free_vision_models` → explain that configuration may be valid but no zero-cost image model is currently eligible;
- `all_models_failed` → explain provider/model failure and retain the current key.

### Asking for an API key in conversation

When setup or change-key requires a key:

1. Tell the user that sending the key means it will enter the **current conversation context**.
2. Ask them to send the API key in the **next message by itself**.
3. Enter conceptual state `WAITING_FOR_API_KEY` (or `WAITING_FOR_NEW_API_KEY` for replacement).
4. Only while in that pending state, treat the next credential-like message as the Free Vision key.
5. Do not echo, quote, summarize, partially mask, or otherwise reproduce the key in the reply.

Outside a pending configuration state, do not interpret arbitrary credential-looking text as a Free Vision key.

### Save or change a key

After receiving the pending key, start the bundled configuration process and pass the key through **stdin**, not as a command-line argument:

```text
python <SKILL_DIR>/scripts/configure.py set --stdin --pretty
```

Provide the key to that running process through stdin using the Agent host's process-input mechanism. Do not build shell commands like `echo KEY | ...`, and do not put the key in process arguments.

The configuration command validates the candidate with a real multimodal request **before** saving it. During change-key, the old key stays untouched until the new key passes validation.

After success, tell the user that configuration, free-model discovery, authentication, and vision testing succeeded, and include the tested model id. Do not echo the key.

If candidate validation fails, tell the user the new key was not saved and the old key remains unchanged.

### Environment-key precedence

Runtime precedence is:

1. `OPENCODE_API_KEY`
2. `FREE_VISION_OPENCODE_API_KEY`
3. Free Vision local config

If `configure.py set` returns `environment_key_active`, explain that an environment variable currently overrides the local file. Do not claim the conversational replacement became active. The user must change/unset that environment variable in the host environment before a local replacement can take effect.

### Clear local key

Run:

```text
python <SKILL_DIR>/scripts/configure.py clear --pretty
```

This removes only the local Free Vision key. If an environment key remains active, explain that Free Vision is still configured through that environment source.

## First-run flow after installation

After installing Free Vision from GitHub or another source:

1. Run `doctor.py --pretty`.
2. If already healthy, tell the user it is ready; do not ask for another key.
3. If `missing_api_key`, explain the conversation-context caveat and ask for the key in the next message.
4. Receive the key only in the pending state.
5. Run `configure.py set --stdin --pretty`.
6. Report READY or the exact failure category in natural language.

## Failure references

For Windows paths, installation checks, discovery/network problems, and detailed command examples, read `references/troubleshooting.md` and `references/usage.md` relative to this Skill directory.

Do not call OpenCode or models.dev APIs directly from the Agent. Use the bundled commands so model qualification, media validation, fallback, diagnostic classification, and secret handling stay consistent.
