# 63 — harness/tests/mechanics/ (whole rounds, stub-driven)

Parent: `60-tests.md`. Every test runs one or more rounds on a temp repo with
the generated one-line spec (`61-tests-stub.md`) and the stub driver. They
assert on `STATE.json`, `HISTORY.md`, the round folder, the branches on the
bare remote, and the ledger. Marker `mechanics`. Limits in the generated
`project.yaml` are small (gate turns 2, run turns 30, round attempts 1) so
limit paths are cheap to reach `[JC-30]`.

## test_happy_path.py
- `test_round_lands_with_all_gates_off` — default script, `approve` with
  checkpoints: two `CHECKPOINT` pauses answered `approve`; ends `landed`;
  `main` contains the round folder, `src/app.py` change, the round test in
  `tests/`; `round/0001` exists on the remote; every step `accepted`.
- `test_round_with_all_gates_on` — every gate switched to 1 in overrides;
  one gate attempt per gated step; `FINDINGS/` has one file per producer
  attempt; `RESULTS/` has `<STEP>-GATE-1.json` files.
- `test_delegate_skips_both_checkpoints` — no `OWNER` action except none;
  `stepStatus skipped` for both checkpoints.
- `test_delegate_through_skips_only_up_to_step` — `delegate through
  PLAN-TO-SPEC`: CHECKPOINT-1 skipped, CHECKPOINT-2 pauses.
- `test_second_round_id_increments_and_remaining_decreases` — two rounds:
  ids `0001`, `0002`; `project.remaining` rendered in the second round's
  prompt is `budget` minus the first round's booked total.
- `test_prompt_files_contain_agents_md_head_and_process_instructions`.
- `test_history_has_one_block_per_attempt_and_owner_command`.

## test_start_refusals.py
- `test_refuses_without_owner_log`, `test_refuses_on_spec_drift` (edit a
  prose file after accept), `test_refuses_on_open_round`,
  `test_refuses_on_unknown_step_in_project_yaml`,
  `test_refuses_on_gate_on_without_prose`, `test_refuses_on_unknown_key`,
  `test_refuses_on_unresolved_token` (a prose file with `{{ project.nope }}`).

## test_owner_verbs.py
- `test_quote_must_be_in_log` — `owner approve --quote "approve"` without
  the word logged -> refused; after logging -> ok.
- `test_answers_required_before_approval` — plan with two questions:
  approve refused until both `answer` verbs recorded; any text accepted.
- `test_override_gate_and_step` — `override` PLAN-AGENTS step and
  POSTMORTEM gate: PLAN-AGENTS `skipped` with default shares in the next
  prompt; POSTMORTEM runs without a gate.
- `test_override_of_plan_refused`, `test_override_of_landing_refused`.
- `test_abandon_ends_without_landing_and_lands_round_folder_only` — `main`
  has `archives/rounds/0001/` and no `src` change; `LEDGER.md` row says
  `abandoned`; outcome recorded.
- `test_mid_round_owner_words_do_not_change_state` — an unrelated log entry
  changes nothing; `next` is idempotent.

## test_gates.py
- `test_fail_then_fix_then_pass` — gate FAIL with one blocking finding;
  producer retry prompt lists it; `resolves_all` then `gate_pass`; `gateTurns
  == 1`; step accepted.
- `test_verdict_wins_over_flags` — `gate_fail_no_blocking_flags`: findings
  become blocking with a note; `gate_pass_with_blocking_flags`: step accepted
  and findings non-blocking with a note.
- `test_dispute_upheld_twice_is_settled` — dispute, upheld, dispute again,
  upheld: finding `settled`; a third dispute rejected with a note.
- `test_repeat_of_withdrawn_finding_dropped` — withdrawn, then re-raised
  with the same quote: dropped; HISTORY notes it; step accepted on PASS.
- `test_gate_turn_limit_pauses` — FAIL three times with limit 2: pause
  `LIMIT`; `resume` after the owner's words continues with a new producer
  attempt; `abandon` ends.
- `test_for_owner_findings_reach_next_checkpoint` — `gate_for_owner` on
  PLAN-AGENTS: CHECKPOINT-1's message contains the item; `ownerItems`
  marked shown.
- `test_gate_garbage_is_mechanical_retry_of_gate`.
- `test_gate_off_still_renders_gate_prose_in_producer_prompt`.

## test_strays.py
- `test_stray_living_file_reverted_not_failed` — SPEC-TO-TESTS writes into
  `src/`: the change is absent from the commit; the attempt is `done`;
  HISTORY notes the path.
- `test_spec_file_edit_reverted` — a producer edits `locked_prose/X.txt`:
  reverted; spec files on the branch identical to base.
