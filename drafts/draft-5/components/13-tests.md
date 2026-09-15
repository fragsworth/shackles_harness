# 13 — Tests (`tests/`)

**Purpose.** The permanent suite. It has three parts: the spec guard (the only test
that reads the real spec files), the mechanics tests (every module, run against a
generated one-line-per-file spec tree so a prose rewrite fails only the guard), and the
stub-driven flow tests (a scripted agent drives every engine path through the real
CLI). Live probes are component 14.

**Owns.** Fixtures, the spec-tree generator, the stub agent and its behavior catalog,
and one test file per source module plus the flow tests.

**Depends on.** Everything in `src` (under test); pytest; git on PATH.

**Depended on by.** `verify.py` runs it at record; CI runs it.

Conventions: pytest, one `test_<module>.py` per `src` module; no test touches the
network; every git test uses a temporary bare "remote" on disk; no test reads
`harness/locked_prose`, `project.yaml`, `subAgents.yaml`, `AGENTS.md` or `SPEC.md`
except `test_spec_guard.py`.

---

## `tests/conftest.py` — fixtures
- `spec_tree(tmp_path) -> SpecTree` — calls `fixtures.spec_tree.make(tmp_path)`:
  returns paths (`repo_root`, `harness_root`, `spec_yaml`) of a complete, minimal
  repository layout: `spec.yaml` (listing the same relative paths as the real one),
  `SPEC.md` (one line), `harness/AGENTS.md` (three `##` sections, one line each),
  `harness/project.yaml` (generated from `fixtures/config_values.py`: every schema
  key without a default gets a small valid value; `steps` in table order, all 1),
  `harness/subAgents.yaml` (four rungs, round prices, `estOutputFraction 0.5`,
  `driverUsdPerStep 1`), `harness/locked_prose/<NAME>.txt` for every required and
  optional name from `steps.required_prose_names() | optional_prose_names() |
  {COMMON-PROJECT, COMMON-ROUND, COMMON-OVERVIEW, COMMON-GATE}`, each **one line**:
  `<NAME>: {{ prose.COMMON-PROJECT }} {{ project.vision }} {{ round.id }}
  {{ agents.INVARIANTS }} {{ plumbing.PROCESS-INSTRUCTIONS }}` for overviews (gates
  get `{{ prose.COMMON-GATE }}` and the same plumbing token; `COMMON-*` files are one
  line with no tokens except `COMMON-ROUND` which uses every `round.*` name).
  Also copies `src/` (the real code) into `harness/src`, writes a minimal
  `harness/tests/test_seed.py` (one passing test) so verify has a suite, the four
  docs files with headers, `pyproject.toml`, `.claude/settings.json`.
- `repo(spec_tree) -> Repo` — `git init`, commit everything, create a bare remote at
  `tmp_path/origin.git`, push `main`; `Repo(checkout: Path, remote: Path, spec:
  SpecTree)`; also runs `setup` (baseline, agent defs, local.yaml) and writes an
  OWNER.log with one marker line.
- `ctx(repo) -> Ctx` — built with a controllable clock (`FakeClock.advance(hours)`).
- `cli(repo)` — `Callable[[list[str]], CliResult(code, stdout, stderr, json)]` that
  runs `shackles.cli.main` in-process with `cwd` at the checkout's harness root.
- `owner_says(repo)` — `Callable[[str], int]` appending a prompt line to OWNER.log
  through `hooks.hook_prompt` with a fake stdin JSON; returns the index.
- `stub(repo, cli)` — a `StubDriver` (below) bound to the CLI.
- `started(repo, cli, stub, owner_says)` — a round already started with a recorded
  minimal plan and `owner approve`; ready at PLAN-AGENTS.

## `tests/fixtures/`
- `spec_tree.py` — `make(tmp_path, *, prose_overrides: dict[str,str] = {}, config_overrides:
  dict = {}, roster_overrides: dict = {}) -> SpecTree`.
- `config_values.py` — `MINIMAL: dict` (one valid value per required key) and
  `ROSTER_MINIMAL`.
- `artifacts.py` — minimal valid `PLAN`, `AGENTS_PLAN(cfg)`, `SPEC`, `SUITE(paths)`,
  `POSTMORTEM_MD`, and result messages `done(...)`, `needs_owner(...)`,
  `blocked(...)`, `gate_pass()`, `gate_fail(findings)` builders.
