# Fix 4: review 4's findings

Fixer: "You are powered by the model named Fable 5.1. The exact model ID is claude-fable-5-1", "running at maximum reasoning effort" (as the system prompt states them). Worked alone in a linked worktree on branch `worktree-agent-a84a12398367390b4`, fast-forwarded to `76fa38d` before reading anything; nothing pushed; no spec file edited; `bootstrap/` untouched but for this file.

## Items

| Item | Status | Commit | Test |
| --- | --- | --- | --- |
| R4-M1 override commits unrecorded work | fixed | `30e4fe9` | `test_outcomes.py::test_override_of_the_pending_step_discards_its_unrecorded_work` (R9a and R9b) |
| R4-M2 override leaves `pending_question` | fixed (the helper also serves the no-ruling branch, see below) | `c1e7b8c` | `test_outcomes.py::test_override_settles_or_drops_the_producers_open_question` (R3 and R3b) |
| R4-M3 scratch fixture asserts True | fixed | `1a6b840` | fixture; `test_checks.py::test_s2_suite_partition`, `::test_m3_verify_red_and_timeout`, `test_probe.py::test_every_defect_fixture_loads` pass unchanged; E1 re-run below |
| R4-m1 "(0 undefined since the last checkpoint)" | fixed | `736112e` | `test_checks.py::test_record_that_raises_a_checkpoint_still_reports_the_attempts_undefined_lines` |
| R4-m2 `record` exit 10 without `undefined_new` | fixed | `736112e` | same test |
| R4-m3 CHAT-TO-PLAN's share in the PLAN-AGENTS prompt | fixed (the prose fix, the smaller) | `028a3a7` | prompt only; the render tests |
| R4-m4 `start --through` without `--delegate` ignored | fixed | `972dce4` | `test_round.py::test_delegation_from_the_plan` (the `through-alone` rows) |
| R4-m5 "already accepted" for a producer whose gate is pending | fixed | `c1e7b8c` | in the R4-M2 test (`r2`) |
| R4-m6 PLAN-AGENTS-GATE's clean seed | fixed (the stub change, the one that keeps the probe honest) | `ef824c8`, `3a3ce76` | `test_round.py::test_full_round_every_gate_enabled` (plan shape) |
| R4-m7 PROCESS.md:35 "a gate runs iff" | fixed | `d9eefb3` | doc only |
| R4-m8 a `review` from `next` | fixed | `d9eefb3` | doc only |
| R4-n1 `record --help` on `--agent` | fixed | `b3a6f96` | none |
| R4-n2 DRIVER.md:12 one sentence short | fixed | `b3a6f96` | `test_round.py::test_start_agent_forces_the_rung_and_tells_the_planner` pins the claim |
| R4-n3 `status` key `branch` | fixed (`round_branch`) | `dddbaf2` | `test_round.py::test_status_spend_and_check_are_read_only` |
| R4-n4 mixed separator in the draft path | fixed (`round.draft_plan`) | `dddbaf2` | `test_round.py::test_render_command_on_a_round_has_no_side_effects` |
| R4-n5 PROCESS.md:84 "the undefined lines added" | fixed | `b3a6f96` | doc only |
| R4-n6 `judgment_calls` counts per run | fixed | `b3a6f96` | prompt only |
| R4-n7 PLAN-AGENTS not told the forced rung | fixed (`round.agent_override`) | `028a3a7` | `test_round.py::test_start_agent_forces_the_rung_and_tells_the_planner` |
| R4-n8 probe repositories lose the owner's comments | fixed | `dddbaf2` | `test_probe.py::test_probe_manual_positions_a_gate_with_a_planted_defect` (comment count, flags) |
| R4-n9 `agents_plan()` after an override | fixed | `c1e7b8c` | in the R4-M2 test (the PLAN-TO-SPEC action names `max` after a plan that said `low`) |
| R4-n10 POSTMORTEM's carry-forward pricing | fixed | `b3a6f96` | prompt only |
| Section 3: `cleanupPaths`, per-test archive unit, `--agent` hint, stronger wrapper, POSTMORTEM close path, budget partition | no change | | the reviewer's verdicts: not to build, or the owner's question |
| Section 4 residuals (R4-n8, R4-m2, R4-n1, R4-m7, R4-m3, R4-m8, R4-n6) | fixed | above | the fifteen fix-3 commits were otherwise found sound; nothing else there |

