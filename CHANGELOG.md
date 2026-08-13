# Changelog

## v0.3.4 — 2026-08-13

### Fixed

- 修复 Windows GBK/cp936 stdout 无法编码 `¥`、emoji 等字符时，`vision.py` / `doctor.py` / `configure.py` 在已经得到有效结果后仍可能因 `UnicodeEncodeError` 崩溃的问题。
- JSON 输出现在先保留正常 Unicode；若当前 stdout 编码无法表示完整结果，则自动使用标准 JSON `\uXXXX` 转义，保证输出仍是可解析的有效 JSON。
- 收紧 Agent Secret 传输协议：宿主没有安全 stdin / hidden process-input 通道时，不再允许创建临时 Key 文件、临时脚本或把 Secret 序列化进 shell 命令。
- 无安全 Secret 通道时，Agent 应让用户在本机运行 `configure.py set --pretty`，由 `getpass` 隐藏读取 Key。

### Verification

- 新增 cp936 输出回归，覆盖 vision / doctor / configure 三个 CLI。
- 新增无安全 stdin 时的 Secret transport 契约测试。
- 完整测试：88 tests passed。
- `python -m compileall -q free_vision scripts` 通过。
- `bash -n scripts/vision.sh` 通过。
- `git diff --check` 通过。

## v0.3.3 — 2026-08-13

### Fixed

- 修复 Agent 宿主通过 PTY / process-input 配置 API Key 时可能发生终端回显的问题：`configure.py set --stdin` 检测到 TTY 后会自动改用隐藏输入。
- `SKILL.md` 现在明确区分非 TTY stdin pipe 与 PTY：真正的 pipe 使用 `--stdin`；PTY 使用 `configure.py set --pretty`，由 `getpass` 隐藏输入。
- 首次/换 Key 的候选验证不再复用完整多模型长时间 fallback：只探测首选免费视觉模型，并把该次 setup probe 的推理 timeout 限制为 45 秒。
- 普通 `vision.py` 分析和正常 doctor 默认行为保持原有 120 秒请求 timeout 与模型 fallback，不受 setup 限制影响。

### Verification

- 新增 PTY 隐藏输入、候选数量边界、setup probe timeout 传递和 Agent secret-input 契约测试。
- 完整测试：83 tests passed。
- `python -m compileall -q free_vision scripts` 通过。
- `bash -n scripts/vision.sh` 通过。
- `git diff --check` 通过。

## v0.3.2 — 2026-08-13

### Fixed

- 将 doctor 的内置探测图从被 OpenCode Zen 拒绝的 1x1 PNG 替换为已验证可用的 64x48 PNG，保持真实多模态探测流程不变。
- 修复 `XDG_CONFIG_HOME` / `XDG_CACHE_HOME` 已设置时仍提前求值 `Path.home()` 的问题，提升 Windows 隔离环境和测试稳定性。
- 收敛 GitHub-first 安装流程：无原生 Skill installer 时优先调用 `scripts/install.py --dest <SKILL_ROOT> --force`，不把整个开发仓库复制进最终 Skill 目录。
- 明确正常 installation/setup/doctor/repair 不允许宿主 Agent 现场修改已安装 Free Vision 源码。

### Agent behavior

- 图片存在本身即可成为 Free Vision 激活信号，不再要求用户显式说“看图”“分析图片”等关键词。
- 支持从可访问的图片附件路径、本地图片后缀和 HTTP/HTTPS 图片 URL 自动判断视觉需求。
- 如果当前主模型/宿主已经可以直接理解该图片，则跳过 Free Vision，避免重复视觉处理。
- 用户只发送图片或图片路径时，优先使用最近上下文中的问题；无可推断任务时默认生成详细视觉描述并提取重要可见文字/UI 状态。

### Verification

- 完整测试：77 tests passed。
- `python -m compileall -q free_vision scripts` 通过。
- `bash -n scripts/vision.sh` 通过。
- `git diff --check` 通过。

## v0.3.1 — 2026-08-13

### Fixed

- 修复 OpenCode Zen 免费视觉模型在 Free Vision 客户端请求下可能返回 HTTP 429 的兼容性问题。
- OpenCode Zen 实际推理请求现在默认携带 `User-Agent: opencode/1.18.16`。
- 支持通过 `ZEN_USER_AGENT` 环境变量覆盖默认 Zen User-Agent。
- User-Agent 仅在 OpenCode Zen provider 的推理请求中设置，不污染 models.dev、普通 HTTP 请求或其他域名。

### Verification

- 新增 Zen User-Agent 默认值、环境变量覆盖和非 Zen 请求隔离测试。
- 完整测试：68 tests passed。
- 已在 Windows 上使用现有 Zen Key、`mimo-v2.5-free` 和真实本地图片完成回归：视觉调用成功，原先的 `provider_request_failed (HTTP 429)` 未再出现。

> 这里只记录已验证的客户端兼容性差异，不推断 OpenCode 服务端为何会针对不同 User-Agent 返回不同结果。

## v0.3.0 — 2026-08-12

### Initial public release

- 通用 Agent Skill，可为文本型 Agent 提供图片理解能力。
- GitHub-first 安装体验，可让支持 Skill 安装/终端能力的 Agent 从仓库自行安装。
- 支持本地图片路径和 HTTP/HTTPS 图片 URL。
- 支持 Windows、macOS、Linux 路径。
- 支持 PNG、JPEG、GIF、WebP，以及单图/多图任务。
- 动态发现当前可用的 OpenCode Zen 免费视觉模型，并进行自动 fallback。
- 支持对话式 API Key 配置、替换、状态检查、doctor、repair 和 clear 生命周期。
- 新 Key 在真实视觉验证成功后才保存；替换失败时保留旧 Key。
- Agent 最终回复跟随用户当前对话语言.
