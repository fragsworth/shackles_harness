# 10 — Tests

The permanent suite lives in `harness/tests/` and is what every round's `verify-suite` check runs. Three layers:

1. **Mechanics tests** (`tests/test_*.py`) — run against a *generated* harness in a temp directory: a one-line-per-file spec produced from the code's own step table, a real git repository with a bare "remote", a seeded `OWNER.log`, and a **stub agent** whose behaviour is scripted per attempt. They never read the owner's real prose, so a prose rewrite fails only the drift test.
2. **Guard tests over the real tree** — `test_spec_drift.py` (the hashed baseline), `test_agent_defs.py::test_committed_definitions_are_fresh`, `test_config_surface.py` (registered keys only; no prose), `test_docs_consistency.py` (docs match code tables). These are the only tests that open files of the real harness other than the code itself. (JC-65)
3. **Probes** (`tests/probes/`) — opt-in live tests that run real agents on the real prose with planted defects. Marked `live`; skipped unless `SHACKLES_LIVE=1` and the `claude` CLI is found.

Conventions: pytest, plain functions, one assertion topic per test, fixtures from `conftest.py`, no network except the `claude` CLI in probes, no sleeping longer than a second (timeouts are tested with tiny configured values). Tests are living files: charged, so dense.

## 10.1 `tests/conftest.py`

Fixtures (function-scoped unless noted):
- `clock` — a controllable `now()` returning ISO timestamps; `clock.advance(seconds)`.
- `fake` — `support.fakespec.generate(tmp_path)` + `support.fakegit.init_repo_with_remote(...)` + a seeded `OWNER.log` line "hello"; yields `FakeHarness(repo, harness, bare, roots, cfg)`; cleans worktrees on teardown.
- `runner` — `support.cli.Runner(fake.harness, now=clock)`; in-process invocation of `run.main`.
- `stub` — `support.stub_agent.StubAgent()` with default behaviours.
- `owner` — `support.ownerlog_writer.Sayer(fake.harness)`; `owner.say("approve")` appends a hook-format line and returns the text for `--quote`.
- `started` — `fake` + `runner.start()`; returns the start output (kind `driver`).
- `approved` — `started` + the stub writes a valid `PLAN.json` with no questions + `record` + `owner approve`; the round is `running` at PLAN-AGENTS.
- `real_roots` (session) — `paths.Roots.discover(Path(__file__).parent)`; used only by layer-2 tests.
- Marker `live` registered; `pytest_collection_modifyitems` skips `live` unless enabled.

## 10.2 `tests/support/`

### `fakespec.py`
- `generate(root: Path, *, gates: dict[str, int] | None = None, checkpoints: dict[str, int] | None = None, config_overrides: dict = {}, remove_keys: list[str] = [], extra_keys: dict = {}, prose_overrides: dict[str, str] = {}, drop_prose: list[str] = [], agents_md: str | None = None) -> FakeHarness` — writes, from `steps.STEPS` and `config.PROJECT_KEYS`/`SUBAGENTS_KEYS`: `spec.yaml` (listing the same relative paths as the real one); `SPEC.md` ("fake spec"); `harness/AGENTS.md` with headings `## ADVICE.`, `## INVARIANTS.`, `## DEFINED AND UNDEFINED JUDGMENT CALLS` each with one line; `harness/project.yaml` with every registered key at small values (quote-friendly prices: tokenBytes 4, livingFileCostPerToken 0.01, base 1, testBase 0.5, limits: maxTurnsPerGate 3, maxTurnsPerRun 120, maxRoundAttempts 2, wall clock 12, verifyTimeoutSeconds 60, cap 2) and the `steps` map from the table (gates default 0, checkpoints default 1); `harness/subAgents.yaml` with rungs `max, high, medium, low`; `locked_prose/<STEP>-OVERVIEW.txt` = one line `"<STEP>-OVERVIEW {{ prose.COMMON-PROJECT }} {{ prose.COMMON-ROUND }} {{ prose.COMMON-OVERVIEW }} gate: {{ plumbing.GATE-PROSE }} {{ plumbing.PROCESS-INSTRUCTIONS }}"` for every step with overview prose (CHAT-TO-PLAN's line omits COMMON-ROUND, matching the real file's shape is *not* required), `<STEP>-GATE.txt` = `"<STEP>-GATE {{ prose.COMMON-GATE }} {{ plumbing.PROCESS-INSTRUCTIONS }}"` for every gated step **except CHAT-TO-PLAN** (absent, like the real tree), `COMMON-PROJECT.txt` with every `project.*` token the real one uses (vision, budget, remaining, lostValuePerHour, living prices, livingSourcePaths, tokenBytes, maxRefactorOverhead, gates), `COMMON-ROUND.txt` with every `round.*` token, `COMMON-OVERVIEW.txt`, `COMMON-GATE.txt`, `COMMON-STEP-END.txt` with `{{ agents.DEFINED_AND_UNDEFINED_JUDGMENT_CALLS }}`, `CHECKPOINT-OVERVIEW.txt`; plus the harness skeleton: `src/run.py` copied from the real runner (so worktree attempts can run the judgment tool through the driver path), `src/shackles` symlink or copy (copy), `src/hooks/owner_log.py`, `docs/{PROCESS,ARCHITECTURE,FORMATS,TODO,CLARIFICATIONS}.md` one line each, `tests/test_smoke.py` (one passing test), `pyproject.toml` (copy of the real one), `.claude/settings.json`, `.claude/agents/` generated, `spec.baseline.json` accepted for the generated files, `archives/rounds/.gitkeep`, `.gitignore`.
- `FakeHarness`: `repo`, `harness`, `bare`, `roots`, `cfg`, `rp(round_id) -> RoundPaths`, `read(rel) -> str`, `write(rel, text)`, `edit_spec_file(rel, text)` (for drift tests), `worktree(round_id) -> Path`.

