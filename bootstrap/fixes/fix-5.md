# Fix 5: review 5's findings

Fixer: "You are powered by the model named Fable 5.1. The exact model ID is claude-fable-5-1", "running at maximum reasoning effort" (as the system prompt states them). Worked alone in a linked worktree on branch `worktree-agent-aa1d73d99fd6982cd`, fast-forwarded to `da32a79` before reading anything; nothing pushed; no spec file edited; `bootstrap/` untouched but for this file.

## Items

| Item | Status | Commit | Test |
| --- | --- | --- | --- |
| R5-M1 a delegated NEEDS-OWNER with the gate off is settled by the runner | fixed | `3f613d7` | `test_outcomes.py::test_needs_owner_with_the_gate_disabled` (the delegated half: exit 10 `question`, `answer`, O1 at attempt 2) |
| R5-M2 a refused owner command leaves HISTORY and the OWNER.log slice dirty | fixed | `ecc46b2` | `test_outcomes.py::test_a_refused_owner_command_leaves_no_trace` (R8b, then R8a) |
| R5-M3 override of another step sweeps the pending attempt's work in unchecked | fixed | `a62ca94` | `test_outcomes.py::test_override_of_another_step_is_refused_while_an_attempt_has_unrecorded_work` (R1) |
| R5-M4 `probe --check` scores one substring | fixed | `ada60d6` | `test_probe.py::test_probe_check_scores_any_listed_anchor_and_finds_its_folder`, `::test_every_defect_fixture_loads` (anchor shapes) |
| R5-m1 UPSTREAM to an overridden producer loops | fixed | `b887f2a` | `test_outcomes.py::test_overridden_spec_to_tests_hands_the_tests_to_the_implementation` (R2) |
| R5-m2 an overridden SPEC-TO-TESTS leaves no step able to write the tests | fixed | `b887f2a` | same test; `test_render.py::test_step_context_write_paths_and_inputs` |
| R5-m3 the review sentence tests the flat `delegated` | fixed (`delegated()` removed, no caller left) | `762f2c3` | `test_round.py::test_full_round_every_gate_disabled_and_delegation` (the `through` round's CLEANUP and PLAN-TO-SPEC prompts) |
| R5-m4 `override` missing from the `question` resume list | fixed | `3f613d7` | in the R5-M1 test |
| R5-m5 `status` without `overrides` and `approval` | fixed | `762f2c3` | `test_round.py::test_overrides` |
| R5-m6 `start --delegate` stamped `source: plan` | fixed | `762f2c3` | `test_round.py::test_full_round_every_gate_disabled_and_delegation`, `::test_delegation_from_the_plan` |
| R5-m7 `resumed` payload without `warnings` | fixed | `ecc46b2` | in the R5-M2 test |
| R5-m8 `probe --check` without `--dir` and a reused `--dir` crash | fixed | `ada60d6` | in the R5-M4 test |
| R5-m9 the clean PLAN-TO-SPEC-GATE seed is thin | fixed (fixture only; the stub's `testPlan` line matches) | `7e963bb` | fixture; `test_probe.py::test_probe_manual_positions_a_gate_with_a_planted_defect` still finds only "dashboard" |
| R5-n1 one OWNER.log line per command, untagged | fixed | `708b0e8` | `test_owner.py::test_round_slice_and_driver_lines` |
| R5-n2 the delegated review-skip line lands above the attempt entry | fixed (the doc sentence, the smaller of the two offered) | `762f2c3` | doc only |
| R5-n3 `status.step` versus `checkpoint.step` | fixed | `762f2c3` | doc only |
| R5-n4 DRIVER.md:37 at a `failure-limit` with only the gate overridden | fixed (the sentence went in with R5-M1's DRIVER.md edit; that subject omits the id) | `3f613d7` | doc only |
| R5-n5 `probe --seed defect` on a producer is silently clean | fixed (refused) | `ada60d6` | in the R5-M4 test |
| R5-n6 TESTING.md:30's synopsis | fixed | `ada60d6` | doc only |
| R5-n7 POSTMORTEM's trace to plans older than the archive | fixed (plumbing clause) | `708b0e8` | prompt only; the render tests |
| Section 3: `retry_cost` from spend, a coverage line, undefined calls on skip lines, OWNER.log dedupe, reordering TESTS-TO-SUITE, a fuller pre-landing review, `through` at settlement, budget over the remaining quote | no change | | the reviewer's verdicts: not to build |
| Section 4: the fix-4 commits | no change beyond the residuals above (R5-M3, R5-M2, R5-m6, R5-m4) | | found sound |

Where I departed from the letter of a fix, and why:
- R5-M3: the unrecorded work is read through `snapshot()` (the same reader `record` uses), so on a merge attempt only what differs from the automerge tree counts, never the sibling's merged files; the message names "or override STEP to discard it" only when STEP is overridable.
- R5-m1: the finding text is generic ("UPSTREAM names X, which is overridden this round"; "fix it under your own WRITE_PATHS, or return BLOCKED") because any overridden producer can be the target, not only SPEC-TO-TESTS.
- R5-M1: PROCESS.md:83 says "the gate not running" rather than "the gate disabled": the code raises the question whenever `gate_runs` is false (disabled, overridden, or no prose).
- R5-m8: a `--dir` given without a `probe.json` is refused too, and the reused-folder check runs after `os.makedirs`, so a fresh `--dir` is still created.
- R5-n2: the doc sentence, not the buffer: a buffered line would also have to survive `raise_checkpoint` overwriting `checkpoint_entry` later in the same `next`, a list rather than a slot.
- R5-m9: the test plan disposes of the edge cases as Python's own `str.lower` behaviour so the canned `test_text.py` (two tests) stays complete against it; no new test in the fixture, so no living-charge or SPEC-TO-TESTS-GATE seed change.

Spec-file edits: none. `doctor` on the worktree: 0 errors, the two known warnings (owner log missing, `core.longpaths`), every prompt renders with no unresolved token.

Suite: `py -3.13 -m pytest` from the repository root, 184 passed (180 before, 4 added), 586.9 s (9 min 47 s), exit 0; `git status --short` empty afterwards (before this report was added).

## What the docs do not say

- A NEEDS-OWNER whose gate does not run raises `question` from `record` (exit 10) in every mode; the HISTORY line `NEEDS-OWNER proceeds on the stated assumption (delegated)` and the undefined line `(runner: gate disabled, delegated; ...)` no longer exist. `settle_question` still writes its line for a gate skipped by `override` and for a gate verdict without a ruling.
- At a `question`, `override --steps <producer>` resumes only for an overridable producer (PLAN-AGENTS, SPEC-TO-TESTS, TESTS-TO-SUITE, CLEANUP, POSTMORTEM) and `next` then drops the question; naming its gate instead keeps the checkpoint (exit 10, the note under `warnings`) and `approve` re-runs the producer with O1 "proceed on your stated assumption", its gate skipped with `source: override`; PLAN-TO-SPEC and SPEC-TO-IMPLEMENTATION are refused (`cannot be overridden`, exit 2).
- A refused owner command (exit 2) now leaves the tree exactly as it was: no slice line, no `RESUME` entry, no FLAG, nothing saved; the refusal messages are unchanged. A `resumed` payload has `warnings` (in a sandbox: `override: quote recorded unverified (no owner log)`).
- New refusal: `STEP attempt N has unrecorded work (<repo-relative paths>): record it first[, or override STEP to discard it]` (exit 2) for an override that does not name the pending step; a result file the driver already saved under `RESULTS/` counts as unrecorded work.
- `expect.json`'s `quote_contains` is now a list for five gates: PLAN-AGENTS-GATE `["0.9", "0.01"]`, SPEC-TO-TESTS-GATE `["shout", "whisper"]`, SPEC-TO-IMPLEMENTATION-GATE `["yell", "_CACHE"]`, TESTS-TO-SUITE-GATE `["test_text.py", "regression test"]`, POSTMORTEM-GATE `["budget", "nothing to change"]`; PLAN-TO-SPEC-GATE keeps `"dashboard"`. `quote_contains_planted` is true when any anchor is a substring of the findings' quotes joined by spaces.
- `probe --check RESULT_FILE` finds the probe folder by walking up from the result file to the first `probe.json` (the result file lives under `<dir>/repo/...`, so `--dir` is optional); `--check` with no such folder, or `--dir` without `probe.json`, exits 2; `probe --step ... --dir D` with `D/repo` present exits 2 (`already holds a probe repository`); `--seed defect` with a producer step exits 2 before anything is built.
- UPSTREAM naming an overridden producer: `FINDINGS/<STEP>-<n>.mechanical.json` with one `S1` (reason `UPSTREAM names X, which is overridden this round`), `failures[STEP]` +1, `limit_check`, `round_retries` unchanged, no `U1`; the attempt's in-scope work is committed with the record as on any UPSTREAM.
- With SPEC-TO-TESTS overridden, SPEC-TO-IMPLEMENTATION's `WRITE_PATHS` are `implPaths + testPaths + conflicts + folder`; its gate's DIFF_FILE covers the tests; TESTS-TO-SUITE's changed list includes them (S2 wants each in `keep` or `archive`); CLEANUP's paths are unchanged (living paths minus `testPaths`). The plumbing clause ("When SPEC-TO-TESTS was overridden, ...") appears in every SPEC-TO-IMPLEMENTATION prompt.
- The producer plumbing's "after a review checkpoint with the owner" now follows `through` (the producer and its gate anchor alike; CLEANUP anchors on itself).
- `status` gains `overrides` (list) and `approval` (object or null). `approval.source` is `cli` for `start --delegate` or `--through`, `plan` for a plan approval, `gate-disabled` when the plan has none, `driver` after a checkpoint `approve`/`delegate`; HISTORY's CHAT-TO-PLAN-GATE line prints it.
- The OWNER.log slice line is `<ts>\t[via driver: <command>]\t<quote>` (or `[via driver: <command>, unverified]`).
- For test E: the probe budgets (`$5.0`, `$0.9` on the fixture quote) are unchanged; a clean PLAN-TO-SPEC-GATE seed now holds a two-sentence test plan and the defect seed's last line is the dashboard sentence; score a FAIL by its listed anchors; never override a gate while its producer's files are on disk unrecorded (refused: `record` first, then override between `record` and `next`); a refused command costs nothing now.
- For the final test: a fabricated undefined judgment call is surfaced as before (`undefined_new` at `record`, exit 0 or 10, the claims FLAG, `status`, checkpoint messages, `done`); a delegated producer's NEEDS-OWNER with the gate off now stops at `question` whose message carries `Question: <q> (assumption: <a>)` and a resume list with `answer`, `approve`, `override`, `abandon`; the prompt told the producer "the round pauses for the owner; their answer returns to you as a finding".
