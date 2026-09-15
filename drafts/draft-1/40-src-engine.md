# 40 — src/shackles/engine/ (the state machine)

Parent: `30-src.md`. Owns the decision "what happens next" and the attempt
lifecycle around it: opening an attempt (worktree, prompt, paths), closing it
at record (checks, verification, commit, fence, billing, findings), executing
the runner-only steps (landing, booking), and phrasing pauses for the owner.
It composes the other components and holds no state of its own: every
decision reads `RoundState` and returns a new one plus an `Action`. Depends
on: everything under `shackles/` except `commands/`. Depended on by:
`commands/next.py`, `commands/record.py`, `commands/owner.py`,
`commands/start.py`.

```
engine/
  advance.py        RoundState -> Action: the one decision function
  attempts.py       open / close attempts; prompt files; result files; billing
  landing_step.py   LANDING: merge, conflict attempt, verify, push to main
  booking.py        CLEANUP booking; abandon booking; LEDGER.md; sync
  pauses.py         owner-facing messages for every pause reason
```

## advance.py

Data: `Action` (`70-contracts.md`): `SELF`, `SPAWN`, `OWNER`, `END`, each with
its fields; `Decision(state: RoundState, action: Action, history:
list[HistoryEntry])`.

- `advance(state, ctx: EngineContext) -> Decision` — pure given `ctx` (which
  bundles settings, roster, paths, table, the repo handle for lease
  verification, and `now`). Order of decision:
  1. `phase == ended` -> `END`.
  2. `phase == paused` -> `OWNER` restating the pause (idempotent: the driver
     may call `next` again while waiting).
  3. An open attempt exists -> the same `SPAWN`/`SELF` again (idempotent).
  4. Unanswered questions exist -> pause `QUESTIONS`.
  5. Owner items are pending and the next step is a checkpoint or the round is
     about to end -> they are attached to that pause.
  6. Current step by kind:
     - `PLAN`: `SELF` with the CHAT-TO-PLAN prompt until `approval` is set;
       once set, the step is accepted (its gate, if on and present, runs
       first).
     - `CHECKPOINT`: skipped when overridden, or when `approval.mode ==
       delegate` and (`through` is None or the checkpoint's index `<=
       index_of(through)`); otherwise pause `CHECKPOINT` with the rendered
       checkpoint prompt for the driver.
     - `PRODUCER`/`CLEANUP`: overridden -> apply `skipDefault` (`attempts.skip`)
       and accept; `stepStatus pending|working` -> open a producer attempt
       (retry when the last verdict was FAIL, carrying findings); `gating` ->
       open a gate attempt; gate off -> accept on DONE.
     - `LANDING`: run `landing_step.land`; on conflict open the conflict
       attempt; on success accept.
     - After `CLEANUP` is accepted: `booking.book_round`, sync, `END`.
  7. Before opening any attempt: `limits.check_before_attempt`, the lease
     check (`lease.verify`), and the round hard stop -> pause instead.
- `gate_is_on(state, step, s) -> bool` — `project.yaml` switch is 1, the gate
  prose file exists, and the gate is not overridden.
- `should_skip_checkpoint(state, step) -> bool`.

## attempts.py

- `open_producer(state, step, ctx, findings: Verdict | None) -> tuple[RoundState, Action]`
  — computes rung and budget (`quote/shares.py`), creates the worktree at the
  round branch head (`git/worktrees.py`), builds the `AttemptView`, renders
  the prompt (`prompts/render.py`), writes `PROMPTS/<id>.txt` into the
  runner's worktree, commits and fences it, records `run.turns += 1`, returns
  `SPAWN` (or `SELF` for `PLAN` and checkpoint attempts, which get no
  worktree). Unresolved tokens are written verbatim and noted in HISTORY.
- `open_gate(state, step, ctx, producer_attempt) -> tuple[RoundState, Action]`
  — like `open_producer` with role gate, read-only agent file, no worktree
  (the gate reads the runner's worktree paths), prior findings and the
  producer's `resolved`/`disputes` listed as inputs.
- `record_producer(state, attempt, result_doc, problems, tokens: int | None, ctx) -> tuple[RoundState, list[HistoryEntry]]`
  — the sequence, in order, each step noting into HISTORY:
  1. Contract problems (`results.py`) or missing/invalid artifact ->
     `mechanicalRetries[step] += 1`; over the limit -> pause `LIMIT`; else the
     attempt closes `invalid` and a retry opens with the problems appended to
     its prompt.
  2. `checks/mechanical.run_all` on the worktree: strays reverted, notes kept.
  3. Verification per the step's rule (`COLLECT` or `PASS`) in the worktree;
     for `SPEC-TO-IMPLEMENTATION` a failing suite is a mechanical retry with
     the tail in the prompt ("until the frozen tests pass"); for
     `SPEC-TO-TESTS` a collection error likewise.
  4. Commit the kept changes from the worktree, advance the branch (CAS),
     fence; on `LeaseLostError` pause `LEASE`.
  5. Bill: `agent_costs` from `tokens` (split) or sizes (estimated); add the
     entry; `hard_stop_attempt` -> pause `HARD-STOP`; `hard_stop_round` ->
     pause `HARD-STOP`.
  6. Judgment calls listed in the final message are appended to the two files
     by the runner (gates and the driver cannot run the tool).
  7. Status: `NEEDS-OWNER` -> store the questions, pause `QUESTIONS`;
     `BLOCKED` -> pause `BLOCKED` with `narrow`; `DONE` -> `flags` become
     owner items; the gate opens if on, else the step is accepted and the
     driver overhead is booked.
  8. TESTS-TO-SUITE `DONE`: `checks/suite_moves` plan and apply in the
     runner's worktree, verify `PASS`, commit; problems are a mechanical
     retry.
  9. Remove the worktree.
- `record_gate(state, attempt, result_doc, problems, tokens, ctx) -> tuple[RoundState, list[HistoryEntry]]`
  — contract problems -> mechanical retry of the gate; else
  `findings.from_gate_result`, write `FINDINGS/<producer attempt>.json`, bill,
  hard stops; `PASS` with no open blocking findings -> accept the step (owner
  flags collected); `FAIL` -> `gateTurns[step] += 1`, over the limit -> pause
  `LIMIT`, else `stepStatus = working` so `advance` opens a retry carrying the
  verdict.
- `record_driver(state, attempt, result_doc, problems, ctx)` — CHAT-TO-PLAN
  and checkpoint results: validate `PLAN.json` at CHAT-TO-PLAN `DONE` (an
  unapproved plan is refused: "record after the owner approves"), append
  judgment calls, book driver overhead.
- `skip(state, step, ctx) -> RoundState` — applies `skipDefault`: PLAN-AGENTS
  -> `agentPlan = None` (defaults apply); TESTS-TO-SUITE -> every new test
  stays in the suite (no moves); POSTMORTEM -> nothing; checkpoints ->
  nothing.
- `prompt_for_retry(base: Rendered, problems: list[str], verify_tail: str | None) -> str`
  — appends a labelled "RUNNER NOTES" block; no prose interpretation.

## landing_step.py

- `land(state, ctx) -> tuple[RoundState, Action | None]` — fetch; `mainBefore`
  = remote `main` sha; projected living charge + spend vs the round hard stop
  -> pause `HARD-STOP` (checked before landing, as the prose says); `merge_main_into`
  in the runner's worktree; clean -> verify `PASS` -> `push_to_main` with
  lease (moved main -> repeat, bounded by `syncAttempts`, then pause `SYNC`);
  conflict -> open a conflict attempt (`attempts.open_producer` with
  `declaredPaths = CONFLICTED`, the conflicted paths and the auto-merged
  commit in the prompt) and return its `SPAWN`.
- `record_conflict(state, attempt, result_doc, problems, tokens, ctx)` —
  `landing.judge_resolution` (only conflicted files may differ from the
  auto-merged tree; markers gone), strays reverted, verify `PASS`, commit,
  push to main with lease; failure -> mechanical retry bounded by
  `maxRoundAttempts`, then pause `LIMIT`.
- On success `state.landing.landedAt` is set and the step accepted; the
  driver overhead is booked.

## booking.py

- `book_round(state, ctx) -> RoundState` — after CLEANUP's record:
  `living.charge_between(mainBefore, round head)`, `archive_costs` from the
  round folder files, `ledger.book`; `LEDGER.md` line appended in the
  runner's worktree; commit "book: round NNNN"; `sync_to_main` bounded;
  failure -> pause `SYNC` (the owner may `resume`, which retries); success
  -> `end(landed)`, remove worktrees.
- `book_abandon(state, ctx) -> RoundState` — agent and driver entries stand,
  no living or archive charge; `LEDGER.md` line; commit; `sync_round_folder_only`;
  `end(abandoned)`.

## pauses.py

- `message_for(pause: Pause, state, s) -> str` — one plain-English paragraph
  per reason the driver relays verbatim: what stopped, where, the attempt id,
  the numbers involved, the verbs the owner can use now, and the pending owner
  items. Never includes prose from agents beyond their `summary`, `questions`,
  `narrow` and `flags` fields, quoted as-is.
- `accepts_for(pause) -> list[str]` — the verbs valid for the pause
  (`CHECKPOINT`: approve, delegate, override, abandon; `QUESTIONS`: answer,
  abandon; `NEEDS-OWNER`: answer, abandon; `BLOCKED`: resume-after-override,
  abandon; `LIMIT`/`HARD-STOP`/`LEASE`/`VERIFY`/`SYNC`: resume, abandon).
