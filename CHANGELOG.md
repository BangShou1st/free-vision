# Changelog

## v0.3.11 — 2026-08-18

### Fixed / Added

- 浏览器/自动化工具结果即使只有 `(no output)`、空 `Structured content`，只要同时暴露可访问截图路径，Free Vision 现在会把截图视为当前任务的视觉证据，而不是把空文本误判为“页面没有内容”。
- ZCode provider-boundary gateway 会在下一次模型请求中识别可信 tool-result screenshot 行，自动调用 Free Vision 并把 `[Free Vision visual evidence]` 追加到工具结果后再转发给主模型；这条路径不依赖 Skill 是否被宿主再次主动选择。
- 自动读取有明确安全边界：只接受 tool-role / `tool_call_id` 消息中的 `Browser screenshot saved to:` / `Screenshot saved to:` 行，只允许当前用户 `~/.zcode/cli/artifacts/` 目录树内、真实存在且扩展名为 PNG/JPEG/GIF/WebP 的文件；普通用户文本和目录外路径不会触发本地文件读取。
- 视觉任务优先继承截图工具结果之前最近的用户请求，保持原始任务目标；同一工具结果里的多张截图按出现顺序一起进入现有多图视觉链路。
- `SKILL.md` 与 README 同步补充 current-task tool-result screenshot fallback 规则，并继续保持原生视觉优先。
- 版本号升级为 `0.3.11`，`source.json` 同步更新。

### Verification

- 新增 v0.3.11 regression contracts，覆盖可信 ZCode artifact、原始用户任务透传、多截图顺序、普通用户文本不触发、artifact 目录外路径不触发，以及无 `image_url` 时 gateway 仍能把视觉证据转发给 upstream。
- 当前执行环境无法解析 `github.com`，因此不能在隔离 checkout 中运行全仓 unittest/compileall；合并前以 GitHub diff、静态合同和可合并状态为基础检查，不把这些检查宣称为完整 CI。
- 仓库目前仍未配置 GitHub Actions；真实 ZCode/browser 宿主级验收应在用户更新到 v0.3.11 后继续执行。

## v0.3.10 — 2026-08-16

### Fixed / Added

- 多图分析增加 Provider 兼容降级：仍优先把多张图片一次交给视觉模型；若批量多图请求因 `400` / `415` / `422` 被拒绝，则对同一候选模型逐图分析，并用稳定的 `[Image N]` 标签聚合视觉证据交回主 Agent。`429` 和 5xx 不会拆分放大请求。
- 新增根目录 `source.json`，随运行时 Skill payload 安装，机器可读地记录官方仓库 `https://github.com/BangShou1st/free-vision`、更新分支 `main` 与当前版本。
- `SKILL.md` 明确规定安装目录是 runtime payload、不是 Git checkout；Agent 更新时必须读取 `source.json` / 官方源说明，禁止搜索或猜测其它同名仓库。
- README 顶部增加官方仓库 / 唯一更新源说明，并补充已安装 Skill 的标准更新流程。
- installer 运行时 payload 现在包含 `source.json`，安装/预览输出同时显示 canonical source，便于 Agent 验证更新来源。
- 版本号升级为 `0.3.10`。

### Verification

- 新增 v0.3.10 canonical-source regression contract，覆盖 metadata、runtime payload、安装复制、installer 输出与 Agent 更新规则。
- v0.3.9 release contract 改为版本下限检查，避免后续补丁版本误报回归。
- 真实宿主更新仍应在安装后执行 ZCode `setup` / `status` 并刷新或重启 ZCode；本条不声称已经替用户机器完成宿主级更新。

## v0.3.7 — 2026-08-14

### Fixed / Added

