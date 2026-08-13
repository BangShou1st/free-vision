# Free Vision v0.3.2 设计：安装收敛、Doctor 兼容、Windows 稳定性与自动视觉触发

日期：2026-08-13

## 背景

真实 Hermes 安装测试证明 Free Vision v0.3.1 的核心视觉链路可用，但普通用户安装过程中宿主 Agent 仍承担了过多“现场开发”职责：它为了让 doctor 通过，生成测试图片、修改已安装的 `doctor.py`、运行临时验证脚本，并把 Windows 测试失败解释为环境问题。

这不符合公开 Agent Skill 的产品目标。正常用户流程应当是：安装 → 配置/读取已有配置 → doctor → 直接使用。宿主 Agent 负责安装、配置、调用和解释错误，不负责修改 Free Vision 源码。

本版本还纳入自动视觉触发：当用户当前消息包含或引用可访问图片，而主模型/宿主本身不能直接理解该图片时，应自动调用 Free Vision；不要求用户显式说“看图”“分析图片”等关键词。

## 目标

v0.3.2 只解决四类问题：

1. 收敛 GitHub-first 安装流程，避免宿主 Agent 直接复制整个仓库或修改已安装源码。
2. 修复 OpenCode Zen 对 doctor 内置 1x1 PNG 探测图返回 HTTP 400 的兼容性问题。
3. 修复 Windows 环境下 XDG 路径已显式提供时仍会提前求值 `Path.home()` 的问题，使完整测试在 Windows 环境语义下可稳定运行。
4. 将视觉触发从“关键词驱动”升级为“图片存在驱动”，同时保留“主模型已有原生视觉时不调用 Free Vision”的边界。

不在本版本范围：重写 provider 架构、OpenRouter、本地 OCR/模型、宿主附件拦截器、OpenCode Server Bridge、视频/音频、通用 Agent runtime。

## 设计原则

### 1. Free Vision 是安装产品，不是宿主 Agent 的可修改模板

正常安装、setup、doctor、repair 过程中，宿主 Agent不得修改 Free Vision 已安装源码。

`repair` 仅表示：检查配置、模型发现、网络/provider 状态、认证状态，以及在必要时引导用户更换 Key。若判断为 Skill 自身兼容性/实现问题，Agent 应报告问题并建议更新版本，不得现场 patch `free_vision/*.py` 或 `scripts/*.py`。

### 2. 安装优先级

推荐安装流程：

1. 若宿主存在原生 Agent Skill 安装器，优先使用原生安装器。
2. 若宿主无原生安装器，但具备 shell/filesystem 能力：
   - 临时 clone/download GitHub 仓库；
   - 找到宿主自己的 Skill 根目录；
   - 优先调用仓库自带 `scripts/install.py --dest <SKILL_ROOT> --force`；
   - 安装完成后可删除临时 clone。
3. 不应把整个开发仓库直接同步到最终 Skill 目录；`tests/`、开发文档等不属于 runtime payload。
4. 不应要求普通用户理解最终 Skill 目录细节。

`install.py` 继续作为 runtime payload 的唯一仓库内定义来源，不新增 Hermes 专用 target；通用 `--dest` 足够覆盖未内置的宿主。

### 3. Doctor 探测图

当前 `doctor.py` 使用 1x1 PNG。真实 Hermes/Zen 回归显示：相同模型、相同 Key、相同 UA 下，正常尺寸 PNG 可成功，而内置 1x1 PNG 返回 HTTP 400。

v0.3.2 将内置 probe 替换为已验证可通过 Zen 的正常尺寸小型 PNG。探测任务仍保持：

`Inspect the attached image, then reply with the single token VISION_OK.`

Doctor 的目的不变：真实验证配置、模型发现、认证和视觉请求是否能完成。

实现时应通过测试确认：

- probe 为有效 PNG；
- 尺寸不再是 1x1；
- doctor 仍通过相同 provider/service 路径发起真实 multimodal 请求；
- 不引入外部图片文件依赖。

### 4. Windows 路径 fallback

当前存在以下模式：

`os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")`

Python 会在调用 `dict.get` 前先求值默认参数，因此即使 `XDG_CONFIG_HOME` 已设置，`Path.home()` 也会被调用。在 Windows 的测试隔离环境中，如果 HOME/USERPROFILE 被清空，会导致不必要的 `Could not determine home directory`。

v0.3.2 改为显式延迟 fallback：

- 若 `XDG_CONFIG_HOME`/`XDG_CACHE_HOME` 存在且非空，直接使用它；
- 仅在对应 XDG 环境变量缺失时调用 `Path.home()`；
- 不改变现有目录布局和配置格式。

影响范围限制在现有 config/cache path helper，不进行配置系统重构。

## 自动视觉触发设计

### 触发核心规则

当且仅当满足以下条件时，Agent 应自动使用 Free Vision：

