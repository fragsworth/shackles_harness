# 62 — harness/tests/unit/ (one file per module)

Parent: `60-tests.md`. Pure-function tests; a temp repo only where the module
runs git. Each file names its module; each test names one behavior and the
assertion is stated here.

## test_config_spec_files.py
- `test_list_expands_globs_relative_to_spec_yaml` — a temp spec set: the
  six patterns expand to the written files; paths are relative to `spec.yaml`.
- `test_pattern_matching_nothing_refuses` — `locked_prose/*` on an empty
  folder raises `RefusedError`.
- `test_baseline_roundtrip` — write then read gives equal `Baseline`.
- `test_drift_none_when_equal`, `test_drift_changed_added_missing` — each
  category populated correctly; `diff` contains the changed file's name.
- `test_missing_baseline_is_all_added`.

## test_config_project.py
- `test_loads_every_owner_key_with_types` — the real key set from a copy of
  the owner's file: every field typed as specified.
- `test_defaulted_keys_recorded` — `testPaths` absent -> in `defaulted` with
  the code default.
- `test_unknown_key_recorded_not_raised`.
- `test_fractions_must_sum_to_one` — `gatesFraction 0.4, workFraction 0.7` -> `LintError`.
- `test_step_switch_must_be_0_or_1`.
- `test_render_value_formats` — lists joined by `, `; `0.25` stays `0.25`;
  ints unchanged; unknown key raises `KeyError`.
- `test_commented_keys_found` — `# ownerHourlyRate: 10` is reported.

## test_config_roster.py
- `test_ladder_is_file_order`, `test_resolve_caps_at_ceiling` (`max` under
  ceiling `medium` -> `medium` with a note), `test_unknown_rung_lint_error`,
  `test_missing_price_refuses`, `test_check_defaults_names_missing_rungs`.

## test_config_paths.py
- `test_discover_finds_spec_yaml_upward`, `test_harness_root_is_parent_of_agents_md`,
  `test_round_folder_substitutes_NNNN`, `test_round_folder_with_base_points_into_worktree`,
  `test_format_round_id_pads_and_widens` (`7 -> 0007`, `12345 -> 12345`),
  `test_is_under_prefix_semantics` (`src/x` under `src/`; `srcx` not).

## test_steps_table.py
- `test_table_order_is_fixed_eleven` — the exact sequence.
- `test_kinds_and_gate_prose` — LANDING, CLEANUP, checkpoints have no gate;
  the six gated steps name `<STEP>-GATE`.
- `test_declared_paths_per_step`, `test_verify_rules_per_step`,
  `test_overridable_set` (CHAT-TO-PLAN not; PLAN-AGENTS, TESTS-TO-SUITE,
  POSTMORTEM, checkpoints yes; LANDING, CLEANUP not),
  `test_attempt_id_formats`, `test_after_last_is_none`,
  `test_prose_stems_expected_contains_commons`.

## test_steps_lint.py
- `test_unknown_step_in_project_is_error`, `test_missing_step_is_error`,
  `test_order_mismatch_is_warning`, `test_gate_on_without_gate_is_note`,
  `test_gate_on_without_prose_file_is_error`,
  `test_extra_prose_file_is_warning`, `test_unknown_key_is_error`,
  `test_defaulted_key_is_note`, `test_default_shares_unknown_step_is_error`,
  `test_round_paths_missing_key_is_error`, `test_clean_spec_has_no_errors`
  (the generated spec set).

## test_prompts_tokens.py
- `test_scan_finds_tokens_with_and_without_spaces`,
  `test_scan_ignores_malformed` (`{{ x }}`, `{{ project. }}`),
  `test_resolve_project_key`, `test_resolve_project_remaining_and_gates`,
  `test_resolve_round_keys`, `test_resolve_round_without_round_is_none`,
  `test_resolve_agents_section_by_slug`, `test_resolve_prose_missing_is_none`,
  `test_unknown_namespace_is_none`.

## test_prompts_render.py
- `test_substitutes_all_namespaces`, `test_recursive_prose_include`,
  `test_cycle_is_unresolved_with_warning`, `test_unresolved_left_verbatim_and_listed`,
  `test_estimated_tokens_uses_token_bytes` (bytes 9, tokenBytes 4 -> 3),
  `test_prompt_size_warning_threshold`, `test_prompt_head_is_agents_md`,
  `test_plumbing_appended_when_token_absent`.

## test_prompts_plumbing.py
- `test_process_instructions_sections_for_producer` — the ten sections
  present, worktree path absolute, declared paths listed, the judgment
  command contains `--attempt <id>`.
