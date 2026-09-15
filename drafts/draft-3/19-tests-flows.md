# 19 — Flow tests, the drift and lint tests, CLI tests, probes

Flow tests drive whole or partial rounds with the fake driver and the stub agent
(file 17) and assert on `STATE.json`, `HISTORY.md`, git and the ledger. All gates are
off in the fixture unless a test turns them on with `fixture_spec.generate(gates_on=…)`.

## `test_flow_start.py` (rounds.start and preconditions)
- `start_claims_round_0001`: branch `round/0001` exists on origin; worktree exists;
  STATE.json `PLANNING`; `base_commit` = origin/main; `origin_quote` stored;
  HISTORY.md has one entry; the OWNER.log slice contains the quote's entry.
- `start_refuses_each_precondition`: drift; stale definitions (edit `subAgents.yaml`);
  no hook (remove settings.json); empty `OWNER.log`; quote not in log; `allowUpstream:
  1`; a bad step order; each raises `RefusedError("PRECONDITIONS")` whose message names
  the reason, and no branch is pushed.
- `start_refuses_while_another_round_active`; `start_after_done_takes_next_id`
  (`0002`); `claim_lost_retries_next_id` (pre-create `round/0001` on origin →
  the claim lands on `0002`).
- `multiple_active_rounds_refuse` (two branches with non-terminal state).

## `test_flow_plan.py` (CHAT-TO-PLAN)
- `next_in_planning_returns_chat_action` with the prompt file rendered and
  `then` showing the decision form; a second `next` returns the same action without
  a new attempt or turn.
- `record_plan_requires_decision_and_quote`; `record_plan_quote_must_be_in_log`;
  `record_plan_refuses_unanswered_questions`; `answers_quotes_verified` (an answer
  quote not in the log refuses).
- `approve_sets_checkpoints_mode`; `delegate_through_sets_through`; `overrides_recorded`
  and `override_unskippable_refuses`.
- `plan_strays_reverted`: `stray_write` behaviour → the stray files are gone, the
  attempt record lists them, the plan is accepted.
- `plan_gate_when_on`: with `CHAT-TO-PLAN: 1` and a `CHAT-TO-PLAN-GATE.txt` in
  `extra_prose`, `next` after the record yields a gate spawn; without the prose file,
  `start` refuses (lint).

## `test_flow_round.py` (a complete round, gates off, delegated)
- `full_round_lands_and_books`: run to `done`; assert in order: every producer step
  accepted with one attempt; checkpoints `skipped`; `landed_commit` set and equal to
  origin/main after landing; POSTMORTEM and CLEANUP ran after landing; `sync.status ==
  synced` and origin/main contains the round folder with `STATE.json` `DONE`,
  `POSTMORTEM.md`, the `HISTORY.md`; the ledger has living, archive and test charges
  with the values recomputed by the test from the fixture prices (new test file,
  `mul` added, `POSTMORTEM.md` summary tokens); `final_message` contains the Summary
  text and the charges block; the worktree is removed; INDEX.md regenerated on main.
- `full_round_with_checkpoints`: approval `approve` → two `checkpoint` actions with
  messages containing `SPEND`, `FLAGS`, `JUDGMENT CALLS SINCE LAST PAUSE`; owner
  script approves both; flags from `done_flags` on TESTS-TO-SUITE appear in the
  CHECKPOINT-2 message and are marked delivered.
- `delegate_through_spec_to_tests`: CHECKPOINT-1 skipped, CHECKPOINT-2 asked.
- `override_skips_step_and_gate`: `--override PLAN-AGENTS,PLAN-TO-SPEC-GATE` (with
  the gate on) → PLAN-AGENTS `skipped`, later attempts use `defaultAgent`, no gate
  attempt for PLAN-TO-SPEC.
- `tests_to_suite_override_keeps_tests_in_suite`.
- `frozen_tests_enforced`: `edit_frozen_tests` on SPEC-TO-IMPLEMENTATION → the test
  edit reverted, the attempt still accepted.
- `judgment_calls_ingested`: `done_jc` → the trails have three lines (two from the
  CLI, one from the message) with step and attempt; the next checkpoint message lists
  them.

