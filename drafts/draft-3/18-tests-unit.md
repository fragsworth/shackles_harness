# 18 — Unit test files, case by case

Every file below lives in `harness/tests/`, uses the fixtures of file 17, and never
reads the owner's real spec files. "asserts" lists what each case checks.

## `test_paths.py` (paths.py)
- `harness_root_override_requires_project_yaml`: an override dir without
  `project.yaml` raises `RefusedError("NO_ROOT")`; with it, returns that dir.
- `repo_root_finds_spec_yaml`: from the fixture harness, returns the fixture repo
  root; from a dir with no `spec.yaml` above, raises `NO_SPEC_YAML`.
- `worktree_paths`: `worktree_dir` is `<repo>/.worktrees/round-0007`;
  `worktree_harness` keeps the `harness/` suffix.
- `round_paths_from_config`: every attribute of `RoundPaths` equals the config's
  names joined under `archives/rounds/0001/`; `prompt("X", 2, gate=True)` ends with
  `PROMPTS/X-GATE-2.txt`; `artifact_by_key("nope")` raises `KeyError`.
- `round_folder_requires_NNNN`: a folder pattern without `NNNN` raises `ConfigError`.

## test_config.py (config.py)
- `loads_example_dict`: `example_project_dict` round-trips through `load_project`
  with zero errors; `defaulted_keys()` lists exactly the five defaulted keys.
- `unknown_key_refuses` (top level, inside `roundPaths`, inside an agent) raises
  `ConfigError` naming the dotted key.
- `wrong_type_refuses`: `budget: "x"`, `steps: [..]`, `livingSourcePaths: "src/"`.
- `fractions_must_sum_to_one`; `steps_values_0_or_1`; `allow_upstream_must_be_0`;
  `token_bytes_positive`; `living_paths_end_with_slash`.
- `default_shares_unknown_step_refuses`.
- `agents_ladder_order`: `ladder()` is file order; `rank("max") == 0`;
  `at_or_below("low", "max")` true, reverse false.
- `cross_validation`: `defaultAgent` above `maxAgent` raises; unknown `gateAgent`
  raises.
- `render_value_forms`: list → `src/, docs/, tests/`; mapping → `a: 1, b: 2`; float
  `0.25` → `0.25`; string unchanged.
- `value_at_nested`: `defaultShares.work.CHAT-TO-PLAN` resolves; unknown raises
  `KeyError`.

## test_specfiles.py (specfiles.py, localstate.py)
- `expand_patterns_globs_and_sorts`: `harness/locked_prose/*` expands to every
  `.txt`; a pattern matching nothing raises `SPEC_FILE_MISSING`.
- `hashes_change_with_content`.
- `drift_report_categories`: after editing one prose file, adding one and deleting
  one: `changed`, `added`, `removed` each name the right path; `clean` false.
- `accept_writes_baseline_and_copies`: `local.yaml` hashes match; copies exist
  under `archives/spec-baseline/`; a second `accept` is a no-op report.
- `diff_text_shows_unified_diff`: contains `-old line` / `+new line`; `added` file
  shows all `+`; missing copy shows `(no baseline copy)`.
- `assert_no_drift_raises_with_files`.
- `localstate_roundtrip_and_missing`: absent file → empty state; malformed → raises.

## test_tokens.py
- `ceil_division`: `estimate(1, 4) == 1`, `estimate(4, 4) == 1`, `estimate(5, 4) == 2`,
  `estimate(0, 4) == 0`; `token_bytes < 1` raises.
- `text_uses_utf8_bytes`: `text_tokens("é", 1) == 2`.
- `missing_file_is_zero`.

## test_steps.py (steps.py)
- `table_matches_fixture_config`: `lint` on the fixture yields no errors.
- `order_mismatch_is_error`: swapping two steps in `steps:` → error listing both
  orders; a missing step → error; an extra step → error.
- `gate_on_without_prose_is_error`; `gate_on_non_capable_is_warning` (LANDING: 1).
- `unknown_prose_file_is_error` (`FOO.txt`), `non_txt_is_error` (`notes.md`),
  `unused_common_is_warning` (`COMMON-UNUSED.txt`).
