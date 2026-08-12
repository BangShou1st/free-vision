# Free Vision

**Free Vision is a portable Agent Skill that gives text-only agents image understanding through currently available zero-cost OpenCode Zen vision models.**

The main agent keeps reasoning and answering. Free Vision only turns images into visual evidence the agent can use.

## What it supports

- Local image paths on Windows, macOS, and Linux
- HTTP/HTTPS image URLs
- PNG, JPEG, GIF, and WebP
- One or multiple images in one request
- Screenshots, UI states, errors, scanned text, diagrams, charts, photos, and comparisons
- Conversational OpenCode API-key setup, replacement, status, doctor, and clear lifecycle
- Dynamic zero-cost vision-model discovery
- Automatic model fallback
- Agent-facing JSON protocol with natural-language final answers
- Python 3.10+ with no third-party runtime dependencies

Not included yet: local OCR/model inference, video/audio, OpenRouter, client drag-and-drop interception, or a model proxy.

## Install with your AI Agent (recommended)

Free Vision is designed to be distributed from a dedicated GitHub repository. The normal user experience is to give that GitHub URL directly to an Agent and ask it to install the Skill.

Example message to the Agent:

```text
Install this Agent Skill from GitHub:
https://github.com/<OWNER>/free-vision

Use your native Agent Skill installer if available. If your client has no native GitHub Skill installer, clone/download the repository and install its Free Vision Skill into your supported Skill directory. After installation, stay in this conversation and continue Free Vision setup.
```

A capable Agent should handle the filesystem/client-specific installation details. The user should not need to know the final Skill directory.

After installation, the same conversation continues into the API-key/doctor flow described below.

### Manual/local installation fallback

If an Agent cannot install GitHub Skills itself, clone or extract the repository and run:

```bash
python scripts/install.py
```

The portable default destination is:

```text
~/.agents/skills/free-vision/
```

The Agent Skills format defines the Skill payload, while host clients may use different discovery roots. The fallback installer also supports client-specific and custom destinations. Restart or refresh the Agent client after a manual installation.

### Project-local universal install

Install only for one repository/project:

```bash
python scripts/install.py --scope project
```

Destination:

```text
<current-project>/.agents/skills/free-vision/
```

Specify a different project root explicitly:

```bash
python scripts/install.py --scope project --project-dir /path/to/project
```

Windows example:

```powershell
python scripts\install.py --scope project --project-dir "E:\my-project"
```

## Client-specific compatibility targets

The Skill contents stay identical. Only the installation directory changes.

### OpenCode native directory

User-wide:

```bash
python scripts/install.py --target opencode
```

Project-local:

```bash
python scripts/install.py --target opencode --scope project
```

These resolve to OpenCode's native `skills` directories. OpenCode also scans the default `.agents/skills` locations, so this target is optional.

### Claude Code / Claude Agent SDK

User-wide:

```bash
python scripts/install.py --target claude
```

Project-local:

```bash
python scripts/install.py --target claude --scope project
```

These resolve to `~/.claude/skills/free-vision` or `<project>/.claude/skills/free-vision`.

### Custom Agent or custom skills root

If another Agent uses a different Skill directory:

```bash
python scripts/install.py --dest /path/to/that/agents/skills
```

The installer appends `free-vision` automatically. If the destination already ends in `free-vision`, it uses it directly.

Example:

```powershell
python scripts\install.py --dest "D:\AgentX\skills"
```

## Safe replacement and preview

Preview without writing anything:

```bash
python scripts/install.py --dry-run
```

Existing installations are never overwritten silently. Replace intentionally with:

```bash
python scripts/install.py --force
```

The installer stages a complete copy before replacing an existing Skill and copies real files rather than creating symlinks.

## Conversational setup and key management

The preferred experience is Agent-native. After installing Free Vision from GitHub, keep using the same conversation.