- `test_process_instructions_for_gate_is_read_only` — says read-only; lists
  prior findings paths; judgment calls in final message.
- `test_gate_prose_when_off_and_when_absent`.
- `test_step_end_inline_vs_follow_up`.
- `test_checkpoint_summary_lists_calls_and_flags`.

## test_prompts_agents_md.py
- `test_slug_examples`, `test_sections_by_heading`, `test_preamble_key`,
  `test_section_missing_is_none`.

## test_round_state.py
- `test_new_state_defaults`, `test_save_load_roundtrip`,
  `test_open_attempt_refuses_second`, `test_close_and_next_n`,
  `test_accept_advances_index`, `test_pause_resume_resets_run_counters`,
  `test_end_sets_phase_and_outcome`, `test_schema_mismatch_raises`,
  `test_view_exposes_only_read_fields`.

## test_round_history.py
- `test_append_creates_block_with_timestamp_kind_id`,
  `test_formatters_produce_labelled_lines`, `test_append_is_only_writer`
  (file unchanged by any other module: a scan of `src/` for the file name).

## test_round_owner_log.py
- `test_read_global_skips_malformed_lines_and_counts`,
  `test_missing_log_refuses`, `test_refresh_appends_and_returns_cursor`,
  `test_verify_quote_exact_and_normalized` (`"approve"` inside `"ok,
  approve it"`; extra spaces tolerated only in normalized mode),
  `test_verify_quote_latest_match_wins`, `test_quote_not_found_raises`.

## test_round_judgment_calls.py
- `test_append_one_line_per_call_newlines_flattened`,
  `test_is_append_only_prefix_rule`, `test_read_lines`.

## test_round_artifacts.py
- `test_validate_plan_requires_answers_for_approval`,
  `test_validate_plan_fields`, `test_validate_agents_plan_shares_and_rungs`
  (sum > 1 is a problem; sub-agents over the max is a problem; advisory
  minimum below default is a warning), `test_validate_spec_fields`,
  `test_validate_suite_every_new_test_decided_once`,
  `test_validate_suite_split_file_is_problem`, `test_render_plan_plain_english`
  (contains title, each non-goal, each answered question with its quote).

## test_round_results.py
- `test_extract_last_json_bare_and_fenced`, `test_extract_with_leading_prose`,
  `test_no_json_raises`, `test_validate_producer_status_rules`
  (NEEDS-OWNER needs questions; BLOCKED needs narrow),
  `test_validate_gate_requires_suggestion_and_quote`,
  `test_validate_driver_shapes`.

## test_round_findings.py
- `test_rulings_withdraw_and_uphold`, `test_upheld_twice_is_settled`,
  `test_repeat_of_withdrawn_dropped_by_id_and_by_quote` (note recorded),
  `test_fail_without_blocking_marks_all_blocking`,
  `test_pass_marks_all_non_blocking_and_resolves_open`,
  `test_unruled_resolved_claims_stay_open_on_fail`,
  `test_disputes_against_settled_rejected`, `test_owner_flags_collected`,
  `test_write_read_roundtrip`.

## test_round_approvals.py
- `test_approve_requires_answered_questions`, `test_delegate_through_unknown_step_refused`,
  `test_override_refuses_plan_and_passed_steps`, `test_answer_stores_quote_any_text`,
  `test_abandon_any_time`, `test_resume_counts_and_refuses_over_limit`,
  `test_needs_answers_lists_open`.

## test_git_repo.py (temp repo)
- `test_run_raises_git_error_with_argv`, `test_push_with_lease_returns_false_on_stale`,
  `test_diff_names_detects_rename`, `test_show_file_absent_is_none`,
  `test_update_ref_cas`, `test_checkout_and_clean_paths`.

## test_git_lease.py (temp repo + bare)
- `test_next_round_id_from_archives_and_remote_branches`,
  `test_claim_creates_branch_with_empty_expected`,
  `test_claim_retries_next_id_once_then_raises`,
  `test_fence_rejected_raises_lease_lost`, `test_verify_detects_foreign_push`.

## test_git_worktrees.py
- `test_create_detached_at_sha`, `test_changes_include_untracked`,
  `test_commit_from_stages_only_paths`, `test_advance_branch_cas_fails_if_moved`,
  `test_runner_worktree_on_branch`, `test_remove_prunes`, `test_list_stale`.

## test_git_landing.py
- `test_clean_merge_commits`, `test_conflict_records_paths_and_auto_merged_commit`,
  `test_judge_resolution_extra_file_is_problem`, `test_judge_resolution_markers_left_is_problem`,
  `test_push_to_main_false_when_main_moved`.