- `sample_tests/` — small pytest files used as "round tests" (`test_new_pass.py`,
  `test_new_fail.py`, `test_mixed.py` with three functions).

## `tests/stub/` — the scripted agent
- `behaviors.py` — `BEHAVIORS: dict[str, Behavior]`; a behavior is `(name, apply:
  Callable[[StubContext], None])` where `StubContext` gives the prompt text, the
  parsed process-instruction paths (artifact, result, worktree, allowed roots; parsed
  from the labelled `PROMPT`/`RESULT` lines of `next` output and the plumbing's
  `ARTIFACT:` line, never from prose), the step, kind, attempt. Catalog (each writes
  the artifact where needed and the result file):
  `done_ok` · `done_with_flags` · `done_missing_resolution` · `done_disputing:F1` ·
  `done_fixing_all` · `needs_owner` · `blocked` · `malformed_json` · `code_fenced_json`
  · `wrong_status` · `stray_edit:<path>` · `spec_file_edit` · `edit_outside_roots` ·
  `gate_pass` · `gate_fail:<n findings>` · `gate_fail_no_findings` ·
  `gate_fail_nonblocking_only` · `gate_pass_with_blocking_flag` · `gate_repeat_withdrawn`
  · `gate_uphold:F1` · `gate_withdraw:F1` · `gate_edits_file` · `plan_with_questions:<n>`
  · `plan_bad_quote` · `agents_plan_ok` · `agents_plan_bad_shares` ·
  `agents_plan_over_ceiling` · `agents_plan_gate_on_off_gate` · `tests_add:<sample>` ·
  `tests_add_broken_syntax` · `impl_pass` (writes code that makes `test_new_fail.py`
  pass) · `impl_still_failing` · `impl_hangs` (sleeps past the timeout) ·
  `suite_archive:<path>` · `suite_split_mixed` · `suite_unknown_path` · `postmortem_ok`
  · `postmortem_no_summary` · `postmortem_edit_todo:<tokens>` · `cleanup_ok` ·
  `cleanup_delete_file:<path>` · `conflict_resolve_ok` · `conflict_leave_markers` ·
  `conflict_touch_other_file` · `jc_defined:<n>` / `jc_undefined:<n>` (calls `run.py jc`).