- `missing_required_prose_is_error` (drop `PLAN-AGENTS-OVERVIEW`); optional ones are
  not (`CHAT-TO-PLAN-GATE`, `LANDING-OVERVIEW` absent → no error).
- `artifact_key_mismatch`: config lacking `artifacts.suite` → error; an extra
  artifact key → error.
- `missing_plumbing_token_is_warning`.
- `parse_overrides`: `PLAN-AGENTS,PLAN-TO-SPEC-GATE` parses; `CHAT-TO-PLAN`,
  `LANDING`, `CLEANUP`, `CHECKPOINT-1-GATE`, `NOPE` each raise `UsageError`.
- `gate_is_on_matrix`: capable+1+prose+not overridden → true; each negation → false.
- `resolve_scopes_per_step`: PLAN-AGENTS → the artifact file and the two trails;
  SPEC-TO-TESTS → `tests/` prefix + trails; SPEC-TO-IMPLEMENTATION → `src/`, `docs/`
  (not `tests/`); POSTMORTEM → the carry-forward files; LANDING → given conflicted
  files.
- `checkpoint_covered`: through `PLAN-TO-SPEC` does not cover CHECKPOINT-1; through
  `SPEC-TO-TESTS` covers CHECKPOINT-1 but not CHECKPOINT-2; `None` covers all.

## test_prose.py
- `loads_txt_only_and_lists_others`; `classify_stems` (overview, gate, common, other).
- `section_keys`: `## DEFINED AND UNDEFINED JUDGMENT CALLS` →
  `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`; `## ADVICE.` → `ADVICE`; `FULL` present;
  duplicate heading → later wins + warning.
- `tokens_in_and_referenced_closure`: from `PLAN-AGENTS-OVERVIEW` the closure
  contains `COMMON-PROJECT` and `COMMON-ROUND`, not `COMMON-GATE`.
- `crlf_normalised`.

## test_templates.py
- `find_tokens_syntax`: spaces optional; keys with dots and hyphens; `{{ bad }}` and
  `{{ ns. }}` are malformed, not tokens.
- `render_recursive`: a prose fragment containing another token renders fully.
- `unresolved_collects_all`: two unknown tokens → one `RenderError` listing both.
- `cycle_detected`: A → B → A raises `RENDER_CYCLE` with the chain.
- `depth_limit`.
- `render_lenient_keeps_unknowns`; `mask_namespace_replaces_only_that_namespace`.

## test_context.py
- `project_values`: `project.vision` is the fixture vision; `project.gates` lists
  gate-capable steps with `on/off` per config; `project.remaining` = budget − spend
  with two decimals; `project.livingSourcePaths` comma-joined; unknown key → `None`.
- `round_values_from_state`: `round.plan` is `plan_as_text`; `round.remaining` =
  quote − spend.
- `agents_sections_resolve`; `prose_resolves_raw` (unrendered fragment returned);
  `plumbing_slot`: unset → `None`, set → the value; `with_plumbing` does not mutate.
- `all_rounds_spend_sums_state_files` and skips unreadable ones.

## test_prompts.py
- `layout_sections_in_order`: header, `---- AGENTS.md ----` with the full AGENTS.md,
  `---- STEP ----` with the overview marker, `---- STEP END ----` with
  `COMMON-STEP-END` and the AGENTS.md judgment-call section rendered.
- `plumbing_appended_when_token_missing` (an overview without the token) with a
  warning; `plumbing_not_duplicated_when_present`.
- `process_instructions_sections`: every fixed heading appears; declared paths,
  artifact paths, the result path, the `jc` command with step and attempt, the limits
  numbers from config, `OWNER DECISIONS` quotes verbatim, `PRIOR FINDINGS` verbatim
  with ids needing resolution.
- `gate_prompt_is_read_only_and_masks_plumbing_preview`: the producer prompt's
  `plumbing.GATE-PROSE` contains `[gate process instructions omitted]` and the gate
  marker; the gate prompt says read-only and lists the diff path or inline diff.
