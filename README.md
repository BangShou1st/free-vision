# Free Vision 👁️

**让没有视觉能力的 AI Agent，也能自然地看懂图片。**

Free Vision 是一个通用 Agent Skill。它通过当前可用的 **OpenCode Zen 免费多模态模型**读取图片，再把视觉结果交还给主 Agent 继续理解、推理和回答。

> **视觉模型负责看，主 Agent 负责想。**

你可以用它处理网页截图、软件 UI、报错界面、图片文字、图表、流程图、照片和多图比较。

> 🌐 **对话语言跟随用户。** 你用中文和 Agent 对话，安装、配置、诊断和最终结果就应该继续用中文；其他语言同理。

---

## 🚀 最简单的安装方式

直接把仓库地址发给你的 AI Agent：

```text
帮我安装这个 Agent Skill：

https://github.com/BangShou1st/free-vision

如果你支持原生 Skill 安装器，请直接使用它安装。
如果不支持，请临时获取仓库，使用仓库自带的 scripts/install.py 安装到你的 Agent Skills 目录。
安装完成后不要结束，请继续在当前对话里完成 Free Vision 配置和测试。
```

### 给 Agent 的安装规则

如果宿主有原生 Skill installer，优先用原生 installer。

如果宿主没有原生 installer，但有终端 / 文件系统能力，应当：

```text
临时 clone / download 仓库
        ↓
找到宿主自己的 Skill 根目录
        ↓
python scripts/install.py --dest <SKILL_ROOT> --force
        ↓
安装完成后删除临时仓库（可选）
        ↓
运行 doctor
```

**不要把整个开发仓库直接复制到最终 Skill 目录。** `scripts/install.py` 会只复制运行时需要的 Skill payload，不会把 `tests/`、开发文档、缓存文件等当成运行时依赖。

同时，正常的 installation / setup / doctor / repair 流程中，宿主 Agent **不应该现场修改 Free Vision 源码**。如果判断是 Free Vision 本身的兼容性问题，应提示更新版本或报告问题，而不是在用户机器上临时 patch `free_vision/*.py`。

---

## 🔑 首次配置

Free Vision 需要一个 OpenCode API Key。

如果本机已经有有效配置，Agent 应直接运行诊断，不重复索要 Key。

如果没有配置，Agent 会说明 Key 会进入当前对话上下文，然后要求你在**下一条消息单独发送 Key**。收到后，它会通过 stdin 调用：

```text
python <SKILL_DIR>/scripts/configure.py set --stdin --pretty
```

配置流程会先进行真实视觉验证，验证成功后才保存 Key。Key 不会作为命令行参数传递，也不会出现在 Free Vision 的 JSON 输出中。

如果你不想把 Key 发进聊天上下文，也可以在终端运行：

```bash
python scripts/configure.py set
```

---

## 🖼️ 安装后不需要“关键词触发”

Free Vision v0.3.2 的规则是：**图片存在本身就可以触发视觉能力。**

不需要特意说：

```text
看图
分析图片
识别截图
inspect image
```

只要当前主模型不能直接看这张图片，下面这些形式都应该让 Agent 自动考虑 Free Vision：

```text
C:\Users\me\Desktop\error.png
```

```text
./screenshots/page.webp
```

```text
https://example.com/chart.png
```

如果宿主把图片附件暴露成可访问的本地路径或 URL，也可以直接调用 Free Vision。

支持的常见图片类型：

```text
.png
.jpg
.jpeg
.gif
.webp
```

后缀只用于快速判断；最终输入仍由 Free Vision 按图片字节和格式做验证。

### 主模型本身已经能看图怎么办？

如果当前主模型 / 宿主**已经能直接访问并理解当前图片**，就不需要调用 Free Vision。

Free Vision 的定位是补足视觉缺口，而不是让已经具备视觉能力的模型再绕一层免费视觉模型。

### 用户只发图片，没有任何文字

Agent 应按以下顺序处理：

1. 最近对话里有明确问题 → 把这个问题作为视觉任务；
2. 没有可推断任务 → 默认详细描述关键画面，并提取重要可见文字、对象和 UI 状态；
3. Free Vision 返回视觉证据后，主 Agent 再自然语言回答。

---

## 🧠 工作方式

```text
用户
  ↓
主 Agent
  ↓
当前任务包含 / 引用了图片
  ↓
主模型自己能直接看？
  ├─ 是 → 主模型直接处理
  └─ 否
      ↓
  Free Vision
      ↓
动态发现当前免费视觉模型
      ↓
视觉模型读取图片
      ↓
返回文本视觉证据
      ↓
主 Agent 继续分析 / 推理
      ↓
自然语言回答用户
```

