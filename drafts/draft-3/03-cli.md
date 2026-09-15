# 03 — CLI surface: `run.py`, `commands.py`, `errors.py`, `paths.py`

## `src/run.py` — the entry point

**Owns:** the argparse tree, the `--json` / `--root` global options, mapping exceptions
to exit codes, printing. **Depends on:** `commands`, `errors`. **Depended on by:**
nobody in `src/` (AGENTS.md names it; the driver and agents call it; tests call it via
subprocess in `test_cli.py`).

Invocation: `python src/run.py [--root PATH] [--json] <command> [args]` from the harness
root. `--root` overrides root discovery (tests use it); `--json` makes the command print
exactly one JSON object on stdout (human text goes to stderr).

Functions:

- `build_parser() -> argparse.ArgumentParser` — builds the parser with one subparser per
  command by calling `commands.register(subparsers)`.
- `main(argv: list[str] | None = None) -> int` — parses, resolves the root
  (`paths.harness_root(args.root)`), calls the command's `run(args) -> CommandResult`,
  prints, returns the exit code. Catches `errors.HarnessError` (prints `code: message`,
  returns its exit code) and `KeyboardInterrupt` (returns 130). Any other exception is
  re-raised only with `--debug`; otherwise printed as `INTERNAL: <type>: <msg>` with exit 1.
- `print_result(result: CommandResult, as_json: bool) -> None` — writes the human block
  or the JSON object.

Commands (name → module function in `commands.py`; details in the linked file):

| command | purpose | file |
|---|---|---|
| `install [--python EXE] [--claude-dir PATH]` | generate derivatives, write local.yaml | 15 |
| `doctor [--offline] [--round NNNN]` | diagnose; exit 3 when errors exist | 15 |
| `spec status|diff|accept` | the drift guard | 04 |
| `start --quote TEXT` | claim a round | 08 |
| `next` | prepare the next action | 10 |
| `record STEP [--attempt N] [--decision D] [--through STEP] [--override LIST] [--quote TEXT] [--input-tokens N] [--output-tokens N] [--cache-read-tokens N] [--cache-write-tokens N]` | record an attempt or an owner decision | 10 |
| `resume --quote TEXT [--hard-stop-multiple F] [--hard-stop-multiple-individual F] [--extend]` | leave PAUSED | 10 |
| `abandon --quote TEXT` | end the round without landing | 08 |
| `status [--round NNNN]` | human summary of a round | 08 |
| `jc --kind defined\|undefined --step STEP --attempt N TEXT` | append a judgment call line [JC-54] | 14 |
| `ledger [--round NNNN]` | show the round's ledger | 13 |
| `owner-log show\|verify TEXT` | inspect the log, test a quote | 14 |
| `index --check\|--write` | INDEX.md | 15 |
| `prune` | delete local worktrees of finished rounds | 08 |

## `src/commands.py` — glue

**Owns:** one `cmd_<name>(root: Path, args: Namespace) -> CommandResult` per command,
each a few lines: build the objects the domain module needs, call it, wrap the result.
**Depends on:** every domain module it dispatches to (`install`, `doctor`, `specfiles`,
`rounds`, `next_action`, `recording`, `pauses`, `judgment_calls`, `ledger`,
`ownerlog`, `index`), plus `paths`, `config`. **Depended on by:** `run.py`.

- `CommandResult` (dataclass): `text: str` (human block), `data: dict` (JSON form),
  `exit_code: int = 0`.
- `register(subparsers) -> None` — adds every subparser with its arguments and sets
  `func=cmd_<name>`.
- `cmd_install(root, args)`, `cmd_doctor(root, args)`, `cmd_spec(root, args)`,
  `cmd_start(root, args)`, `cmd_next(root, args)`, `cmd_record(root, args)`,
  `cmd_resume(root, args)`, `cmd_abandon(root, args)`, `cmd_status(root, args)`,
  `cmd_jc(root, args)`, `cmd_ledger(root, args)`, `cmd_owner_log(root, args)`,
  `cmd_index(root, args)`, `cmd_prune(root, args)` — each `-> CommandResult`; each may
  raise the domain module's `HarnessError`s unchanged.