## `test_flow_gates.py` (gates on for every capable step)
- `gate_pass_accepts`: producer → gate spawn (`agent_definition` ends with `-gate`,
  `read_only`) → PASS → next step.
- `gate_fail_retries_with_findings`: `fail_blocking` then `pass`; the second producer
  prompt contains the finding verbatim and its id under `PRIOR FINDINGS`; the producer
  used `fix_all`; the finding is `closed` after acceptance.
- `missing_resolution_is_invalid`: `missing_resolution` → `InvalidError` (exit 5),
  attempt marked `INVALID`, next `next` re-prepares the same phase with a new attempt
  number; after `maxRoundAttempts` invalid results → pause `INVALID_LIMIT`.
- `dispute_then_withdraw`: `dispute_all` → gate `withdraw_all` → finding `withdrawn`,
  step accepted.
- `dispute_then_uphold_twice_settles`: `uphold_all` twice → `settled`; a later
  `dispute_settled` result is invalid.
- `repeat_of_withdrawn_dropped`: after a withdrawal, `fail_repeat` → the repeated
  finding `dropped`, HISTORY has the note, and since no other finding is open the
  verdict FAIL with zero remaining findings still fails the producer (verdict wins)
  and the retry prompt shows no findings needing resolution.
- `verdict_wins_both_ways`: `fail_nonblocking_only` → findings upgraded to blocking;
  `pass_blocking` → downgraded to flags delivered at the next pause.
- `gate_limit_pauses`: three `fail_blocking` → pause `GATE_LIMIT` with the findings in
  the message; `resume` grants three more turns; the round continues.
- `gate_strays_reverted`: `gate_writes` → the file is gone; verdict applied.
- `gate_findings_file_saved` under `FINDINGS/<STEP>-<n>.json`; the gate prompt lists
  the artifact, its inputs and, for SPEC-TO-IMPLEMENTATION, the diff.

## `test_flow_pauses.py`
- `needs_owner_pauses_even_when_delegated`: `needs_owner` on PLAN-TO-SPEC → pause
  `NEEDS_OWNER`; the message has the question verbatim; `resume` with a quote → the
  next PLAN-TO-SPEC prompt has the quote under `OWNER DECISIONS`; attempt number 2.
- `blocked_pauses_with_narrow`.
- `turn_limit_pauses`: `maxTurnsPerRun = 3` → pause `TURN_LIMIT` at the fourth
  `next`; `resume` resets the counter.
- `wall_clock_pauses`: `clock.advance(13h)` → pause `WALL_CLOCK`.
- `hard_stop_on_attempt_cost`: usage callable returning huge tokens → pause
  `HARD_STOP` after `record`; `resume --hard-stop-multiple 100` continues and the
  override is stored with the quote.
- `individual_hard_stop`; `resume_refuses_past_max_restarts_without_extend`;
  `resume_refuses_when_not_paused`; `abandon_from_pause_ends_round` (worktree removed,
  state `ABANDONED`, branch kept, nothing on main).
- `abandon_after_landing_syncs_record`: abandon during POSTMORTEM → origin/main has
  the round folder with `ABANDONED` state.
- `invalid_json_and_prose_wrapped`: `invalid_json` → exit 5; `prose_wrapped` → accepted.

## `test_flow_landing.py`
- `landing_clean_fast_forwards_main`.
- `landing_retries_when_main_moves`: `advance_main_elsewhere` (a non-conflicting
  file) between `pre_landing_main` capture and the push, simulated by a hook the test
  injects into `landing.land` via monkeypatch of `gitops.Repo.push_to` on first call →
  second loop succeeds; `landing.loops == 2`; `pre_landing_main` unchanged (the first
  captured sha) and the living charge measured from it.
- `landing_conflict_becomes_one_attempt`: `advance_main_elsewhere` edits `src/app.py`
  conflictingly → `next` yields a `LANDING` spawn with the conflicted file in the
  prompt; the stub `done` resolves; `record LANDING 1` commits the merge; main updated;
  the attempt's rung is `defaultAgent` when the agents plan has no LANDING entry.
- `landing_attempt_leaves_markers_is_invalid`; `landing_attempt_stray_reverted`
  (the non-conflicted edit is reverted, judged against the auto-merged index);
  `second_conflict_pauses`; `landing_verify_failure_pauses`.