Free Vision 的脚本内部返回机器可读 JSON，但正常用户不应该看到 raw JSON。

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
- ✅ 图片存在即可触发，不依赖“看图”等关键词
- ✅ 主模型已有原生视觉时自动跳过 Free Vision
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
- 宿主不给文件路径时的通用附件拦截器
- 模型代理服务

---

## 🩺 配置和诊断

查看配置：

```bash
python scripts/configure.py status --pretty
```

完整诊断：

```bash
python scripts/doctor.py --pretty
```

更换 Key：

```text
换一下 Free Vision 的 API Key
```

删除本地 Key：

```bash
python scripts/configure.py clear --pretty
```

运行时 Key 优先级：

```text
OPENCODE_API_KEY
FREE_VISION_OPENCODE_API_KEY
Free Vision 本地配置文件
```

常见错误含义：

| 状态 | 含义 |
|---|---|
| `missing_api_key` | 还没有配置 Key |
| `authentication_failed` | 当前 Key 无效或没有权限 |
| `model_discovery_failed` | 当前无法完成模型发现 |
| `no_free_vision_models` | 当前没有符合条件的免费视觉模型 |
| `all_models_failed` | 候选模型存在，但本次 Provider / 模型调用全部失败 |

Agent 应先诊断，不应把所有失败都归因到 API Key，也不应通过修改 Free Vision 源码来“自愈”。

---

## 🆓 免费模型是怎么选的？

Free Vision 不会因为模型名字里有 `free` 就认为它免费。

自动候选必须同时满足：

1. 当前仍存在于 OpenCode Zen 模型列表；
2. models.dev 中存在对应 OpenCode Provider 元数据；
3. `input cost = 0`；
4. `output cost = 0`；
5. 输入模态包含 `image`；
6. 未标记为 deprecated。

发现结果默认缓存 6 小时。

项目真实测试中，`mimo-v2.5-free` 已经完成 Windows 本地图片视觉回归；Free Vision 仍然通过动态发现机制决定当前候选，不永久绑定单一模型。

---

# 高级 / 手动使用

## 手动安装

默认用户级安装：

```bash
python scripts/install.py
```

默认目录：

```text
~/.agents/skills/free-vision/
```

项目级：

```bash
python scripts/install.py --scope project
```

OpenCode 原生目录：

```bash
python scripts/install.py --target opencode
```

Claude Code / Claude Agent SDK：

```bash
python scripts/install.py --target claude
```

自定义 Agent Skills 目录：

```bash
python scripts/install.py --dest /path/to/agent/skills
```

Windows：

```powershell
python scripts\install.py --dest "D:\AgentX\skills"
```

覆盖已有安装：

```bash
python scripts/install.py --force
```

预览但不写入：

```bash
python scripts/install.py --dry-run
```

---

## 手动视觉测试

查看当前候选：

```bash
python scripts/vision.py --list-models --pretty
```

Windows 本地图片：

```powershell
python scripts\vision.py "C:\Users\me\Desktop\test.png" --task "描述这张图片" --pretty
```

图片 URL：

```bash
python scripts/vision.py "https://example.com/image.png" --task "详细分析这张图片" --pretty
```

多图比较：

```bash
python scripts/vision.py before.png after.png --task "比较两张图片所有可见差异" --pretty
```

---

## 返回协议

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

`result` 是给主 Agent 的视觉证据。主 Agent 应继续结合用户上下文推理并输出最终自然语言答案。

---

## 🔐 安全说明

- API Key 不会出现在 Free Vision 的结果 JSON 中。
- Agent 配置 Key 时应通过 stdin 传入，不放进命令行参数。
- 更换 Key 时，新 Key 验证成功后才替换旧 Key。
- 远程图片只接受 `http://` 和 `https://`。
- 默认单张图片大小限制 20 MiB。
- 支持 PNG、JPEG、GIF、WebP 文件签名验证。
- 当前没有付费模型 fallback。
- 如果选择在聊天中发送 API Key，请注意 Key 会进入当前对话上下文。

---

## 🧪 开发与测试

```bash
python -m unittest discover -s tests -v
python -m compileall -q free_vision scripts
bash -n scripts/vision.sh
```

测试套件使用 fake / mock，不需要真实 API Key。

---

## English

**Free Vision gives text-only AI agents image understanding through currently available zero-cost OpenCode Zen multimodal models.**

Image presence is enough to activate the Skill when the host/model cannot already inspect the image directly; explicit “analyze image” keywords are not required. If native vision is already available for that image, Free Vision should be skipped.

Recommended install flow: use the host's native Skill installer when available; otherwise clone/download the repository temporarily and run `python scripts/install.py --dest <SKILL_ROOT> --force`. Do not copy the full development repository into the final Skill directory, and do not patch installed Free Vision source during normal setup or repair.