### `fakegit.py`
- `init_repo_with_remote(repo: Path) -> Path` — `git init -b main`, user config, initial commit of everything, bare repo at `repo.parent / "origin.git"`, `remote add origin`, push, return the bare path.
- `commit_on_main_elsewhere(bare: Path, files: dict[str, str | None], message: str) -> str` — clone bare to a temp dir, apply files (None = delete), commit, push to main; return the sha (simulates another contributor or an earlier round landing).
- `remote_branches(bare) -> list[str]`, `remote_sha(bare, ref) -> str | None`, `file_at(bare, ref, path) -> str | None`, `move_remote_branch(bare, branch, files, message)` (simulate another runner pushing to the round branch — the fence test).

### `ownerlog_writer.py`
- `class Sayer`: `say(text, *, session="s1", ts=None) -> str` appends a hook-format line; `run_hook(payload: dict) -> subprocess.CompletedProcess` runs the real hook script with the payload on stdin.

### `cli.py`
- `class Runner`: `run(*args: str) -> Result(code: int, json: dict, stdout: str, stderr: str)` — calls `run.main` in-process with captured stdout, `--root` fixed to the fake harness; `run_subprocess(*args)` — real subprocess for `test_cli.py`; helpers `start()`, `next()`, `record(attempt: str, message: dict | str, *, tokens: int | None = None, usage: dict | None = None)` (writes the result file itself), `owner(kind, quote, **opts)`, `status(**opts)`, `doctor(**opts)`, `judgment(kind, text, *, root)`.

