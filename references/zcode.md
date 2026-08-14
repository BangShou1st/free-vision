# Free Vision for ZCode

ZCode may attach an uploaded image to the primary provider request before a text-only main model can invoke an Agent Skill. Free Vision therefore uses an optional **provider-boundary loopback gateway** for ZCode rather than relying on hooks.

## Install and first setup

Install to ZCode's Skill directory, then run:

```text
python scripts/install.py --target zcode --force
python <SKILL_DIR>/scripts/zcode.py setup
python <SKILL_DIR>/scripts/zcode.py status
```

Do not declare drag-image fallback READY until `status` reports:

```text
running: true
zcode_connected: true
gateway_current: true
```

If an older Free Vision gateway is already running, `setup` replaces it when its `/health` version does not match the installed Skill. This prevents a v0.3.6 background process from surviving a v0.3.7 file update.

## Console / UUID providers with no Base URL

Some ZCode account/Console providers have a UUID but no editable `baseURL`. When Free Vision can identify the current provider and model safely, v0.3.7 creates a **managed overlay on the same provider id** instead of asking the user to rewrite an unavailable Base URL.

The overlay keeps the provider id stable, sets it to OpenAI-compatible Chat Completions, points it at the local gateway, and writes only a harmless placeholder API key (`free-vision-local`) into ZCode. The real OpenCode API key stays in Free Vision's own configuration and is injected by the gateway only when forwarding to `opencode.ai`.

The credential-free managed overlay is intentionally conservative: it requires an identified OpenCode model whose id ends in `-free`. It will not silently reroute an unknown or non-free model through OpenCode.

If automatic detection cannot identify the active provider/model, `setup` returns `manual_action_required: true`. If the ZCode runtime or current provider error already exposes the exact values, the Agent should rerun setup itself:

```text
python <SKILL_DIR>/scripts/zcode.py setup --provider-id <exact provider UUID> --model <exact model id>
```

Use only exact runtime facts. **Do not guess** either value, and do not ask the user to edit provider JSON by hand when the runtime facts are already available. Provider UUIDs and model ids are routing metadata, not API secrets.

## Native multimodal precedence

For an image request from an unknown model, the gateway first forwards the request unchanged. If the model supports images, native multimodal behavior is preserved.

Only when the upstream explicitly rejects the request as text-only (for example `Model only supports text input` with unsupported `image_url`) does the gateway call Free Vision, replace image blocks with textual visual evidence, and retry once. Other provider errors pass through unchanged. A model that explicitly rejects images is remembered as text-only for the lifetime of that gateway process.

## Windows startup

v0.3.7 does not require an elevated `schtasks /SC ONLOGON` task. It uses the current user's Windows **Startup** folder and writes a small launcher containing only the Python command and Free Vision state-file path; it contains no API key.

If Startup registration fails, the current successful gateway/provider setup remains valid. `setup` returns the failure as a warning instead of rolling back the working gateway. The user can still run `scripts/zcode.py start` after login.

## Lifecycle and rollback

```text
python <SKILL_DIR>/scripts/zcode.py status
python <SKILL_DIR>/scripts/zcode.py start
python <SKILL_DIR>/scripts/zcode.py stop
python <SKILL_DIR>/scripts/zcode.py remove
```

`status` exposes the running gateway version and `gateway_current` so an outdated background process is visible.

For managed overlays, Free Vision stores only the non-secret field state needed to undo its own changes. `remove` restores the original provider/cache shape exactly when those values are still managed by Free Vision, removes the Startup launcher, stops the gateway, and deletes the Free Vision ZCode state. It does not copy an existing ZCode credential into Free Vision state and will refuse to overlay a provider that already contains credential-like fields.

After a successful setup, refresh or restart ZCode before the first drag-image acceptance test so the host reloads its provider/model routing.
