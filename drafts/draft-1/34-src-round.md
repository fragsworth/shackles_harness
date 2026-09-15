# 34 — src/shackles/round/ (the round folder and its records)

Parent: `30-src.md`. Owns every file in the round folder that the runner
writes or validates: `STATE.json` (the runner's only state), `HISTORY.md`,
the owner-log slice, the judgment-call files, the artifact schemas, the
final-message schemas, the findings rules, and the owner-verb transitions.
Pure data and file I/O confined to the round folder; no git, no prompts.
Depends on: `config/` (paths, settings), `steps/` (names, order). Depended on
by: `engine/`, `commands/`, `ledger/` (reads ledger entries out of the state),
`prompts/` (through read-only views built by the engine).

```
round/
  state.py            STATE.json model, load/save, transitions
  history.py          HISTORY.md appender
  owner_log.py        the global OWNER.log -> the round's slice; quote verification
  judgment_calls.py   DEFINED_/UNDEFINED_JUDGMENT_CALLS.md appenders
  artifacts.py        PLAN.json, AGENTS-PLAN.json, SPEC.json, SUITE.json schemas + plan rendering
  results.py          final-message extraction and validation (producer, gate, driver)
  findings.py         FINDINGS/ records; the mechanical finding rules
  approvals.py        owner verbs -> state changes (approve, delegate, override, answer, abandon, resume)
```

## state.py

`RoundState` (dataclass, JSON-serialisable, versioned with `schema: 1`):

| field | type | meaning |
|---|---|---|
| `id`, `branch`, `baseCommit` | str | round id, `round/NNNN`, the `main` commit it started from |
| `startedAt`, `endedAt` | str/None | UTC |
| `phase` | `open`, `paused`, `ended` | |
| `pause` | `Pause | None` | `{reason: CHECKPOINT|NEEDS-OWNER|BLOCKED|QUESTIONS|LIMIT|HARD-STOP|LEASE|VERIFY|SYNC, attempt, message, items}` |
| `outcome` | `landed`, `abandoned`, None | |
| `stepIndex` | int | index into the table of the current step |
| `stepStatus` | `pending`, `working`, `gating`, `accepted`, `skipped` | of the current step |
| `approval` | `Approval | None` | `{mode: approve|delegate, through: str|None, quote, at}` |
| `overrides` | `Overrides` | `{steps: [..], gates: [..], quote}` |
| `questions` | list[`Question`] | `{n, text, options, answerQuote|None, askedBy}` |
| `attempts` | list[`Attempt`] | every attempt, in order (below) |
| `gateTurns` | dict[str,int] | FAIL verdicts per step |
| `mechanicalRetries` | dict[str,int] | mechanical re-spawns per step |
| `run` | `RunCounters` | `{startedAt, turns, resumes}` reset by `resume` |
| `quote` | float/None | approved plan's total |
| `agentPlan` | dict/None | the accepted AGENTS-PLAN.json, copied |
| `ownerItems` | list[`OwnerItem`] | flagged items not yet shown: `{text, from, shownAt|None}` |
| `landing` | `Landing | None` | `{mainBefore, mergedCommit, conflictAttempt|None, landedAt}` |
| `ledger` | `LedgerBlock` | `{entries: [...], booked: {...}|None, total}` (shapes in `37-src-ledger.md`) |
| `lease` | str | last commit known pushed to `round/NNNN` |
| `ownerLogCursor` | int | global-log entries consumed into the slice |

`Attempt`: `{id, step, role: producer|gate|checkpoint|conflict|driver, n, rung,
agentFile, worktree|None, promptFile, resultFile, budgetUsd, openedAt,
closedAt|None, status: open|done|needs-owner|blocked|invalid|passed|failed,
commit|None, notes: [str]}`.

Functions:

- `new_state(id, branch, base_commit, cursor, now) -> RoundState`.
- `load(path: Path) -> RoundState` — raises `ContractError` on schema mismatch.
- `save(state: RoundState, path: Path) -> None` — atomic; sole writer of `STATE.json`.
- `current_step(state) -> Step`.
- `open_attempt(state, attempt: Attempt) -> RoundState` — refuses (`RefusedError`)
  when another attempt is open (attempts are serial).
- `close_attempt(state, id, status, commit, notes) -> RoundState`.
- `accept_step(state) -> RoundState` — marks accepted and advances `stepIndex`.
- `skip_step(state, reason) -> RoundState`.
- `pause(state, pause: Pause) -> RoundState`, `resume(state, now) -> RoundState`
  (increments `run.resumes`, resets `run.turns` and `run.startedAt`), `end(state,
  outcome, now) -> RoundState`.
- `open_attempt_of(state) -> Attempt | None`, `attempts_for(state, step) ->
  list[Attempt]`, `next_n(state, step, role) -> int`.
- `add_owner_items(state, items) -> RoundState`, `mark_items_shown(state, now)`.
- `view(state) -> RoundView` — the read-only view the prompts use (`70-contracts.md`).

All transitions are pure (return a new state); `save` is the only side effect.

## history.py

- `append(path: Path, entry: HistoryEntry) -> None` — sole writer of
  `HISTORY.md`; appends one Markdown block: `## <UTC> <kind> <attempt or verb>`
  then labelled lines. `HistoryEntry(kind: attempt|verdict|owner|landing|sync|
  booking|pause|note, id, lines: list[str])`.
- `entry_for_attempt(attempt, result_summary, cost_line, notes) -> HistoryEntry`
  and the same for verdicts, owner commands, landing, sync, booking: small
  formatters so the engine never builds Markdown.

## owner_log.py

Data: `LogEntry(ts: str, session: str, text: str)`.

- `read_global(path: Path) -> list[LogEntry]` — parses JSON lines; a malformed
  line is skipped and counted (returned via a second value `skipped: int`).
  Missing file -> `RefusedError("no owner log")`.
- `slice_since(entries, cursor: int) -> list[LogEntry]`.
- `write_slice(path: Path, entries) -> None` and `append_slice(path, entries)`
  — the round's `OWNER.log` (same JSON-lines format).
- `refresh(global_path, round_path, cursor: int) -> int` — appends new global
  entries to the round slice, returns the new cursor. Called at `start` and at
  every `owner` command.
- `verify_quote(round_path: Path, quote: str, mode: "exact"|"normalized") -> LogEntry`
  — the entry whose `text` contains `quote` verbatim (`normalized`: runs of
  whitespace collapsed on both sides before the substring test); the latest
  match wins; raises `QuoteNotFoundError` otherwise `[JC-15]`.

## judgment_calls.py

- `append(path: Path, attempt_id: str, text: str, now: str) -> None` — one
  line `- <UTC> [<attempt>] <text>`; newlines in `text` become spaces.
- `read(path: Path) -> list[str]` — the lines, for checkpoint summaries.
- `is_append_only(before: str, after: str) -> bool` — the mechanical check
  used at record: the old content must be a prefix of the new.

## artifacts.py

Schemas are dicts of field -> (type, required); validation returns a list of
problems, never raises, so gates and mechanical notes can carry them.

- `validate_plan(doc: dict) -> list[str]` — `PLAN.json`: `title`, `scope`
  (prose), `nonGoals` (list of prose), `assumptions` (list), `validationSteps`
  (list of prose), `todosAccepted` (list), `questions` (list of `{n, text,
  options: {letter: text}, answerQuote}`), `quote: {total, agentsUsd,
  livingUsd, archiveUsd, driverUsd, notes}`, `refactorUsd` (estimate,
  optional), `ownerQuotes` (the verbatim words the plan rests on). Rule
  checked here: every question has an `answerQuote` before the plan can be
  approved (the engine calls this at `owner approve`).
- `validate_agents_plan(doc, settings, roster, table) -> list[str]` —
  `AGENTS-PLAN.json`: `steps: {STEP: {agent: rung, subAgents: int, share:
  float, note}}` and `gates: {STEP: {agent, share, note}}`; every key a table
  step; rungs in the roster; work shares sum `<= 1 + 1e-9` and gate shares
  likewise; `subAgents <= maxSimultaneousSubAgentsPerRound`; rungs above
  `maxAgent` are a problem. Advisory `defaultShares` minimums produce
  `warnings` (second return value), not problems.
- `validate_spec(doc) -> list[str]` — `SPEC.json`: `summary`, `components:
  [{name, text, paths: [..], tests: [..prose..]}]`, `testPlan: [prose]`,
  `integrationTests: [prose]`, `nonGoals`, `refactor: {text, estimatedUsd}`,
  `implementationSteps: [{n, text, component}]`.
- `validate_suite(doc, new_tests: list[str]) -> list[str]` — `SUITE.json`:
  `tests: {"<file>::<function>": "suite"|"archive"}`, `flags: [prose]`; every
  new test decided exactly once; a file whose tests are split between
  destinations is a problem ("split the file; the runner moves whole files").
- `render_plan(doc: dict) -> str` — the plain-English form used for
  `{{ round.plan }}`: title, scope, non-goals, assumptions, validation steps,
  accepted TODOs, answered questions (question, chosen answer quote), quote
  lines, refactor estimate `[JC-16]`.
- `load_json(path) -> dict` — raises `ContractError` on unreadable JSON.

## results.py

The final message is what the driver saved; the runner extracts the last JSON
object in it (bare, or inside the last fenced block), so a sub-agent that adds
a sentence before its JSON is still parsed `[JC-17]`.

- `extract_json(text: str) -> dict` — raises `ContractError("no JSON object")`.
- `validate_producer(doc) -> list[str]` — `status` in DONE|NEEDS-OWNER|BLOCKED;
  `summary` str; `questions` required and non-empty when NEEDS-OWNER (each
  `{n, text, options}`); `narrow` str when BLOCKED; optional `resolved:
  [{finding, how}]`, `disputes: [{finding, argument}]`, `flags: [str]`,
  `judgmentCalls: [{kind, text}]`, `subAgentsUsed: int`.
- `validate_gate(doc) -> list[str]` — `verdict` PASS|FAIL; `summary`;
  `rulings: [{finding, ruling: upheld|withdrawn, quote}]`; `findings: [{id,
  quote, text, suggestion, blocking, forOwner, repeats?}]`; every finding has
  a non-empty `suggestion` and `quote`; `judgmentCalls`.
- `validate_driver(doc) -> list[str]` — CHAT-TO-PLAN's own result: `status`
  DONE (plan approved) and `judgmentCalls`; and a checkpoint's result:
  `status` DONE with `shownItems: [str]`.
- `load_result(path) -> tuple[dict, list[str]]` — read, extract, validate by
  role; the problems list drives a mechanical retry.

## findings.py

Data: `Finding(id, quote, text, suggestion, blocking: bool, forOwner: bool,
state: open|resolved|withdrawn|settled, upheldCount: int, raisedIn:
attempt_id, repeats: str | None)`; `Verdict(attempt, gateAttempt, verdict,
findings: list[Finding], rulings, summary, notes: list[str])`.

- `from_gate_result(doc, prior: list[Finding], producer_attempt, gate_attempt) -> Verdict`
  — applies the rules, all mechanical:
  1. **Rulings first.** Each ruling names a prior open/disputed finding:
     `withdrawn` -> state withdrawn; `upheld` -> `upheldCount += 1`, and at 2
     the state becomes `settled` (no further disputes accepted).
  2. **Repeats of withdrawn findings are dropped with a note**: a new finding
     is dropped when its `repeats` names a withdrawn finding, or when its
     normalized `quote` equals a withdrawn finding's quote `[JC-18]`.
  3. **The verdict wins.** FAIL with no blocking finding -> every new and
     upheld finding is marked blocking (note). PASS -> every finding is
     non-blocking (note), and open blocking priors are marked resolved (the
     gate passed the artifact).
  4. Prior findings the producer listed under `resolved` and the gate did not
     rule on stay open on FAIL and are noted; on PASS they resolve.
- `open_blocking(findings) -> list[Finding]` — what blocks acceptance.
- `owner_flags(findings) -> list[str]` — `forOwner` findings as owner items.
- `write(path: Path, verdict: Verdict) -> None`, `read(path) -> Verdict`,
  `latest_for_step(folder, step) -> Verdict | None`.
- `disputes_allowed(findings, disputes) -> list[str]` — disputes against
  `settled` findings are rejected with a note (the finding stands).

## approvals.py

Each function takes the state, the verified `LogEntry` for the quote, and
arguments, and returns a new state or raises `RefusedError` with the reason
the driver must relay. No prose is read: the driver supplies the interpretation.

- `approve(state, quote_entry) -> RoundState` — at CHAT-TO-PLAN: requires
  `PLAN.json` validated with every question answered; sets `approval.mode =
  approve`, freezes `quote`. At a checkpoint pause: clears the pause.
- `delegate(state, quote_entry, through: str | None) -> RoundState` — like
  approve with `mode = delegate`, `through` a table step name (`LintError` on
  unknown); later checkpoints at or before `through` are skipped.
- `override(state, quote_entry, steps: list[str], gates: list[str]) -> RoundState`
  — each step must be `overridable` (CHAT-TO-PLAN never); gates must be gated
  steps; already-passed steps are refused; recorded with the quote.
- `answer(state, quote_entry, n: int) -> RoundState` — stores the verbatim
  quote as the answer of question `n`; any text counts.
- `abandon(state, quote_entry, reason: str) -> RoundState` — `phase = ended`,
  `outcome = abandoned`; allowed at any time.
- `resume(state, quote_entry) -> RoundState` — from a `paused` state whose
  reason is LIMIT, HARD-STOP, LEASE, VERIFY or SYNC; counts a round attempt
  (`run.resumes`) and is refused once `run.resumes` would exceed
  `maxRoundAttempts`: at that point the owner's only verbs are `abandon` or a
  temporary, round-specific `override` of the limit, which the driver may hand
  in only with the owner's explicit words as the quote `[JC-19]`.
- `needs_answers(state) -> list[Question]` — open questions; used by the
  engine to keep the round from starting or continuing with unanswered ones.
