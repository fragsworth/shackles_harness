# 10 — Round engine (`round_start.py`, `round_next.py`, `round_record.py`, `round_owner.py`, `advance.py`, `mechanical.py`, `verify.py`, `suite.py`, `landing.py`)

**Purpose.** The state machine that takes a round from claim to end. It is split into
files by *event* (start, next, record, owner verb) and by *mechanism* (advance,
mechanical checks, verify, suite moves, landing) so that each can be rewritten from its
section alone. Every file reads and writes the round only through `state.py` (08) and
performs git only through `gitops.py` (07).

**Owns.** Preconditions of `start`; what `next` yields; what `record` checks and books;
owner verbs and pauses; step acceptance and skipping; mechanical checks; running the
suite; archiving tests; landing, the conflict attempt and the bounded sync.

**Depends on.** 04, 05, 06, 07, 08, 09.

**Depended on by.** 03 (CLI) only.

Shared context object (defined in `round_start.py`, built by the CLI once per command):
`class Ctx` (frozen): `paths: Paths`, `cfg: Config`, `roster: Roster`, `prose:
dict[str,str]`, `now: Callable[[], datetime]`, `run_py: Path`. Round-bound context
`class RoundCtx(Ctx)`: `state: State`, `state_path: Path`, `worktree: Path`,
`wt_paths: Paths` (layout inside the worktree), `round_folder: Path`.

---

## `round_start.py`