- `landing_prompt_without_prose_uses_fragments`; `landing_prompt_with_prose_uses_it`.
- `size_warning_threshold`: a prompt over `promptWarnTokens` yields a warning; the
  diff over the threshold goes to `PROMPTS/<STEP>-<n>.diff`.
- `render_all_covers_every_step_and_gate`: keys for each step, each gate with prose,
  and `LANDING`; no unresolved tokens on the fixture.
- `unknown_token_in_prose_refuses`: `extra_prose` with `{{ project.nope }}` →
  `RenderError` from `assemble`, listed by `render_all`.

## test_schemas.py
- `extract_json_prefers_last_fence_then_last_object`; `no_json_raises`.
- `plan_valid_and_invalid`: missing text, quote ≤ 0, duplicate `n`, one option,
  unknown key → problems list names each; `unanswered` lists numbers;
  `plan_as_text` format.
- `agents_plan_rules`: missing step entry, unknown rung, rung above `maxAgent`,
  work shares ≠ `workFraction`, gate shares > `gatesFraction`, sub-agents over the
  limit → problems; below `defaultShares` → warning only; `rung_for`/`budget_for`
  fall back to config without a plan.
- `spec_rules`: dangling component reference; empty test plan; unknown `kind`.
- `suite_rules`: missing decision names the test; unknown test; bad `where`.
- `postmortem_summary_extraction`: `## Summary` body until the next `##`; `# summary`
  case-insensitive; none → `None`.
- `result_rules`: statuses; NEEDS-OWNER needs a question with two options; BLOCKED
  needs `narrow`; required resolution missing; disputed on settled; disputed without
  note; unknown finding id.
- `findings_rules`: disputed without ruling; blocking without suggestion; ruling on
  unknown id is a warning.
- `describe_mentions_every_field` and `docs/SCHEMAS.md` contains each of them.

## test_state.py / test_history.py
- `new_state_shape_and_roundtrip`: `to_dict`/`from_dict` identity; version mismatch
  raises; bad field raises `STATE_SHAPE`.
- `attempt_numbering_and_open_attempt`; `flags_delivery`; `owner_decisions_since_pause`;
  `finding_ids_unique_and_prefixes`; `covered_checkpoint_uses_approval`;
  `effective_hard_stop_override`; `bump_turn_and_new_run`.
- history: `append_creates_heading_once`; each builder renders its title and bullets;
  `gate` entry truncates finding text to 120 chars.

## test_gitops.py (against a temp origin)
- `push_new_branch_is_cas`: two clones create the same branch; the second push raises
  `FenceError("CLAIM_LOST")`.
- `push_lease_rejects_when_moved`: after `advance_main_elsewhere` on the branch, the
  lease push raises `FENCE`; with the right sha it succeeds.
- `push_to_main_with_lease`; `worktree_add_remove_list`; `status_and_revert_paths`
  (tracked modified, untracked new, deleted, renamed all reverted; unlisted files
  untouched); `merge_clean_and_conflict` (conflicted list, markers detected,
  `commit_merge_resolution` completes, `abort_merge` restores); `ls_tree_sizes`;
  `show_missing_is_none`; `add_and_commit_only_given_paths`; `config_identity_sets_when_missing`;
  `backup_branch`.

## test_ownerlog.py
- `append_and_read_jsonl`; `malformed_lines_skipped_and_counted`; `hook_payload_parsing`
  (missing `prompt` ignored; extra keys ignored); `verify_normalises_whitespace`
  (a quote with different spacing and line breaks verifies; an empty quote never
  does; a quote not present → `None`); `verify_searches_round_slice`;
  `slice_since_and_write_slice`; `hook_script_exit_0_on_garbage` (subprocess with
  bad stdin exits 0, prints nothing to stdout).

## test_judgment_calls.py
- `append_line_format`; `empty_text_refuses`; `unknown_step_refuses`;
  `ingest_from_message_counts`; `read_since_filters_by_timestamp`; `cli_command_text`;
  `jc_subcommand_appends_in_worktree` (via `run.py --root <worktree harness> jc`).