## test_git_sync.py
- `test_ancestor_pushes_directly`, `test_merge_then_push`,
  `test_conflict_returns_not_ok_with_paths`, `test_exhausted_after_attempts`,
  `test_round_folder_only_adds_just_the_folder`.

## test_checks_mechanical.py
- `test_allowed_for_each_path_rule`, `test_classify_keeps_declared_and_round_files`,
  `test_spec_file_change_is_stray`, `test_frozen_artifact_is_stray`,
  `test_rename_judged_by_both_paths`, `test_revert_restores_tracked_removes_untracked`,
  `test_append_only_violation_restored_and_noted`,
  `test_check_artifacts_missing_is_problem`.

## test_checks_verify.py
- `test_collect_mode_uses_collect_command`, `test_pass_counts_parsed`,
  `test_timeout_flagged`, `test_non_pytest_runner_judged_by_exit_code`,
  `test_output_written_to_scratch`.

## test_checks_suite_moves.py
- `test_new_tests_between_refs`, `test_plan_moves_whole_files`,
  `test_mixed_file_is_problem`, `test_pre_existing_tests_in_archived_file_is_problem`,
  `test_apply_git_mv_preserves_relative_path`.

## test_ledger_tokens.py
- `test_ceil_division`, `test_zero_bytes_zero_tokens`, `test_count_tests_py_only`,
  `test_count_tests_indented_methods`.

## test_ledger_pricing.py
- `test_file_price_below_cap`, `test_file_price_across_cap`,
  `test_missing_file_is_zero`, `test_carry_forward_flat_rate`,
  `test_test_delta_refund_negative`, `test_archive_costs_fields_and_total`.

## test_ledger_living.py (temp repo)
- `test_new_file_charges_base_plus_tokens`, `test_deleted_file_refunds`,
  `test_pure_rename_costs_nothing`, `test_rename_with_change_charges_delta_only`,
  `test_outside_living_paths_ignored`, `test_tests_counted_suite_wide_moves_net_zero`,
  `test_created_and_removed_inside_round_not_charged`,
  `test_carry_forward_file_uses_special_rate`, `test_projected_equals_charge_when_nothing_after`.

## test_ledger_agent_costs.py
- `test_split_by_output_fraction`, `test_estimate_from_sizes_raises_output_floor`,
  `test_cost_uses_rung_prices_plus_spawn`, `test_driver_overhead_value`.

## test_ledger_ledger.py
- `test_add_entry_updates_total`, `test_book_once_refuses_twice`,
  `test_hard_stop_round_and_attempt`, `test_project_spent_sums_all_rounds`,
  `test_ledger_line_format`, `test_time_cost_note_not_in_entries`.

## test_quote_shares.py
- `test_pools_from_fractions`, `test_shares_plan_default_equal_sources`,
  `test_off_gate_has_no_share`, `test_over_one_scaled_with_warning`,
  `test_retry_budget_equals_share`, `test_advisory_warnings_below_minimum`,
  `test_rung_for_defaults_and_ceiling`, `test_sub_agents_capped`,
  `test_refactor_note_threshold`.

## test_quote_limits.py
- `test_run_turns_limit`, `test_wall_clock_limit`, `test_gate_turns_limit`,
  `test_mechanical_limit`, `test_message_names_verbs`.

## test_agents_definitions.py
- `test_two_files_per_rung`, `test_frontmatter_fields_model_effort_tools`,
  `test_gate_tools_read_only`, `test_write_all_removes_stale`,
  `test_is_stale_on_roster_change`, `test_agent_file_for`.

## test_agents_hooks.py
- `test_merge_preserves_other_keys_and_dedups`, `test_write_settings_returns_hash`,
  `test_handle_owner_log_appends_line`, `test_handle_empty_prompt_appends_nothing`,
  `test_handle_never_raises`.

## test_engine_advance.py (in-memory state, fake context)
- `test_ended_gives_end`, `test_paused_restates_owner`, `test_open_attempt_is_idempotent`,
  `test_questions_pause`, `test_plan_self_until_approval`,
  `test_checkpoint_skipped_when_delegated_and_through_rules`,
  `test_producer_then_gate_when_on`, `test_gate_off_accepts_on_done`,
  `test_override_applies_skip_default`, `test_limits_checked_before_attempt`,
  `test_gate_is_on_requires_prose_and_switch`.

## test_engine_pauses.py
- `test_message_for_each_reason_mentions_verbs`, `test_accepts_for_each_reason`,
  `test_owner_items_included`.

## test_cli.py
- `test_registry_builds_all_verbs`, `test_refused_exit_2_with_json`,
  `test_crash_exit_1`, `test_stdout_is_single_json_object`.
