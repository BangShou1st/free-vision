# Free Vision for ZCode

ZCode can attach an uploaded image to the primary provider request before a text-only main model has a chance to invoke an Agent Skill. If the upstream rejects the turn with an error such as `Model only supports text input` and unsupported `image_url`, Free Vision can handle the fallback at the provider boundary.

## Install

Prefer the native ZCode Skill target:

```text
python scripts/install.py --target zcode --force
```

After normal Free Vision configuration, doctor, and bundled self-test, run from the installed Skill:

```text
python <SKILL_DIR>/scripts/zcode.py setup
python <SKILL_DIR>/scripts/zcode.py status
```

Do not report ZCode drag-image fallback as ready until status reports both `running: true` and `zcode_connected: true`.

## What setup changes

The adapter uses `~/.zcode/v2/config.json` and, when present, `~/.zcode/v2/bots-model-cache.v2.json` to identify the current or only unambiguous enabled OpenAI-compatible provider. It changes only the managed provider Base URL to the local loopback gateway. Existing API keys, model ids, modalities, and unrelated settings remain unchanged. Free Vision stores only provider identifiers and original Base URLs needed for status and removal; it does not copy the ZCode provider secret.

If provider detection is ambiguous, setup returns `manual_action_required: true` and does not guess. In that case connect the intended OpenAI-compatible Chat Completions provider to the reported `gateway_base_url`, keeping its existing API key and model unchanged.

## Adaptive native-vision precedence

The gateway does not assume every selected model is text-only. For an image request from an unknown model it first forwards the original request unchanged. If the model supports images, its native multimodal behavior is preserved.

Only when the upstream explicitly rejects the image as text-only — for example `Model only supports text input` plus unsupported `image_url` — does the gateway call Free Vision, replace image blocks with textual visual evidence, and retry once. Unrelated provider errors are passed through unchanged. A model that explicitly rejects images is remembered as text-only for the lifetime of the gateway process so later image turns can go directly through the fallback.

The gateway does not rely on ZCode hooks and listens only on loopback. On Windows, setup registers a current-user login task unless `--no-autostart` is used.

## Lifecycle

```text
python <SKILL_DIR>/scripts/zcode.py status
python <SKILL_DIR>/scripts/zcode.py start
python <SKILL_DIR>/scripts/zcode.py stop
python <SKILL_DIR>/scripts/zcode.py remove
```

`remove` stops the managed gateway, removes managed Windows autostart, and restores the original provider/cache Base URLs only if those values are still pointing at the managed gateway. A newer user change is never overwritten.

If setup/status is successful but the current ZCode session still uses its old route, refresh or reopen ZCode and retest rather than patching Free Vision source.