Where I departed from the letter of a fix, and why:
- R4-M2: `settle_question(who, why)` writes the one undefined line and clears the question; it serves the delegated branch (text unchanged), `skip_gate` and the no-ruling branch as well, so every runner-written "assumed" line has one shape (the no-ruling line now reads `(runner: GATE attempt N gave no ruling; question: Q)`); `skip_producer` clears with a HISTORY line, as asked.
- R4-M1: DRIVER.md got a sentence too (the reviewer named PROCESS.md only), because test D's driver reads DRIVER.md literally and will override a running step.
- R4-m4: the reviewer's message, plus `--through` is applied when a delegated plan makes it acceptable (it replaces the plan's `through`); refusing-but-ignoring was the defect.
- R4-m6: the work shares are weighted, the gates split stays equal (the reviewer's probe budgets, `$5.0` and `$0.9`, stay true); the stub also lists CHAT-TO-PLAN at the minimum its prompt shows, because R4-m3's instruction now asks every planner to, and a seed that ignores its own prompt is not a clean seed.
- R4-n4: `draft_plan` is built once in `prompts.empty_round_context` from `harness_root`, which covers the round, the planning and the fixture (`doctor`) contexts, instead of twice.
- R4-n8: `set_yaml_keys` replacing the whole `gates` block would drop the block's inline comments, the very ones the finding names; scalars (the gate flags, `lostValuePerHour`) are flipped in place by a regex and the other keys go through `set_yaml_keys`.

Spec-file edits: none. `doctor` on the worktree: 0 errors, the two known warnings (owner log missing, `core.longpaths`).

Reproduced on the real prose after the fixes (`probe --manual` under `%TEMP%`): the PLAN-AGENTS-GATE clean seed is rungs by kind with work shares 0.05/0.068/0.204/0.136/0.271/0.068/0.136/0.068 summing to 1 and an equal gates split; the SPEC-TO-TESTS-GATE diff carries `test_shout_scratch` asserting `shout("scratch") == "SCRATCH"`; a FAIL quoting the TESTS-TO-SUITE-GATE fixture scores `verdict_as_expected` and `quote_contains_planted` true.

Suite: `py -3.13 -m pytest` from the repository root, 180 passed (176 before, 4 added), 609.11 s (10 min 9 s), exit 0; `git status --short` afterwards showed only this untracked file, and nothing once it was committed.

## What the docs do not say

- `override` of the step whose attempt is pending reverts every dirty path but STATE, HISTORY and the OWNER.log slice, the result file the driver may already have saved under `RESULTS/` included, and clears `attempt_pending`; HISTORY: `override: unrecorded work of STEP attempt N discarded: <paths>`. The reviewer's "never `next --discard` after an override" is moot: there is nothing left to discard.
- New HISTORY lines: `<PRODUCER>'s question stands on its assumption: <GATE> was skipped` and `<STEP> overridden: its open question is dropped`. New undefined line shape from `skip_gate`: `- <PRODUCER> assumed: <assumption> (runner: <GATE> skipped (override); question: <q>)`; the delegated line is unchanged; the no-ruling line's tail changed as above. `skip_producer` clears the question at the next `next`, not inside the `override` command.
- `override` refusals: `X is already accepted` (its gate passed) and `X already ran; its gate G is pending: override the gate instead` (recorded, unjudged). Overriding the gate accepts the artifact as it is.
- `agents_plan()` returns nothing while PLAN-AGENTS is overridden, whatever the round folder holds.
- `record` exit 10 carries `undefined_new` (all the lines the attempt appended, runner-written ones included) and `finish` prints them; `next`'s and the owner commands' checkpoint payloads do not carry it.
- `status` prints `round_branch` instead of `branch`.
- `start --through STEP` alone: `--through needs --delegate or a delegated plan` (exit 2, before any git command); with a delegated plan it replaces the plan's `through`.
- Prompt context keys: `round.agent_override` (the forced rung or `none`, from `start --agent` or `agentOverride`) and `round.draft_plan` (`os.path.join(harness_root, "DRAFT-PLAN.json")`), both in `prompts.ROUND_KEYS`; the PLAN-AGENTS plumbing prints the forced rung and the minimum shares on their own lines, then says CHAT-TO-PLAN is listed in `shares.work` at its minimum because `start` booked it; `agents` excludes CHAT-TO-PLAN and overridden steps, as S1 checks.
- The stub's plan (`stub_agent.RUNGS`, `WEIGHTS`): `max` for PLAN-TO-SPEC and POSTMORTEM, `medium` for PLAN-AGENTS and TESTS-TO-SUITE, `low` for the code steps unless `STUB_RUNG` is set; work shares weighted 3/2/4/2 for PLAN-TO-SPEC, SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, CLEANUP, 1 otherwise, over 0.95 after CHAT-TO-PLAN's 0.05 (read from the prompt's minimum-shares line); gates equal. Stub-round budgets therefore changed: on a `$100` quote SPEC-TO-IMPLEMENTATION gets `$19.0`, PLAN-TO-SPEC `$14.25`, PLAN-AGENTS `$4.75`; actions after the plan name `low` for the code steps, so `test_probe`'s headless SPEC-TO-IMPLEMENTATION probe runs the stub as `low`.
- `fixtures/canned/test_scratch.py` imports the toy like `test_text.py`; still one `def test_`, still archived by `STUB_ARCHIVE`. `fixtures.py` now imports `shackles.probe` (for `set_yaml_keys`); probe repositories carry the owner's `project.yaml` comments and `lostValuePerHour: 0` flipped in place.
- `producer.txt` asks for `judgment_calls` as counts of the lines appended this run; `POSTMORTEM.txt` says the carry-forward edits are not charged as living tokens.
- For test D: override only names steps not yet accepted; at a `question` checkpoint `override --steps <producer>` resumes and drops the question, `override --steps <gate>` records and the checkpoint stands (`approve` follows, which answers "proceed on your stated assumption"); with the gate on, the question waits at the gate and overriding that gate writes the undefined line.
- For test E: the reviewer's note 2 budgets (`$5.0`, `$0.9`) still hold; a clean seed's PLAN-AGENTS-GATE FAIL now judges the gate, not the fixture.
- For the final test: the attempt entry and the CHECKPOINT entry in HISTORY now agree on the count since the previous checkpoint; a `record` that raises a `question` prints `undefined judgment call:` lines on stderr like exit 0 does.
