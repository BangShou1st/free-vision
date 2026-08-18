# Tool-Generated Screenshot Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically convert trusted ZCode browser/tool screenshots into visual evidence even when textual/structured tool output is empty, while preserving the user's original task.

**Architecture:** Add a safety-scoped provider-boundary transformation before normal image-url fallback. The gateway only reads real screenshot files under the current user's ZCode artifact tree from tool-result messages, analyzes them with the existing Free Vision service/cache, and appends evidence before forwarding. `SKILL.md` documents the same behavior for Agent-driven fallbacks. Version metadata advances to 0.3.11.

**Tech Stack:** Python 3.10+ standard library, unittest, Markdown, JSON.

## Global Constraints

- Canonical repository remains `https://github.com/BangShou1st/free-vision` on `main`.
- Release version becomes `0.3.11`.
- Preserve the user's original task when analyzing a tool screenshot.
- Automatic gateway reads are restricted to tool-result messages and resolved files under `~/.zcode/cli/artifacts/`.
- Ordinary user text must never authorize local-file reading.
- Preserve existing provider routing, secret handling, media limits, installer behavior, and normal image-url fallback.

---

### Task 1: Lock behavior with regression contracts

**Files:**
- Create: `tests/test_v0311_regressions.py`
- Modify: `tests/test_v0310_regressions.py`

- [x] Add Skill/README contracts for current-task tool results, `(no output)`, `Structured content`, original-task preservation, and multi-screenshot ordering.
- [x] Add gateway tests for trusted artifact transformation and latest preceding user task.
- [x] Add multi-screenshot ordering test.
- [x] Add negative tests proving user-role text and paths outside the artifact root do not trigger analysis.
- [x] Add HTTP integration coverage proving a request with no `image_url` still reaches upstream with appended Free Vision evidence.
- [x] Make the v0.3.10 source metadata contract forward-compatible so later patch versions do not fail merely because the version advanced.

### Task 2: Implement trusted tool-screenshot transformation

**Files:**
- Modify: `free_vision/gateway_transform.py`
- Modify: `free_vision/gateway_handler_request.py`
- Modify: `free_vision/gateway_handler.py`

- [x] Parse fixed `Browser screenshot saved to:` / `Screenshot saved to:` lines from tool-result messages only.
- [x] Require absolute, existing, supported image files whose resolved path remains under the configured/default ZCode artifact root.
- [x] Derive the vision task from the latest preceding user message.
- [x] Reuse the existing analyzer and evidence cache, then append a `[Free Vision visual evidence]` block to the tool result.
- [x] Run this transformation before normal image-url adaptive fallback and forward the transformed request even when it contains no `image_url`.
- [x] Add an optional `artifact_root` injection point to `create_gateway_server()` for deterministic tests while preserving production defaults.

### Task 3: Update Agent behavior and release metadata

**Files:**
- Modify: `SKILL.md`
- Modify: `free_vision/__init__.py`
- Modify: `source.json`

- [x] Broaden activation from only user-turn images to relevant current-task tool-result images.
- [x] Document empty/no-output screenshot fallback, original-task preservation, multiple screenshots, native-vision precedence, and the ZCode local-file safety boundary.
- [x] Bump runtime and source metadata to `0.3.11`.

### Task 4: Document the behavior for humans

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-08-18-tool-screenshot-fallback-design.md`

- [x] Add a README example matching real browser `(no output)` / screenshot / empty `Structured content` output.
- [x] Document the ZCode artifact safety boundary and original-task behavior.
- [x] Add `v0.3.11 — 2026-08-18` changelog entry with verification limitations.
- [x] Align the design document with the provider-boundary implementation.

### Task 5: Final verification and integration

**Files:** all changed files.

- [ ] Inspect the final GitHub diff for syntax/interface/version consistency and unintended changes.
- [ ] Attempt a fresh checkout/full unittest run; if the environment cannot resolve GitHub, record that limitation rather than claiming full test execution.
- [ ] Confirm the PR head is mergeable and has no unexpected CI/status failures.
- [ ] Merge to `main` after verification review.