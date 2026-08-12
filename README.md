# Free Vision 👁️

**让没有视觉能力的 AI Agent，也能看懂图片。**

Free Vision 是一个通用的 Agent Skill。它可以让 Codex、Claude Code、OpenCode，以及其他支持 Agent Skills / 本地 Skill 的 AI Agent，通过当前可用的 **免费多模态模型**理解图片。

它负责“看”，主 Agent 继续负责“思考和回答”。

你可以用它分析：

- 网页截图、软件界面和报错页面
- 图片中的文字、表格和扫描内容
- 图表、流程图、示意图
- 普通照片
- 多张图片之间的差异
- Windows / macOS / Linux 本地图片
- HTTP / HTTPS 图片链接

> 🌐 **对话语言跟随用户。** 你用中文和 Agent 对话，安装、配置、诊断和视觉结果就应该继续用中文；英文或其他语言同理。

---

## 🚀 最简单的安装方式：直接把 GitHub 地址发给 AI Agent

推荐不要手动下载 ZIP，也不需要先研究 Skill 应该放在哪个目录。

把下面这段直接发给你的 AI Agent：

```text
帮我安装这个 Agent Skill：

https://github.com/BangShou1st/free-vision

如果你支持原生 Skill 安装器，请直接使用它安装。
如果不支持，就从 GitHub 获取仓库并安装到你支持的 Agent Skills 目录。
安装完成后不要结束，请继续在当前对话里帮我完成 Free Vision 配置和测试。
```

支持 GitHub Skill 安装或具备终端 / 文件操作能力的 Agent，可以自行完成安装。

安装完成后，用户不需要记住 `vision.py`、`doctor.py` 等命令——这些属于 Agent 内部调用细节。

---

## 🔑 首次配置：直接在对话里完成

Free Vision 通过 OpenCode Zen 调用当前可用的免费视觉模型，因此需要一个 OpenCode API Key。

如果安装后还没有配置 Key，Agent 应该继续在当前对话中提示你：

> Free Vision 已安装，但还没有配置 OpenCode API Key。  
> 如果你愿意继续在当前对话中配置，请下一条消息单独发送 API Key。  
> 该 Key 会进入当前对话上下文，我不会在回复中回显它。  
> 收到后我会保存配置并进行真实视觉调用测试。

然后你只需要在**下一条消息单独发送 Key**。

Agent 会自动完成：

```text
收到 API Key
    ↓
通过 stdin 交给 Free Vision
    ↓
动态发现当前免费视觉模型
    ↓
进行真实多模态请求测试
    ↓
验证成功后保存
    ↓
告诉用户 Free Vision 已可用
```

Key 不会作为命令行参数传递，也不会出现在 Free Vision 的 JSON 输出中。

### 已经配置过？

如果系统里已经存在有效配置，Agent 会直接运行诊断。

正常情况下不会重复让你输入 Key。

---

## 💬 安装后怎么用？

**直接正常和 Agent 说话。**

例如：

```text
看看 C:\Users\me\Desktop\test.png 里面有什么
```

```text
分析一下 C:\Users\me\Desktop\error.png，告诉我这个页面为什么报错
```

```text
提取 ./receipt.png 里面的文字和关键信息
```

```text
比较 before.png 和 after.png，告诉我 UI 有哪些可见变化
```

```text
分析 https://example.com/chart.png，解释图表的趋势
```

当任务需要视觉信息时，兼容的 Agent 会自动调用 Free Vision，读取视觉模型返回的证据，然后继续推理并用自然语言回答。

你不需要手动运行：

```text
python scripts/vision.py ...
```

---

## 🔄 以后换 Key，也直接和 Agent 说

配置不是一次性的安装步骤，而是 Free Vision 长期能力的一部分。

你可以随时说：

```text
换一下 Free Vision 的 API Key
```

Agent 会：

1. 提示你下一条单独发送新 Key；
2. 先使用新 Key 做真实视觉验证；
3. **验证成功后才替换旧 Key**；
4. 如果新 Key 验证失败，旧 Key 保持不变。

也可以说：

```text
检查一下 Free Vision 能不能用
```

```text
Free Vision 最近不能用了，帮我修一下
```

```text
看看 Free Vision 配置好了没有
```

```text
删除 Free Vision 的 Key
```

Agent 会自动进入对应的 `status / doctor / repair / clear-key` 流程。

---

## 🩺 Free Vision 会自己区分哪里出了问题