1. 当前用户消息包含或引用一个可访问图片；
2. 当前主模型/宿主不能直接理解该图片内容；
3. 图片可通过 Free Vision 现有输入方式访问（本地路径或 HTTP/HTTPS URL，或宿主提供可访问的附件路径）。

明确不要求出现 `看图`、`分析`、`识别`、`截图`、`image`、`inspect` 等关键词。

### 图片识别信号

按可靠性从高到低：

1. 宿主明确提供 image MIME/attachment metadata，且能取得可访问路径/URL；
2. 本地路径后缀为 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`；
3. HTTP/HTTPS URL 明显使用上述图片后缀；
4. URL 无图片后缀时，可继续交由现有 media resolver 通过响应字节/signature 做最终校验。

后缀仅作为触发信号，最终输入合法性仍由 Free Vision 现有 media validation 决定。

### 主模型已有原生视觉

若当前主模型/宿主已经能够直接访问并理解当前图片，则不调用 Free Vision。Free Vision 的角色是补足视觉缺口，不与宿主原生视觉重复处理。

由于通用 Skill 无法可靠自省所有宿主的模型能力，本版本通过 `SKILL.md` 行为规则约束 Agent 决策，不在 Python runtime 增加虚假的“检测当前 LLM 是否多模态”接口。

### 用户只发送图片或图片路径

如果用户只提供图片，没有显式任务：

1. 若最近对话上下文存在明确问题，将该问题作为视觉任务；
2. 若不存在可推断任务，默认要求视觉模型详细描述关键可见内容，并提取重要文字/UI 状态；
3. 主 Agent 使用返回的视觉证据自然回答，不向用户倾倒 raw JSON。

### 数据流保持不变

Free Vision 不接管最终回答：

`用户 → 主 Agent → Free Vision → 免费视觉模型 → 文本视觉证据 → 主 Agent 推理/组织 → 用户`

视觉模型负责“看”；主 Agent 继续负责上下文理解、推理、决策和最终语言表达。

## 错误处理

- 安装失败：报告具体安装错误，不修改源码尝试自愈。
- `missing_api_key` / `authentication_failed`：按现有对话式 Key 流程处理。
- `model_discovery_failed` / `no_free_vision_models` / provider 失败：解释分类，不误判为 Key 问题。
- Skill 自身疑似 bug：告诉用户当前版本存在兼容性问题，建议升级或报告 issue，不 patch 已安装源码。
- API Key 继续不得出现在日志、命令行参数、JSON 输出或用户可见回显中。

## 测试策略

必须使用 TDD。

### Doctor

先新增会失败的测试，证明 probe 不得是 1x1，并验证真实 `OpenCodeProvider` 接收到的 media payload 来自新的有效 PNG。然后替换 probe，运行 doctor tests 和完整测试。

### Windows config/cache

先新增测试，在 `patch.dict(os.environ, {"XDG_CONFIG_HOME": ...}, clear=True)` / `XDG_CACHE_HOME` 场景下调用 path helper，确认不需要 `Path.home()`。RED 后做最小延迟 fallback 修改。

### 自动触发与安装行为

自动触发主要属于 `SKILL.md` Agent 行为协议，因此测试重点为：

- Skill 文档明确“图片存在即可触发，不依赖关键词”；
- 明确“主模型已有原生视觉则跳过”；
- 明确图片路径/URL/附件路径信号；
- 明确无任务时默认描述；
- 明确禁止正常 repair 修改已安装源码；
- README 安装说明要求无原生 installer 时优先执行 `scripts/install.py --dest ...`，而不是复制整个仓库。

若仓库已有文档/安装契约测试，则扩展现有测试；否则新增最小静态契约测试，不为文档规则造复杂 parser。

## 验收标准

代码级：

- 新增测试先 RED 后 GREEN；
- Linux/当前开发环境完整 unittest 全绿；
- Windows 语义下此前因 `Path.home()` 触发的 11 个测试不再因该问题失败；
- compileall、shell syntax、diff check 通过。

真实用户级：

1. 新开一个未参与开发的 Agent 会话；
2. 用户只发送 GitHub 地址和安装请求；
3. Agent 安装最新版 Free Vision；
4. 安装过程不修改 Free Vision 源码，不把开发仓库 `tests/` 当 runtime 必需内容；
5. 已有 Key 时不重复索要；无 Key 时只走既有安全对话式配置；
6. doctor 一次通过；
7. 用户只发送一个可访问图片路径，即使没有“看图”关键词，也能自动触发 Free Vision（前提：主模型不能直接看该图片）；
8. Free Vision 返回视觉证据，主 Agent 输出自然语言最终结果；
9. 若主模型自身已经能直接看图，则不额外调用 Free Vision。

## 版本

实现和真实回归完成后发布为 `v0.3.2`，并在 CHANGELOG 中记录上述四类改动。