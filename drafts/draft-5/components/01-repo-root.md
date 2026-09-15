# 01 — Repository root

**Purpose.** The files at the top of the git repository: the owner's two spec files, and
the scaffolding that lets a fresh clone install, test and run the harness.

**Owns.** `spec.yaml` and `SPEC.md` (owner-owned, never written by the harness),
`README.md`, `.gitignore`, `.github/workflows/ci.yml`, the gitignored `.worktrees/`.

**Depends on.** Nothing in `src/`. CI depends on `harness/pyproject.toml` (02) and the
CLI (03).

**Depended on by.** `shackles/paths.py` (04) locates the repo root by walking up from
`src/` until it finds `spec.yaml`. Everything else addresses paths through 04.

## Files

### `spec.yaml` — OWNER
Lists the spec files, relative to itself; globs allowed (`harness/locked_prose/*`). The
runner reads it only through `specfiles.list_spec_files` (04). Never modified by code.

### `SPEC.md` — OWNER
The implied spec and the architecture-feature list. Read by humans; hashed by the guard.

### `README.md`
Not in living paths, not charged. Sections, in order:
1. One paragraph: what the harness is (quote `project.yaml: vision` by reference, not copy).
2. Requirements: Python ≥ 3.11, git ≥ 2.38 (`merge-tree --write-tree`), a git remote,
   Claude Code with hooks enabled.
3. Install: `cd harness && pip install -e .` (or `pip install pyyaml pytest`).
4. First run: `python3 src/run.py setup`, restart the Claude Code session in `harness/`,
   `python3 src/run.py doctor`, `python3 src/run.py start`.
5. Command table (one line each; the authority is `cli.py` in 03).
6. Where things are: link to `harness/INDEX.md` and `harness/docs/PROCESS.md`.
7. Spec-file changes: what the guard does, `accept-spec`.
8. Running tests: `pytest harness/tests -q`; probes: `SHACKLES_PROBES=1 pytest harness/tests/probes`.

### `.gitignore`
```
harness/OWNER.log
harness/local.yaml
.worktrees/
__pycache__/
.pytest_cache/
*.pyc
```
`harness/.claude/agents/` is **committed** (JC-10); `harness/INDEX.md` is committed
(JC-25); `harness/archives/` is committed.

### `.github/workflows/ci.yml`
One job, `ubuntu-latest`, Python 3.11. Steps: checkout (full history, `fetch-depth: 0`,
because tests build bare remotes from the checkout), `pip install -e harness`,
`python3 harness/src/run.py doctor --offline --json` (exit code must be 0; drift is
reported as an error by doctor only when `--strict` is passed, and CI passes `--strict`
so an unaccepted spec edit fails CI exactly like the guard test), then
`pytest harness/tests -q --ignore=harness/tests/probes`. Probes never run in CI
(they need credentials and money).

### `.worktrees/` (gitignored)
`round-NNNN/` per round, created by `gitops.worktree_add` (07). Removed by CLEANUP after
the sync succeeds, or left in place when a round is paused or abandoned so its contents
can be inspected; `run.py status` lists stale worktrees.

## Invariants
- No file at the repo root is read by the runner except `spec.yaml` (through 04).
- The owner files are byte-identical to their baseline snapshot whenever a round runs.

## Covered by
- `tests/test_spec_guard.py` (drift), `tests/test_paths.py::test_repo_root_found_from_src`.
- CI itself is verified by `tests/test_repo_scaffold.py` (the workflow file parses as YAML,
  names the two commands above, ignores `probes`; `.gitignore` contains the five entries).