## test_agentdefs.py / test_install.py
- `definitions_per_rung_with_effort_and_gate_twin`: frontmatter `model`, `effort`,
  `name`; the `-gate` file has `tools: Read, Grep, Glob`.
- `settings_merge_keeps_other_keys`; `hook_installed_detection`.
- `staleness_after_subagents_change`: editing `subAgents.yaml` → a message; after
  `install`, none.
- `install_idempotent`: second run reports everything `unchanged`; `CLAUDE.md` never
  overwritten; `.gitignore` lines appended once; first baseline taken with a note.

## test_ledger.py
- `attempt_cost_measured_vs_estimated`: exact arithmetic with the fixture prices
  (cache terms included when measured; `estOutputFraction` when not; spawn cost
  always; driver overhead only when `first_of_step`).
- `file_price_cap_boundary`: `cap` tokens → all at the low rate; `cap + 1` → one token
  at the high rate.
- `living_charge_cases`: grown file (delta tokens × rate); new file (+ base cost);
  removed file (− base cost, − tokens); renamed unchanged file → 0; carry-forward
  file priced at `postMortemFileCostPerToken`; a file outside living paths → 0;
  net negative allowed.
- `archive_charge_with_and_without_summary`; `test_charge_counts_functions_not_files`
  (a moved test → 0; a new test → `testBaseCost`); `elapsed_is_informational`
  (excluded from `total`); `book_round_writes_state_entries`; `project_remaining`.

## test_suite.py
- `tests_in_source_names_and_spans` (decorators included; class-level tests
  qualified); `syntax_error_raises`; `enumerate_round_tests_added_and_changed`
  (unchanged pre-existing tests excluded; whitespace-only edits excluded);
  `apply_moves_functions_to_archive` (archive file has the import block, the
  function; the source file no longer has it; a class-level test becomes a prefixed
  top-level function; an emptied file is deleted); `apply_name_clash_suffix`;
  `count_tests_at_ref`.

## test_findings.py
- `new_findings_get_ids_and_statuses`; `verdict_fail_upgrades_nonblocking`;
  `verdict_pass_downgrades_blocking_to_flags`; `withdrawn_repeat_is_dropped_with_note`
  (same normalised quote; a different quote is not dropped); `upheld_twice_settles`;
  `apply_resolutions_statuses`; `runner_finding_prefix_R`; `close_on_accept`;
  `views_exclude_closed_and_dropped` and mark `needs_resolution`.

## test_checks.py
- `classify_declared_vs_strays` for each scope kind; `spec_file_always_stray`;
  `runner_round_files_always_stray_except_own_result`; `frozen_tests_are_strays`;
  `run_for_attempt_reverts_and_reports` (strays gone from `git status`, accepted
  changes kept, reasons recorded); `validate_artifacts_missing_file_is_problem`.

## test_verify.py
- `collect_mode_ok_and_syntax_error`; `suite_mode_pass_and_fail_tail`; `timeout_marks_timed_out`
  (a test that sleeps with `verifyTimeoutSeconds = 1`); `log_written`;
  `finding_text_has_quote_and_suggestion`; env has `SHACKLES_VERIFY=1`.

## test_doctor.py / test_index.py
- doctor on the fixture: `ok` true, five defaulted-key infos, one prompt per step and
  gate rendered; with a bad token in prose → an error naming token and prompt; with
  drift → error; with stale definitions → error; without the hook → error; without
  `OWNER.log` → warning; `--offline` skips git; exit code 3 with errors.
- index: `collect_covers_expected_files`; `purpose_extraction_per_type`;
  `check_detects_stale_and_missing`; `write_then_check_ok`.

## test_docs.py
- Every `docs/*.md` starts with `# ` and has an `Audience:` line; every registered
  command name appears in `OWNER-GUIDE.md` or `PROCESS.md`; `SCHEMAS.md` names every
  field of `schemas.describe("producer")` and `describe("gate")`.
