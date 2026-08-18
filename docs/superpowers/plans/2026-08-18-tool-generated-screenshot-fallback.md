# Tool-Generated Screenshot Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach Free Vision's Agent Skill contract to automatically consume relevant tool-generated screenshots when textual/structured tool output is empty or insufficient, while preserving the user's original task.

**Architecture:** Keep the change declarative in `SKILL.md` and documentation. No host-specific browser parser or daemon is added; the Agent recognizes screenshot paths already exposed in tool results and invokes the existing `scripts/vision.py` path. Version metadata advances to 0.3.11.

**Tech Stack:** Markdown, JSON, Python 3.10+ unittest contracts.

## Global Constraints

- Canonical repository remains `https://github.com/BangShou1st/free-vision` on `main`.
- Release version becomes `0.3.11`.
- Preserve native-vision precedence.
- Preserve the user's original task when calling Free Vision.
- Do not change ZCode gateway routing, provider behavior, secret handling, installer mechanics, or media resolver behavior.

---

### Task 1: Lock the Agent behavior with regression contracts

**Files:**
- Create: `tests/test_v0311_regressions.py`

**Interfaces:**
- Consumes: `SKILL.md`, `README.md`, `source.json`, `free_vision.__version__`.
- Produces: release and behavior contracts for tool-result screenshots.

- [ ] Add a test requiring `SKILL.md` to mention tool results/current task, tool-generated screenshots, `(no output)`, structured content, and screenshot paths.
- [ ] Add a test requiring the Skill to preserve the user's original task and avoid replacing it with a generic description prompt.
- [ ] Add a test requiring multiple tool-generated screenshots to be passed together in task order.
- [ ] Add a release metadata test requiring `0.3.11` in both `source.json` and `free_vision.__version__`.
- [ ] Run the new test against the pre-change branch state and confirm failure.

### Task 2: Implement the Skill behavior and version bump

**Files:**
- Modify: `SKILL.md`
- Modify: `free_vision/__init__.py`
- Modify: `source.json`

- [ ] Broaden the frontmatter/activation rule from only the current user turn to the current user turn or relevant tool results in the current task.
- [ ] Add a `Tool-generated screenshot fallback` section describing browser/Playwright/screenshot artifacts, empty or insufficient structured output, accessible screenshot paths, original-task preservation, multi-screenshot handling, and native-vision precedence.
- [ ] Bump runtime and source metadata to `0.3.11`.
- [ ] Run targeted regression tests and confirm green.

### Task 3: Document the behavior for humans

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] Add a concise README capability note and example flow for browser `(no output)` plus a saved screenshot path.
- [ ] Add `v0.3.11 — 2026-08-18` changelog entry describing the new fallback and verification scope.
- [ ] Keep documentation consistent with the Skill contract and avoid claiming host-level interception that does not exist.

### Task 4: Final verification and integration

**Files:** all changed files.

- [ ] Run `python -m unittest discover -s tests -v` when a full checkout is available.
- [ ] Run `python -m compileall -q free_vision scripts`.
- [ ] Run `bash -n scripts/vision.sh` where available.
- [ ] Review diff for version consistency and unintended changes.
- [ ] Open a PR to `main` and merge only after verification evidence is reviewed.