- `projected_hard_stop_before_landing`: `big_artifact`-like growth of `src/` beyond
  the multiple → pause `HARD_STOP` before any merge; origin/main unchanged.
- `post_landing_sync_merges_postmortem_commits`: after CLEANUP, origin/main has the
  POSTMORTEM edits to `docs/TODO.md`; `sync_conflict_uses_landing_attempt`
  (another landing edits `docs/TODO.md` after our landing → LANDING-2 attempt →
  synced); `sync_exhausted_marks_failed` (push_to always rejected → `sync.status ==
  failed`, round `DONE`, message names the manual merge).
- `fence_recovery_keeps_orphan_branch`: two worlds on two clones of the same origin
  both `record` the same attempt; the loser gets `FenceError`, its local branch is
  reset to the remote and a `round/0001-orphan-*` branch exists locally.

## `test_flow_suite.py`
- `round_tests_listed_in_prompt`; `suite_mixed_moves_archive`: the archived function
  is under `tests-archive/tests/test_round.py`, gone from `tests/`, the suite still
  passes, `HISTORY.md` records the move, the ledger's test delta counts only suite
  tests; `suite_missing_decision_invalid`; `suite_flags_reach_owner`.

## `test_flow_ledger.py`
- `measured_usage_bills_what_happened`: the driver passes `--*-tokens` → `measured`
  true and the cost equals the arithmetic; without → estimated from the prompt file's
  tokens; `driver_overhead_once_per_step` (a retried step is charged once);
  `living_charge_uses_pre_landing_main` (a change landed elsewhere between
  `pre_landing_main` and the sync is not charged to this round);
  `postmortem_carry_forward_priced_specially`; `elapsed_cost_reported_not_summed`.

## `test_cli.py` (subprocess, `python src/run.py --root <fixture harness>`)
- `doctor_json_and_exit_codes` (0 clean, 3 with drift); `spec_status_diff_accept`
  round trip; `status_without_round_is_refused` (exit 3); `next_record_jc_via_cli`
  for one step with the stub writing files; `usage_error_exit_2` (unknown command,
  partial token flags); `owner_log_verify`; `index_check_and_write`; `prune`.

## `test_spec_drift.py` — THE drift test (real files)
- `spec_files_match_accepted_baseline`: from `real_repo_root()`, `specfiles.check_drift`
  is clean. On failure the assertion message is: one paragraph explaining that a spec
  file changed and must be reviewed, then `specfiles.diff_text` for every `added`,
  `removed` and `changed` file, then `run: python src/run.py spec accept` (and commit
  `local.yaml` and `archives/spec-baseline/`). Also fails when `local.yaml` has no
  baseline ("run install").

## `test_spec_lint.py` — the real spec data fits the code
- `real_config_loads_with_no_unknown_keys` (`load_project`, `load_agents`,
  `validate_cross`); `real_step_table_lint_has_no_errors` (`steps.lint` with the real
  prose; warnings are printed, not failed); `real_prompts_render_offline`
  (`doctor.run(offline=True)` has no `render` or `lint` errors; drift/generated/hook
  areas are ignored here because the drift test owns drift and a fresh clone may not
  be installed) [JC-45].

## `tests/probes/` — live agents with planted defects (opt-in, `-m probe`)
Each probe: generates the fixture spec, starts a round with a stub through the plan,
then runs one real attempt with `ClaudeCliAgent` at the `systemTestAgent` rung and
asserts the **harness reaction**, never the agent's wording:
- `test_probe_gate_catches_planted_ambiguity`: a `SPEC.md` with a planted
  contradiction; asserts the gate's message parses and contains at least one finding
  with a non-empty quote and suggestion (verdict not asserted).
- `test_probe_producer_respects_declared_paths`: a real PLAN-AGENTS attempt; asserts
  the result parses, the artifact validates, and any strays were reverted.
- `test_probe_final_message_parses`: a real gate on a valid artifact; asserts
  `validate_findings` succeeds.
- `test_probe_jc_tool_used`: the prompt asks (through the fixture prose) for a
  judgment call to be logged; asserts a line landed in a trail or the message.
Each probe records measured usage into the ledger when the CLI reports it.
