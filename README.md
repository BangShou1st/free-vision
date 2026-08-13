# Free Vision 👁️

**让没有视觉能力的 AI Agent，也能自然地看懂图片。**

Free Vision 是一个通用 Agent Skill。它动态发现当前可用的 **OpenCode Zen 免费多模态模型**读取图片，再把视觉证据交还给主 Agent 继续理解、推理和回答。

> **视觉模型负责看，主 Agent 负责想。**

适合网页截图、软件 UI、报错界面、图片文字、图表、流程图、照片和多图比较。

> 🌐 **对话语言跟随用户。** 用户用中文，安装、配置、诊断和最终回答都继续使用中文；其他语言同理。

---

## 🚀 最简单的安装方式

把仓库地址直接交给 Agent：

```text
帮我安装这个 Agent Skill：

https://github.com/BangShou1st/free-vision

如果你支持原生 Skill 安装器，请直接使用它安装。
如果不支持，请临时获取仓库，使用仓库自带的 scripts/install.py 安装到你的 Agent Skills 目录。
安装完成后不要结束，请继续在当前对话里完成 Free Vision 配置和测试。
```

### 给 Agent 的安装规则

有原生 Skill installer 时优先使用原生能力。

没有原生 installer、但有终端/文件系统能力时：

```text
临时 clone / download 仓库
        ↓
找到宿主自己的 Skill 根目录
        ↓
python scripts/install.py --dest <SKILL_ROOT> --force
        ↓
运行 doctor
        ↓
必要时安全配置 Key
        ↓
运行 bundled selftest
        ↓
READY
```

**不要把整个开发仓库直接复制到最终 Skill 目录。** `scripts/install.py` 只复制运行时 payload，不把 `tests/`、开发文档和缓存当成运行时依赖。

正常 installation / setup / doctor / repair 中，宿主 Agent **不应该现场修改 Free Vision 源码**。如果判断是 Free Vision 自身兼容问题，应更新版本或报告问题，而不是在用户机器上 patch `free_vision/*.py`。

---

## 🧪 内置安装验收测试

Free Vision v0.3.5 内置一张固定测试图片。安装和配置完成后，Agent 应直接运行：

```text
python <SKILL_DIR>/scripts/selftest.py --pretty
```

这条命令使用随 Skill 安装的 `free_vision/assets/selftest.png`，并走正常的图片读取、模型发现、Provider 和 fallback 链路。

**普通安装验收不需要 Playwright，也不要临时生成截图或测试图片。** 只有用户明确要求测试某张真实图片/网页时，才额外使用真实输入。

标准首次运行流程固定为：

```text
install
  ↓
doctor
  ↓
configure（仅在需要时）
  ↓
doctor
  ↓
bundled selftest
  ↓
READY
```

---

## 🔑 API Key 配置与安全边界

Free Vision 需要 OpenCode API Key。

如果本机已经有有效配置，Agent 应直接运行 doctor，不重复索要 Key。

### 什么才算安全的对话式配置？

只有当宿主本身能把已经收到的 Secret 直接送进子进程、且**不把 Key 序列化到 shell/tool-visible 内容**时，才允许在聊天里收 Key。

真正的非 TTY pipe 可以使用：

```text
python <SKILL_DIR>/scripts/configure.py set --stdin --pretty
```

有隐藏 PTY / process-input 的宿主可以使用：

```text
python <SKILL_DIR>/scripts/configure.py set --pretty
```

然后通过宿主的隐藏输入机制喂给 `getpass`。

以下做法**不安全，也不允许**：

```text
python -c "key=...; subprocess.run(..., input=key)"
```

即使最后子进程收到的是 stdin，这仍然**不是安全 stdin**：Key 已经进入 shell/tool-visible Python source。PowerShell / Bash 拼接脚本同理。

同样禁止：

- 把 Key 放 argv；
- `echo KEY | ...`；
- 创建临时 Key 文件；
- 创建包含 Key 的临时 Python / PowerShell / Bash 脚本；
- 把 Key 写进日志或工具可见的环境变量赋值命令。

### 宿主没有安全 Secret 通道怎么办？

不要先让用户把 Key 发进聊天再想办法转运。直接让用户本地运行：

```text
python <SKILL_DIR>/scripts/configure.py set --pretty
```

该命令通过 `getpass` 隐藏输入。完成后 Agent 继续：

```text
python <SKILL_DIR>/scripts/doctor.py --pretty
python <SKILL_DIR>/scripts/selftest.py --pretty
```

新 Key 会先做真实视觉验证，成功后才保存；更换 Key 失败时旧 Key 保持不变。

---

## 🖼️ 不需要关键词触发

**图片存在本身就是视觉需求的触发证据。** 不需要用户特意说“看图”“分析图片”“识别截图”。

当主模型本身不能直接读取当前图片时，以下形式都应该自动考虑 Free Vision：

```text
C:\Users\me\Desktop\error.png
./screenshots/page.webp
https://example.com/chart.png
```

支持常见：`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`。URL 没有后缀时，现有 media resolver 仍会按响应内容/文件签名验证。

