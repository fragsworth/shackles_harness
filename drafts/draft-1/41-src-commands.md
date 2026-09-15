# 41 — src/shackles/commands/ (one module per CLI verb)

Parent: `30-src.md`. Owns the command surface the driver, the hooks and the
tests call. Each module is thin: load settings, load state, call the engine or
a component, print an `Outcome` (`cli.py`). Every command's stdout is one JSON
object (`70-contracts.md`); refusals exit 2 with `{"refused": reason,
"details": {...}}`. Depends on: `engine/` and every component it fronts.
Depended on by: `cli.py`; the driver; `.claude/settings.json` hooks; the stub
driver in tests.

```
commands/
  __init__.py     REGISTRY: the ordered list of command modules
  setup.py        generate local.yaml, agent definitions, hooks
  doctor.py       offline checks; renders every prompt; names problems
  accept_spec.py  rebaseline the spec files
  start.py        claim a new round
  next.py         the next action
  record.py       record an attempt's final message
  owner.py        hand the runner an owner verb with a verbatim quote
  judgment.py     the judgment-call tool for producers
  status.py       where the round is, the ledger, the limits
  hook.py         hook entry points (owner-log)
```

Each module exposes `NAME: str`, `add_arguments(parser) -> None`, `run(args)
-> Outcome`; the signatures below are of `run` after argument parsing.

## setup.py — `run.py setup`

- `run(args) -> Outcome` — discovers paths; writes `.claude/agents/`
  (`agents/definitions.write_all`); merges the hook block
  (`agents/hooks.write_settings`); writes `local.yaml` with the two hashes;
  creates `harness/archives/`, `.worktrees/`, `.verify/` if missing; prints
  `{"agents": [...], "hooksInstalled": true, "local": path, "restartSession":
  bool}`. Idempotent. Refuses when no `spec.yaml` is found.

## doctor.py — `run.py doctor [--offline] [--quiet] [--fix]`

- `run(args) -> Outcome` — collects `problems`, `warnings`, `notes`:
  1. settings load (`LintError` becomes problems), `steps/lint.lint`;
  2. spec drift (`config/spec_files.compute_drift`) -> problem with the diff;
  3. owner log present -> else warning ("start will refuse");
  4. hooks installed, agent definitions not stale -> else warning naming
     `setup` and "restart the session";
  5. **renders every prompt offline**: for every table step, the overview
     prompt and (when the prose exists) the gate prompt, with a synthetic
     `RoundView` (id `0000`, empty plan, zero spend) and a synthetic attempt;
     every unresolved token is a problem naming the file and the token; every
     prose file that no step includes is a warning;
  6. defaulted config keys -> one note each ("defaulted: testPaths =
     ['tests/']"); commented placeholders -> notes; unknown keys -> problems;
  7. git identity, remote reachable (skipped with `--offline`), stale
     worktrees -> warnings;
  8. an open round on disk -> note with its id and phase.
  `--fix` runs `setup` first. `--quiet` prints only problems and warnings, as
  lines (for the SessionStart hook). Exit 2 when any problem.

## accept_spec.py — `run.py accept-spec`

- `run(args) -> Outcome` — refuses when a round is open (accept between
  rounds `[JC-29]`); hashes the current spec files, writes
  `archives/spec-baseline.yaml` with HEAD as `acceptedCommit`, prints the
  files accepted and which changed since the previous baseline. Does not
  commit: the owner commits the accepted baseline with the spec change.

## start.py — `run.py start`

- `run(args) -> Outcome` — in order, each a refusal with reason:
  1. doctor problems (drift, lint, unresolved tokens) -> `refused`;
  2. no owner log -> `refused: "no owner log"`;
  3. an open round in `archives/rounds/*/STATE.json` with `phase != ended`
     -> `refused` naming it (use `next`, or `owner abandon`);
  4. fetch; `next_round_id`; create `round/NNNN` from remote `main`; the
     runner worktree; the round folder with `STATE.json`, `HISTORY.md`, the
     owner-log slice (`refresh` from the local cursor); commit "round NNNN:
     start"; `lease.claim`; update `local.ownerLog.cursor`.
  Prints `{"round": "NNNN", "branch": ..., "baseCommit": ..., "folder": ...}`.

## next.py — `run.py next`

- `run(args) -> Outcome` — loads the open round's state (refuses when none);
  `engine/advance.advance`; saves the state; appends history; commits the
  round folder and fences; prints the `Action`. Idempotent while an attempt is
  open or a pause stands.

## record.py — `run.py record <attempt> [--tokens N] [--result PATH] [--no-follow-up]`

- `run(args) -> Outcome` — the attempt must be the open one (refuses
  otherwise); reads `RESULTS/<attempt>.json` (or `--result` copied there);
  `results.load_result`; dispatches to `attempts.record_producer`,
  `record_gate`, `record_driver` or `landing_step.record_conflict` by role;
  saves, appends history, commits, fences; prints `{"attempt", "status",
  "cost", "notes", "next": "run next"}`. `--tokens` is the Agent tool's
  reported total; absent -> the size estimate (`source: estimated`).
  `--no-follow-up` is accepted only when `stepEndDelivery` is `follow-up` and
  records that the reminder could not be delivered.

## owner.py — `run.py owner <verb> --quote "<verbatim>" [verb args]`

Verbs and arguments: `approve`; `delegate [--through STEP]`; `override
[--step STEP]... [--gate STEP]...`; `answer --n N`; `abandon --reason TEXT`;
`resume`.

- `run(args) -> Outcome` — refreshes the round's owner-log slice; verifies the
  quote (`owner_log.verify_quote`; `QuoteNotFoundError` -> refused, telling
  the driver to quote the owner's actual words); applies the verb via
  `round/approvals.py`; on `abandon` runs `booking.book_abandon`; saves,
  history, commit, fence; prints the new phase and the next verb hint.

## judgment.py — `run.py judgment <defined|undefined> "<one line>" --attempt ID`

- `run(args) -> Outcome` — the attempt must be open and a producer/conflict
  attempt; appends to the matching file inside that attempt's worktree
  (`round/judgment_calls.append`); prints `{"appended": path}`. Never touches
  git: the record commit carries the line.

## status.py — `run.py status [--ledger] [--history N]`

- `run(args) -> Outcome` — prints the round id, phase, pause, current step and
  status, attempts with their status and cost, gate turns, run counters and
  limits left, quote/spend/remaining, project remaining, pending owner items,
  the time-cost note; `--ledger` adds every entry; `--history N` the last N
  HISTORY blocks. Read-only.

## hook.py — `run.py hook owner-log`

- `run(args) -> Outcome` — reads the hook JSON from stdin,
  `agents/hooks.handle_owner_log`; always exits 0 (a failing hook must not
  block the owner's chat); prints nothing to stdout.

## `__init__.py`

- `REGISTRY: list[module]` — the modules above, in the order `setup, doctor,
  accept-spec, start, next, record, owner, judgment, status, hook`; `cli.py`
  builds its parser from this list.
