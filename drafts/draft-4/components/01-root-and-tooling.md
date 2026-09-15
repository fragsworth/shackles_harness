# 01 — Root files and tooling

Everything at the harness root and repository root that is neither source, docs, tests nor an owner spec file. None of these files is charged (they are outside the living paths) and none is editable by agents except as noted.

## 1.1 `harness/pyproject.toml`

**Owns:** package identity, dependencies, pytest configuration. **Depends on:** nothing. **Depended on by:** CI, `scripts/check.sh`, every developer install, the runner's own `verify` step (which runs pytest in a worktree using this file's config).

Contents to specify:
- `[project]` name `shackles`, version `0.1.0`, `requires-python >= 3.11`, dependencies: `PyYAML >= 6` only. Optional group `test`: `pytest >= 8`. (JC-09)
- `[tool.setuptools]` src layout: `package-dir = {"" = "src"}`, packages `shackles`, `shackles.commands`, `shackles.plumbing`; package data: `shackles/plumbing/templates/*.txt`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = "-q -m 'not live' -p no:cacheprovider"`, markers: `live: runs real agents; opt in with -m live and SHACKLES_LIVE=1`.
- No build step is needed for development: `python src/run.py` works from a checkout because `run.py` puts its own directory on `sys.path`.

## 1.2 `harness/.gitignore`

Lines: `/OWNER.log`, `/local.yaml`, `/.worktrees/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `/.claude/settings.local.json`. Anchored patterns so the round folder's `OWNER.log` copy is *not* ignored. (JC-10)

## 1.3 `harness/.claude/settings.json` (committed, static)

**Owns:** the prompt hook registration. **Depended on by:** `ownerlog.py` (needs the log to exist), `doctor.py` (checks the hook is registered).

Content: a `hooks` map with one `UserPromptSubmit` entry whose command is `python3 "$CLAUDE_PROJECT_DIR"/src/hooks/owner_log.py` (falling back to a relative `src/hooks/owner_log.py` when the variable is unset — the hook script itself locates the harness root from its own file path, so cwd does not matter). No other settings. Permissions are left to the owner's user settings. (JC-11)

## 1.4 `harness/.claude/agents/*.md` (generated, committed)

Produced by `agentdefs.py` ([04]) from `subAgents.yaml`; two files per rung: `shackles-<rung>.md` and `shackles-<rung>-gate.md`. They are committed so a fresh clone has them at session start; `doctor --check` and `tests/test_agent_defs.py` fail when they are stale. See [04] §4.5 for the exact content.

## 1.5 `harness/scripts/check.sh`

**Owns:** the one-line local/CI check. Runs, from the harness root: `python src/run.py doctor --check --offline` then `python -m pytest`. Exit status is the first failure. No other scripts exist; everything else is a runner command.

## 1.6 `.github/workflows/harness.yml` (repository root)

**Owns:** CI. Triggers on push and pull request. One job on `ubuntu-latest`: checkout with full history (`fetch-depth: 0`, so `spec-drift` can diff against the accepted commit), set up Python 3.12, `pip install -e "harness[test]"`, run `harness/scripts/check.sh` with working directory `harness`. Live probes never run in CI. (JC-12)

## 1.7 `harness/archives/rounds/.gitkeep`

Keeps the archives folder present on main before any round has landed. `archivesPath` and `roundPaths.folder` from `project.yaml` decide the real locations; if the owner changes them, `doctor` reports the placeholder as orphaned (warning only).

## 1.8 `harness/spec.baseline.json`, `harness/local.yaml`, `harness/OWNER.log`, `harness/.worktrees/`

Owned by [03] `specfiles.py`, [03] `localcfg.py`, [08] hook, [06] gitops respectively. Listed here only so the root inventory is complete. `INDEX.md` and `README.md` are documented in [09].

## 1.9 What agents may touch here

Nothing, with one exception: the CLEANUP step's declared paths include `INDEX.md` and `README.md` at the harness root (uncharged, outside living paths) so routing and the readme can follow structural changes made in the round. (JC-13) Any other change under the root, `.claude/`, `scripts/`, `pyproject.toml` or `spec.baseline.json` in an attempt's diff is a stray and is reverted by [06] checks.
