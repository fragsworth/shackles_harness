# 02 — Runner CLI: `src/run.py`, `errors.py`, `commands/*`

The runner is the only program in the harness. `run.py` is deliberately thin: it parses arguments, builds a `Session` (paths + config + optional round), calls one command module, prints one JSON object, maps exceptions to exit codes. Each command module is a short orchestration of lower components and can be rewritten alone.

**Type aliases used below:** `Json = dict[str, object]`; `ts` = ISO-8601 UTC string; `Path` = `pathlib.Path`.

## 2.1 `src/run.py`

**Owns:** argument grammar, dispatch, output/exit-code convention ([00] §0.1). **Depends on:** `shackles.errors`, `shackles.commands.*`, `shackles.paths`. **Depended on by:** the driver, the hook-free tests in [10] via `tests/support/cli.py`, and the rendered prompts (which spell the command for the judgment-call tool and `spawn`).

Functions:
- `main(argv: list[str] | None = None) -> int` — parse, dispatch, print, return exit code. Never raises; converts `HarnessError` to `{"ok": false, ...}` and its `exit_code`, any other exception to exit 1 with `code: "unexpected"` and a traceback on stderr.
- `build_parser() -> argparse.ArgumentParser` — the grammar: global `--root PATH`, `--human`; subcommands listed in 2.3 with their options.
- `dispatch(ns: argparse.Namespace) -> Json` — instantiate `Session` for `ns.root`, look up the command module by name, call its `run(session, ns) -> Json`.
- `emit(result: Json, human: bool) -> None` — print JSON (or the human rendering; the renderer is `render_human(result) -> str`, a generic key/value walker, no per-command formatting).
- `_bootstrap_sys_path() -> None` — put `src/` on `sys.path` so `import shackles` works from a checkout.

Errors: none raised to the caller; `main` returns codes.

## 2.2 `src/shackles/errors.py`

**Owns:** the error taxonomy of [00] §0.2. **Depends on:** nothing. **Depended on by:** every module.

- `class HarnessError(Exception)`: `__init__(self, message: str, *, detail: dict | None = None, exit_code: int = 2)`; attributes `code` (class attribute, kebab-case class name), `message`, `detail`, `exit_code`; `to_json() -> Json` renders `{"code","message","detail"}`.
- Subclasses as listed in [00] §0.2, each a one-line class with its `code` and default `exit_code`.

## 2.3 The `Session` object — `src/shackles/commands/__init__.py`

**Owns:** the per-invocation bundle handed to every command. **Depends on:** `paths`, `config`, `specfiles`, `localcfg`, `state`, `gitops` (lazy). **Depended on by:** all command modules.