Ask the Agent to verify the installation or simply use Free Vision. The Skill instructs the Agent to run:

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
```

If a working key is already active, the Agent should tell you Free Vision is ready and should not ask for another key.

If no key exists, the Agent should explain that sending a key puts it into the current conversation context, then ask you to send the OpenCode API key in the **next message by itself**. The Agent then passes that key to:

```text
python <SKILL_DIR>/scripts/configure.py set --stdin --pretty
```

The key is sent to the process through stdin, never as a command-line argument. The command performs a real multimodal validation before saving it and never prints the key back.

A successful setup verifies configuration, current free-model discovery, authentication, and a live vision request.

### Change the key later

You do not need to remember a command. Tell the Agent naturally:

```text
换一下 Free Vision 的 API Key
```

or:

```text
Reconfigure the OpenCode key for Free Vision.
```

The Agent asks for the new key in the next message. The existing local key stays untouched until the candidate key passes the live vision validation. If the new key fails, the old key remains in place.

### Check or repair configuration

Ask:

```text
检查一下 Free Vision 能不能用
```

```text
Free Vision 最近不能用了，帮我修一下
```

The Agent runs doctor first and distinguishes missing/invalid credentials from discovery/network/provider/no-free-model failures. It should ask for a new key only when configuration or authentication actually requires one.

### View configuration state

```text
python <SKILL_DIR>/scripts/configure.py status --pretty
```

This reports only whether configuration exists and which source is active. It never shows the key.

### Clear the locally saved key

Tell the Agent “删除 Free Vision 的 Key”, or run:

```text
python <SKILL_DIR>/scripts/configure.py clear --pretty
```

This removes only the local Free Vision key. Environment variables are not modified.

### Environment-variable precedence

Runtime precedence remains:

```text
OPENCODE_API_KEY
FREE_VISION_OPENCODE_API_KEY
local Free Vision config file
```

If an environment key is active, a conversational local replacement is intentionally blocked because the local file would be shadowed. The Agent should report the active source instead of pretending a new local key became active.

### Manual hidden-input fallback

If you prefer not to send the key through conversation context, run interactively from the installed Skill directory:

```bash
python scripts/configure.py set
```

The prompt uses hidden terminal input. The legacy `scripts/onboard.py` remains available for simple local setup, but `configure.py set` is the recommended validated path.

## Normal Agent usage

After installation, you should not need to type `vision.py` manually during normal use.

Ask the Agent naturally:

```text
看看 C:\Users\32962\Desktop\test.png 里面有什么
```

```text
分析 ./screenshots/error.png，告诉我为什么页面报错
```

```text
比较 before.png 和 after.png，列出 UI 上所有可见变化
```

```text
读取 https://example.com/chart.png 的标签和趋势
```

The Skill description tells compatible Agents when Free Vision is relevant. When activated, the Agent resolves the installed Skill directory, runs its bundled CLI with the user's actual visual task, reads the returned `result`, then continues reasoning and answers naturally.

## Manual runtime verification

You can still test the runtime directly.

### List currently eligible free vision models

```bash
python scripts/vision.py --list-models --pretty
```

Force a fresh lookup:

```bash
python scripts/vision.py --list-models --refresh-models --pretty
```

### Windows local image

```powershell
python scripts\vision.py "C:\Users\32962\Desktop\test.png" --task "描述这张图片" --pretty
```

Both Windows path forms are supported:

```text
C:\Users\me\Desktop\test.png
C:/Users/me/Desktop/test.png
```

### Image URL

```bash
python scripts/vision.py "https://example.com/image.png" --task "Describe this diagram precisely." --pretty
```

### Multiple images

```bash
python scripts/vision.py before.png after.png --task "Compare the visible differences." --pretty
```

## How free-model discovery works

Free Vision does **not** decide that a model is free because its model ID contains `free`.

It joins two live sources:

1. OpenCode Zen's current model list — which models are currently exposed.
2. models.dev OpenCode metadata — pricing, lifecycle status, and input modalities.

Automatic candidates must satisfy all of these:

- currently present in Zen;
- OpenCode provider metadata exists;
- input cost is exactly `0`;
- output cost is exactly `0`;
- input modalities include `image`; and
- status is not deprecated.

Discovery results are cached for six hours. A forced `--model` is accepted only if current discovery still qualifies it as a zero-cost image-capable model.

At the time this project was built and tested, `mimo-v2.5-free` qualified and completed a real Windows local-image test successfully. It is a preference, not a permanent hard-coded dependency.

## Result protocol

Success:

```json
{
  "ok": true,
  "provider": "opencode",
  "model": "mimo-v2.5-free",
  "result": "The screenshot shows ...",
  "media": ["C:\\Users\\me\\Desktop\\test.png"],
  "attempts": [
    {"model": "mimo-v2.5-free", "status": "success", "reason": null}
  ]
}
```

The Skill tells the main Agent to use `result` as visual evidence and produce the final natural-language answer. It should not dump the raw JSON unless the user asks for it.

## Security and limits

- API keys are never included in result JSON or sanitized provider errors.
- Remote media accepts only `http://` and `https://` URLs.
- Image size limit defaults to 20 MiB.
- Supported signatures: PNG, JPEG, GIF, WebP.
- Remote content is validated from image bytes, not just filename/content type.
- Remote URLs are fetched from the machine running the Skill.
- No paid model fallback exists in the current version.

## Troubleshooting

Installed Skills include:

```text
references/usage.md
references/troubleshooting.md
```

Common issues include hidden API-key paste behavior, Agent skill discovery, Windows drive paths, DNS/firewall discovery failures, temporary lack of free image models, and provider fallback failures.

## Manual installation fallback

If an Agent supports filesystem Agent Skills but cannot use the installer, copy the **runtime Skill payload** into that client's Skill root so the final layout contains:

```text
<skills-root>/free-vision/
├── SKILL.md
├── free_vision/
├── scripts/
│   ├── vision.py
│   ├── vision.sh
│   └── onboard.py
├── references/
└── agents/
```

Keep the directory together because scripts and references are resolved relative to `SKILL.md`.

## Development

Run all tests:

```bash
python -m unittest discover -s tests -v
```

Compile-check Python:

```bash
python -m compileall -q free_vision scripts
```

Shell syntax check:

```bash
bash -n scripts/vision.sh
```

The test suite uses fakes/mocks and does not require live credentials.