- `test_frozen_artifact_edit_reverted` — PLAN-TO-SPEC edits `PLAN.json`.
- `test_state_and_history_edits_reverted`.
- `test_judgment_file_truncation_restored`.
- `test_judgment_tool_lines_land_in_commit` — three calls -> three lines in
  `DEFINED_JUDGMENT_CALLS.md` on the branch; gate's `judgmentCalls` appended
  by the runner to the right file.

## test_contracts_and_retries.py
- `test_garbage_final_message_respawns_with_notes` — `garbage()` once then
  DONE: two attempts; the second prompt has a RUNNER NOTES block; `mechanicalRetries == 1`.
- `test_missing_fields_respawn`, `test_prose_then_json_accepted`.
- `test_missing_artifact_respawn`.
- `test_mechanical_limit_pauses` — garbage forever with limit 1: pause `LIMIT`.
- `test_needs_owner_pauses_even_when_delegated` — questions stored; pause
  `QUESTIONS`; `answer` then `next` re-opens the step with the answers in the
  prompt.
- `test_blocked_pauses_with_narrow`.

## test_verification.py
- `test_failing_impl_respawns_until_pass` — `done_then_pass(1)`: two
  IMPLEMENTATION attempts; the retry prompt contains the failure tail.
- `test_tests_that_do_not_collect_respawn`.
- `test_verify_timeout_pauses` — `verifyTimeoutSeconds 1` and a sleeping
  test: pause `VERIFY` after the mechanical limit.
- `test_suite_moves_archive_files_and_suite_still_passes` — SUITE.json
  archives the round test: file appears under `tests-archive/`, absent from
  `tests/`; `main` after landing agrees.
- `test_mixed_suite_decisions_respawn`.
- `test_tests_to_suite_override_keeps_all_tests`.

## test_landing_and_sync.py
- `test_landing_merges_moved_main` — `move_main` on an unrelated file
  before LANDING: merged; `main` has both.
- `test_landing_conflict_becomes_one_attempt` — `conflicting_main` on
  `src/app.py`: `LANDING-1` attempt with the conflicted path in its prompt;
  `conflict_resolve`; landed; the auto-merged commit recorded in
  `state.landing`.
- `test_conflict_attempt_touching_other_file_is_reverted`,
  `test_conflict_markers_left_respawn`.
- `test_post_landing_commits_reach_main` — POSTMORTEM edits `docs/TODO.md`
  after landing: `main` has the edit at the end.
- `test_sync_bounded_and_pauses_on_conflict` — a conflicting `main` change
  to `docs/TODO.md` between landing and booking: pause `SYNC`; after the
  owner resolves on main, `resume` lands it.
- `test_main_moving_during_landing_retries_then_lands`.

## test_lease.py
- `test_two_starts_get_different_rounds` — start from two clones: `0001`
  and `0002`, no shared branch.
- `test_foreign_push_pauses_with_lease_lost` — `move_round_branch` after a
  producer attempt opens: `record` pauses `LEASE`; HISTORY names expected
  and actual shas.
- `test_every_state_change_is_pushed` — after each `next`/`record`/`owner`,
  the remote branch head equals `state.lease`.

## test_ledger.py
- `test_attempt_cost_from_tokens_split` — `--tokens 10000` at rung prices:
  entry `usd` equals the arithmetic; `source split`.
- `test_attempt_cost_estimated_without_tokens` — `source estimated`.
- `test_driver_overhead_once_per_step`.
- `test_living_charge_on_net_change_only` — a file created in
  IMPLEMENTATION and deleted in CLEANUP is not charged; the base cost applies
  to the surviving new file; the test base cost applies to the suite test.
- `test_archive_costs_frozen_at_booking` — plan, spec, summary tokens priced
  by their rates.
- `test_carry_forward_rate_applied`.
- `test_hard_stop_round_pauses_before_landing` — a tiny quote and a big
  living projection: pause `HARD-STOP` before LANDING.
- `test_hard_stop_attempt_pauses` — one attempt with huge `--tokens`.
- `test_ledger_md_row_after_landing_and_after_abandon`.
- `test_abandoned_round_bills_agents_but_not_living`.

## test_limits.py
- `test_run_turns_limit_pauses_and_resume_resets`,
  `test_wall_clock_limit_pauses` (limit set to a tiny fraction of an hour;
  `slow` behavior), `test_resume_over_round_attempts_refused`.

## test_prompts_offline.py
- `test_doctor_renders_every_prompt_clean_on_generated_spec` — no
  unresolved tokens; every table step's overview and gate rendered.
- `test_doctor_names_unresolved_token_and_file`, `test_doctor_names_unknown_step`,
  `test_doctor_names_defaulted_keys`, `test_doctor_names_extra_prose_file`,
  `test_doctor_warns_on_stale_agents_and_missing_hooks`.
- `test_step_end_follow_up_mode_returns_follow_up_action` — with
  `stepEndDelivery: follow-up`: after a producer record, `next` returns a
  `SPAWN` with `phase: step-end` for the same attempt; recording it appends
  the judgment calls `[JC-31]`.
