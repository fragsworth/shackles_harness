# 10 — The `next`/`record` machine: `next_action.py`, `recording.py`, `pauses.py`

These three orchestrate; they call the domain modules and are called only by
`commands`. Every state change follows one pattern: mutate `RoundState` → write
`STATE.json` and `HISTORY.md` (and the round's `OWNER.log` slice) → `add_and_commit`
the round-folder paths (plus the attempt's accepted paths) → `push_lease` with the sha
the state was read at. A `FenceError` leaves the remote authoritative: the local branch
is reset to the remote after the local commit is saved to a backup branch
`round/NNNN-orphan-<timestamp>` [JC-31].

## `src/next_action.py`

**Owns:** deciding what happens next and preparing it (rendering the prompt, opening
the attempt). Never records results. **Depends on:** `rounds`, `state`, `steps`,
`prompts`, `context`, `schemas` (agents plan for rungs/budgets), `findings` (views
for prompts), `suite` (round tests for TESTS-TO-SUITE), `landing`, `pauses`,
`history`, `gitops`, `ledger` (spend for context), `config`, `paths`, `errors`.
**Depended on by:** `commands`.

- `Action` (dataclass): `kind` (`chat | spawn | checkpoint | paused | done`),
  `round: str`, `step: str | None`, `attempt: int | None`, `role: str | None`,
  `rung: str | None`, `agent_definition: str | None` (`<rung>` or `<rung>-gate`),
  `read_only: bool`, `prompt_file: str | None` (absolute), `result_file: str | None`,
  `worktree: str | None`, `budget_usd: float | None`, `then: str | None` (the exact
  `record` command line), `message_for_owner: str | None`, `warnings: list[str]`.
  `to_dict()`; `human() -> str` (the block the driver reads).
- `next(world: World, now: str) -> Action` — loads the active round; returns `done`
  for a terminal round (with `state.final_message`), `paused` for a paused one (message
  recomposed by `pauses.pause_message`); re-returns the open attempt's action when one
  is `spawned` and unrecorded (idempotent, no new turn); runs
  `pauses.check_run_limits` first (may pause); then walks from `position` through
  `advance_through(...)` until an action is produced; saves, commits, pushes; returns.
- `advance_through(world, lr: LoadedRound, now) -> Action` — the loop over the table
  from the current position: skipped steps (`state.step_skipped`) are marked
  `skipped` and passed; covered checkpoints are marked `skipped`; an uncovered
  checkpoint yields `prepare_checkpoint`; `LANDING` calls `landing.land` and either
  passes (landed), yields `prepare_landing_attempt` (conflict) or yields `paused`;
  chat/producer steps yield `prepare_producer` or `prepare_gate` by phase. After the
  last step nothing remains: a `done` action (recording already set `DONE`).
- `prepare_producer(world, lr, step: Step, attempt: int, now) -> Action` — builds
  the `AttemptSpec` (rung and budget via `schemas.rung_for`/`budget_for` from
  `AGENTS-PLAN.json` when it exists; inputs = the artifact files of every accepted
  earlier step plus, for code steps, the spec; prior findings from
  `findings.views_for_prompt`; owner decisions from `state.decisions_since_pause`;
  round tests for TESTS-TO-SUITE via `suite.enumerate_round_tests`; the frozen-tests
  note for SPEC-TO-IMPLEMENTATION), renders and writes the prompt, adds the
  `AttemptRecord` (`spawned`), bumps the turn, appends the history entry, returns
  `spawn` (or `chat` for CHAT-TO-PLAN, whose `then` shows the `--decision/--quote`
  form).
- `prepare_gate(world, lr, step: Step, attempt: int, now) -> Action` — like
  `prepare_producer` with role GATE, `read_only=True`, `agent_definition =
  "<rung>-gate"`, inputs = the artifact and its inputs, the diff text for code steps
  (`gitops.diff_text(base_commit, HEAD, living paths)`), prior findings with
  resolutions, the disputed ids to rule on.
- `prepare_checkpoint(world, lr, step: Step, now) -> Action` — sets phase
  `checkpoint`, composes `pauses.checkpoint_message`, returns `checkpoint` with
  `then = record <STEP> --decision approve|delegate|abandon --quote "..."`.
- `prepare_landing_attempt(world, lr, conflicted: list[str], now) -> Action` — role
  LANDING, declared paths = the conflicted files, rung from the agents plan or
  `defaultAgent`, prompt via `prompts.landing_prompt_body`.
- `turn_budget_note(lr) -> str` — the one-line "turn n of maxTurnsPerRun, run k".

## `src/recording.py`

**Owns:** `record`: reading the agent's final message, validating it, running the
mechanical checks, applying findings and resolutions, ledger entries, commits, the
transitions out of a step, and the end-of-round booking after CLEANUP. **Depends
on:** `rounds`, `state`, `steps`, `schemas`, `checks`, `verify`, `findings`, `suite`,
`ledger`, `pauses`, `landing` (after a LANDING attempt; sync after CLEANUP),
`judgment_calls`, `ownerlog`, `index`, `history`, `gitops`, `config`, `paths`,
`errors`. **Depended on by:** `commands`.

- `DecisionArgs` (dataclass): `decision: str | None` (`approve | delegate | abandon`),
  `through: str | None`, `overrides: str | None`, `quote: str | None`.
- `RecordOutcome` (dataclass): `step`, `attempt`, `outcome: str`, `next_hint: str`
  (e.g. "run next"), `warnings: list[str]`, `problems: list[str]`, `exit_code: int`.
- `record(world: World, step_name: str, attempt: int | None, decision: DecisionArgs,
  usage: Usage | None, now: str) -> RecordOutcome` — dispatches by step kind:
  `record_checkpoint`, `record_plan` (CHAT-TO-PLAN), `record_gate` (when the open
  attempt is a gate), `record_producer` (producers and LANDING attempts). Raises
  `RefusedError("NO_OPEN_ATTEMPT")` when the named step/attempt is not the open one,
  `RefusedError("PAUSED")` when the round is paused (except checkpoint records),
  `UsageError` for a decision on a non-decision step.
- `record_plan(world, lr, decision: DecisionArgs, usage, now) -> RecordOutcome` —
  requires `decision` ∈ `approve | delegate` and a quote; `through`/`overrides` parsed
  by `steps.parse_overrides`; loads and validates `PLAN.json`; refuses on unanswered
  questions (`RefusedError("UNANSWERED")`); verifies every quote (`ownerlog.verify`,
  raising `RefusedError("QUOTE_NOT_IN_LOG")` naming the quote); runs
  `checks.run_for_attempt` (declared: the plan and the trails); stores approval and
  quote, status `RUNNING`; ledger entry for the chat attempt; if the CHAT-TO-PLAN gate
  is on → phase `gate`, else accept and advance; commit, push.
- `record_checkpoint(world, lr, step, decision, now) -> RecordOutcome` — decision ∈
  `approve | delegate | abandon` with a verified quote; `delegate` updates
  `approval.mode/through`; `abandon` delegates to `rounds.abandon`; marks undelivered
  flags delivered; accepts the checkpoint and advances; commit, push.
- `record_producer(world, lr, step, att: AttemptRecord, usage, now) ->
  RecordOutcome`:
  1. `schemas.load_json_file(result)` → `validate_result(required_resolutions =
     state.open_blocking(step), settled = state.settled(step))`. Invalid →
     `handle_invalid` (below) and raise `InvalidError`.
  2. `checks.run_for_attempt(...)` → strays reverted (recorded in the attempt and
     history), artifacts present and valid for the step (`checks.validate_artifacts`),
     conflict markers absent (LANDING), spec files untouched (always a stray).
  3. Status `NEEDS-OWNER` → commit the accepted work, `pauses.pause(NEEDS_OWNER,
     questions)`; `BLOCKED` → `pauses.pause(BLOCKED, narrow)`. Both still book the
     ledger entry and ingest judgment calls and flags [JC-50].
  4. `DONE` → step-specific work: TESTS-TO-SUITE `suite.apply` after
     `validate_suite(expected = suite.enumerate_round_tests)`; then `verify.run` per
     `step.verify`. A failed verify creates a runner finding (`findings.raise_runner`)
     and is handled like a gate FAIL (`fail_producer`).
  5. `findings.apply_resolutions`, `state.add_flags`, `judgment_calls.ingest`,
     `ledger.book_attempt` (+ driver overhead on the step's first attempt),
     `pauses.check_individual` and `pauses.check_hard_stop`.
  6. Accept or move to the gate: `steps.gate_is_on` → phase `gate`; else
     `accept_step` (freeze tests when `step.freezes_tests_after`; after LANDING
     attempts call `landing.after_conflict_resolved`; after CLEANUP call `finish_round`).
  7. Commit the attempt's accepted paths plus round files; push with the lease.
- `record_gate(world, lr, step, att, usage, now) -> RecordOutcome` — load and
  validate the findings file (`disputed = state.disputed(step)`); every uncommitted
  change is a stray (reverted); `findings.apply_gate` (rulings, repeats dropped,
  verdict wins, new ids); PASS → `accept_step`; FAIL → `fail_producer`; ledger entry;
  judgment calls ingested from the message; commit, push.
- `fail_producer(lr, step, reason: str, now) -> None` — `gate_turns += 1`; when
  `gate_turns >= gate_allowance` → `pauses.pause(GATE_LIMIT)`; else phase `produce`,
  next attempt number [JC-32] [JC-61].
- `accept_step(world, lr, step, now) -> None` — marks accepted, advances the position
  to the next step (phase `produce`, attempt 1), records `frozen_tests` when the step
  freezes tests.
- `handle_invalid(lr, att, problems, now) -> None` — marks the attempt `INVALID`,
  reverts strays, increments `invalid_in_row`; at `maxRoundAttempts` pauses
  `INVALID_LIMIT` [JC-56]; otherwise the same phase is re-prepared by the next `next`.
- `finish_round(world, lr, now) -> None` — after CLEANUP: `index.write`, the
  OWNER.log slice, `ledger.book_round` (living, archive, tests, elapsed), the final
  owner message (`pauses.final_message`), status `DONE`, commit, push, then
  `landing.sync`; a sync failure leaves the round `DONE` with `sync.status = failed`
  and a pause-like message the driver relays [JC-33].
- `commit_and_push(world, lr, paths: list[str], message: str, now) -> str` — the
  shared tail: save state, append history, commit, `push_lease(read_sha)`; on
  `FenceError` performs the backup-and-reset recovery and re-raises.

## `src/pauses.py`

**Owns:** limits, pausing, resuming, abandoning through the CLI, and every
owner-facing message the runner composes. **Depends on:** `state`, `rounds`,
`ledger`, `judgment_calls` (reading the trails), `schemas` (postmortem summary),
`history`, `ownerlog`, `config`, `steps`, `errors`. **Depended on by:** `commands`,
`next_action`, `recording`, `landing`.

- `check_run_limits(st: RoundState, cfg, now) -> str | None` — `TURN_LIMIT` when
  `run.turns >= maxTurnsPerRun`; `WALL_CLOCK` when `now − run.started_at >=
  maxRunWallClockHours` [JC-14].
- `check_hard_stop(st, cfg, projected: float = 0.0) -> bool` — `ledger.total +
  projected > multiple × quote` with the round override when set.
- `check_individual(st, cfg, cost: float, budget: float) -> bool` — `cost > multiple ×
  budget` (skipped when `budget` is 0).
- `pause(lr, reason: str, step: str, attempt: int | None, message: str, questions:
  list, now) -> None` — sets `status PAUSED`, the pause record, appends history; the
  caller commits.
- `resume(world, quote: str, hard_stop_multiple: float | None, individual: float |
  None, extend: bool, now) -> RoundState` — refuses unless `PAUSED`; verifies the
  quote; `restarts += 1` (refuses past `maxRoundAttempts` without `extend` [JC-15]);
  applies overrides (recorded with the quote); for `GATE_LIMIT` resets
  `gate_allowance` to `maxTurnsPerGate` more turns; clears the pause; `new_run`;
  status `RUNNING`; commit, push.
- `checkpoint_message(lr, cfg) -> str` — fixed sections: `ROUND`, `SO FAR` (accepted
  steps with one line each from the attempts' summaries), `SPEND` (attempts total vs
  quote), `JUDGMENT CALLS SINCE LAST PAUSE` (lines from the two trails), `FLAGS`
  (undelivered), `OPEN NON-BLOCKING FINDINGS`, `NEXT` (the next step). Verbatim
  quotes only; no interpretation.
- `pause_message(lr, cfg) -> str` — the reason, the agent's questions or `narrow`
  text verbatim, spend, flags, judgment calls since the last pause, and the exact
  `resume`/`abandon` command shapes.
- `final_message(lr, cfg) -> str` — the POSTMORTEM Summary verbatim (or a note that
  none was found), the charges block, undelivered flags, the landed commit.
- `judgment_calls_since(lr, since: str | None) -> list[str]` — lines appended to
  either trail after the timestamp (trail lines start with an ISO timestamp).
- `deliver_flags(st, now) -> list[Flag]` — marks and returns them.