- ZCode Console / UUID provider 即使没有可编辑 `baseURL`，也可以在精确识别当前 provider/model 后通过**同 provider id 的可逆 managed overlay**接入 Free Vision gateway，不再要求用户手工改不存在的 Base URL。
- managed overlay 只写 localhost Base URL 与非 Secret 占位 token `free-vision-local`；真实 OpenCode API Key 继续只保存在 Free Vision 配置中，并由 gateway 仅在转发到 `opencode.ai` 时注入。
- 当 ZCode 无法从配置/cache 自动推断当前路由时，`setup` 支持使用运行时已经明确暴露的 `--provider-id` 与 `--model` 精确重跑；禁止猜测 routing metadata。
- credential-free overlay 仅允许已识别且以 `-free` 结尾的 OpenCode model，并拒绝覆盖已经含 credential-like 字段的 provider。
- Windows 自启从可能需要更高权限的 `schtasks /SC ONLOGON` 改为当前用户 Startup 文件夹；自启注册失败只作为 warning，不再回滚已经成功的 gateway/provider 接入。
- gateway `/health` 增加 Skill 版本；更新 Skill 后若旧 v0.3.6 gateway 进程仍在运行，`setup/start` 会识别并替换旧进程，`status` 同时暴露 `gateway_version` / `gateway_current`。
- `remove` 可恢复 managed provider/cache 原始结构、移除 Startup launcher、停止 gateway 并删除受管状态。

### Verification

- 隔离工作区 ZCode 历史 + v0.3.7 专项回归：25 tests passed。
- 精简公开回归与 v0.3.6 ZCode 公共回归：12 tests passed。
- `python -m compileall -q free_vision` 通过。
- 真实 ZCode 拖图仍需在 v0.3.7 发布并更新到用户宿主后做最终验收；本条不宣称宿主级验收已经完成。

## v0.3.6 — 2026-08-13

### Added / Fixed

- 新增 ZCode 原生安装 target 与本地 loopback adaptive image fallback gateway，解决 ZCode 在文本主模型执行 Skill 前把 `image_url` 直接送给 Provider、导致 `Model only supports text input` 400 的问题。
- gateway 对未知模型的第一次图片请求仍原样转发，保持原生多模态优先；只有上游明确拒绝图片为 text-only 时才调用 Free Vision、把图片替换为视觉证据文本并自动重试一次。
- 已明确拒绝图片的模型会在当前 gateway 进程内被记忆，后续同 model 图片请求直接走视觉 fallback，避免重复的必失败 400。
- `zcode.py setup` 可从 `~/.zcode/v2/config.json` 与 `bots-model-cache.v2.json` 保守识别当前 OpenAI-compatible provider，并同步管理 Base URL；现有 API Key、model、modalities 与其他配置保持不变。
- `zcode.py remove` 只在配置仍指向受管 gateway 时恢复原 Base URL，不覆盖用户之后的手动修改；setup/config/cache 写入失败会事务回滚。
- gateway 仅监听 loopback；Windows 支持当前用户登录自启；data URI 同样遵守现有 20 MiB 图片限制。
- 新增 `references/zcode.md`，并让 ZCode 安装 target 输出 gateway setup/status 的下一步提示。

### Verification

- 开发全量回归：141 tests passed。
- `python -m compileall -q free_vision scripts`、`bash -n scripts/vision.sh`、`git diff --check` 通过。
- 本地真实子进程 lifecycle 使用 ZCode UUID provider + `deepseek-v4-flash-free` 形态完成 `setup -> config/cache connect -> gateway proxy -> status -> remove -> restore` 闭环验证。
- 真实 ZCode 拖图仍需在发布后做最终宿主验收；本条不宣称宿主级测试已经完成。

## v0.3.5 — 2026-08-13

### Fixed

- 机器可读 JSON 现在始终使用 ASCII-safe JSON 序列化；中文、`¥`、emoji 等通过标准 Unicode escape 表示，避免 Windows GBK/cp936 与宿主 UTF-8 解码不一致造成乱码，也不再需要 `PYTHONIOENCODING=utf-8` 作为正常 workaround。
- 新增运行时内置 `free_vision/assets/selftest.png` 与 `scripts/selftest.py --pretty`，安装后的端到端验收不再依赖 Playwright、浏览器截图或临时测试图片。
- doctor 改为复用同一张内置测试图，移除重复的 base64 probe 图片来源。
- Secret transport 规则进一步收紧：`python -c "key=...; subprocess.run(..., input=key)"` 即使最终把 Key 送入子进程 stdin，也不属于安全 stdin，因为 Secret 已进入 shell/tool-visible source。
- README、SKILL、usage、troubleshooting 的首次配置与验收流程统一为 `install -> doctor -> configure if needed -> bundled selftest -> READY`。

### Verification

