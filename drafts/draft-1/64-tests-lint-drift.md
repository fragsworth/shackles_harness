# 64 — harness/tests/lint/ and harness/tests/drift/ (the real spec files vs the code)

Parent: `60-tests.md`. These are the only tests that read the owner's real
files. `lint/` checks that the code and the spec data agree; `drift/` is the
guard the owner asked for: a test that fails whenever a spec file changes,
until the change is reviewed and accepted.

```
harness/tests/lint/
  test_step_table.py        the table vs project.yaml's steps and the real prose files
  test_settings_surface.py  every key is used, no unknown keys, defaulted keys named
  test_prompts_real.py      every real prompt renders with no unresolved token
  test_index.py             INDEX.md covers the tree
  test_docs_contracts.py    CONTRACTS.md names every required field
  test_repo_root.py         CLAUDE.md, .gitignore, hooks, agent definitions
harness/tests/drift/
  test_spec_files_guard.py  hashes vs archives/spec-baseline.yaml, with a diff
```

## lint/test_step_table.py
- `test_every_project_step_is_in_table` — the real `steps` keys equal the
  table's names, same order (order mismatch is a warning in lint but this
  test asserts equality so the owner sees drift in intent).
- `test_gate_switched_on_has_prose` — for every step with value 1 and a
  gate in the table, `<STEP>-GATE.txt` exists.
- `test_every_expected_prose_file_exists_or_is_known_absent` — overview
  files all exist; gate files missing are exactly those the table allows to
  be absent (currently `CHAT-TO-PLAN-GATE`); the test prints the list.
- `test_no_orphan_prose_files` — every `.txt` in `locked_prose/` is an
  expected stem.

## lint/test_settings_surface.py
- `test_no_unknown_keys` — `settings.unknown` is empty for the real file.
- `test_every_key_is_read_somewhere` — after a full `doctor` run on the real
  spec, the `Settings` access tracker (a set of field names read via
  attribute access, recorded by a thin wrapper used only under this test)
  contains every non-defaulted key `[JC-32]`.
- `test_defaulted_keys_are_exactly_the_documented_set` — equals the table
  in `SPEC.md` §7 / `config/project.DEFAULTS`.
- `test_roster_defaults_exist` — `defaultAgent`, `gateAgent`,
  `systemTestAgent`, `maxAgent` are roster keys.
- `test_default_shares_name_table_steps`.

## lint/test_prompts_real.py
- `test_doctor_offline_is_clean` — `doctor --offline` on the real repo:
  no problems (warnings allowed); failure output lists them.
- `test_every_token_in_real_prose_resolves` — scan every real prose file
  and AGENTS.md; each token resolves against a synthetic round.
- `test_real_prompts_under_warning_size` — every rendered real prompt is
  below `promptWarnTokens` (a warning-level assertion: fails to make the
  owner look).

## lint/test_index.py
- `test_index_lists_every_src_module_and_doc` — each `src/shackles/*/*.py`
  (except `__init__.py`), each `docs/*.md`, each `tests/<folder>/` appears in
  `INDEX.md`.
- `test_index_names_only_existing_paths`.

## lint/test_docs_contracts.py
- `test_contracts_md_names_required_fields` — every required field of every
  validator in `round/artifacts.py` and `round/results.py` appears verbatim
  in `docs/CONTRACTS.md`.
- `test_process_md_names_every_verb_and_pause_reason`.

## lint/test_repo_root.py
- `test_claude_md_points_at_agents_md_and_process`,
  `test_gitignore_covers_runtime_files` (the five entries),
  `test_settings_json_has_both_hooks`,
  `test_agent_definitions_match_roster` (`definitions.is_stale` is false
  for the committed files against the real roster).

## drift/test_spec_files_guard.py
- `test_spec_files_match_accepted_baseline` — `compute_drift` on the real
  files against `archives/spec-baseline.yaml`; on drift the assertion
  message is: the changed, added and missing paths, the diff text, and the
  sentence "review the change, then run `python harness/src/run.py
  accept-spec` and commit the baseline".
- `test_baseline_exists` — a missing baseline fails with the same
  instruction (a fresh clone of a repo whose owner never accepted).
- `test_baseline_lists_only_spec_files` — every baseline path is matched by
  a `spec.yaml` pattern (a stale baseline entry for a removed file is drift).