如果当前主模型/宿主**已经能直接理解当前图片**，则跳过 Free Vision，避免重复视觉处理。

如果用户只发图片/图片路径：

1. 最近上下文有明确问题 → 作为视觉任务；
2. 没有可推断问题 → 默认详细描述关键画面、可见文字、对象和 UI 状态；
3. Free Vision 返回视觉证据后，由主 Agent 继续自然语言回答。

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

脚本内部返回机器可读 JSON。v0.3.5 起，机器 JSON **始终使用 ASCII-safe JSON**；中文、`¥`、emoji 等可能显示为标准 `\uXXXX` 转义，但 Agent `json.loads` 后会还原为原始 Unicode。这样不再依赖 Windows GBK/cp936、UTF-8 或宿主终端的解码方式，也不需要把 `PYTHONIOENCODING=utf-8` 当成正常 workaround。

---

## ✨ 主要能力

- ✅ Windows / macOS / Linux 本地图片
- ✅ HTTP / HTTPS 图片 URL
- ✅ PNG / JPEG / GIF / WebP
- ✅ 单图 / 多图
- ✅ 截图、UI、报错、文字提取、图表、照片
- ✅ 图片存在即可触发，不依赖关键词
- ✅ 主模型已有原生视觉时自动跳过
- ✅ 动态发现当前可用免费视觉模型
- ✅ 模型失败自动 fallback
- ✅ 对话式 Key 设置 / 更换 / 状态 / doctor / clear
- ✅ 新 Key 验证成功后才覆盖旧 Key
- ✅ 内置确定性 end-to-end selftest
- ✅ Python 3.10+
- ✅ 运行时无第三方 Python 依赖

目前暂不包含：本地 OCR/视觉模型、OpenRouter、视频/音频、宿主不暴露附件文件时的通用拦截器、模型代理服务。

---

## 🩺 配置和诊断

```bash
python scripts/configure.py status --pretty
python scripts/doctor.py --pretty
python scripts/selftest.py --pretty
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

常见错误：

| 状态 | 含义 |
|---|---|
| `missing_api_key` | 尚未配置 Key |
| `authentication_failed` | Key 无效或权限不足 |
| `model_discovery_failed` | 模型发现/网络元数据失败 |
| `no_free_vision_models` | 当前没有符合条件的免费视觉模型 |
| `all_models_failed` | 候选存在，但本次 Provider / 模型调用全部失败 |
| `unsafe_secret_transport` | 尝试从普通文件等不安全载体读取 Secret |

Agent 应先诊断，不要把所有失败都归因到 Key，也不要通过修改已安装源码“自愈”。

---

## 🆓 免费模型筛选

候选必须同时满足：

1. 当前存在于 OpenCode Zen 模型列表；
2. models.dev 有对应 OpenCode Provider 元数据；
3. input cost = 0；
4. output cost = 0；
5. 输入模态包含 image；
6. 未 deprecated。

发现结果默认缓存 6 小时。项目已用 `mimo-v2.5-free` 完成 Windows 真实图片回归，但运行时仍动态发现候选，不永久绑定单一模型。

---

# 高级 / 手动使用

默认安装：

```bash
python scripts/install.py
```

OpenCode：

```bash
python scripts/install.py --target opencode
```

Claude Code / Claude Agent SDK：

```bash
python scripts/install.py --target claude
```

自定义 Agent Skills 根目录：

```bash
python scripts/install.py --dest /path/to/agent/skills
```

Windows：

```powershell
python scripts\install.py --dest "D:\AgentX\skills"
```

覆盖旧安装：

```bash
python scripts/install.py --force
```

手动看图：

```powershell
python scripts\vision.py "C:\Users\me\Desktop\test.png" --task "描述这张图片" --pretty
```

多图：

```bash
python scripts/vision.py before.png after.png --task "比较两张图片所有可见差异" --pretty
```

列出当前候选：

```bash
python scripts/vision.py --list-models --pretty
```

---

## 返回协议

成功 JSON 包含 `ok`、`provider`、`model`、`result`、`media`、`attempts`。`result` 是视觉证据，主 Agent 应继续结合用户上下文推理，不应把 raw JSON 直接当最终用户回复。

---

## 🧪 开发验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q free_vision scripts
bash -n scripts/vision.sh
```

测试套件使用 fake/mock，不需要真实 API Key。

---

## English

**Free Vision gives text-only AI agents image understanding through currently available zero-cost OpenCode Zen multimodal models.** Image presence is enough to activate it when native vision is unavailable.

Recommended install flow: native Skill installer when appropriate; otherwise use `python scripts/install.py --dest <SKILL_ROOT> --force`. Normal acceptance is `doctor -> configure if needed -> scripts/selftest.py --pretty -> READY`; do not create Playwright/browser or temporary test images.

Only accept a conversational API key when the host has a genuinely secure hidden secret-to-process channel. `python -c "key=...; subprocess.run(..., input=key)"` is not a secure stdin transport because the secret appears in tool-visible source. Without secure input, use the local hidden `configure.py set --pretty` prompt.
