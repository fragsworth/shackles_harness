# 05 — Round state and records

`state.py` holds `STATE.json` and its transitions; `history.py` appends `HISTORY.md`; `messages.py` parses final messages; `artifacts.py` validates artifacts; `findings.py` runs the finding lifecycle; `judgment.py` appends judgment-call lines; `ownerlog.py` reads the owner log and verifies quotes; `decisions.py` applies owner decisions. Each is a pure-ish module over the `STATE.json` structure of [00] §0.5; none runs git.

Common types: `FindingRecord`, `AttemptRecord`, `QuestionRecord`, `DecisionRecord`, `LedgerEntry` are `dataclass`es mirroring [00] §0.5 with `to_json()/from_json()`.

## 5.1 `src/shackles/state.py`

**Owns:** the `RoundState` model, atomic load/save, and every transition of `status`, `cursor`, `attempts`, `counters`, `questions`, `flags`. **Depends on:** `paths`, `steps`, `errors`. **Depended on by:** all commands, `prompts`, `findings`, `ledger`, `limits`, `landing`, `decisions`, `history`.

- `@dataclass class RoundState` — fields of [00] §0.5 plus `path: Path` (its file) and `extra: dict` (unknown keys preserved).
  - `load(path: Path) -> RoundState` (`StateError` on missing/corrupt; schema > 1 is loaded with a warning field), `save(self) -> None` (temp + rename), `snapshot(self) -> Json`.
  - `new_round(rp: RoundPaths, *, round_id: str, branch: str, base_commit: str, worktree: Path, slice_from: ts, now: ts) -> RoundState` — status `planning`, cursor at CHAT-TO-PLAN/`produce`, mode `approve`.