当你说“Free Vision 不能用了”时，Agent 应该先诊断，而不是直接让你重新输入 Key。

| 状态 | 含义 |
|---|---|
| `missing_api_key` | 还没有配置 Key |
| `authentication_failed` | 当前 Key 无效或没有权限 |
| `model_discovery_failed` | 当前无法完成模型发现，通常是网络或元数据访问问题 |
| `no_free_vision_models` | 配置可能正常，但当前没有符合条件的免费视觉模型 |
| `all_models_failed` | 候选模型存在，但本次 Provider / 模型调用全部失败 |

所以 `Free Vision 不能用` 并不等于 `API Key 一定错了`。

---

## ✨ 主要能力

- ✅ Windows / macOS / Linux 本地图片
- ✅ HTTP / HTTPS 图片 URL
- ✅ PNG / JPEG / GIF / WebP
- ✅ 单张或多张图片
- ✅ 截图、UI、报错界面
- ✅ 图片文字提取
- ✅ 图表、流程图、照片
- ✅ 多图比较
- ✅ 动态发现当前可用的免费视觉模型
- ✅ 模型调用失败自动 fallback
- ✅ 对话式 API Key 设置 / 更换 / 检查 / 删除
- ✅ 新 Key 验证成功后才覆盖旧 Key
- ✅ Agent 获取视觉证据后继续自然语言推理
- ✅ Python 3.10+
- ✅ 运行时无第三方 Python 依赖

目前暂不包含：

- 本地 OCR / 本地视觉模型推理
- OpenRouter
- 视频 / 音频分析
- 客户端拖拽图片拦截
- 模型代理服务

---

## 🧠 它是怎么工作的？

Free Vision 不会取代主 Agent。

```text
用户
  ↓
主 Agent
  ↓
发现任务需要看图
  ↓
Free Vision Skill
  ↓
动态发现免费视觉模型
  ↓
视觉模型读取图片
  ↓
返回视觉证据
  ↓
主 Agent 继续分析 / 推理
  ↓
自然语言回答用户
```

简单来说：

> **视觉模型负责看，主 Agent 负责想。**

---

## 🆓 “免费模型”不是靠名字判断

Free Vision 不会因为模型名称里包含 `free` 就直接认为它免费。

自动候选模型必须同时满足：

1. 当前仍然存在于 OpenCode Zen 模型列表；
2. models.dev 中存在对应 OpenCode Provider 元数据；
3. `input cost = 0`；
4. `output cost = 0`；
5. 输入模态包含 `image`；
6. 模型没有被标记为 deprecated。

模型发现结果默认缓存 6 小时。

因此 Free Vision 不永久绑定某一个“免费模型”。

在项目开发和真实 Windows 本地图像测试期间，`mimo-v2.5-free` 曾满足条件并成功完成视觉调用，但它只是当前偏好候选，不是永久硬编码依赖。

---

## 🤖 Agent 兼容性

Free Vision 本身采用目录式 Agent Skill 设计：

```text
free-vision/
├── SKILL.md
├── free_vision/
├── scripts/
├── references/
└── agents/
```

不同 Agent 的区别主要在于：

- 是否支持 Agent Skills；
- 是否支持直接从 GitHub 安装；
- Skill 的发现目录在哪里；
- 是否可以运行本地 Python / shell 命令。

因此最推荐的方式始终是：

> **把 GitHub 地址直接交给你正在使用的 Agent，让它优先使用自己的原生 Skill Installer。**

如果宿主 Agent 没有 GitHub Skill 安装能力，再使用下面的手动方式。

---

# 高级 / 手动使用

普通用户通常不需要阅读下面这些内容。

## 手动安装

克隆或解压仓库后：

```bash
python scripts/install.py
```

默认安装到：

```text
~/.agents/skills/free-vision/
```

### 只安装到当前项目

```bash
python scripts/install.py --scope project
```

结果：

```text
<current-project>/.agents/skills/free-vision/
```

也可以指定项目：

```bash
python scripts/install.py --scope project --project-dir /path/to/project
```

Windows：

```powershell
python scripts\install.py --scope project --project-dir "E:\my-project"
```

### OpenCode 原生目录

用户级：

```bash
python scripts/install.py --target opencode
```

项目级：

```bash
python scripts/install.py --target opencode --scope project
```

### Claude Code / Claude Agent SDK

用户级：

```bash
python scripts/install.py --target claude
```

项目级：

```bash
python scripts/install.py --target claude --scope project
```

### 自定义 Agent Skills 目录