- `load_world(root: Path) -> World` — the one shared helper: loads `ProjectConfig`,
  `AgentsConfig`, the `Repo`, the `RoundPaths` factory and the `Prose` bundle into a
  small dataclass `World(root, project, agents, repo, prose)`. Raises
  `errors.RefusedError` if config is invalid. Commands that must not read config
  (`install`, `spec`) do not call it.
- `parse_token_flags(args) -> Usage | None` — turns the four `--*-tokens` flags into a
  `ledger.Usage` or `None` when none were given. Raises `errors.UsageError` if only some
  were given.

## `src/errors.py` — exceptions and exit codes

**Owns:** the exception hierarchy. **Depends on:** nothing. **Depended on by:** every
module.

- `class HarnessError(Exception)` — fields `code: str` (SCREAMING_SNAKE), `message:
  str`, `exit_code: int = 1`, `details: dict = {}`; `__str__` returns `code: message`.
- `class UsageError(HarnessError)` — exit 2; bad flags or arguments.
- `class RefusedError(HarnessError)` — exit 3; a precondition failed (drift, stale
  derivatives, missing log, lint failure, wrong status for the command, active round).
- `class FenceError(HarnessError)` — exit 4; the lease push was rejected.
- `class InvalidError(HarnessError)` — exit 5; a result, artifact or findings file was
  rejected; the attempt must be re-run.
- `class ConfigError(RefusedError)` — code `CONFIG`; unknown or bad config key.
- `class LintError(RefusedError)` — code `LINT`; step table vs spec data mismatch.
- `class DriftError(RefusedError)` — code `SPEC_DRIFT`; carries `details["files"]`.
- `class RenderError(RefusedError)` — code `RENDER`; unresolved or cyclic token.
- `class GitError(HarnessError)` — exit 1; a git command failed; carries the command
  and stderr.
- `exit_code_for(exc: BaseException) -> int` — the mapping used by `run.py`.

## `src/paths.py` — where things are

**Owns:** root discovery and every path derivation from `roundPaths`. **Depends on:**
`config` (for the `RoundPathsConfig` values), `errors`. **Depended on by:** almost
every module that touches files; they receive a `RoundPaths` object rather than
computing paths.

- `harness_root(override: str | None = None) -> Path` — the override if given (must
  contain `project.yaml`), else `Path(__file__).resolve().parent.parent`. Raises
  `RefusedError("NO_ROOT")` if `project.yaml` is absent there.
- `repo_root(harness: Path) -> Path` — the parent directory that contains `spec.yaml`;
  walks up at most 5 levels. Raises `RefusedError("NO_SPEC_YAML")`.
- `worktree_dir(repo: Path, round_id: str) -> Path` — `<repo>/.worktrees/round-<id>`.
- `worktree_harness(repo: Path, harness: Path, round_id: str) -> Path` — the harness
  root inside the worktree (same relative position as `harness` under `repo`).
- `class RoundPaths` — constructed with `(harness_root: Path, cfg: RoundPathsConfig,
  round_id: str)`; every attribute is an absolute `Path` inside the given harness root
  (main checkout or worktree, whichever root was passed):
  `folder`, `plan`, `agents_plan`, `spec`, `spec_prose`, `suite`, `postmortem`,
  `state`, `history`, `owner_log`, `prompts_dir`, `results_dir`, `findings_dir`,
  `tests_archive`, `jc_defined`, `jc_undefined`;
  `prompt(step: str, attempt: int, gate: bool = False) -> Path`,
  `result(step: str, attempt: int) -> Path`, `findings(step: str, attempt: int) -> Path`,
  `verify_log(step: str, attempt: int) -> Path` (`RESULTS/<STEP>-<n>.verify.txt`),
  `diff_file(step: str, attempt: int) -> Path` (`PROMPTS/<STEP>-<n>.diff`),
  `relative(p: Path) -> str` (path relative to the harness root, posix form),
  `artifact_by_key(key: str) -> Path` (raises `KeyError` for unknown keys),
  `all_dirs() -> list[Path]` (the folders `start` must create).
- `round_folder_name(cfg: RoundPathsConfig, round_id: str) -> str` — substitutes the
  literal `NNNN` in `roundPaths.folder` with the id. Raises `ConfigError` if the pattern
  has no `NNNN`.
- `is_under(path: Path, roots: list[Path]) -> bool` — helper used by `checks`.
- `to_posix_rel(path: Path, root: Path) -> str`.
