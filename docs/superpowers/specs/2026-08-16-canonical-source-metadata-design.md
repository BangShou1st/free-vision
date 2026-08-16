# Canonical Source Metadata Design

## Goal

Prevent installed Free Vision agents from guessing or web-searching the upstream repository during updates. The canonical repository is `https://github.com/BangShou1st/free-vision`, and installed runtime payloads must retain that fact.

## Design

1. `README.md` shows the official repository prominently for humans.
2. `SKILL.md` contains an explicit update-source section instructing Agents to use only the canonical repository and not infer/search for similarly named repositories.
3. Add runtime file `source.json` with stable machine-readable fields: `name`, `repository`, `branch`, and `version`.
4. `free_vision.install` includes `source.json` in the runtime payload, validates that it exists, and prints the canonical source after installation.
5. Version becomes `0.3.10`; `source.json`, `free_vision.__version__`, and release-contract tests must agree.
6. `CHANGELOG.md` records both the multi-image compatibility fix already merged after v0.3.9 and this canonical-source/update change.

## Update behavior

An installed Skill directory is intentionally not a Git checkout. On an update request, the Agent reads `source.json` or the equivalent explicit `SKILL.md` section, fetches the canonical repository `main`, runs the bundled installer with `--force`, then runs ZCode `setup` and `status` when the target is ZCode.

## Safety and scope

No automatic self-updater is introduced. No secrets or credentials are added to metadata. Existing installer replacement, ZCode gateway lifecycle, and source-integrity rules remain unchanged.

## Verification

Regression tests must verify `source.json` is part of the install payload and copied into installed Skills, its version/repository values are correct, `SKILL.md` contains the canonical URL plus a no-search rule, and installer output exposes the canonical source.