- `stub_agent.py` — `class StubDriver`: `__init__(cli, script: dict[str, list[str]])`
  where the script maps `"STEP"` or `"STEP-gate"` or `"LANDING-conflict"` to a list of
  behavior names consumed in order (last one repeats); `step_once() -> NextAction`
  (calls `next`, applies the behavior for the yielded attempt, calls `record` with
  `--tokens-*` from the behavior's declared usage or none) and `run_until(pred,
  max_steps=60) -> State`; `usage_default = {"in": 1000, "out": 200, ...}`.
- Its own tests: `tests/test_stub_agent.py` — every behavior name in `BEHAVIORS` is
  exercised once against a fake `StubContext` and produces the artifact/result it
  promises (parametrized over the catalog; guarantees the catalog stays truthful).

## `tests/test_spec_guard.py` (reads the REAL spec files)
- `test_baseline_exists` — `read_manifest` is not None (else fail with "run setup").
- `test_spec_files_match_baseline` — `drift` empty; on failure the message is
  `format_drift` (per-file unified diffs) — the owner sees exactly what changed.
- `test_no_unbaselined_spec_file` — `unbaselined` empty (a new `locked_prose/*` file).
- `test_no_missing_spec_file` — `missing` empty.

## `tests/test_paths.py`
`test_repo_root_found_from_src`, `test_paths_error_when_no_spec_yaml`,
`test_round_folder_substitutes_nnnn`, `test_round_folder_without_nnnn_raises`,
`test_round_file_resolves_every_roundpaths_key` (parametrized over S1's keys),
`test_paths_for_worktree_relocates_everything`, `test_is_under_rejects_symlink_escape`.

## `tests/test_specfiles.py`
`test_list_expands_glob_sorted_dedup`, `test_list_keeps_missing_nonglob_path`,
`test_list_error_without_files_key`, `test_write_baseline_snapshots_and_manifest`,
`test_write_baseline_removes_stale_snapshot`, `test_drift_none_after_accept`,
`test_drift_reports_unified_diff_for_changed_prose`, `test_drift_reports_missing`,
`test_drift_reports_unbaselined_new_prose_file`, `test_drift_no_baseline_flag`,
`test_format_drift_mentions_accept_command`, `test_binary_diff_phrase`.

## `tests/test_config.py`
`test_load_minimal_ok_no_defaulted_when_all_keys_present`,
`test_defaulted_keys_are_exactly_the_documented_ones` (asserts the set equals
`{testPaths, verifyCommand, promptTokenWarning, gitRemote, mainBranch}`),
`test_unknown_top_level_key_recorded`, `test_unknown_nested_roundpaths_key_recorded`,
`test_type_error_lists_all_problems_at_once`, `test_missing_required_key_named`,
`test_fractions_must_sum_to_one`, `test_steps_must_be_mapping_of_zero_one`,
`test_steps_preserve_file_order`, `test_roster_rank_from_order`,
`test_roster_missing_price_field`, `test_rung_ceiling_and_at_most`,
`test_gates_on_respects_table_and_overrides`,
`test_project_values_renders_lists_and_derived_keys`,
`test_project_values_has_every_config_key` (so any `{{ project.X }}` the owner can
write for an existing key resolves).

## `tests/test_agentsmd.py`
`test_sections_by_normalized_heading` (`## ADVICE.` → `ADVICE`; the long heading →
underscores), `test_body_runs_to_next_heading`, `test_duplicate_heading_raises`,
`test_all_key_is_whole_file`, `test_no_sections_gives_empty_dict`.

## `tests/test_localyaml.py`
`test_derive_contains_only_derived_keys` (S12 key set exactly),
`test_write_then_read_roundtrip`, `test_header_says_generated`,
`test_remote_url_none_without_remote`.

## `tests/test_steps.py`
`test_order_is_fixed_eleven_steps`, `test_step_lookup_unknown_raises`,
`test_gated_steps_exactly_six`, `test_agent_steps_include_landing_for_conflict`,
`test_required_prose_names_match_table`, `test_lint_ok_on_generated_tree`,
`test_lint_unknown_step_in_config_is_error`, `test_lint_missing_step_in_config_is_error`,
`test_lint_order_mismatch_is_error`, `test_lint_missing_required_prose_is_error`,
`test_lint_prose_naming_unknown_step_is_error`,
`test_lint_gate_prose_for_gateless_step_is_error`,
`test_lint_gate_on_for_gateless_step_is_warning`, `test_lint_unused_common_file_is_warning`,
`test_skip_effects_all_known_symbols`.

## `tests/test_prose.py`
`test_load_prose_stems`, `test_find_tokens_all_namespaces_and_spacing`,
`test_render_prose_include_recursive`, `test_render_cycle_raises_with_chain`,
`test_render_depth_limit`, `test_unresolved_collected_not_raised_when_lenient`,
`test_unresolved_raises_all_at_once_when_strict`, `test_unknown_namespace_left_as_text`,
`test_referenced_prose_set`, `test_round_values_plan_includes_answers_and_overrides`,
`test_round_values_owner_words_since_pause`, `test_used_prose_tracked`.

## `tests/test_plumbing.py`
`test_process_instructions_lists_absolute_paths_and_roots`,
`test_process_instructions_contains_result_schema_for_each_kind` (parametrized: driver,
producer, gate, conflict; asserts the S7 keys appear),
`test_process_instructions_jc_command_for_producer_and_field_for_gate`,
`test_process_instructions_turn_and_budget_and_prices`,
`test_process_instructions_findings_verbatim`,
`test_gate_prose_for_gateless_step_fixed_sentence`,
`test_gate_prose_replaces_process_instructions_token`,
`test_assemble_producer_ends_with_step_end`, `test_assemble_gate_ends_with_step_end`,
`test_assemble_conflict_uses_landing_overview_when_present`,
`test_assemble_conflict_falls_back_to_common_prose`,
`test_assemble_checkpoint_appends_summary`, `test_prompt_token_warning_threshold`,
`test_assemble_strict_raises_unresolved`, `test_placeholder_attempt_renders_every_step`.

## `tests/test_ownerlog.py`
`test_append_assigns_sequential_index_and_creates_file`, `test_read_all_skips_corrupt_line`,
`test_exists_and_nonempty_with_marker_only`, `test_normalize_whitespace_and_nfc`,
`test_verify_quote_substring_after_index`, `test_verify_quote_ignores_entries_before_index`,
`test_verify_quote_ignores_markers`, `test_verify_quote_empty_is_none`,
`test_verify_quote_missing_log_is_none`, `test_slice_byte_exact`, `test_last_index_zero_when_absent`,
`test_concurrent_appends_keep_all_lines` (two processes).

## `tests/test_hooks.py`
`test_prompt_hook_appends_and_prints_nothing`, `test_prompt_hook_survives_bad_stdin`,
`test_session_start_creates_log_marker_and_local_yaml`,
`test_session_start_warns_when_agent_defs_stale`, `test_session_start_mentions_paused_round`,
`test_hooks_exit_zero_on_any_exception`.

## `tests/test_agents_defs.py`
`test_definition_text_frontmatter_fields`, `test_gate_role_has_read_only_tools`,
`test_work_role_has_no_tools_line`, `test_expected_files_two_per_rung`,
`test_write_all_removes_stale_shackles_files_only`, `test_is_stale_detects_missing_changed_extra`,
`test_regenerate_is_idempotent`, `test_committed_defs_current` (regenerates from the
generated fixture roster into memory and compares with what `write_all` produced — plus
a second assertion against the real `harness/.claude/agents` using only the roster
*hash stamp*, which does not read `subAgents.yaml` content beyond hashing it),
`test_definition_name_format`.

## `tests/test_gitops.py`
`test_require_version`, `test_next_round_id_from_folders_and_branches`,
`test_claim_round_pushes_new_branch`, `test_claim_round_rejected_when_branch_exists`
(a second clone claims first), `test_fence_push_ok_then_rejected_after_foreign_push`,
`test_commit_all_returns_none_when_clean`, `test_worktree_add_remove_list`,
`test_uncommitted_changes_with_untracked_and_bytes`, `test_changes_between_detects_rename`,
`test_revert_paths_tracked_and_untracked_and_empty_dirs`, `test_restore_from_tree`,
`test_conflict_markers_detection`, `test_merge_tree_clean`, `test_merge_tree_conflicts_listed`,
`test_commit_tree_and_push_ref_with_lease`, `test_push_ref_rejected_when_main_moved`,
`test_fast_forward_checkout_refuses_dirty`, `test_no_force_push_anywhere` (source scan
of `gitops.py` for `--force` without `-with-lease`).

## `tests/test_state.py`
`test_new_state_shape_matches_s1` (every S1 key present), `test_save_atomic_sorted_trailing_newline`,
`test_load_errors_name_file`, `test_schema_mismatch_raises`,
`test_open_attempt_numbers_per_step_and_counts_total`, `test_open_attempt_refuses_when_current`,
`test_close_attempt_clears_current`, `test_pause_set_clear`, `test_flags_unshown_then_shown`,
`test_next_pending_step_in_order`, `test_view_for_prose_keys`.

## `tests/test_results.py`
`test_read_producer_ok_defaults_lists`, `test_read_tolerates_code_fence`,
`test_read_missing_file_malformed`, `test_read_not_object_malformed`,
`test_read_bad_status_for_kind_malformed`, `test_read_gate_needs_verdict`,
`test_read_bad_resolution_value`, `test_read_bad_ruling_value`, `test_read_bad_jc_kind`,
`test_read_keeps_unknown_keys_in_raw`, `test_normalize_pass_clears_blocking`,
`test_normalize_fail_without_blocking_sets_all_blocking`,
`test_normalize_fail_without_findings_malformed`, `test_missing_resolutions_only_when_done`.

## `tests/test_findings.py`
`test_next_id_sequence`, `test_add_new_assigns_ids_and_history`,
`test_add_new_drops_repeat_of_withdrawn_by_normalized_quote`,
`test_add_new_keeps_repeat_of_non_withdrawn`, `test_apply_rulings_withdrawn`,
`test_apply_rulings_upheld_once_then_settled_on_second`,
`test_apply_rulings_unknown_id_noted`, `test_apply_resolutions_fixed_and_disputed`,
`test_apply_resolutions_dispute_of_settled_ignored`, `test_apply_verdict_pass_closes_all_but_withdrawn`,
`test_apply_verdict_fail_keeps_open`, `test_handed_to_producer_set`,
`test_blocks_acceptance_statuses`, `test_render_for_prompt_verbatim_quote`,
`test_write_findings_file_shape_s8`.

## `tests/test_judgmentcalls.py`
`test_append_line_format_and_header`, `test_newlines_collapsed`,
`test_append_from_result_routes_kinds_and_counts`, `test_counts_exclude_header`,
`test_jc_command_exact_string`.

## `tests/test_history.py`
`test_append_attempt_entry_shape_s14`, `test_append_note`, `test_round_end_includes_bill`,
`test_created_on_first_use_and_append_only`.

## `tests/test_tokens.py`
`test_estimate_ceil_and_zero`, `test_estimate_bad_token_bytes_raises`, `test_tokens_of_text_utf8_bytes`,
`test_count_python_tests_incl_async_and_indented`, `test_count_js_tests`, `test_count_unknown_suffix_zero`,
`test_summary_section_bytes_h1_and_h2`, `test_summary_section_absent_zero`,
`test_summary_stops_at_same_or_higher_heading`.

## `tests/test_pricing.py`
`test_file_price_below_and_above_cap`, `test_living_delta_new_file_adds_base`,
`test_living_delta_deleted_refunds_base`, `test_living_delta_modified_no_base`,
`test_living_delta_rename_free`, `test_test_delta_sign`, `test_carry_forward_no_cap_no_base`,
`test_archive_charges_three_rates`, `test_usage_price_all_columns`, `test_estimate_usage_fraction_ceil`,
`test_attempt_cost_floor_spawn`, `test_pool_and_step_budget`, `test_hard_stops`, `test_time_context`.

## `tests/test_ledger.py`
`test_bill_attempt_measured_vs_estimated_flag`, `test_bill_attempt_driver_kind_costs_zero`,
`test_bill_driver_step_once`, `test_living_change_created_and_removed_in_round_is_free`
(a file added then deleted between `main_before` and the cleanup commit does not appear),
`test_living_change_negative_credit_when_tree_shrinks`, `test_living_change_rename_only_token_delta`,
`test_living_change_counts_tests_joined_and_left`, `test_living_change_excludes_carry_forward`,
`test_living_change_ignores_tests_archive`, `test_carry_forward_change_rate`,
`test_book_round_idempotent`, `test_projected_living_uses_base_before_landing`,
`test_over_hard_stop_uses_round_override_multiple`, `test_over_individual_stop`,
`test_project_remaining_sums_ended_rounds_only`, `test_project_remaining_skips_unreadable`,
`test_format_bill_lists_every_section`.

## `tests/test_round_start.py`
`test_start_refuses_on_drift_with_diff_text`, `test_start_refuses_without_owner_log`,
`test_start_refuses_stale_agent_defs`, `test_start_refuses_unknown_config_key`,
`test_start_refuses_unknown_step_in_config`, `test_start_refuses_unresolved_token`,
`test_start_refuses_dirty_living_paths`, `test_start_refuses_without_remote`,
`test_start_refuses_second_concurrent_round`, `test_start_claims_branch_and_worktree`,
`test_start_claim_race_retries_next_id` (a foreign `round/0001` appears between id
choice and push), `test_start_first_next_is_driver_step_chat_to_plan`,
`test_fence_lost_sets_pause_and_raises`, `test_open_round_finds_single_active`.

## `tests/test_round_owner.py`
`test_quote_must_exist_after_pause_index`, `test_quote_normalized_match`,
`test_approve_requires_all_answers`, `test_answer_stored_and_rendered_in_round_plan`,
`test_delegate_sets_mode_and_through`, `test_override_refuses_plan_step`,
`test_override_unknown_step_refused`, `test_verb_not_allowed_in_pause_kind`,
`test_abandon_ends_and_lands_archives_only`, `test_continue_resets_gate_rejections`,
`test_continue_extends_run_limits`, `test_continue_after_fence_requires_equal_heads`,
`test_raise_hard_stop_round_only`, `test_owner_slice_written_after_each_verb`.

## `tests/test_advance.py`
`test_accept_bills_driver_step_once`, `test_accept_plan_agents_validates_and_stores`,
`test_accept_plan_agents_invalid_becomes_rejection`, `test_skip_default_agents_plan_shares`
(minimums honoured, remainder equal, sums to 1), `test_skip_plan_is_spec_redirects_inputs`,
`test_skip_checkpoint`, `test_skip_no_cleanup_attempt_still_books`,
`test_validate_agents_plan_rules` (parametrized: missing step, extra step, bad sum,
off gate non-zero, rung over ceiling, unknown rung), `test_end_landed_books_and_syncs`,
`test_end_keeps_worktree_on_sync_failure`.

## `tests/test_mechanical.py`
`test_strays_reverted_not_failed`, `test_spec_file_edit_reverted`, `test_gate_diff_reverted_never_fails`,
`test_plan_json_checks`, `test_agents_plan_checks`, `test_spec_files_exist`,
`test_tests_step_new_tests_may_fail_but_must_collect`, `test_tests_step_pre_existing_must_pass`,
`test_impl_step_verify_must_pass`, `test_impl_step_timeout_fails_with_note`,
`test_suite_json_paths_must_be_round_tests`, `test_postmortem_needs_summary`,
`test_cleanup_verify`, `test_conflict_no_markers`, `test_conflict_other_files_restored_from_tree`,
`test_allowed_roots_symbols` (parametrized over the table's symbols).

## `tests/test_verify.py`
`test_run_pass_fail_output_tail`, `test_run_timeout_flag`, `test_collect_only`,
`test_pre_existing_tests_from_base_commit`, `test_probes_env_unset`.

## `tests/test_suite.py`
`test_apply_moves_archive_files_relative_to_testpaths_root`, `test_apply_keeps_suite_files`,
`test_apply_split_mixed_python`, `test_apply_non_python_mixed_archives_whole_and_flags`,
`test_apply_reruns_verify_and_rejects_on_failure`, `test_round_test_files_since_base`.

## `tests/test_landing.py`
`test_land_clean_pushes_main_with_lease`, `test_land_records_main_before_once`,
`test_land_hard_stop_pauses_with_projection`, `test_land_verify_failure_pauses`,
`test_land_race_retries_up_to_max_round_attempts_then_pauses`,
`test_land_conflict_opens_single_conflict_attempt_on_conflicted_files`,
`test_land_after_conflict_resolution_completes`, `test_round_branch_rebased_onto_landed`,
`test_sync_fast_forward`, `test_sync_merges_when_main_moved`, `test_sync_conflict_attempt`,
`test_sync_exhausted_pauses`, `test_sync_archives_only_for_abandoned`.

## `tests/test_round_flow.py` — stub-driven, through the real CLI
Each test builds a script for `StubDriver` and asserts on STATE, HISTORY, files and
the bill. Paths covered (one test each unless noted):
- `test_happy_path_checkpoints` — approve; every producer `done_ok`, every gate
  `gate_pass`; pauses at CHECKPOINT-1 and -2 (owner `approve` each); ends `landed`;
  eleven steps accepted; `main` contains the round folder, the new test, the code;
  bill has attempts, driver steps, living, archive; worktree removed.
- `test_happy_path_delegated` — `delegate`: no checkpoint pauses; same end state.
- `test_delegate_through_checkpoint_1` — pauses only at CHECKPOINT-2.
- `test_delegation_does_not_skip_needs_owner` / `..._blocked` / `..._limit`.
- `test_needs_owner_pause_shows_questions_verbatim` and `continue` re-issues the
  producer with the owner's quote in the prompt.
- `test_blocked_pause_shows_narrow`.
- `test_gate_fail_reissues_producer_with_findings` — findings text verbatim in the
  retry prompt; ids `F1..`.
- `test_max_turns_per_gate_pauses_limit` — three `gate_fail`s → pause `limit`;
  `continue` resets.
- `test_verdict_wins_pass_with_blocking_flag_accepts`.
- `test_verdict_wins_fail_nonblocking_only_reissues`.
- `test_gate_fail_no_findings_is_malformed_and_gate_reissued`.
- `test_missing_resolution_rejects_producer`.
- `test_dispute_upheld_twice_settled_then_dispute_ignored`.
- `test_withdrawn_repeat_dropped_with_history_note`.
- `test_flags_reach_owner_at_next_pause_once`.
- `test_judgment_calls_from_producer_tool_and_gate_field_land_in_files`.
- `test_strays_reverted_and_noted_not_failed`, `test_spec_file_edit_reverted`.
- `test_malformed_json_reissued_bounded`, `test_code_fenced_json_accepted`.
- `test_tests_then_frozen_impl_must_pass` — `tests_add:test_new_fail.py` then
  `impl_still_failing` → mechanical rejection with output → `impl_pass` → accepted;
  the implementation attempt could not modify `tests/` (a `stray_edit:tests/...`
  is reverted).
- `test_tests_to_suite_moves_archive_and_bills_only_suite_tests`.
- `test_override_skips_plan_agents_with_default_plan`, `test_override_skips_gate`,
  `test_override_cannot_skip_plan`.
- `test_abandon_mid_round_lands_archives_only`.
- `test_landing_conflict_attempt_judged_against_auto_merge` — main moves under the
  round with a conflicting edit; `conflict_touch_other_file` is restored; markers left
  → rejected; `conflict_resolve_ok` → landed.
- `test_post_landing_commits_synced_when_main_moves_again`.
- `test_hard_stop_before_landing`, `test_individual_hard_stop_pauses_after_attempt`,
  `test_raise_hard_stop_lets_landing_proceed`.
- `test_max_turns_per_run_pauses`, `test_wall_clock_pauses` (fake clock).
- `test_fence_lost_when_foreign_push` — another clone pushes to the round branch;
  next `record` exits 3 with pause `fence`.
- `test_next_is_idempotent_until_record`.
- `test_ledger_bills_actual_attempts_not_shares` — three rejected attempts billed;
  the plan's shares never appear in totals.
- `test_postmortem_edits_todo_charged_special_rate_never_stop`.
- `test_owner_log_slice_in_round_folder_matches_indices`.
- `test_history_has_entry_per_attempt_with_verbatim_final_message`.
- `test_prompt_ends_with_step_end_for_every_agent_attempt`.

## `tests/test_cli.py`
`test_setup_writes_defs_local_baseline_gitignore`, `test_doctor_exit_codes`,
`test_accept_spec_refuses_mid_round_and_non_tty_without_yes`, `test_record_usage_flags_all_or_none`,
`test_owner_verb_arguments`, `test_jc_appends`, `test_status_json_fields`, `test_ledger_prints_bill`,
`test_verify_command_exit_code`, `test_index_check`, `test_render_offline`,
`test_error_mapping_exit_codes` (parametrized over the documented exceptions),
`test_output_labels_stable` (every S16 label present in text mode).

## `tests/test_doctor.py`
`test_clean_tree_no_errors`, `test_drift_warning_unless_strict`, `test_defaulted_keys_named_with_values`,
`test_unknown_key_error`, `test_unknown_step_error`, `test_unresolved_token_named_per_prompt`,
`test_prompt_size_warning`, `test_unused_prose_warning`, `test_stale_agent_defs_error`,
`test_owner_log_missing_error`, `test_hooks_missing_error`, `test_offline_skips_git`,
`test_checks_for_start_subset`, `test_json_shape_s17`.

## `tests/test_index.py`
`test_generate_one_line_per_file_sorted`, `test_headers_by_file_type`,
`test_regenerate_only_when_changed`, `test_committed_index_current` (real `INDEX.md`
equals `generate` over the real tree — the only test besides the guard that looks at
real files; it reads only first lines/headings, never prose bodies).

## `tests/test_docs.py`
`test_process_md_json_shapes_match_s7`, `test_architecture_step_names_match_table`,
`test_docs_repeat_no_project_numbers` (no literal value of a numeric `project.yaml`
key appears in the four docs — checked against the generated fixture config, so the
test does not read the real project.yaml), `test_carry_forward_headers_present`.

## `tests/test_repo_scaffold.py`
`test_ci_workflow_parses_and_names_commands`, `test_gitignore_entries`,
`test_settings_json_hooks`, `test_probes_excluded_from_default_run`,
`test_pyproject_dependencies_only_two`.

## Invariants
- The mechanics tests never fail because the owner reworded prose, renamed a rung,
  changed a price, or toggled a gate: they read the generated tree only.
- Every engine path listed in 10 has at least one flow test; every stub behavior is
  used by at least one flow test (`test_stub_agent.py::test_every_behavior_used_in_flow`
  greps `test_round_flow.py`).
- No test sleeps for real time except `impl_hangs` with a 1-second timeout override.