- `class Session`: fields `roots: paths.Roots`, `config: config.Config`, `roster: config.AgentRoster`, `round: state.RoundState | None` (loaded lazily from the newest local worktree's STATE.json), `local: localcfg.LocalConfig | None`, `now: Callable[[], ts]` (injectable clock), `git: gitops.Git` (lazy).
  - `Session.open(root: Path | None, *, now: Callable[[], ts] | None = None) -> Session` — resolve roots, load config and roster (raises `ConfigError`, `StepTableError`), do **not** touch git.
  - `require_round(self) -> state.RoundState` — raise `StateError("no active round")` when none.
  - `require_no_round(self) -> None` — raise `StateError("round NNNN is active")` when one exists and is not done/abandoned.
  - `fence(self, message: str) -> None` — commit the round folder in the round worktree and push the branch with lease ([06] gitops `fence_push`); raises `FenceError`.
- `COMMANDS: dict[str, ModuleType]` — name → module; `run.py` reads it. Every command module exposes `add_arguments(p: argparse.ArgumentParser) -> None` and `run(session: Session, ns: argparse.Namespace) -> Json`.

## 2.4 Command modules — `src/shackles/commands/`

Each module: `add_arguments`, `run`, private helpers only. Below: purpose, options, effects, result keys, errors.

### `doctor.py` — `run.py doctor [--check] [--offline]`
Runs `doctor.run_all(session, offline)` ([08]); without `--check` also writes `local.yaml` and regenerates agent definitions. Result: `{"ok": errors == 0, "errors": [...], "warnings": [...], "notes": [...], "rendered": [attempt-kind → prompt token count], "defaulted_keys": [...], "unresolved_tokens": [...], "unknown_steps": [...]}`. Exit 2 when errors exist. Never touches a round. Errors: `ConfigError`, `ProseError` are *collected*, not raised.

### `start.py` — `run.py start`
Preflight: `session.require_no_round()`; `doctor.run_all(session, offline=False)` must have no errors (else `RefusedError` with the doctor report as detail); `specfiles.drift(...)` must be empty (`DriftError` with diff); `ownerlog.require_log(...)` (`OwnerLogError`); `config.get("allowUpstream")` must be 0 (`ConfigError`, JC-14). Then: `gitops.claim_round(...)` (CAS; `GitError` if all retries rejected), create worktree, create round folder skeleton and judgment-call headers, `state.new_round(...)`, `ownerlog.write_slice(...)`, render the CHAT-TO-PLAN attempt via `prompts.open_attempt(...)`, `history.append(...)`, `session.fence("start round NNNN")`. Result: the `next`-style `driver` object ([00] §0.12) plus `round`, `branch`, `worktree`. Effects are all-or-nothing: on any failure after the claim, the branch is deleted remotely and the worktree removed (`gitops.unclaim_round`).

### `next_.py` — `run.py next`
Loads the round; `gitops.fence_check` (FenceError); if `open_attempt` is set, returns it again (idempotent); if the round is `paused` or `awaiting-owner`, returns the `owner` object (with a freshly written pause summary file); otherwise calls `advance(session) -> Json` which loops over the step table from the cursor: skip overridden steps and delegated/off checkpoints (recording a `SKIPPED` history entry), perform LANDING inline via `landing.land(...)`, evaluate `limits.before_attempt(...)`, open the appropriate attempt via `prompts.open_attempt(...)`, or return a `checkpoint`/`owner`/`done` object. When the cursor is past CLEANUP but `landing.synced` is false (a `sync` pause that was resumed, or a sync conflict attempt just accepted), `advance` calls `landing.sync(...)` again and ends the round on success. Every branch that changes state ends with `session.fence(...)`. Errors: `StateError`, `FenceError`, `ProseError` (unresolved token at render time — cannot normally happen after start's preflight, but a mid-round spec edit is caught as drift first: `next` calls `specfiles.drift` and pauses with kind `drift` instead of rendering).

### `record.py` — `run.py record --attempt ID --result FILE [--tokens N] [--usage-json FILE] [--duration-seconds S]`
The heart of the loop; the sequence is fixed and each item is a call into another component:
1. load round; fence check; `ID` must equal `open_attempt` (`StateError`).
2. `specfiles.drift` → non-empty: pause `drift`, still commit nothing from the worktree (the diff stays uncommitted for the retry), fence, return.
3. `messages.parse_file(result, kind)` → `INVALID` on `MessageError` (mechanical rejection, the attempt is still recorded).
4. `checks.run_for_attempt(...)` → `CheckReport` (strays reverted, mechanical findings, verify result, suite moves to perform).
5. for gate attempts: `findings.accept_gate_message(...)`; for producer attempts: `findings.check_resolutions(...)`.
6. `judgment.append_from_message(...)` (gates), `state.register_questions(...)` (NEEDS-OWNER), flags → pending.
7. `ledger.book_attempt(...)` with measured usage if `--usage-json`/`--tokens` given, else estimated from prompt size ([07]).
8. `suite.apply_moves(...)` when TESTS-TO-SUITE is accepted.
9. outcome via `state.settle_attempt(...)`: accepted → advance phase (to gate if the gate is on, else to the next step); rejected → new attempt number of the same step or pause `mechanical` when `limits.rejections_exhausted`; NEEDS-OWNER/BLOCKED → pause.
10. `limits.after_record(...)` → may pause (`limit`, `hard-stop`).
11. `gitops.commit_all(...)` of the worktree diff within declared paths plus the round folder (the attempt commit), then `history.append(...)` and `ownerlog.write_slice(...)`.
12. for CLEANUP accepted only: `ledger.book_round_end(...)` on the tree just committed (before = `landing.main_before`, after = the round branch HEAD), `landing.sync(...)` (may open a conflict attempt or pause `sync` instead of ending), and when synced `state.end_round("done")` plus worktree removal.
13. a final commit of `STATE.json`/`HISTORY.md` if they changed after step 11, and `session.fence(...)`.
Result: `{"attempt", "status", "accepted", "strays", "mechanical", "spend_usd", "spend_source", "next_hint": "next"|"owner"|"done", "pause": ...}`. Errors: `StateError`, `FenceError`, `UsageError` (unreadable result file path), `GitError`.

### `owner.py` — `run.py owner --decision KIND --quote TEXT [--through STEP] [--targets A,B] [--question N] [--limit KEY --value V] [--reason TEXT]`
`KIND ∈ {approve, delegate, delegate-through, override, answer, abandon, revise, resume, raise-limit}`. Verifies the quote (`ownerlog.verify_quote`, `QuoteNotFoundError`), then `decisions.apply(...)` ([05]) which validates the decision against the state and mutates it (`DecisionError`). `abandon` additionally calls `landing.abandon(...)`, `ledger.book_round_end(...)`, `state.end_round("abandoned")`. Records the decision, appends history, fences. Result: `{"decision", "status", "pause", "questions_open": [...], "next_hint"}`.

### `status.py` — `run.py status [--ledger] [--findings] [--decisions]`
Read-only. Result: round summary (id, status, cursor, open attempt, spend, quote, remaining round and project, elapsed active hours and its context cost `lostValuePerHour × hours`, pending flags count, open questions, limits with current counters and overrides, drift status, fence status); optional sections. Works with no round (`{"round": null, "drift": ..., "doctor_hint": ...}`). Never fences.

### `judgment.py` — `run.py judgment --kind defined|undefined --text TEXT`
Run by producers from their worktree (the prompt spells the exact invocation with `--root <worktree harness root>`). Appends one line to the matching round file via `judgment.append_line(...)`; attempt id is `open_attempt`. No fence (the line is committed with the attempt at record). Errors: `StateError` when no attempt is open, `UsageError` on empty text.

### `spawn.py` — `run.py spawn --rung R --prompt-file F --out F [--read-only]`
Run by producers (helpers) and by probes. Enforces `maxSimultaneousSubAgentsPerRound` through `invoke.acquire_slot(...)` (`SpawnError` when full), runs `invoke.CliInvoker` ([08]), writes the final message to `--out`, books a `helper` ledger entry with measured usage under the open attempt, and appends a history line. Errors: `SpawnError`, `ConfigError` (unknown rung or above `maxAgent`).

### `spec_drift.py` — `run.py spec-drift`
Prints `{"drift": bool, "changed": [...], "added": [...], "removed": [...], "diff": str}`; exit 2 when drift exists (so the command doubles as a check). Read-only.

### `accept_spec.py` — `run.py accept-spec (--quote TEXT | --by-owner) [--note TEXT]`
Refuses while a round is active. Runs doctor (must be error-free after the change), rewrites `spec.baseline.json`, regenerates agent definitions and `local.yaml`, commits those files on the main branch in the driver checkout and pushes with lease (`GitError`). Result: the new baseline summary and the doctor report. (JC-15)

## 2.5 Argument-to-component map (for the implementer)

| Command | Reads state | Writes state | Git | Agents |
|---|---|---|---|---|
| doctor | no | no (writes local.yaml, agent defs) | remote probe unless `--offline` | no |
| start | no | creates | claim, worktree, fence | no |
| next | yes | yes | fence; landing merges | no |
| record | yes | yes | commit attempt, fence, verify runs pytest | no |
| owner | yes | yes | fence; abandon merges record | no |
| status | yes | no | fetch (optional) | no |
| judgment | yes | round files only | no | no |
| spawn | yes | ledger | no | runs `claude` |
| spec-drift | no | no | `git show` for the diff | no |
| accept-spec | no | baseline | commit+push main | no |
