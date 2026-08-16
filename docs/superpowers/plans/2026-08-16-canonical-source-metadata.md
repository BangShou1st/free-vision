# Canonical Source Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every installed Free Vision Skill self-identify its canonical GitHub source and update branch, while synchronizing the release version to 0.3.10.

**Architecture:** Keep source discovery declarative. A root `source.json` is copied into the runtime payload; `SKILL.md` gives the same rule to Agents in natural language; installer output surfaces the canonical URL. No network self-updater is added.

**Tech Stack:** Python 3.10+, standard library, unittest, Markdown, JSON.

## Global Constraints

- Canonical repository: `https://github.com/BangShou1st/free-vision`
- Canonical branch: `main`
- Release version: `0.3.10`
- Runtime remains dependency-free.
- Do not change ZCode routing, secret handling, or gateway lifecycle behavior.

---

### Task 1: Lock canonical-source behavior with tests

**Files:**
- Modify: `tests/test_install.py`
- Create: `tests/test_v0310_regressions.py`

**Interfaces:**
- Consumes: `free_vision.install.iter_payload_files`, `free_vision.install.install_skill`, installer `main()` output.
- Produces: regression contract for `source.json`, canonical URL, version sync, and Agent update instructions.

- [ ] **Step 1: Add tests asserting `source.json` is in the runtime payload and copied by installation.**
- [ ] **Step 2: Add release-contract tests asserting repository=`https://github.com/BangShou1st/free-vision`, branch=`main`, version=`0.3.10`, and `free_vision.__version__ == 0.3.10`.**
- [ ] **Step 3: Add documentation contract checking `SKILL.md` contains the canonical URL and explicitly forbids searching/guessing an update source.**
- [ ] **Step 4: Add CLI-output contract checking installer output contains the canonical repository.**
- [ ] **Step 5: Verify these tests fail against the current implementation before production changes.**

### Task 2: Add canonical source metadata to the runtime

**Files:**
- Create: `source.json`
- Modify: `free_vision/install.py`
- Modify: `free_vision/__init__.py`

**Interfaces:**
- Consumes: root source tree and existing runtime payload selection.
- Produces: installed `<SKILL_DIR>/source.json` with `name`, `repository`, `branch`, `version`.

- [ ] **Step 1: Create `source.json` with exact canonical values.**
- [ ] **Step 2: Include `source.json` in `_runtime_roots()` and require it in `_validate_source()`.**
- [ ] **Step 3: Add canonical source constant(s) in installer and print `Source: https://github.com/BangShou1st/free-vision (main)` after install/dry-run.**
- [ ] **Step 4: Bump `free_vision.__version__` to `0.3.10`.**
- [ ] **Step 5: Run targeted install/release tests and confirm green.**

### Task 3: Make update instructions unambiguous

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: canonical metadata contract from Task 2.
- Produces: human and Agent-facing update instructions consistent with `source.json`.

- [ ] **Step 1: Add an `Official source / Update source` section near the top of `SKILL.md`.**
- [ ] **Step 2: State that installed Skill directories are runtime payloads, not Git repositories; Agents must not search the web or infer another repository when updating.**
- [ ] **Step 3: Document update flow: fetch canonical `main` → bundled installer `--force` → for ZCode run `setup` then `status` → refresh/restart host.**
- [ ] **Step 4: Add a prominent official-repository line near the top of `README.md`.**
- [ ] **Step 5: Add `v0.3.10 — 2026-08-16` changelog entry covering multi-image compatibility fallback and canonical update-source metadata.**

### Task 4: Final verification and integration

**Files:** all changed files.

- [ ] **Step 1: Run `python -m unittest discover -s tests -v`.**
- [ ] **Step 2: Run `python -m compileall -q free_vision scripts`.**
- [ ] **Step 3: Run `bash -n scripts/vision.sh` where available.**
- [ ] **Step 4: Check diff for source/version consistency and no secret data.**
- [ ] **Step 5: Open PR to `main`; merge only after verification evidence is available.**