### `stub_agent.py`
- `@dataclass class Behavior`: `message: dict | str | None` (None → the default for the kind), `artifact: dict | str | None` (written to the step's artifact path; None → sample), `edits: dict[str, str | None]` (worktree-harness-relative path → content, None = delete), `strays: dict[str, str]` (edits outside declared paths, kept separate so tests can assert reverts), `judgment_calls: list[tuple[str, str]]` (run through the judgment command with `--root` = worktree harness), `raw_result: str | None` (write this text as the result file instead of JSON), `tokens: int | None`, `usage: dict | None`.
- `class StubAgent`: `script: dict[str, Behavior | Callable[[dict], Behavior]]` keyed by attempt id, then step name, then kind (`producer`, `gate`, `driver`, `conflict`); `act(next_output: dict, fake: FakeHarness) -> tuple[str, dict]` — performs edits/artifact/judgment calls in the worktree, writes the result file, returns (attempt id, record kwargs); `calls: list[dict]`. Default behaviours: driver → sample plan; producer → sample artifact for the step (PLAN-AGENTS: shares that satisfy validation; PLAN-TO-SPEC: sample spec + SPEC.md; SPEC-TO-TESTS: add `tests/test_round.py` with two tests; SPEC-TO-IMPLEMENTATION: add `src/round_feature.py`; TESTS-TO-SUITE: SUITE.json keeping one test, archiving one; POSTMORTEM: POSTMORTEM.md with Summary + a TODO line; CLEANUP: no edits) and `DONE`; gate → `PASS` with no findings; conflict → remove markers keeping "ours".

### `artifacts_samples.py`
- `sample_plan(quote=100.0, questions=(), non_goals=("no ui",))`, `sample_agents_plan(cfg, roster, *, gate_on)`, `sample_spec(non_goals)`, `sample_spec_md()`, `sample_suite(new_tests, archive=())`, `sample_postmortem()`; message builders `producer_done(**kw)`, `producer_needs_owner(questions)`, `producer_blocked(narrow)`, `gate_pass(findings=())`, `gate_fail(findings, rulings=())`, `finding(quote, text, suggestion="fix it", blocking=True)`.

### `stub_driver.py`
- `@dataclass class OwnerScript`: `on_checkpoint: str = "approve"`, `on_needs_owner: Callable[[list[dict]], list[tuple[int, str]]]` (answers), `on_blocked: str | None`, `on_limit: str | None` (`raise-limit:<key>=<v>` | `resume` | `abandon`), `on_hard_stop`, `on_sync`, `on_drift`.
- `drive(runner: Runner, stub: StubAgent, fake: FakeHarness, owner: Sayer, *, script: OwnerScript = OwnerScript(), until: Callable[[dict], bool] | None = None, max_steps: int = 300) -> Trace` — the loop: `next` → by kind: `driver`/`producer`/`gate`/`conflict` → `stub.act` → `record`; `checkpoint`/`owner` → issue the scripted decision (quotes via `owner.say`) ; `done` → stop; `until(output)` → stop early. `Trace(events: list[dict], kinds: list[str], attempts: list[str], final: dict)` with `.attempt_ids()`, `.pauses()`.

## 10.3 `tests/fixtures/`

`messages/producer_done.json`, `producer_needs_owner.json`, `producer_blocked.json`, `gate_pass.json`, `gate_fail.json`, `invalid_not_json.txt`, `two_objects.txt`, `fenced_json.txt`; `findings/prior_findings.json` (a FINDINGS file with one disputed and one withdrawn finding); `owner_log/sample.jsonl` (three lines, one malformed); `hook/payload.json`; `automerge/conflicted.py` (a file with markers). Fixture files are loaded by a `fixture(name) -> str` helper in `conftest.py`.

## 10.4 Test files — cases and assertions (part 1)

### `test_spec_drift.py` (real tree; the guard)
- `test_spec_files_match_baseline` — `specfiles.drift(real_roots, Baseline.load(...))` is empty; on failure the assertion message contains the changed/added/removed lists and `drift_diff(...)` output (unified diff via `git show`), so the failing test *shows the diff*.
- `test_baseline_covers_exactly_the_listed_files` — `set(baseline.files) == set(list_spec_files(real_roots))`.
- `test_baseline_accepted_commit_exists` — skipped without git; otherwise `git cat-file -e` on `accepted_commit` succeeds.

### `test_paths.py`
- `test_discover_from_nested_dir_finds_harness_and_spec_yaml`; `test_discover_without_project_yaml_raises_config_error`; `test_discover_without_spec_yaml_raises`.
- `test_round_folder_pads_to_placeholder_width` (`NNNN`→`0007`, `NN`→`07`); `test_folder_pattern_without_n_run_raises`.
- `test_artifact_runner_attempt_lookup_by_key`; `test_unknown_round_path_key_raises_naming_it`; `test_prompt_result_findings_file_names`; `test_relative_uses_forward_slashes`.
- `test_is_under_prefix_semantics` (`src/` matches `src/a.py`, not `srcx/a.py`, not `src`).
- `test_for_worktree_maps_layout`.

### `test_specfiles.py`
- `test_list_spec_files_expands_globs_sorted_relative_to_spec_dir`; `test_list_spec_files_empty_glob_allowed`; `test_list_spec_files_malformed_raises`.
- `test_hash_format_and_determinism`.
- `test_drift_detects_changed_added_removed`; `test_missing_baseline_is_total_drift`.
- `test_drift_diff_unified_with_show`; `test_drift_diff_without_show_notes_hash_only`; `test_added_and_removed_listed_in_diff`.
- `test_accept_writes_hashes_commit_by_note`; `test_is_spec_file`.

### `test_config.py`
- `test_load_fake_project_yaml_has_only_registered_defaults` (defaulted == `["testPaths", "promptSizeWarnTokens"]`).
- `test_missing_required_key_names_it`; `test_wrong_type_names_key_and_type`; `test_unregistered_key_listed_as_unused`; `test_wildcard_keys_match_steps_and_agents`.
- `test_fractions_must_sum_to_one`; `test_living_paths_must_end_with_slash`; `test_test_paths_must_be_under_living`; `test_round_folder_needs_placeholder`; `test_steps_values_must_be_0_or_1`.
- `test_get_unregistered_path_raises`; `test_step_gate_on_and_checkpoint_on`.
- `test_prose_values_renders_lists_and_numbers` (`livingSourcePaths` → `src/, docs/, tests/`; `0.25` → `0.25`; `50000` → `50000`).
- Roster: `test_rungs_keep_file_order_and_rank`; `test_within_ceiling`; `test_unknown_rung_raises`; `test_default_agent_must_exist`; `test_table_text_one_line_per_rung`; `test_subagents_file_name_from_config`; `test_roster_missing_price_key_raises`.

### `test_localcfg.py`
- `test_generate_fields_complete`; `test_generated_contains_no_setting_keys_as_inputs` (no key from the registry appears outside `effectiveConfig`); `test_save_load_roundtrip`; `test_ensure_generates_when_absent`; `test_defaults_when_absent` (`origin`, `main`, `claude`).

### `test_steps.py`
- `test_step_names_unique_and_order_fixed` (asserts the exact eleven names in order — this is the one place the order is written down twice, on purpose); `test_checkpoints_have_no_gate_no_artifacts`; `test_non_overridable_steps` (CHAT-TO-PLAN, checkpoints, LANDING, CLEANUP); `test_kinds_valid`; `test_artifact_keys_exist_in_round_paths` (against the fake config).
- `test_lint_matching_map_ok`; `test_lint_unknown_step`; `test_lint_missing_step`; `test_lint_reordered`; `test_lint_bad_value`; `test_lint_gate_flag_on_no_gate_step_is_note`.
- `test_consumers_lists_fakespec_and_process_doc`.

### `test_prose.py`
- `test_load_reads_every_txt_by_stem`; `test_missing_dir_raises`; `test_agents_sections_keys_normalized` (`ADVICE`, `INVARIANTS`, `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`) and bodies exclude headings.
- `test_render_substitutes_each_namespace`; `test_unknown_token_left_verbatim_and_listed`; `test_unknown_namespace_left_verbatim`; `test_recursive_prose_include_records_included_order`; `test_cycle_raises_with_chain`; `test_depth_limit_raises`.
- `test_find_tokens_order_and_duplicates`; `test_references_map`; `test_gates_text_on_off_and_no_prose`; `test_list_text_formats`; `test_text_without_tokens_is_byte_identical`; `test_token_spacing_variants` (`{{prose.X}}`, `{{  prose.X  }}`).

### `test_plumbing.py`
- Producer: `test_producer_instructions_name_worktree_declared_paths_and_artifact`; `test_judgment_tool_command_uses_driver_runner_and_worktree_root`; `test_final_message_schema_present`; `test_helper_section_shows_cap_and_spawn_command_or_none`; `test_open_findings_listed_with_states_and_settled_note`; `test_no_findings_section_when_none`.
- Gate: `test_gate_instructions_read_only_and_findings_file`; `test_disputed_findings_require_rulings_sentence`; `test_verify_result_included_when_present`.
- Driver: `test_driver_template_lists_every_decision_kind` (from `decisions.KINDS`); `test_driver_template_names_plan_path_and_record_command`.
- `test_conflict_template_lists_files`; `test_checkpoint_summary_contents`; `test_pause_summary_lists_questions_flags_unblocks`.
- `test_gate_prose_on_off_absent`; `test_gate_prose_has_no_nested_process_instructions`; `test_missing_placeholder_raises_prose_error`; `test_missing_template_raises`.

### `test_prompts.py`
- `test_open_attempt_writes_prompt_and_registers` (file exists; `open_attempt` set; output paths absolute; `agent` = `shackles-<rung>`; gates `read_only`).
- `test_prompt_ends_with_step_end_prose`; `test_missing_step_end_stem_adds_note_and_no_trailer`.
- `test_every_step_and_kind_renders_without_unresolved_tokens` (parametrized over `steps.STEPS` × kinds).
- `test_round_values_plan_with_answers_and_placeholder_before_approval`; `test_round_values_numbers`.
- `test_prompt_size_warning_when_over_threshold` (config override `promptSizeWarnTokens: 5`).
- `test_render_offline_writes_nothing_and_uses_synthetic_round`; `test_open_while_open_raises_state_error`; `test_inputs_resolved_to_absolute_paths_and_listings`.

### `test_agentdefs.py`
- `test_two_definitions_per_rung_with_names`; `test_frontmatter_model_and_effort_from_roster`; `test_gate_definition_read_only_tools`; `test_producer_definition_has_no_tools_key`; `test_write_all_creates_and_removes_stale`; `test_check_reports_missing_stale_orphaned`; `test_agent_name`.
- `test_committed_definitions_are_fresh` (real tree: `agentdefs.check(real_roots, real roster)` is empty).

### `test_state.py`
- `test_new_round_initial_fields`; `test_save_is_atomic_no_temp_left`; `test_load_preserves_unknown_keys`; `test_load_corrupt_raises`.
- `test_attempt_ids_sequence_producer_and_gate`; `test_open_twice_raises`; `test_turns_counter_increments_on_open`; `test_close_attempt_fields`.
- `test_advance_phase_gate_on_then_off`; `test_goto_and_is_done`.
- `test_pause_resume_and_restarts_only_for_limit_kinds`; `test_active_seconds_excludes_paused_time` (clock-driven).
- `test_register_questions_global_ids_continue`; `test_answer_unknown_or_answered_raises`; `test_flags_pending_to_delivered`; `test_bump_rejection`; `test_end_round_sets_status_and_time`.
- `test_find_active_round_picks_newest_non_ended`.

### `test_history.py`
- `test_entry_heading_has_timestamp_kind_title`; `test_attempt_recorded_includes_fenced_json_and_fields`; `test_owner_entry_blockquotes_quote`; `test_read_entries_splits_on_headings`; `test_append_is_append_only`.

### `test_messages.py`
- `test_parse_producer_fixture`; `test_parse_gate_fixture`; `test_fenced_json_accepted`; `test_two_objects_rejected`; `test_not_json_rejected_with_reason`; `test_status_not_allowed_for_kind`; `test_needs_owner_requires_questions_with_two_options`; `test_blocked_requires_narrow`; `test_bad_resolution_value`; `test_bad_ruling_value`; `test_finding_requires_quote_text_suggestion`; `test_judgment_call_kinds`; `test_extra_keys_ignored`; `test_missing_optional_arrays_default_empty`; `test_parse_file_unreadable_is_usage_error`.

### `test_artifacts.py`
- Plan: `test_valid_plan`; `test_quote_must_be_positive`; `test_question_needs_two_options`; `test_missing_text`; `test_multiple_errors_collected`.
- Agents plan: `test_valid_agents_plan`; `test_unknown_rung`; `test_rung_above_ceiling`; `test_helper_count_over_cap`; `test_work_shares_over_fraction_error`; `test_work_shares_under_by_margin_warning`; `test_share_below_advisory_minimum_warning`; `test_missing_step_entry_error`; `test_gate_entry_required_only_when_gate_on`.
- Spec: `test_valid_spec`; `test_unknown_component_reference`; `test_empty_test_plan`; `test_refactor_over_cap_is_warning`; `test_non_goal_not_carried_is_warning`; `test_spec_md_must_be_non_empty`.
- Suite: `test_complete_suite_decisions`; `test_missing_new_test_error`; `test_unknown_test_error`; `test_mixed_file_error`; `test_bad_decision_value`.
- Postmortem: `test_summary_first_heading_any_level_case_insensitive`; `test_other_first_heading_error`; `test_summary_text_extraction_stops_at_next_heading`.

### `test_findings.py`
- `test_new_findings_get_step_scoped_ids`; `test_pass_turns_open_findings_into_notes`; `test_fail_marks_all_open_blocking`; `test_fail_with_no_surviving_findings_not_accepted_with_reason`.
- `test_repeat_of_withdrawn_by_normalized_quote_dropped_with_note`; `test_repeat_by_identical_text_dropped`; `test_non_repeat_kept`.
- `test_ruling_upheld_increments_and_stays_open`; `test_second_uphold_settles`; `test_ruling_withdrawn`; `test_missing_ruling_counts_as_upheld_and_flagged`.
- `test_resolutions_all_open_resolved_ok`; `test_missing_resolution_is_error`; `test_dispute_settled_is_error`; `test_unknown_finding_id_is_error`; `test_fixed_sets_state`.
- `test_findings_file_written_with_contract_fields`; `test_findings_file_keyed_by_judged_attempt`.

### `test_judgment.py`
- `test_init_headers`; `test_append_line_format_and_newline_collapse`; `test_empty_text_raises`; `test_append_from_message_counts`; `test_read_lines`.

## 10.5 Test files — cases and assertions (part 2)

### `test_ownerlog.py`
- Hook: `test_hook_appends_json_line_with_ts_session_cwd_prompt` (runs the real script via `Sayer.run_hook`); `test_hook_unparsable_payload_logs_error_line_and_exits_zero`; `test_hook_prints_nothing`; `test_hook_locates_harness_from_its_own_path` (cwd elsewhere).
- Reader: `test_read_skips_malformed_lines_and_counts`; `test_require_log_missing_raises`; `test_require_log_empty_raises`.
- Quotes: `test_verify_exact`; `test_verify_whitespace_normalized`; `test_verify_substring`; `test_verify_not_found_raises_with_count`; `test_verify_since_excludes_older_entries`; `test_verify_empty_quote_raises`.
- Slices: `test_slice_and_write_slice_counts`; `test_previous_round_end_from_archives` (two archived STATE.json files; newest `ended_at` wins; none → None).

### `test_decisions.py`
- Approval: `test_approve_with_open_questions_refused`; `test_approve_after_answers_starts_round` (status `running`, `approved_at`, cursor PLAN-AGENTS); `test_delegate_sets_mode`; `test_delegate_through_validates_step`; `test_approve_at_checkpoint_resumes`; `test_delegate_at_checkpoint_switches_mode_and_resumes`.
- Override: `test_override_unknown_target`; `test_override_plan_refused`; `test_override_landing_and_cleanup_refused`; `test_override_checkpoint_refused`; `test_override_done_step_refused`; `test_override_gate_target_form`; `test_override_does_not_resume`.
- Answers: `test_answer_records_quote`; `test_last_answer_clears_needs_owner_pause`; `test_answer_does_not_clear_blocked_pause`.
- `test_abandon_any_time_records_reason`; `test_revise_only_before_approval`.
- Resume: `test_resume_blocked_requires_answer_since_pause`; `test_resume_limit_kinds`; `test_resume_drift_requires_no_drift`; `test_resume_refused_when_restarts_exhausted`; `test_resume_allowed_after_raise_limit_max_round_attempts`.
- `test_raise_limit_key_validation`; `test_raise_limit_must_exceed_current`; `test_raise_limit_recorded_in_overrides`.
- `test_checkpoint_skipped_matrix` (flag 0; mode delegate; through before/at/after the checkpoint; mode approve); `test_is_overridden_step_and_gate`.

### `test_gitops.py` (real git, bare remote)
- Claim: `test_claim_allocates_max_plus_one_from_folders_and_remote_branches`; `test_claim_creates_branch_at_main_sha`; `test_claim_retries_next_id_when_remote_branch_exists`; `test_claim_exhausted_raises`; `test_unclaim_removes_local_and_remote`.
- Fence: `test_fence_push_returns_new_sha`; `test_fence_push_rejected_when_remote_moved` (via `move_remote_branch`); `test_fence_check_mismatch_raises`.
- Worktrees: `test_add_and_remove_worktree`; `test_worktree_head`.
- Working tree: `test_status_porcelain_kinds_M_A_D_untracked_rename`; `test_revert_paths_restores_tracked_and_deletes_untracked`; `test_commit_all_with_path_subset`; `test_commit_all_nothing_returns_none`.
- Trees: `test_show_file_and_none_when_absent`; `test_tree_files_under_prefixes`; `test_changed_between_with_renames`.
- Merges: `test_merge_clean`; `test_merge_conflict_lists_files_and_leaves_markers`; `test_snapshot_automerge_ref_tree_contains_markers`; `test_diff_against_ref_after_resolution`; `test_conclude_merge_after_fix`; `test_conclude_merge_with_unmerged_raises`; `test_abort_merge`; `test_has_conflict_markers`.
- Main: `test_fast_forward_main_with_lease_success`; `test_fast_forward_main_rejected_when_main_moved_returns_false`; `test_update_driver_checkout_ff_only`; `test_update_driver_checkout_raises_when_diverged`.
- `test_restore_paths_from_removes_new_and_restores_changed`; `test_log_subjects`; `test_is_ancestor`; `test_detect_main_branch_fallback`; `test_git_error_detail_has_cmd_and_stderr`.

### `test_checks.py`
- `test_declared_paths_symbols_expand_and_intersect_living` (parametrized over every step); `test_gate_declared_paths_empty`; `test_root_docs_only_for_cleanup`; `test_conflicts_symbol_literal_list`.
- `test_path_policy_spec_file_is_stray`; `test_path_policy_outside_allowed_is_stray`; `test_path_policy_runtime_files_are_strays`; `test_path_policy_rename_counts_both_paths`.
- `test_run_for_attempt_reverts_and_lists_strays_keeps_allowed`; `test_gate_attempt_edits_all_reverted_no_mechanical`; `test_git_error_becomes_mechanical`.
- CHECKS: `test_artifact_missing_is_mechanical`; `test_artifact_invalid_is_mechanical_with_rules`; `test_artifact_warnings_pass_through`; `test_tests_collect_syntax_error_mechanical_with_tail`; `test_new_tests_exist_none_mechanical`; `test_verify_suite_pass_sets_verify`; `test_verify_suite_fail_mechanical`; `test_verify_suite_timeout_mechanical` (`verifyTimeoutSeconds: 1`, a sleeping test); `test_suite_consistent_fills_moves`; `test_conflict_only_counts`; `test_no_markers_mechanical_when_markers_remain`; `test_run_pytest_captures_tail`.

### `test_suite.py`
- `test_enumerate_module_functions_and_test_class_methods`; `test_non_test_names_ignored`; `test_syntax_error_safe_flag`; `test_enumerate_tree_respects_test_paths`; `test_test_names_bare`; `test_new_tests_vs_base`; `test_plan_moves_paths_relative_to_test_root`; `test_apply_moves_uses_git_mv`; `test_stats`.

### `test_charges.py`
- `test_estimate_tokens_ceil`; `test_zero_token_bytes_raises`; `test_file_price_under_and_over_cap`.
- `test_new_file_charges_base_plus_tokens`; `test_removed_file_refunds`; `test_changed_file_delta_only`; `test_rename_no_base_cost_delta_only`; `test_carry_file_special_rate_no_cap_no_base`; `test_tests_added_and_removed_base`; `test_moved_test_is_neutral`; `test_negative_total_when_tree_shrinks`; `test_files_outside_living_ignored`.
- `test_archive_charges`; `test_summary_bytes`; `test_usage_usd_with_cache_rates`; `test_estimate_usage_math`; `test_spawn_floor`.

### `test_ledger.py`
- `test_book_attempt_measured_usage`; `test_book_attempt_total_tokens_split_by_fraction`; `test_book_attempt_estimated_from_prompt`; `test_spawn_floor_applied`; `test_driver_attempt_books_zero`; `test_book_driver_step_once_per_step`; `test_book_helper_measured`.
- `test_book_round_end_entries_when_landed` (living, archive, carry); `test_book_round_end_no_living_when_not_landed`; `test_negative_living_entry`; `test_round_total_and_remaining`; `test_project_spent_sums_archived_and_active`; `test_elapsed_context_not_booked`.

### `test_budget.py`
- `test_share_default_shares_for_early_steps`; `test_share_from_agents_plan`; `test_missing_share_zero_with_warning`; `test_attempt_budget_same_on_retry`; `test_rung_default_gate_plan_and_ceiling_fallback`; `test_helpers_for`; `test_individual_cap`.

### `test_limits.py`
- `test_effective_uses_overrides`; `test_before_attempt_turns`; `test_before_attempt_wall_clock_active_only`; `test_after_record_individual_cap`; `test_after_record_round_multiple`; `test_after_record_rejections_reach_max_turns`; `test_round_hard_stop_skipped_after_landing`; `test_restarts_exhausted`; `test_describe_headroom`.

### `test_cli.py`
- `test_ok_exit_zero_single_json_line`; `test_refused_exit_two_json_error`; `test_fence_error_exit_three`; `test_usage_error_exit_four`; `test_unexpected_exception_exit_one_with_code`; `test_human_flag_renders`; `test_root_override`; `test_unknown_command_usage_error`; `test_every_command_module_has_add_arguments_and_run`; `test_subprocess_invocation_matches_in_process` (one command through `run_subprocess`).

### `test_cmd_doctor.py`
- `test_clean_fake_ok_with_defaulted_notes`; `test_unknown_step_error_and_list`; `test_unresolved_token_error_names_token_and_file`; `test_missing_overview_prose_error`; `test_gate_on_without_prose_error_off_is_note`; `test_unused_prose_warning`; `test_extra_config_key_error`; `test_stale_agent_defs_warning_error_under_check`; `test_hook_missing_error`; `test_drift_error`; `test_offline_skips_git`; `test_write_regenerates_local_yaml_and_defs`; `test_no_write_when_errors`; `test_rendered_has_every_step_kind`; `test_prompt_size_warning`; `test_price_date_stale_warning`; `test_leftover_worktree_note`.

### `test_cmd_start.py`
- Refusals: `test_refuses_drift_with_diff`; `test_refuses_without_owner_log`; `test_refuses_unknown_step`; `test_refuses_allow_upstream_one`; `test_refuses_active_round`; `test_refuses_without_remote`; `test_refuses_doctor_errors`.
- Success: `test_claims_branch_on_remote`; `test_creates_worktree_and_round_folder`; `test_state_planning_and_cursor`; `test_writes_chat_to_plan_prompt`; `test_judgment_headers_written`; `test_owner_log_slice_written`; `test_history_entry`; `test_output_kind_driver_with_paths`; `test_failure_after_claim_unclaims` (monkeypatch `prompts.open_attempt` to raise).

### `test_round_flow.py` (stub-driven, end to end)
- `test_happy_path_gates_off_checkpoints_on` — kinds sequence: driver, producer×2, checkpoint, producer×3, checkpoint, (landing inline), producer×2, done; two checkpoint pauses answered by `approve`; final STATE `done`; round folder present on main (`file_at(bare, "main", ".../STATE.json")`); ledger has `driver`, `agent`, `living`, `archive` entries; worktree removed; remote branch still exists.
- `test_delegate_skips_both_checkpoints`; `test_delegate_through_checkpoint_1_pauses_only_at_2`; `test_checkpoint_flag_zero_never_pauses`.
- `test_gate_pass_advances`; `test_gate_fail_retries_with_findings_in_prompt_and_resolutions_required`; `test_disputed_finding_ruled_by_next_gate`; `test_fail_times_max_turns_pauses_limit`; `test_override_gate_skips_it_with_history`.
- `test_needs_owner_pauses_and_answer_clears`; `test_answer_appears_in_next_prompt_round_plan`; `test_blocked_pauses_resume_needs_answer`.
- `test_invalid_message_is_mechanical_rejection_and_counts`; `test_missing_artifact_mechanical_retry`; `test_strays_reverted_attempt_still_accepted`; `test_spec_file_edit_reverted_and_noted`.
- `test_flags_delivered_at_next_pause_then_cleared`; `test_plan_questions_block_approval_until_answered`; `test_revise_opens_second_plan_attempt`.
- `test_abandon_before_landing_lands_record_only` (main has round folder; living files unchanged; status `abandoned`; ledger has agent entries, no living entry); `test_abandon_reason_in_history`.
- `test_override_step_skipped_with_history`; `test_max_turns_per_run_pauses_and_raise_limit_resumes`; `test_restarts_exhausted_resume_refused_until_raised`.
- `test_mid_round_drift_pauses_and_revert_allows_resume`; `test_fence_broken_returns_exit_three`; `test_next_is_idempotent_while_attempt_open`; `test_judgment_tool_from_worktree_appends_with_attempt_id`; `test_helper_spawn_with_stub_invoker_books_helper_entry`.
- `test_driver_overhead_booked_once_per_step`; `test_history_has_entry_per_event`.

### `test_landing.py`
- `test_clean_landing_fast_forwards_main_and_records_main_before`; `test_driver_checkout_updated`.
- `test_hard_stop_before_landing_pauses_and_raise_limit_resumes` (tiny `hardStopBudgetMultiple`, big generated file).
- `test_conflict_opens_attempt_with_conflicted_files`; `test_conflict_resolution_accepted_concludes_and_lands`; `test_conflict_strays_outside_conflicted_files_reverted`; `test_conflict_leftover_markers_mechanical`; `test_conflict_attempts_bounded_by_max_turns`.
- `test_merged_tree_failing_suite_pauses_mechanical`.
- `test_main_moves_between_fetch_and_push_retried`; `test_sync_bound_exhausted_pauses_sync_and_resume_retries` (a background pusher via `commit_on_main_elsewhere` in a loop, or monkeypatched `fast_forward_main` returning False).
- `test_post_landing_commits_reach_main_via_sync`; `test_sync_conflict_opens_landing_attempt`; `test_abandon_after_landing_syncs_record`.

### `test_suite_moves.py`
- `test_archive_files_moved_preserving_relative_path_and_committed`; `test_suite_files_stay`; `test_mixed_file_mechanical_retry`; `test_unlisted_new_test_mechanical`; `test_moves_recorded_in_state_and_history`; `test_archived_tests_not_run_by_verify`.

### `test_invoke.py`
- `test_stub_invoker_records_and_returns`; `test_cli_invoker_builds_args_from_constant` (fake runner); `test_cli_invoker_parses_usage_json`; `test_cli_invoker_nonzero_raises_spawn_error`; `test_acquire_slot_cap`; `test_stale_slot_reaped`; `test_invoke_for_spawn_rung_checks`.

### `test_cmd_spawn.py` (StubInvoker injected through `SHACKLES_INVOKER=stub` and a script file path)
- `test_spawn_writes_out_and_books_helper_measured`; `test_spawn_cap_reached_exit_two`; `test_spawn_unknown_rung`; `test_spawn_requires_open_attempt`.

### `test_cmd_status.py`
- `test_status_without_round`; `test_status_with_round_fields`; `test_status_ledger_findings_decisions_sections`; `test_status_context_cost_and_limits`; `test_status_drift_and_fence`.

### `test_cmd_accept_spec.py`
- `test_refuses_while_round_active`; `test_requires_quote_or_flag`; `test_quote_verified`; `test_rewrites_baseline_and_regenerates`; `test_commits_on_main_and_pushes`; `test_doctor_errors_block_acceptance`.

### `test_cmd_spec_drift.py`
- `test_clean_exit_zero`; `test_drift_exit_two_with_diff_and_lists`.

### `test_cmd_judgment.py`
- `test_appends_with_open_attempt_id`; `test_no_open_attempt_state_error`; `test_empty_text_usage_error`; `test_undefined_goes_to_undefined_file`.

### `test_docs_consistency.py` (real tree)
- `test_process_md_step_table_matches_steps` (names in order appear in the "step table" section); `test_formats_md_has_every_required_heading`; `test_index_md_has_line_for_every_module_command_doc_and_support_file`; `test_readme_mentions_every_command`; `test_architecture_module_map_covers_every_module`.

### `test_config_surface.py` (real spec files, no prose)
- `test_real_project_yaml_has_no_unregistered_keys`; `test_real_subagents_yaml_has_no_unregistered_keys`; `test_real_roster_defaults_exist`; `test_real_steps_map_lints_clean`.

## 10.6 `tests/probes/` — live probes with planted defects

`conftest.py`: skip all unless `SHACKLES_LIVE=1` and `shutil.which(claude command)`; fixture `live_harness` = a *copy of the real harness* (real prose, real config) in a temp dir with git + bare remote + owner log; fixture `probe_invoker` = `CliInvoker` at rung `systemTestAgent`; helper `run_gate(step, artifact_files, prior_findings=None) -> GateMessage` and `run_producer(step) -> ProducerMessage` that render the real prompt through `prompts.render_offline`-like assembly with a synthetic round, invoke, and parse. Each probe asserts on structure and on quoted text, never on wording.

- `test_probe_producer_message_parses.py` — a real producer given the PLAN-AGENTS prompt returns a message `messages.parse_text` accepts and writes a valid `AGENTS-PLAN.json`.
- `test_probe_spec_gate_catches_ambiguity.py` — SPEC.md/SPEC.json with one planted sentence two implementers would read differently → PLAN-TO-SPEC gate `FAIL` with a finding whose `quote` contains the planted phrase.
- `test_probe_impl_gate_catches_outside_spec.py` — an implementation diff with a planted function not in the spec → SPEC-TO-IMPLEMENTATION gate `FAIL` quoting the function.
- `test_probe_tests_gate_catches_uncovered_component.py` — spec with three components, tests for two → `FAIL` naming the third.
- `test_probe_agents_plan_gate_small_imbalance_non_blocking.py` — a slightly imbalanced plan → `PASS` with ≥1 finding; an absurd plan (all budget on CLEANUP) → `FAIL`.
- `test_probe_gate_rules_on_disputed.py` — prior FINDINGS with a disputed finding → the gate's message has a ruling for it before any new finding; then a second gate turn re-raising a withdrawn finding → `findings.accept_gate_message` drops it (runner behaviour on real output).
- `test_probe_postmortem_gate_incomplete_trace.py` — POSTMORTEM.md with an issue lacking its trace → `FAIL`.
- `test_probe_undefined_judgment_call_logged.py` — a producer prompt whose inputs contradict a doc it is pointed at → the judgment tool receives an `UNDEFINED` line (the stub runner path records the call).

Probe budget: each probe is one or two spawns at the `systemTestAgent` rung; the probe conftest prints the measured cost total at session end.