- 新增 ASCII-safe JSON、内置 PNG、doctor 资产复用、自检命令、installer payload、Secret transport 和文档一致性回归测试。
- 完整测试：101 tests passed。
- 内置测试图已检查为有效 320×180 PNG，包含固定高对比视觉元素。
- 确定性集成检查：ASCII JSON round-trip、selftest payload、普通文件 Secret 重定向拒绝均通过。
- `python -m compileall -q free_vision scripts` 通过。
- `bash -n scripts/vision.sh` 通过。
- `git diff --check` 通过。

## v0.3.4 — 2026-08-13

### Fixed

- 修复 Windows GBK/cp936 stdout 无法编码 `¥`、emoji 等字符时，`vision.py` / `doctor.py` / `configure.py` 在已经得到有效结果后仍可能因 `UnicodeEncodeError` 崩溃的问题。
- JSON 输出先保留正常 Unicode；若 stdout 编码无法表示完整结果，则使用标准 JSON `\uXXXX` 转义。
- 收紧 Agent Secret 传输协议：宿主没有安全 stdin / hidden process-input 通道时，不允许创建临时 Key 文件、临时脚本或把 Secret 序列化进 shell 命令。
- `configure.py set --stdin` 拒绝从普通文件重定向读取 API Key，并返回 `unsafe_secret_transport`。
- 无安全 Secret 通道时，Agent 应让用户本机运行 `configure.py set --pretty`。

### Verification

- 完整测试：89 tests passed。
- `python -m compileall -q free_vision scripts`、`bash -n scripts/vision.sh`、`git diff --check` 通过。

## v0.3.3 — 2026-08-13

### Fixed

- 修复 Agent 宿主通过 PTY / process-input 配置 API Key 时可能发生终端回显的问题：`configure.py set --stdin` 检测到 TTY 后自动改用隐藏输入。
- `SKILL.md` 明确区分非 TTY stdin pipe 与 PTY。
- 首次/换 Key 的候选验证只探测首选免费视觉模型，并把 setup probe 推理 timeout 限制为 45 秒。
- 普通 `vision.py` 分析和正常 doctor 保持原有 120 秒请求 timeout 与模型 fallback。

### Verification

- 完整测试：83 tests passed。

## v0.3.2 — 2026-08-13

### Fixed

- doctor 探测图从被 OpenCode Zen 拒绝的 1x1 PNG 替换为 64x48 PNG。
- 修复 `XDG_CONFIG_HOME` / `XDG_CACHE_HOME` 已设置时仍提前求值 `Path.home()` 的问题。
- 无原生 Skill installer 时优先调用 `scripts/install.py --dest <SKILL_ROOT> --force`。
- 正常 installation/setup/doctor/repair 不允许宿主 Agent 现场修改已安装源码。

### Agent behavior

- 图片存在本身即可成为 Free Vision 激活信号，不要求“看图”“分析图片”等关键词。
- 主模型/宿主已经可以直接理解图片时跳过 Free Vision。
- 用户只发送图片时优先使用最近上下文；否则默认详细视觉描述。

### Verification

- 完整测试：77 tests passed。

## v0.3.1 — 2026-08-13

### Fixed

- 修复 OpenCode Zen 免费视觉模型在 Free Vision 请求下可能返回 HTTP 429 的兼容性问题。
- Zen 推理请求默认携带 `User-Agent: opencode/1.18.16`。
- 支持 `ZEN_USER_AGENT` 覆盖默认值，且不污染普通 HTTP 请求。

### Verification

- 完整测试：68 tests passed。
- Windows 上使用现有 Zen Key、`mimo-v2.5-free` 和真实本地图片完成回归，原 429 未再出现。

> 这里只记录已验证的客户端兼容性差异，不推断 OpenCode 服务端内部为何根据 User-Agent 返回不同结果。

## v0.3.0 — 2026-08-12

### Initial public release

- 通用 Agent Skill，为文本型 Agent 提供图片理解能力。
- GitHub-first 安装体验。
- 支持本地图片路径和 HTTP/HTTPS URL，覆盖 Windows、macOS、Linux。
- 支持 PNG、JPEG、GIF、WebP，单图/多图任务。
- 动态发现 OpenCode Zen 免费视觉模型并自动 fallback。
- 支持对话式 API Key 配置、替换、状态检查、doctor、repair 和 clear。
- 新 Key 真实视觉验证成功后才保存；替换失败保留旧 Key。
- Agent 最终回复跟随用户当前对话语言。
