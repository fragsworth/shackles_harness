# 08 — Round state: `state.py`, `history.py`, `rounds.py`

## `src/state.py` — `STATE.json`, the runner's only state

**Owns:** the shape of `STATE.json`, loading/saving, and every small transition on it.
Pure data: no git, no files other than its own, no policy. **Depends on:** `errors`,
`localstate` (`HARNESS_VERSION`), `steps` (step order for coverage helpers).
**Depended on by:** `rounds`, `next_action`, `recording`, `pauses`, `findings`,
`landing`, `ledger`, `context`, `history`, `doctor`, tests.

### Shape

```json
{
  "harness_version": "1", "round": "0001", "status": "RUNNING",
  "created_at": "…", "updated_at": "…", "branch": "round/0001", "base_commit": "sha",
  "origin_quote": "the owner's words that started the round",
  "quote": 120.0,
  "position": {"step": "PLAN-AGENTS", "phase": "produce", "attempt": 1},
  "approval": {"mode": "checkpoints", "through": null,
               "overrides": {"skip_steps": [], "skip_gates": []}, "quote": "approved", "at": "…"},
  "step_records": {"PLAN-AGENTS": {"status": "active", "producer_attempts": 1, "gate_turns": 0,
                    "invalid_in_row": 0, "gate_allowance": 3, "accepted_at": null}},
  "attempts": [{"step": "PLAN-AGENTS", "attempt": 1, "kind": "producer", "rung": "max",
                "prompt_file": "PROMPTS/PLAN-AGENTS-1.txt", "result_file": "RESULTS/PLAN-AGENTS-1.json",
                "findings_file": null, "status": "spawned", "outcome": null,
                "spawned_at": "…", "recorded_at": null, "prompt_tokens": 3210,
                "usage": null, "measured": false, "cost_usd": 0.0,
                "strays_reverted": [], "verify": null, "commit": null}],
  "findings": {"F1": {"step": "PLAN-TO-SPEC", "raised_in": 1, "severity": "blocking",
               "quote": "…", "text": "…", "suggestion": "…", "status": "open",
               "upheld": 0, "resolutions": [], "rulings": []}},
  "flags": [{"id": 1, "text": "…", "source": "TESTS-TO-SUITE attempt 1", "delivered_at": null}],
  "owner_decisions": [{"purpose": "resume", "quote": "…", "step": "…", "attempt": 2, "at": "…"}],
  "frozen_tests": null,
  "landing": {"pre_landing_main": null, "landed_commit": null, "landed_at": null,
              "loops": 0, "conflict_attempts": 0},
  "sync": {"status": "pending", "loops": 0, "synced_commit": null},
  "ledger": {"entries": [], "attempts_total": 0.0, "driver_total": 0.0, "living_charge": null,
             "archive_charge": null, "test_charge": null, "total": 0.0,
             "elapsed_hours": null, "elapsed_cost": null},
  "run": {"number": 1, "started_at": "…", "turns": 0},
  "restarts": 0,
  "pause": null,
  "hard_stop_override": {"multiple": null, "individual": null, "quote": null},
  "abandoned": null
}
```

Finding ids are unique per round (`F1`, `F2`, …); runner-generated verify findings are
`R1`, `R2`, …. `pause`, when set: `{"reason", "step", "attempt", "message",
"questions", "at"}`. `frozen_tests`, when set: `{"commit", "files"}`. `abandoned`,
when set: `{"quote", "at", "after_landing"}`.

### Types

`Position`, `Approval`, `Overrides`, `StepRecord`, `AttemptRecord`, `FindingRecord`,
`Resolution`, `RulingRecord`, `Flag`, `OwnerDecision`, `Landing`, `Sync`,
`LedgerState`, `LedgerEntry`, `Run`, `Pause`, `HardStopOverride`, `Abandoned`, and
`RoundState` — all dataclasses with `to_dict()`/`from_dict()`; `from_dict` raises
`RefusedError("STATE_SHAPE")` naming the bad field.