- Attempts: `next_attempt_id(self, step: str, gate: bool) -> str`; `open_attempt(self, rec: AttemptRecord) -> None` (`StateError` if one is open; sets `open_attempt`, increments `counters.turns`); `attempt(self, id: str) -> AttemptRecord`; `close_attempt(self, id, *, status, accepted, mechanical, strays, spend_usd, spend_source, now) -> None`; `attempts_for(self, step: str, kind: str | None = None) -> list[AttemptRecord]`; `producer_attempt_being_judged(self) -> AttemptRecord | None`.
- Cursor: `current_step(self) -> Step`; `advance_phase(self, cfg_gate_on: bool) -> None` (`produce` → `gate` if on, else next step's `produce`; `gate` → next step); `set_phase(self, phase: str)`; `goto_step(self, name: str)`; `is_done(self) -> bool`.
- Pauses: `pause(self, kind: str, reason: str, *, step, attempt, questions: list[int] = [], narrow: str | None = None, limit: str | None = None, now: ts) -> None` (status `paused`, closes the active interval into `counters.active_seconds`); `resume(self, now: ts) -> None` (`StateError` unless paused; increments `counters.restarts` when the pause kind is `limit`, `mechanical`, `hard-stop` or `sync` (JC-34); reopens the active interval); `await_owner(self, reason, now)` (status `awaiting-owner`, used during planning).
- Questions: `register_questions(self, attempt: str, qs: list[dict]) -> list[int]` (assign global ids); `answer(self, qid: int, quote: str, now: ts) -> None` (`DecisionError` unknown/answered); `open_questions(self) -> list[QuestionRecord]`.
- Flags: `add_flags(self, attempt: str, texts: list[str])`, `deliver_flags(self, now: ts) -> list[dict]` (moves pending → delivered, returns them).
- Rejections/limits helpers: `bump_rejection(self, step: str) -> int`, `rejections(self, step: str) -> int`, `active_seconds(self, now: ts) -> float`.
- End: `end_round(self, status: "done"|"abandoned", now: ts) -> None`.
- `find_active_round(roots: Roots, rp_factory) -> RoundState | None` — scans `.worktrees/round-*/` for the newest `STATE.json` whose status is not `done`/`abandoned` (JC-35).

Errors: `StateError`.

## 5.2 `src/shackles/history.py`

**Owns:** `HISTORY.md` formatting and appending ([00] §0.9). **Depends on:** `paths`. **Depended on by:** commands, `landing`, `ledger` (via commands).

- `append(path: Path, entry: Entry) -> None` — appends one entry with a blank line before it.
- `@dataclass class Entry`: `kind: "ATTEMPT"|"OWNER"|"RUNNER"|"ROUND"`, `title: str`, `fields: list[tuple[str, str]]`, `body_json: Json | None`, `at: ts`; `render(self) -> str`.
- Convenience constructors: `attempt_opened(rec, prompt_tokens, warnings)`, `attempt_recorded(rec, message: Json, findings_summary: str, flags, jc_counts: tuple[int, int])`, `owner(decision: DecisionRecord)`, `runner(event: str, fields)`, `round_end(status, total_usd)`.
- `read_entries(path: Path) -> list[str]` — split by `## ` headings (used by tests and the checkpoint summary).

## 5.3 `src/shackles/messages.py`

**Owns:** parsing and validating final messages ([00] §0.6). **Depends on:** `errors`. **Depended on by:** `commands/record`, `commands/spawn`, `invoke`, `findings`, stub agent tests.

- `@dataclass class ProducerMessage`: `status`, `summary`, `questions: list[dict]`, `narrow: str | None`, `flags: list[str]`, `resolutions: list[dict]`, `judgment_calls: list[dict]`, `raw: Json`.
- `@dataclass class GateMessage`: `status`, `summary`, `rulings: list[dict]`, `findings: list[dict]`, `flags`, `judgment_calls`, `raw`.
- `parse_text(text: str, kind: "producer"|"gate") -> ProducerMessage | GateMessage` — accepts a bare JSON object; tolerates a single fenced ```json block or leading/trailing whitespace (JC-36); everything else → `MessageError` with a reason (`not-json`, `not-object`, `bad-status`, `missing-<field>`, `bad-<field>`). Validation: status allowed for kind; `questions` non-empty with ≥2 options each iff NEEDS-OWNER; `narrow` non-empty iff BLOCKED; `resolutions[*].resolution ∈ {fixed, disputed}`; `rulings[*].ruling ∈ {upheld, withdrawn}`; each finding has non-empty `quote`, `text`, `suggestion`; `judgment_calls[*].kind ∈ {DEFINED, UNDEFINED}`.
- `parse_file(path: Path, kind: str) -> ...` — `UsageError` when unreadable, else `parse_text`.
- `kind_for(attempt_kind: str) -> str` — `gate` → `gate`, else `producer`.

## 5.4 `src/shackles/artifacts.py`

**Owns:** artifact schema validation ([00] §0.7) and the small extractions other modules need (plan quote, non-goals, postmortem summary text). **Depends on:** `errors`, `steps`, `config` (limits and fractions for AGENTS-PLAN checks). **Depended on by:** `checks`, `state` (plan registration), `charges` (postmortem summary tokens), `prompts` (assumptions for the checkpoint summary).

- `validate_plan(path: Path) -> PlanInfo` — `ArtifactError` listing every violated rule; `PlanInfo(text, quote_usd, non_goals, validation_steps, assumptions, questions, refactor_fraction)`.
- `validate_agents_plan(path: Path, cfg: Config, roster: AgentRoster, gate_on: Callable[[str], bool]) -> AgentsPlanInfo` — rules: every producer/cleanup step of the table after PLAN-AGENTS has a `steps` entry; every gated step with its gate on has a `gates` entry; rungs exist and are within the ceiling; helper counts ≤ `maxSimultaneousSubAgentsPerRound`; Σ work shares (including the `defaultShares.work` values for CHAT-TO-PLAN and PLAN-AGENTS) ≤ `workFraction + 0.01`; Σ enabled gate shares ≤ `gatesFraction + 0.01`; shares ≥ 0. Returns `warnings` (non-blocking) when a sum is below its fraction by more than 0.05 or a share is under its `defaultShares` advisory minimum. (JC-37)
- `validate_spec(path_json: Path, path_md: Path, plan: PlanInfo, cfg: Config) -> SpecInfo` — non-empty components, implementation steps, test plan; every step/test references known component ids; `SPEC.md` non-empty. Advisory (returned as `warnings`, not errors): refactor shares sum > `maxRefactorOverhead`; a plan non-goal whose text does not appear (case-insensitive substring) in the spec's non-goals. (JC-38)
- `validate_suite(path: Path, new_tests: list[TestRef]) -> SuiteInfo` — every new test (file+name) appears exactly once; every listed test exists among the new tests; decisions valid; files mixed between `suite` and `archive` are an error (the producer must split the file).
- `validate_postmortem(path: Path) -> PostmortemInfo` — first heading is `Summary` (case-insensitive, any `#` level); `summary_text` = text until the next heading.
- `read_json(path) -> Json` (`ArtifactError` on missing/invalid).

## 5.5 `src/shackles/findings.py`

**Owns:** the finding lifecycle and `FINDINGS/` files ([00] §0.8). **Depends on:** `state`, `messages`, `paths`, `errors`. **Depended on by:** `commands/record`, `plumbing` (open findings view), `prompts`.

- `accept_gate_message(rs: RoundState, gate_attempt: AttemptRecord, judged: AttemptRecord, msg: GateMessage, *, inputs: dict, verify: dict | None, mechanical: list[str], now: ts) -> GateOutcome` — the rules, in order:
  1. **Rulings.** For each finding of the step in state `disputed`: the gate's ruling `upheld` → `upheld += 1`, state `open` (or `settled` when `upheld >= 2`); `withdrawn` → state `withdrawn`. A disputed finding with no ruling counts as `upheld` and is recorded with `missing: true` (JC-39).
  2. **New findings.** Each finding in the message is compared with every `withdrawn` finding of the step by normalized quote (whitespace-collapsed, case-sensitive) or identical `text`; matches are **dropped** into `dropped` with a note; the rest become `FindingRecord`s with fresh ids, state `open`.
  3. **Verdict wins.** `verdict = msg.status`. If PASS: every finding of this step still `open` (new or upheld) becomes `note` (non-blocking, needs no resolution). If FAIL: every `open`/`settled` finding is `blocking = True`; if none is open (all dropped or none raised) the outcome still fails and `reason = "gate failed with no surviving findings; see summary"`.
  4. Write `FINDINGS/<judged>.json`; return `GateOutcome(verdict, accepted: bool = verdict == "PASS", open_ids, dropped, missing_rulings)`.
- `check_resolutions(rs: RoundState, step: str, msg: ProducerMessage) -> ResolutionOutcome` — for a producer attempt after a FAIL: every finding of the step in state `open` or `settled` needs a resolution; `fixed` → state `fixed` (verified by the next gate turn, which may re-raise it — as a *new* finding, not a repeat of a withdrawn one); `disputed` on `open` → `disputed`; `disputed` on `settled` → error "settled finding F-… cannot be disputed"; unknown finding id → error. Returns `ok: bool`, `errors: list[str]` (each is a mechanical finding for the attempt).
- `open_findings(rs, step) -> list[FindingRecord]`, `summary(rs, step) -> str` (one line per finding: id, state, upheld count), `normalize_quote(s: str) -> str`.
- `write_findings_file(rp, judged_id, payload: Json) -> Path`, `read_findings_file(rp, judged_id) -> Json`.

Errors: none raised for agent mistakes (they become mechanical findings or notes); `StateError` for inconsistent state.

## 5.6 `src/shackles/judgment.py`

**Owns:** the two judgment-call files. **Depends on:** `paths`, `errors`. **Depended on by:** `commands/judgment`, `commands/record`, `commands/start`, `plumbing` (reads for the checkpoint summary).

- `init_files(rp: RoundPaths, round_id: str) -> None` — write the two headers.
- `append_line(rp: RoundPaths, kind: "defined"|"undefined", attempt_id: str, text: str) -> None` — one line `- [<attempt>] <text>` with newlines in `text` replaced by spaces; `UsageError` on empty text.
- `append_from_message(rp, attempt_id, calls: list[dict]) -> tuple[int, int]` — for gates (and any producer that also put calls in its message); returns counts (defined, undefined).
- `read(rp, kind) -> list[str]`, `counts(rp) -> tuple[int, int]`.

## 5.7 `src/shackles/ownerlog.py`

**Owns:** reading `OWNER.log`, verifying quotes, slicing into the round folder ([00] §0.10). **Depends on:** `paths`, `errors`. **Depended on by:** `commands/start`, `commands/owner`, `commands/record`, `commands/accept_spec`, `doctor`.

- `log_path(roots: Roots) -> Path` — `<harness>/OWNER.log`.
- `@dataclass class Entry`: `ts: ts`, `session: str`, `cwd: str`, `prompt: str`.
- `read(path: Path) -> list[Entry]` — JSON lines; malformed lines are skipped and counted (`Entry` list plus `skipped: int` via `read_with_stats`).
- `require_log(roots: Roots) -> list[Entry]` — `OwnerLogError` when the file is missing or has no valid entry ("the prompt hook has not logged anything; run doctor").
- `verify_quote(entries: list[Entry], quote: str, *, since: ts | None) -> Entry` — normalize both sides (strip, collapse whitespace runs); the quote must be non-empty and a substring of some entry's prompt with `ts >= since` (JC-40); `QuoteNotFoundError` otherwise, with the number of entries searched.
- `slice(entries, since: ts) -> list[Entry]`, `write_slice(rp: RoundPaths, entries, since) -> int` — writes the round's `OWNER.log`; returns the count.
- `previous_round_end(roots: Roots, rp_factory) -> ts | None` — newest `ended_at` among `archives/rounds/*/STATE.json` on the driver checkout; used for `slice_from` at start.

## 5.8 `src/shackles/decisions.py`

**Owns:** the vocabulary of owner decisions the runner accepts and their effect on state ([00] §0.5 `decisions`). The driver maps owner words to these kinds; the runner never inspects the words beyond verifying the quote. **Depends on:** `state`, `steps`, `config`, `errors`. **Depended on by:** `commands/owner`, `decisions` tests, `plumbing` (renders the kinds into the driver prompt via `KINDS`).

- `KINDS: dict[str, str]` — kind → one-line meaning (rendered to the driver): `approve` (proceed; checkpoints pause), `delegate` (proceed; no checkpoints), `delegate-through` (no checkpoints up to and including `--through STEP`), `override` (skip `--targets` steps/gates this round), `answer` (record `--quote` as the answer to `--question N`), `abandon` (end without landing; `--reason`), `revise` (reopen CHAT-TO-PLAN with a new attempt), `resume` (continue after a pause), `raise-limit` (set `--limit KEY` to `--value V` for this round).
- `apply(rs: RoundState, kind: str, *, quote: str, through: str | None, targets: list[str], question: int | None, limit: str | None, value: float | None, reason: str | None, cfg: Config, now: ts) -> Applied` — validates and mutates:
  - `approve`/`delegate`/`delegate-through`: allowed in `awaiting-owner` (planning) and when paused at a checkpoint; refuses while questions are open (`DecisionError("unanswered questions: …")`); sets `mode`; in planning sets `approved_at`, status `running`, cursor to PLAN-AGENTS; at a checkpoint resumes. `through` must be a step name (`DecisionError`).
  - `override`: targets are step names or `<STEP>-GATE`; each must exist, be overridable ([04] §4.1), and not already be done; adds to `overrides`; allowed any time before the target runs (if paused, does not resume by itself).
  - `answer`: `question` must be open; records the quote; if no questions remain open and the pause kind is `needs-owner`, the pause is cleared automatically (the step retries with a new attempt) (JC-41).
  - `abandon`: allowed any time; sets `pause` cleared, status remains for `landing.abandon` to finish; records `reason`.
  - `revise`: allowed only while CHAT-TO-PLAN is not approved; opens nothing itself (returns `reopen_plan: True` for the command to open a new driver attempt).
  - `resume`: allowed when paused with kind `blocked` (requires at least one answer recorded since the pause), `limit`, `mechanical`, `hard-stop`, `sync`, `drift` (drift must be gone); refuses when `restarts >= maxRoundAttempts` unless `limit_overrides.maxRoundAttempts` is higher (`DecisionError("restarts exhausted; raise-limit maxRoundAttempts or abandon")`).
  - `raise-limit`: `limit ∈ {hardStopBudgetMultiple, hardStopBudgetMultipleIndividual, maxRoundAttempts, maxTurnsPerGate, maxTurnsPerRun, maxRunWallClockHours}`; `value` required and greater than the current effective value; recorded in `limit_overrides` (round-scoped, as the owner's "temporary, specific new multiple for the round").
  - Returns `Applied(kind, resumed: bool, reopen_plan: bool, status_after, notes)`.
- `checkpoint_skipped(rs: RoundState, step: Step, cfg: Config) -> bool` — the delegation rule: `steps.<CHECKPOINT>` is 0, or mode is `delegate` with `through` null, or `through` is at or after the checkpoint in table order.
- `is_overridden(rs, step: Step, gate: bool) -> bool`.

Errors: `DecisionError` with a reason the driver can relay.
