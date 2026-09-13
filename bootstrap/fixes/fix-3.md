# Fix 3: review 3's findings, the open test-B items and the sandbox builder

Fixer: "You are powered by the model named Fable 5.1. The exact model ID is claude-fable-5-1", "running at maximum reasoning effort" (as the system prompt states them). Worked alone in a linked worktree on branch `worktree-agent-a07b8b4079b1102a3`; nothing pushed; no spec file edited.

## Items

| Item | Status | Commit | Test |
| --- | --- | --- | --- |
| Sandbox and probe builders (SPEC.md missing) | fixed | `7936c64` | `test_probe.py::test_sandbox_of_the_real_repository_passes_spec_status_and_doctor`, `::test_set_yaml_keys_replaces_or_appends_and_keeps_comments`; the two probe tests that failed pass |
| R3-M1 delegate through the producer's name | fixed | `2aea88d` | `test_round.py::test_delegation_from_the_plan` (`through` PLAN-TO-SPEC, PLAN-TO-SPEC-GATE and PLAN-AGENTS) |
| R3-M2 producer edits an earlier artifact | fixed | `366da07` | `test_checks.py::test_m1_reverts_an_edit_of_an_earlier_steps_artifact` (the review's R2 scenario) |
| R3-M3 undefined calls unseen when delegated | fixed | `4c4cf1e` | `test_checks.py::test_record_reports_the_undefined_lines_the_attempt_added` |
| R3-m1 silent rung substitution | fixed | `3c3f077` | `test_round.py::test_record_agent_names_the_rung_that_ran` |
| R3-m2 carried notes look open | fixed | `1849698` | prompt clause only; the render tests show the prompt renders |
| R3-m3 CHAT-TO-PLAN-GATE leaves no trace | fixed | `b8c4433` (sandbox half in `7936c64`) | `test_round.py::test_action_shape_prompt_commit_and_record_command` |
| R3-m4 minimum gate share for CHAT-TO-PLAN | fixed | `9edb5ca` | `test_render.py::test_step_context_minimum_shares_are_filtered_to_the_steps_present` |
| R3-m5 raise_with_owner has no route | fixed (the smaller route) | `403f237` | `test_checks.py::test_raise_with_owner_is_flagged_in_history_and_carried` |
| R3-m6 override at a review | fixed | `1e567e5` | `test_outcomes.py::test_override_at_a_review_checkpoint_stands_until_approve`, `::test_failure_limit_and_approve_resets` |
| R3-m7 record exit 10 wording | fixed | `1e567e5`, `7b45814` | doc only |
| R3-m8 claimed judgment calls ignored | fixed | `adf7bb0` | `test_checks.py::test_claimed_judgment_calls_are_compared_with_the_files` |
| R3-m9 start --delegate without words | fixed | `1ac860a` | `test_round.py::test_start_requires_approval_words_when_the_gate_is_enabled` |
| R3-m10 next lands, annotation appended, done carries calls | fixed | `1e567e5`, `7b45814` (done half in `4c4cf1e`) | doc only |
| R3-n1 double `(via runner)` suffix | fixed | `5acf17a` | `test_checks.py::test_gate_line_already_suffixed_is_not_suffixed_twice` |
| R3-n2 status `worktree` key | fixed (renamed `root`) | `5acf17a` | none (a key rename) |
| R3-n3 spec accept's `commit` | fixed (`head_at_accept`, PROCESS.md) | `5acf17a` | none |
| R3-n4 help text, delegate hint | fixed | `5acf17a` | none |
| R3-n5 CHECKPOINT before the attempt entry | fixed | `5acf17a` | `test_outcomes.py::test_blocked_checkpoint_and_answer`, `test_round.py::test_full_round_every_gate_enabled` |
| R3-n6 gate's retry cost spawnCost | fixed | `5acf17a` | `test_round.py::test_gate_prompt_retry_cost_uses_the_producers_rung` |
| R3-n7 approve at blocked | fixed | `5acf17a` | doc only |
| test-B 5.3 action's `model` is advisory | fixed (one DRIVER.md sentence) | `1e567e5` | none |
| test-B 5.10 prose before the JSON | skipped | | extraction coped every time and every message was valid at attempt 1; a stronger wrapper is a guess with no evidence it lands better |
| test-B 5.14 the ledger pays to archive a test (verdict 3) | no change | | the owner's numbers; no `living_charge` exemption added |
| test-B 5.12 carried findings "cannot be closed" (verdict 2) | no change beyond R3-m2 | | no close path built |

Spec-file edits: none. `doctor` on the worktree: 0 errors.

Suite: `py -3.13 -m pytest` from the repository root, 176 passed (166 before, 10 added), 592.37 s (9 min 52 s), exit 0; `git status --short` empty afterwards (before this report was added).

## What the docs do not say

- Where the probe fix lives: the probe's "real" spec is copied by `fixtures.write_spec(spec="real")`, which `probe.prepare` reaches through `fixtures.Repo`; that is what now copies `spec.yaml` and every listed path. The sandbox does the same on top of its `harness/` copy.
- `probe.set_yaml_keys` replaces a top-level key's block (the key line plus the indented or `- ` lines under it) or appends the key; a column-0 comment inside a key's value would end the block early, a shape the owner's file does not have. The real-repository sandbox test asserts only that the copy has at least as many `#` lines as the source, never on any comment's wording.
- Payload changes a driver or a test must expect: `status` prints `root` instead of `worktree`; `spec accept` prints `head_at_accept` instead of `commit`; `recorded` carries `undefined_new` and `undefined_file`; `checkpoint` and `invalid` payloads carry `warnings`; `attempts` gains a `CHAT-TO-PLAN-GATE` key at the first `next`; `finish` prints `undefined judgment call: <line>` on stderr per new line.
- R3-m3: the mechanical gate's attempt is incremented per pass, not set to 1 as the review wrote, because the gate passes again after an out-of-band plan edit or an UPSTREAM to CHAT-TO-PLAN and attempt numbers never restart.
- R3-M2: `owned_extra` is passed on the UPSTREAM/BLOCKED path as well as on DONE, so the revert rule is the same whatever the status; the M1 finding is blocking, so the producer re-runs (attempt 2) with the finding, as for any stray.
- R3-m4: `minimum_shares.work` keeps CHAT-TO-PLAN (the reviewer's "producers not overridden"; its floor is charged at `start`, and round B's plan honoured it); `minimum_shares.gates` lists only producers whose LLM gate runs, so CHAT-TO-PLAN never appears there.
- R3-m5: a carried flag has `id` `raise_with_owner`, `source` `flag`, the item as `quote`.
- R3-m8: the comparison runs after M4 restored a rewritten file, so an M4 attempt may also show a claims FLAG; both are honest.
- R3-n5: `raise_checkpoint` keeps the CHECKPOINT line and `save()` writes it, which puts it after the attempt entry in `record` and after the INVALID RESULT line in `infra`; every path that raises a checkpoint saves before it commits.
- For test D: "delegate through PLAN-TO-SPEC" and "delegate through PLAN-TO-SPEC-GATE" now skip the same reviews; "delegate through PLAN-AGENTS" skips none.
- For test C: DRIVER.md's loop was re-read sentence by sentence against the code after the edits (`override` never resumes at a review because the review's own step, `PLAN-TO-SPEC-GATE` or `CLEANUP`, is already accepted; `approve` at `question`/`blocked` re-runs the producer with O1; at `infra` it resets the count and `next` reprints the attempt).