### Functions and methods

- `RoundState.new(round_id: str, branch: str, base_commit: str, origin_quote: str,
  now: str) -> RoundState` — status `PLANNING`, position at the first step, phase
  `produce`, attempt 1, every step record `pending` with `gate_allowance =
  maxTurnsPerGate` (passed in by the caller as `gate_allowance: int`).
- `load(path: Path) -> RoundState` / `loads(data: bytes) -> RoundState` — raises
  `RefusedError("STATE_UNREADABLE")` or `RefusedError("STATE_VERSION")` when
  `harness_version` differs from `HARNESS_VERSION`.
- `save(path: Path, state: RoundState, now: str) -> None` — sets `updated_at`.
- `is_terminal() -> bool` — `DONE` or `ABANDONED`.
- `step_record(step: str) -> StepRecord`; `mark_step(step, status, now=None)`.
- `next_attempt_number(step: str) -> int` — 1 + the highest attempt of that step.
- `add_attempt(rec: AttemptRecord) -> None`; `attempt(step, n) -> AttemptRecord`
  (raises `KeyError`); `last_attempt(step, kind=None) -> AttemptRecord | None`;
  `open_attempt() -> AttemptRecord | None` — the one with status `spawned`, if any.
- `advance(step: str, phase: str, attempt: int) -> None`.
- `set_pause(reason, step, attempt, message, questions, now) -> None`;
  `clear_pause() -> None`; `new_run(now) -> None` (increments `run.number`, resets
  `turns`); `bump_turn() -> int`.
- `add_flags(texts: list[str], source: str) -> list[int]`; `undelivered_flags() ->
  list[Flag]`; `mark_flags_delivered(ids: list[int], now) -> None`.
- `add_owner_decision(purpose, quote, step, attempt, now) -> None`;
  `decisions_since_pause() -> list[OwnerDecision]` — the quotes that the next prompt
  shows (those added after the last recorded attempt of the current step).
- `next_finding_id(prefix: str = "F") -> str`; `findings_for(step) -> list[FindingRecord]`;
  `open_blocking(step) -> list[str]`; `disputed(step) -> list[str]`; `settled(step) ->
  list[str]`; `withdrawn_quotes(step) -> set[str]`.
- `is_covered_checkpoint(step: str) -> bool` — uses `approval.mode`/`through` and
  `steps.checkpoint_covered`.
- `step_skipped(step) -> bool`; `gate_skipped(step) -> bool` — from
  `approval.overrides`.
- `effective_hard_stop() -> tuple[float | None, float | None]` — the round overrides.
- `summary() -> dict` — status, position, spend, quote, pause reason; for `status`
  output and messages.

## `src/history.py` — `HISTORY.md`

**Owns:** the append-only narrative: one entry per attempt, verdict, owner decision,
pause, landing loop, sync, charge, dropped finding and stray revert. **Depends on:**
`tokens` (to show prompt sizes), `errors`. **Depended on by:** `recording`,
`next_action`, `pauses`, `landing`, `rounds`, `judgment_calls`. Never read by code.

- `HistoryEntry` (dataclass): `at: str`, `title: str`, `lines: list[str]`.
- `append(path: Path, entry: HistoryEntry) -> None` — writes `## <at> <title>` and one
  `- ` bullet per line, then a blank line; creates the file with a `# HISTORY` heading
  when absent.
- Entry builders, each `-> HistoryEntry`: `spawned(step, attempt, kind, rung,
  prompt_tokens, budget)`, `recorded(step, attempt, outcome, summary, cost, measured,
  strays: list[str], verify_ok: bool | None)`, `gate(step, attempt, verdict, findings:
  list[tuple[str, str, str]]` (id, severity, first 120 chars of text)`, `rulings`)`,
  `owner(purpose, quote, step)`, `paused(reason, message)`, `resumed(quote)`,
  `landing(event: str, detail: str)`, `sync(event, detail)`, `charges(living,
  archive, tests, total, elapsed_cost)`, `note(text)`.

