# Changelog

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
- Agent 最终回复跟随用户当前对话语言。
