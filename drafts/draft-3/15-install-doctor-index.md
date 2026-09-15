# 15 — Install, doctor, index: `install.py`, `doctor.py`, `index.py`

## `src/install.py` — generating every derivative

**Owns:** the one command that (re)creates the generated files: agent definitions,
hook settings, `CLAUDE.md`, `INDEX.md`, `local.yaml`, the `.gitignore` entries the
harness needs, and an initial spec baseline when none exists. Idempotent; no
network; no round state. **Depends on:** `agentdefs`, `localstate`, `specfiles`,
`index`, `config` (only `load_agents`; `project.yaml` is validated by `doctor`, not
here, so an owner can install with a temporarily broken project.yaml), `paths`,
`errors`. **Depended on by:** `commands`.

- `InstallReport` (dataclass): `written: list[Path]`, `unchanged: list[Path]`,
  `notes: list[str]`.
- `install(harness_root: Path, python: str = "python", claude_dir: Path | None =
  None, now: str = ...) -> InstallReport` — `claude_dir` defaults to
  `<harness>/.claude` [JC-42]; steps: `agentdefs.generate`; write `CLAUDE.md`
  containing exactly `@AGENTS.md` when absent (never overwrites an existing one)
  [JC-03]; `index.write`; ensure `<repo>/.gitignore` contains the lines of
  `REQUIRED_GITIGNORE` (`.worktrees/`, `harness/OWNER.log` as the harness-relative
  path of `ownerLogPath`, `__pycache__/`, `.pytest_cache/`) — appended, never
  removed; if `local.yaml` has no spec baseline, run `specfiles.accept` and note
  that the first baseline was taken (the owner is told to review with `spec diff`
  before the next edit); write `local.generated` hashes and `installed_at`.
- `check(harness_root: Path, claude_dir: Path | None = None) -> list[str]` — what
  `install` would change (used by `doctor`); empty when everything is fresh.

## `src/doctor.py` — offline diagnosis

**Owns:** the read-only report of everything that can be wrong before a round:
config, lint, every prompt rendered, drift, staleness, hook, log, git. Never writes.
**Depends on:** `config`, `steps`, `prose`, `templates`, `context`, `prompts`,
`specfiles`, `localstate`, `agentdefs`, `ownerlog`, `gitops` (only with network),
`rounds` (preconditions, when a round exists), `tokens`, `paths`, `errors`.
**Depended on by:** `commands`, `test_spec_lint.py` (asserts zero errors on the
real files), `test_doctor.py`.

- `Finding` (dataclass): `level` (`error | warning | info`), `area: str`, `message:
  str`.
- `DoctorReport` (dataclass): `findings: list[Finding]`, `prompts: dict[str, int]`
  (prompt name → tokens), `defaulted_keys: list[str]`, `ok` property (no errors),
  `text() -> str`, `to_dict()`.
- `run(harness_root: Path, offline: bool = False, round_id: str | None = None) ->
  DoctorReport` — areas, each isolated so one failure does not hide the others:
  1. `config`: `load_project`, `load_agents`, `validate_cross`; each `ConfigError`
     is an error; every `defaulted_keys()` entry is an `info` naming key and value.
  2. `lint`: `steps.lint` errors and warnings; `prose.other_files` as errors; a
     `prose.warnings` duplicate heading as warning; malformed `{{ }}` spans as errors.
  3. `render`: `prompts.render_all` with `context.sample_round`; every unresolved
     token is an error `unresolved token {{ ns.KEY }} in <prompt>`; every prompt's
     token count is reported and a `warning` when above `promptWarnTokens`; a prose
     file without the plumbing token is a warning (it will be appended).
  4. `spec`: `specfiles.check_drift`; drift is an error listing the files; a missing
     baseline is an error telling the owner to run `install` or `spec accept`.
  5. `generated`: `agentdefs.staleness`, `install.check`; each entry is an error
     (stale definitions block `start`).
  6. `hook`: `agentdefs.hook_installed`; missing is an error; `OWNER.log` absent or
     empty is a warning (`start` will refuse).
  7. `git` (skipped with `--offline`): `has_remote`, `fetch` reachability; an active
     round's `rounds.preconditions` list when `round_id` is given or one is active.
- `render_prompt(harness_root, step: str, gate: bool) -> str` — one rendered sample
  prompt, for humans (`doctor --show STEP [--gate]`); unresolved tokens are left in
  place and marked.
- Exit code: `doctor` returns 3 when any error exists, 0 otherwise; warnings never
  change the exit code.

## `src/index.py` — `INDEX.md`

**Owns:** generating and checking the one-line-per-file routing index at the harness
root (AGENTS.md says "grep INDEX.md for routing"). **Depends on:** `paths`,
`errors`. **Depended on by:** `install`, `recording` (`finish_round` regenerates it),
`commands` (`index`), `test_index.py`.

Format: a heading line `# INDEX — one line per file; regenerate with: python
src/run.py index --write`, then one line per file: `<path> — <purpose>`, sorted by
path. Covered: every file under `src/`, `docs/`, `tests/` (recursively, excluding
`__pycache__`), the top-level files of the harness root (`AGENTS.md`, `project.yaml`,
`subAgents.yaml`, `local.yaml`, `pyproject.toml`, `CLAUDE.md`), and every file under
`locked_prose/`. Not covered: `archives/`, `.claude/`, `OWNER.log`.

The purpose text is mechanical [JC-43]: for `.py` the first line of the module
docstring; for `.md` the first heading's text without `#`; for `.txt` the first
non-empty line truncated to 100 characters; for `.yaml`/`.toml` the first comment
line without `#`, else the first key; `(no description)` when none is found — and
`--check` reports files with `(no description)` as warnings, not failures.

- `IndexLine` (frozen dataclass): `path: str`, `purpose: str`.
- `collect(harness_root: Path) -> list[IndexLine]`.
- `purpose_of(path: Path) -> str`.
- `render(lines: list[IndexLine]) -> str`.
- `write(harness_root: Path) -> Path`.
- `check(harness_root: Path) -> tuple[bool, list[str]]` — `(up_to_date, diff_lines)`
  comparing the rendered text with the file's content (missing file → not up to date).