```bash
python scripts/install.py --dest /path/to/agent/skills
```

Windows 示例：

```powershell
python scripts\install.py --dest "D:\AgentX\skills"
```

### 预览和覆盖安装

只预览：

```bash
python scripts/install.py --dry-run
```

覆盖已有版本：

```bash
python scripts/install.py --force
```

---

## 手动配置与诊断

### 查看当前配置状态

```bash
python scripts/configure.py status --pretty
```

不会显示 API Key。

### 配置 / 更换 Key

隐藏终端输入：

```bash
python scripts/configure.py set
```

Agent 自动配置时使用 stdin：

```bash
python scripts/configure.py set --stdin --pretty
```

候选 Key 会先经过真实视觉调用验证，成功后才保存。

### 完整诊断

```bash
python scripts/doctor.py --pretty
```

### 删除本地 Key

```bash
python scripts/configure.py clear --pretty
```

只会删除 Free Vision 本地配置文件中的 Key，不会修改系统环境变量。

### Key 优先级

运行时优先级：

```text
OPENCODE_API_KEY
FREE_VISION_OPENCODE_API_KEY
Free Vision 本地配置文件
```

如果环境变量中的 Key 正在生效，本地 Key 会被覆盖。

---

## 手动测试视觉能力

### 查看当前可用免费视觉模型

```bash
python scripts/vision.py --list-models --pretty
```

强制刷新：

```bash
python scripts/vision.py --list-models --refresh-models --pretty
```

### Windows 本地图片

```powershell
python scripts\vision.py "C:\Users\me\Desktop\test.png" --task "描述这张图片" --pretty
```

同时支持：

```text
C:\Users\me\Desktop\test.png
C:/Users/me/Desktop/test.png
```

### 图片 URL

```bash
python scripts/vision.py "https://example.com/image.png" --task "详细分析这张图片" --pretty
```

### 多张图片

```bash
python scripts/vision.py before.png after.png --task "比较两张图片所有可见差异" --pretty
```

---

## 返回协议

Free Vision 的脚本面向 Agent 返回机器可读 JSON。

成功示例：

```json
{
  "ok": true,
  "provider": "opencode",
  "model": "mimo-v2.5-free",
  "result": "这张截图显示……",
  "media": ["C:\\Users\\me\\Desktop\\test.png"],
  "attempts": [
    {
      "model": "mimo-v2.5-free",
      "status": "success",
      "reason": null
    }
  ]
}
```

`result` 是提供给主 Agent 的视觉证据。

正常使用时，Agent 应该根据这些证据继续思考并自然语言回答用户，而不是把原始 JSON 直接扔给用户。

---

## 🔐 安全说明

- API Key 不会出现在 Free Vision 的结果 JSON 中。
- Agent 配置 Key 时应通过 stdin 传入，而不是放进命令行参数。
- 更换 Key 时，新 Key 验证成功后才会替换旧 Key。
- 远程图片只接受 `http://` 和 `https://`。
- 默认单张图片大小限制为 20 MiB。
- 支持 PNG、JPEG、GIF、WebP 文件签名验证。
- 当前版本不存在付费模型 fallback。
- 如果你选择直接在聊天中发送 API Key，请注意：**Key 会进入当前对话上下文。**

---

## ❓ 常见问题

更详细说明：

```text
references/usage.md
references/troubleshooting.md
```

其中包含：

- Windows 路径问题
- API Key 配置与更换
- Skill 未被 Agent 发现
- DNS / 防火墙 / 网络错误
- 当前没有免费视觉模型
- Provider / 模型 fallback 失败

---

## 🧪 开发与测试

运行测试：

```bash
python -m unittest discover -s tests -v
```

Python 编译检查：

```bash
python -m compileall -q free_vision scripts
```

Shell 语法：

```bash
bash -n scripts/vision.sh
```

测试套件使用 fake / mock，不需要真实 API Key。

---

## English

**Free Vision is a portable Agent Skill that gives text-only AI agents image understanding through currently available zero-cost OpenCode Zen multimodal models.**

Recommended installation flow:

1. Give your AI Agent this repository URL: `https://github.com/BangShou1st/free-vision`
2. Ask it to install the Agent Skill using its native Skill installer when available.
3. Continue setup in the same conversation.
4. Let the Agent configure and validate the OpenCode API key.
5. Use Free Vision naturally by asking the Agent to inspect local images or HTTP/HTTPS image URLs.

The vision model **sees**; the main Agent still **reasons and answers**.