## `src/rounds.py` — claiming, discovering and ending rounds

**Owns:** round ids, the claim (`start`), discovery of the active round from git,
worktree presence, scaffolding, `abandon`, `status`, `prune`. **Depends on:**
`gitops`, `state`, `history`, `paths`, `config`, `specfiles`, `localstate`,
`ownerlog`, `agentdefs` (staleness), `steps` (lint), `prose`, `landing` (sync on
abandon after landing), `errors`. **Depended on by:** `commands`, `next_action`,
`recording`, `pauses`, `doctor` (preconditions).

- `RoundRef` (dataclass): `id`, `branch`, `remote_sha`, `status`, `is_terminal`.
- `LoadedRound` (dataclass): `ref: RoundRef`, `state: RoundState`, `rp: RoundPaths`
  (inside the worktree), `worktree_harness: Path`, `read_sha: str` (the branch sha
  the state was read at; every later push uses it as the lease).
- `discover(repo: Repo, cfg: ProjectConfig) -> list[RoundRef]` — after `fetch`, for
  every `origin/round/NNNN` branch reads `STATE.json` with `repo.show(ref, path)`;
  unreadable state → a ref with status `UNKNOWN`, non-terminal (so it blocks `start`
  until the owner looks).
- `active(repo, cfg) -> RoundRef | None` — the single non-terminal ref; more than one
  raises `RefusedError("MULTIPLE_ACTIVE")` naming them [JC-05].
- `next_id(repo, cfg) -> str` — 1 + max of ids under `archivesPath/rounds/` on
  `origin/main` and of `round/*` branches; `0001` when none.
- `preconditions(world: World) -> list[str]` — the `start` refusals listed in
  `02-lifecycle.md §3`, as messages; empty when all pass. Shared with `doctor`.
- `start(world: World, quote: str, now: str) -> LoadedRound` — runs `preconditions`
  (raises `RefusedError("PRECONDITIONS")` with the list), verifies the quote
  (`ownerlog.verify`), claims the id (`gitops.create_branch_from`, scaffold, commit,
  `push_new_branch`; on `FenceError` retries with the next id, at most
  `maxRoundAttempts` times, then raises), writes the OWNER.log slice, appends the
  history entry, ensures the worktree, returns the loaded round.
- `scaffold(rp: RoundPaths, st: RoundState) -> list[Path]` — creates the folders,
  `STATE.json`, `HISTORY.md`, the two empty judgment-call files (a one-line heading
  each), returns the created paths for the commit.
- `ensure_worktree(repo: Repo, round_id: str, branch: str) -> Path` — adds
  `.worktrees/round-<id>` on the branch if missing; if present, checks out the branch
  and fast-forwards it to `origin/<branch>`; raises `RefusedError("WORKTREE_DIRTY")`
  only when the worktree has uncommitted changes **and** no attempt is `spawned`
  (a spawned attempt's uncommitted work is expected).
- `load_active(world: World) -> LoadedRound` — `discover` + `active` +
  `ensure_worktree` + `state.load`; raises `RefusedError("NO_ACTIVE_ROUND")`.
- `load_by_id(world: World, round_id: str) -> LoadedRound`.
- `abandon(world, quote: str, now: str) -> RoundState` — verifies the quote; refuses
  when terminal; sets `ABANDONED` with `after_landing` = whether `landed_commit` is
  set; commits and pushes with the lease; when landed, runs `landing.sync` so the
  record reaches main [JC-64]; removes the worktree.
- `status_text(lr: LoadedRound) -> str` — a human block: status, position, attempts
  so far, spend/quote, pause, undelivered flags count.
- `prune(world) -> list[Path]` — removes worktrees of terminal rounds; remote branches are kept [JC-52].
