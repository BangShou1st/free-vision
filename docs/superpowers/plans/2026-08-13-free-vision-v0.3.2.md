# Free Vision v0.3.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Free Vision install and run like a finished product: no host-side source patching, reliable Zen doctor probing, Windows-safe XDG path resolution, and automatic image-driven activation when the host model itself cannot inspect the image.

**Architecture:** Keep the existing runtime boundaries. Python remains responsible for installation payload, config/cache paths, doctor probing, provider calls, and JSON evidence. Agent behavior remains defined in `SKILL.md`: the host decides whether native vision already covers the image, otherwise invokes Free Vision automatically. No host-specific runtime or provider rewrite is introduced.

**Tech Stack:** Python 3.10+, stdlib only, `unittest`, Markdown Agent Skill contract.

## Global Constraints

- Do not modify the provider architecture or CLI surface.
- Do not add third-party runtime dependencies.
- Do not add Hermes-specific install targets; use existing `--dest` support.
- Normal install/setup/doctor/repair must never instruct the host Agent to patch installed Free Vision source.
- Image presence, not keywords, is sufficient activation evidence when an accessible image exists and the main model cannot inspect it directly.
- If the main model/host already has direct native vision access to the current image, do not invoke Free Vision.
- Keep Free Vision as visual evidence: `user -> main Agent -> Free Vision -> vision model -> text evidence -> main Agent -> user`.
- Release target after verification: `0.3.2`.

---

### Task 1: Replace the incompatible 1x1 doctor probe

**Files:**
- Modify: `free_vision/doctor.py`
- Modify: `tests/test_doctor.py`

**Interfaces:**
- Consumes: existing `run_doctor(...)`, `MediaInput`, `OpenCodeProvider.analyze(...)`.
- Produces: an embedded valid PNG probe with normal dimensions, still passed through `MediaInput("<free-vision-doctor>", "image/png", probe)`.

- [ ] **Step 1: Write failing tests**

Add tests that parse the embedded PNG IHDR and assert width/height are greater than 1, and that `run_doctor` passes those bytes to the provider factory without external file dependencies.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_doctor -v`

Expected: the new dimension test fails because the current probe is `1x1`.

- [ ] **Step 3: Implement the minimal fix**

Replace only `_PROBE_PNG` and its comment with a small, known-good embedded PNG of normal dimensions. Keep `_PROBE_TASK` unchanged and do not alter doctor control flow.

- [ ] **Step 4: Verify GREEN**

Run: `python -m unittest tests.test_doctor -v`

Expected: all doctor tests pass.

---

### Task 2: Make XDG config/cache paths lazily fall back to `Path.home()`

**Files:**
- Modify: `free_vision/config.py`
- Modify: `free_vision/discovery.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_discovery.py`

**Interfaces:**
- Consumes: existing `config_path() -> Path`, `cache_path() -> Path`.
- Produces: the same paths as before, but `Path.home()` is called only when the matching XDG variable is absent/empty.

- [ ] **Step 1: Write failing tests**

Use `patch.dict(os.environ, {"XDG_CONFIG_HOME": td}, clear=True)` and patch `pathlib.Path.home` to raise if called; assert `config_path()` still resolves under `td`. Add the corresponding `XDG_CACHE_HOME` test for `cache_path()`.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_config tests.test_discovery -v`

Expected: the new tests fail because the current `dict.get(..., Path.home() / ...)` eagerly evaluates `Path.home()`.

- [ ] **Step 3: Implement the minimal fix**

Use explicit branching:

```python
configured = os.environ.get("XDG_CONFIG_HOME")
base = Path(configured) if configured else Path.home() / ".config"
```

and the equivalent for `XDG_CACHE_HOME` / `.cache`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m unittest tests.test_config tests.test_discovery -v`

Expected: all tests pass.

---

### Task 3: Lock down installation and image-driven Agent behavior

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `tests/test_install.py`

**Interfaces:**
- Consumes: existing `scripts/install.py --dest <SKILL_ROOT> --force` and runtime payload filtering in `free_vision/install.py`.
- Produces: a documented installation/activation contract for generic Agents.

- [ ] **Step 1: Write failing contract tests**

Extend `tests/test_install.py` with small static assertions over repository `README.md` and `SKILL.md` that require these behaviors:

1. no-native-installer fallback explicitly prefers `scripts/install.py --dest` rather than copying the full repository;
2. normal install/setup/doctor/repair must not modify installed Free Vision source;
3. image attachment/path/URL can activate Free Vision without keywords;
4. native host/model vision takes precedence and skips Free Vision;
5. an image-only turn uses recent context, otherwise defaults to useful visual description/text/UI extraction.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_install -v`

Expected: at least the new activation/no-source-patching contract assertions fail against v0.3.1 docs.

- [ ] **Step 3: Implement the minimal documentation contract**

Update `SKILL.md` with a high-priority automatic activation section and a source-integrity rule. Update `README.md` so GitHub fallback installation explicitly runs the bundled installer with the host's Skill root and describes the simple user flow.

Do not add a Python "detect whether my LLM is multimodal" API; the host Agent must decide whether it already has direct image access.

- [ ] **Step 4: Verify GREEN**

Run: `python -m unittest tests.test_install -v`

Expected: all install/contract tests pass.

---

### Task 4: Full verification and release metadata

**Files:**
- Modify: `free_vision/__init__.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: release metadata `0.3.2` after all functional tests are green.

- [ ] **Step 1: Run the complete suite before version bump**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run static/runtime checks**

Run:

```bash
python -m compileall -q free_vision scripts
bash -n scripts/vision.sh
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Update release metadata**

Set `free_vision.__version__ = "0.3.2"` and prepend a `v0.3.2` changelog section covering doctor probe compatibility, lazy Windows/XDG fallback, installer/source-integrity behavior, and image-driven activation.

- [ ] **Step 4: Re-run complete verification**

Repeat the complete unittest suite, compileall, shell syntax, and diff check after the version/changelog edits.

- [ ] **Step 5: Publish branch for review**

Push/update `agent/v0.3.2-ux-hardening`, compare it to `main`, and only merge/release after verification evidence is fresh. Real host acceptance remains: clean Agent session -> GitHub install -> no source patching -> doctor passes -> image path without vision keyword automatically invokes Free Vision when native vision is unavailable.
