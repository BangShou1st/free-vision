# Free Vision v0.3.5 Stability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Free Vision installation testing deterministic and host-encoding independent while closing the remaining secret-transport ambiguity observed in Claude/Hermes.

**Architecture:** Keep provider/discovery/runtime behavior unchanged. Centralize machine JSON as unconditional ASCII-safe JSON, add one bundled PNG runtime asset plus a focused self-test command, reuse that asset in doctor, and tighten Agent instructions so shell-visible secret serialization is never treated as secure stdin.

**Tech Stack:** Python 3.10+ standard library, unittest, existing Free Vision CLI/service/provider modules, GitHub Skill distribution.

## Global Constraints

- No host-specific Claude/Hermes code paths.
- Do not change OpenCode Zen provider UA, model discovery, cache policy, or model selection.
- Runtime remains dependency-free outside Python standard library.
- Raw machine JSON may use Unicode escapes; parsed semantic values must remain unchanged.
- The bundled self-test must not depend on exact OCR text matching.
- Never serialize API keys into shell commands, temporary scripts/files, argv, logs, or tool-visible environment assignments.

---

### Task 1: Make machine JSON encoding-independent

**Files:**
- Modify: `free_vision/output.py`
- Test: `tests/test_v035_regressions.py`

**Interfaces:**
- Consumes: existing `write_json(stdout: TextIO, payload: Any, *, pretty: bool = False) -> None`
- Produces: same signature, but always emits ASCII-only valid JSON via `ensure_ascii=True`

- [ ] **Step 1: Write failing tests**

Add tests that pass Chinese, `¥`, and emoji through `write_json`, assert every emitted character is ASCII, then `json.loads` and assert the original Unicode values are recovered. Add integration assertions for vision/configure/doctor CLI output paths using cp936-style streams.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m unittest tests.test_v035_regressions.WindowsJsonContractTests -v
```

Expected: FAIL because current `write_json` emits direct cp936-compatible Chinese instead of ASCII escapes.

- [ ] **Step 3: Implement minimal fix**

Replace encoding detection in `write_json` with one serialization path:

```python
text = json.dumps(payload, ensure_ascii=True, indent=indent) + "\n"
stdout.write(text)
```

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run the same unittest target; expected PASS.

---

### Task 2: Add a bundled runtime self-test image and asset helper

**Files:**
- Create binary: `free_vision/assets/selftest.png`
- Create: `free_vision/assets.py`
- Test: `tests/test_v035_regressions.py`

**Interfaces:**
- Produces: `selftest_image_path() -> Path` and `load_selftest_image() -> bytes`
- Asset must be a valid PNG with dimensions comfortably above the previous rejected 1x1 probe.

- [ ] **Step 1: Write failing tests**

Assert the helper/module and PNG exist, the bytes start with PNG signature, dimensions are greater than 1x1, and `iter_payload_files()` includes `free_vision/assets/selftest.png` automatically because `free_vision/` is recursively copied.

- [ ] **Step 2: Run tests and verify RED**

Expected: FAIL because the asset/helper do not exist.

- [ ] **Step 3: Add deterministic PNG and helper**

Create a high-contrast PNG containing stable simple shapes/text suitable for a general visual description. Implement helper functions using `Path(__file__).resolve().parent / "assets" / "selftest.png"`.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Expected: PASS.

---

### Task 3: Reuse the bundled asset in doctor

**Files:**
- Modify: `free_vision/doctor.py`
- Test: `tests/test_v035_regressions.py`

**Interfaces:**
- Consumes: `load_selftest_image() -> bytes`
- Keeps: `run_doctor(...) -> dict` public signature and existing `VISION_OK` task semantics

- [ ] **Step 1: Write failing test**

Patch `load_selftest_image`/provider boundary and assert doctor constructs its `MediaInput` from bundled asset bytes, not a module-level base64 fixture.

- [ ] **Step 2: Run test and verify RED**

Expected: FAIL while `_PROBE_PNG` base64 constant remains.

- [ ] **Step 3: Implement minimal refactor**

Remove `base64` and `_PROBE_PNG`; import `load_selftest_image`; construct doctor media from the helper bytes.

- [ ] **Step 4: Run targeted doctor tests and verify GREEN**

Expected: PASS with all existing doctor behavior unchanged.

---

### Task 4: Add a dedicated end-to-end self-test command

**Files:**
- Create: `free_vision/selftest.py`
- Create: `free_vision/selftest_cli.py`
- Create: `scripts/selftest.py`
- Modify: `free_vision/install.py`
- Test: `tests/test_v035_regressions.py`

**Interfaces:**
- Produces: `run_selftest(*, task: str = DEFAULT_SELFTEST_TASK, analyzer=analyze) -> dict`
- CLI: `python <SKILL_DIR>/scripts/selftest.py --pretty`
- Uses bundled `selftest_image_path()` and normal `service.analyze` behavior/fallback

- [ ] **Step 1: Write failing tests**

Assert `run_selftest` passes the bundled image path to analyzer, returns normal result data plus `selftest: true`, CLI emits parseable JSON, and installer payload/validation includes `scripts/selftest.py`.

- [ ] **Step 2: Run tests and verify RED**

Expected: FAIL because command/modules do not exist and installer does not require the script.

- [ ] **Step 3: Implement minimal self-test path**

Use existing service `analyze([str(selftest_image_path())], DEFAULT_SELFTEST_TASK)`; convert `VisionResult.to_dict()` and add `selftest: True`. CLI accepts only `--pretty` and writes via shared `write_json`.

Add `selftest.py` to installer runtime script list and required validation set.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Expected: PASS.

---

### Task 5: Tighten Agent install/test and secret-transport contracts

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/usage.md` if current install/testing guidance duplicates the old flow
- Test: `tests/test_v035_regressions.py`

**Interfaces:**
- Agent first-run acceptance becomes: `install -> doctor -> configure if needed -> bundled selftest -> READY`

- [ ] **Step 1: Write failing contract tests**

Assert docs explicitly contain:

- bundled `scripts/selftest.py --pretty` as the default installation acceptance test;
- prohibition on generating Playwright/browser screenshots or temporary images for ordinary Free Vision self-test;
- statement that `python -c` / shell source containing a key is NOT a secure stdin channel even if it later calls `subprocess(..., input=key)`;
- no-secure-channel fallback to local `configure.py set --pretty`.

- [ ] **Step 2: Run tests and verify RED**

Expected: FAIL on missing v0.3.5 contract language.

- [ ] **Step 3: Update documentation minimally**

Replace old generic "real vision test" wording with bundled self-test. Preserve automatic image activation, native-vision precedence, language-following, and installed-source integrity rules.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Expected: PASS.

---

### Task 6: Release metadata and complete verification

**Files:**
- Modify: `free_vision/__init__.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump version to `0.3.5` and document the release**

Record ASCII-safe machine JSON, bundled self-test asset/command, doctor asset reuse, and clarified shell-visible secret prohibition.

- [ ] **Step 2: Run the complete unit suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 3: Run static/package checks**

```bash
python -m compileall -q free_vision scripts
bash -n scripts/vision.sh
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 4: Run local deterministic integration checks**

Verify emitted JSON is ASCII-only and parseable for Unicode payloads. Verify installed payload contains the PNG and `scripts/selftest.py`. Verify `configure.py set --stdin < regular-file` remains rejected before validation.

- [ ] **Step 5: Open PR and merge only after fresh verification**

PR summary must explicitly state that real Claude/Hermes host acceptance is the final external check; do not claim host-level closure before that run.