- `preflight(ctx: Ctx, *, for_start: bool) -> list[str]` — errors, all collected:
  spec drift (`specfiles.drift` non-empty or no baseline; message = `format_drift`);
  `steps.lint` errors; every prompt renders offline with no unresolved token (via
  `plumbing.placeholder_attempt` + `assemble_prompt` for each step's producer, gate,
  checkpoint and the conflict prompt); `config.unknown` and `roster.unknown` non-empty
  (JC-08); OWNER.log absent (`ownerlog.exists_and_nonempty` false: "without a log,
  start refuses"); agent definitions stale (JC-10); git: version, remote exists (JC-12), fetch
  succeeds, main exists; when `for_start`: the driver's checkout has no dirty paths
  under living paths or the archives (JC-37); no other worktree holds a round that is
  not `ended` (one round at a time per checkout).
- `start(ctx) -> RoundCtx` — `preflight`; `next_round_id`; create the round folder
  inside a temporary branch checkout via `claim_round` (the first commit contains only
  `STATE.json` with status `claimed`); on `REJECTED` retry the id up to 3 times, then
  raise `StartRefused("could not claim a round id")`; `worktree_add`; write
  `HISTORY.md` header; set `limits.started_at`; `status = planning`; `save`; fence
  push (`expected = claim sha`). Records the OWNER.log `last_index` as `claim_index`
  in `owner_words[0]` (verb `start`, no quote).
- `open_round(ctx, round_id: str | None) -> RoundCtx` — locates the round to act on:
  the given id, else the single non-ended round among worktrees; raises
  `NoActiveRound`. Loads STATE from the worktree.
- `fence(rctx: RoundCtx, message: str) -> None` — `commit_all(round folder)`,
  `fence_push(expected = state.fence)`; on `REJECTED` sets pause `fence` (saved
  locally only) and raises `FenceLost`. Every state change in the engine ends with a
  call to this function; it is the "every state change pushes the branch" rule (JC-41).

Errors: `StartRefused(reasons)`, `NoActiveRound`, `FenceLost`.

## `round_next.py`

- `next_action(rctx) -> NextAction` (S16) — pure decision from STATE plus limits:
  1. `status == ended` → `ended` with the bill.
  2. `pause` set → `pause` with `owner_text = pause_text(rctx)`.
  3. `current` set → the same `spawn`/`driver-step` again (idempotent; the prompt
     file already exists).
  4. Limits (JC-16): wall clock (`now − started_at > maxRunWallClockHours`) or
     `attempts_total >= maxTurnsPerRun` → set pause `limit`, fence, return `pause`.
  5. Otherwise `issue(rctx)`.
- `issue(rctx) -> NextAction` — determines the step and kind: the first `pending` step;
  if it is skipped by override → `advance.skip(rctx, step)` and recurse; CHECKPOINT
  and delegated through it → skip; CHECKPOINT otherwise → pause `checkpoint` (JC-38) with the
  rendered checkpoint prompt as `owner_text`; LANDING → `landing.land(rctx)` (which
  either advances, pauses, or opens a conflict attempt and returns its spawn); a
  gated step whose producer was accepted but whose gate has not passed → gate attempt;
  else producer attempt (or `driver-step` for CHAT-TO-PLAN). Builds the
  `AttemptSpec` (`build_attempt_spec`), assembles the prompt (strict), writes
  `PROMPTS/STEP-n.txt`, `open_attempt`, fence. Turn accounting: `turn =
  state.steps[step].rejections + 1`, `max_turns = maxTurnsPerGate`.
- `build_attempt_spec(rctx, step: Step, kind, n: int) -> AttemptSpec` — resolves
  inputs and write roots from the step table symbols to absolute worktree paths; rung
  from `state.agents_plan` (`steps[step].agent` / `gates[step].agent`) or the config
  defaults before a plan exists (`defaultAgent`, `gateAgent`); budget from
  `pricing.step_budget` with the plan's share or `defaultShares` (JC-34); findings and
  resolutions text from 08; owner words since the last pause; `jc_command`;
  `agent_definition` from 06.
- `pause_text(rctx) -> str` — owner-facing: the pause kind and detail; the step;
  spend/quote/remaining; unshown flags (then marked shown); counts of judgment calls
  (defined/undefined) with the file paths; the last result's `summary`, `questions`
  (NEEDS-OWNER) or `narrow` (BLOCKED) verbatim; for `checkpoint`, the rendered
  `CHECKPOINT-OVERVIEW` first; the verbs that clear this pause.

## `round_record.py`

- `record(rctx, *, usage: dict | None, elapsed_s: float | None) -> RecordOutcome` —
  `RecordOutcome(outcome, notes, next_hint)`. Steps, in order:
  1. Require `current`; read the result with `results.read_result` → on
     `MalformedResult`: `close_attempt(MALFORMED)`, note, `rejections += 1`, re-issue
     the same kind next time (bounded by `maxTurnsPerGate`, JC-14); fence; return.
  2. `mechanical.check_attempt(rctx, attempt)` → reverts strays and spec-file edits
     (notes), then runs the kind-specific checks; a failing check →
     `close_attempt(MECHANICAL-FAIL)` with the output in `extra_notes` for the retry,
     `rejections += 1`; fence; return.
  3. Bill: `ledger.bill_attempt` (kind ≠ driver); individual hard stop → pause `limit`
     (JC-33) after step 4.
  4. Judgment calls in the result → `judgmentcalls.append_from_result`; flags →
     `add_flags`.
  5. By kind and status: producer/driver/conflict `DONE` → `missing_resolutions`
     non-empty → reject (note lists ids); else `findings.apply_resolutions`; commit the
     worktree (`commit_all(None)`, message `STEP-n`) so the attempt's diff is frozen;
     `close_attempt(accepted)`; CHAT-TO-PLAN → pause `approval`; gated step → gate
     next; else `advance.accept(rctx, step)`. `NEEDS-OWNER`/`BLOCKED` → pause of that
     kind. Gate → `normalize_gate`, `apply_rulings`, `add_new` (dropped repeats noted),
     `apply_verdict`, `write_findings_file`; `PASS` → `advance.accept`; `FAIL` →
     `rejections += 1`; at `maxTurnsPerGate` → pause `limit`; else the producer is
     re-issued on the next `next`.
  6. `history.append_attempt`; `save`; `fence`.
- `read_usage_flags(args) -> dict | None` — all four token counts required for
  `measured=True`; partial flags are an error at the CLI.

## `round_owner.py`

- `owner_verb(rctx, verb: str, quote: str, args: dict) -> str` — verifies the quote
  with `ownerlog.verify_quote(after_index = pause.log_index_at_pause)`; a miss raises
  `QuoteNotFound` (the runner never guesses). Records the owner word, appends the
  round's OWNER.log slice (JC-50), applies the verb, fences, returns owner text. Verbs:
  - `approve` — allowed in pauses `approval`, `checkpoint`; `approval` requires every
    PLAN.json question answered (else `PlanQuestionsOpen(numbers)`); sets
    `mode = checkpoints` (from approval) and clears the pause; `status = running`.
  - `delegate [--through STEP]` — as `approve` but `mode = {delegated, through}`
    (JC-42): checkpoints whose table position ≤ `through` are skipped; no `through` =
    all checkpoints skipped.
  - `override --steps A,B --gates C` — allowed in `approval`/`checkpoint`; names must
    be table steps; `not-skippable` steps raise `OverrideRefused` ("the plan itself
    cannot be skipped"); recorded, applied by `advance.skip`.
  - `answer --number N` — allowed in `approval`; stores the quote as the answer.
  - `abandon` — any pause or none; `advance.end(rctx, "abandoned")` (JC-22).
  - `continue` — allowed in `needs-owner`, `blocked`, `limit`, `fence`, `landing`
    (JC-27): clears the pause; for `limit` resets the counter that fired (`rejections`
    of the step, or grants `maxTurnsPerRun` more attempts, or extends wall clock by
    `maxRunWallClockHours` from now); for `fence` re-fetches and requires the remote
    branch to equal the local head (else stays paused); the quote is carried into the
    next prompt as owner words.
  - `raise-hard-stop --multiple X` — any time; `state.hard_stop_multiple = X` for this
    round only.

Errors: `QuoteNotFound`, `PlanQuestionsOpen`, `OverrideRefused`, `VerbNotAllowed(kind)`.

## `advance.py`

- `accept(rctx, step: str) -> None` — `bill_driver_step`; kind-specific acceptance:
  PLAN-AGENTS → validate S3 (`validate_agents_plan`, errors → treated as a mechanical
  rejection of the producer, not acceptance), store in `state.agents_plan`; TESTS-TO-
  SUITE → `suite.apply(rctx)`; CHAT-TO-PLAN → `state.quote_usd = plan.quote_usd`;
  POSTMORTEM/CLEANUP → nothing special; then `set_step_status(accepted)`. CLEANUP
  acceptance continues into `end(rctx, "landed")`.
- `skip(rctx, step) -> None` — applies `skip_effect` (JC-21): `default-agents-plan`
  (defaultAgent/gateAgent everywhere, `defaultShares` minimums, remainder split equally),
  `plan-is-spec` (SPEC-TO-TESTS/IMPLEMENTATION inputs point at PLAN.json), `no-new-tests`,
  `no-code`, `all-to-suite`, `skip-checkpoint`, `no-postmortem`, `no-cleanup-attempt`
  (the runner's own cleanup still runs). Marks the step `skipped`, notes HISTORY.
- `validate_agents_plan(plan: dict, cfg, roster, overrides) -> list[str]` — S3 rules (JC-35).
- `end(rctx, reason: "landed"|"abandoned"|"failed") -> None` — for `landed`:
  `ledger.book_round`, write OWNER.log slice (final), `index.regenerate` into the
  worktree, commit, `landing.sync(rctx)`; for `abandoned`: commit the round folder
  only and `landing.sync_archives_only(rctx)`; then `status = ended`, HISTORY round-end
  with the bill, fence, `fast_forward_checkout` of the driver's checkout when clean,
  `worktree_remove` on success (kept on failure with a note).

## `mechanical.py`

- `check_attempt(rctx, attempt: Attempt, spec: AttemptSpec) -> CheckResult` —
  `CheckResult(ok: bool, output: str, reverted: list[str], notes: list[str])`. Runs on
  the worktree's **uncommitted** diff (the attempt's own work), in this order:
  1. `strays(rctx, spec)` → `revert_paths` (never a failure); note each path. Only the worktree is ever touched (JC-23).
  2. Spec-file edits inside the worktree (any path whose worktree-relative form is a
     spec file) → reverted, noted as `spec file edit reverted`.
  3. Kind-specific:
     - `driver` (CHAT-TO-PLAN): PLAN.json parses as S2 with its mechanical checks.
     - PLAN-AGENTS producer: AGENTS-PLAN.json parses; `validate_agents_plan` empty.
     - PLAN-TO-SPEC producer: both artifact files exist and are non-empty; SPEC.json parses.
     - SPEC-TO-TESTS producer: `verify.collect_only` succeeds (syntax/import errors
       fail); the pre-existing suite (tests present at `base_commit`) still passes
       (`verify.run(select=pre_existing)`); new tests may fail (JC-46).
     - SPEC-TO-IMPLEMENTATION producer: `verify.run()` passes (whole suite, frozen
       tests included) within `verifyTimeoutSeconds`; a timeout fails with the note.
     - TESTS-TO-SUITE producer: SUITE.json parses (S5); every path is a test file
       changed by this round; no duplicate decisions.
     - POSTMORTEM producer: POSTMORTEM.md exists and has a Summary section (S6).
     - CLEANUP producer: `verify.run()` passes.
     - `conflict`: `conflict_markers(conflict_files)` empty; every file outside
       `conflict_files` equals the auto-merged tree (`restore_from_tree` for any that
       differ, noted as strays); `verify.run()` passes.
     - `gate`: no diff allowed at all (a gate is read-only): any change is reverted and
       noted; never fails.
- `strays(rctx, spec) -> list[str]` — changed paths not under `spec.write_roots` and not
  under the round folder.
- `allowed_roots(rctx, step: Step, conflict_files) -> list[Path]` — resolves the
  table's write-path symbols: `round-folder`, `living` (livingSourcePaths), `tests`
  (testPaths), `living-minus-tests`, `carry-forward` (`docs/TODO.md`,
  `docs/CLARIFICATIONS.md`), `conflict-files`.

## `verify.py`

- `run(worktree: Path, cfg, select: list[str] | None = None, timeout_s: int | None =
  None) -> VerifyResult` — `VerifyResult(passed: bool, timed_out: bool, output: str
  (last 200 lines), seconds: float, command: list[str])`; runs `cfg.verifyCommand`
  (+ `select` paths when given) with `cwd = worktree/harness_root`,
  `timeout = timeout_s or cfg.verifyTimeoutSeconds`, environment `SHACKLES_PROBES`
  unset. Never raises for a failing suite; raises `VerifyError` only when the command
  cannot be started.
- `collect_only(worktree, cfg) -> VerifyResult` — the command plus `--collect-only -q`.
- `pre_existing_tests(rctx) -> list[str]` — test files under `testPaths` at
  `base_commit` (`ls_tree_files`).

## `suite.py`

- `apply(rctx) -> SuiteReport` — reads SUITE.json (S5); for `archive` decisions moves
  the file (or splits it, JC-53) into `tests-archive/<path relative to the testPaths
  root>`; `suite` decisions leave files in place; then `verify.run()` must pass, else
  the acceptance is turned into a mechanical rejection of TESTS-TO-SUITE with the
  output. Commits the move (`TESTS-TO-SUITE: archive`). `SuiteReport(moved: list[str],
  kept: list[str], split: list[str])`.
- `split_file(src: Path, archive_dst: Path, archived_functions: list[str]) -> None` —
  copies the whole file to the archive and removes the named functions from the suite
  copy (Python only: by `def`-block boundaries; for other languages the whole file is
  archived and a flag is added for the owner).
- `round_test_files(rctx) -> list[str]` — files under `testPaths` added or modified
  since `base_commit`.

## `landing.py`

- `land(rctx) -> NextAction | None` — the LANDING step, re-entered by `next` until it
  completes:
  1. If `state.landing.landed_commit` → already landed: `advance.accept(LANDING)`; `None`.
  2. `fetch`; `main_before = rev_parse(<remote>/<main>)`; store it (first time only).
  3. Hard stop: `ledger.projected_living(main_before → HEAD)`; `over_hard_stop` → pause
     `limit` with the projection in the text; return the pause.
  4. `merge_tree(base = merge-base, ours = main_before, theirs = HEAD)`.
     - Clean → `verify_tree(rctx, tree)` (a temporary worktree of `commit_tree`) → fail
       → pause `landing` with the output; pass → `push_ref(commit, main, expected =
       main_before)`; `PUSHED` → `landed_commit`; rebase the round branch onto it
       (`update_branch` + `checkout_tree_into_worktree(tree)`) so POSTMORTEM starts from
       the landed tree; `advance.accept(LANDING)`; `None`. `REJECTED` → `landing_tries
       += 1`; `< maxRoundAttempts` → loop from 2 (JC-15); else pause `landing`.
     - Conflicts → store `conflict_files`, `auto_merged_tree`;
       `checkout_tree_into_worktree(tree)`; open one `conflict` attempt (through
       `round_next.issue` with kind `conflict`, rung = plan's LANDING agent or
       `defaultAgent`); return its spawn action. When that attempt is accepted
       (`record`), `land` is re-entered: the worktree's HEAD (the resolved commit)
       replaces `theirs` and the loop continues at step 4's clean path (the merge is
       now trivial because the resolution commit descends from both).
- `verify_tree(rctx, tree: str) -> VerifyResult` — temporary worktree, `verify.run`,
  removed afterwards.
- `sync(rctx) -> None` — after CLEANUP: bounded loop (`maxRoundAttempts`): `fetch`;
  if `<remote>/<main>` is an ancestor of HEAD → `push_ref(HEAD, main, expected)`;
  else `merge_tree` → clean → `commit_tree` with both parents, verify, push; conflict →
  one `conflict` attempt as in `land` (re-entered via `next`); exhausted → pause
  `landing` ("post-landing sync needs the owner"). On success: `synced_commit`.
- `sync_archives_only(rctx) -> None` — for abandoned rounds: a commit onto
  `<remote>/<main>` containing only the round folder (from the round branch), pushed
  with lease, bounded the same way (JC-22).

## Invariants (component-wide)
- Every state change is followed by exactly one `fence`; a `FenceLost` stops the
  command with the local state saved and the pause `fence` recorded.
- `next` never spawns anything itself and never changes the worktree except by
  writing a prompt file and STATE; `record` is the only place worktree content is
  committed, reverted or moved.
- Delegation influences only `issue`'s treatment of CHECKPOINT steps.
- The engine never reads a prompt or result as prose; every branch on agent output is
  on a field of S7.
- No function in this component prints; owner text is returned and printed by 03.

## Covered by
`tests/test_round_flow.py` (stub-driven end-to-end paths), `tests/test_round_start.py`,
`tests/test_round_owner.py`, `tests/test_advance.py`, `tests/test_mechanical.py`,
`tests/test_verify.py`, `tests/test_suite.py`, `tests/test_landing.py`.
