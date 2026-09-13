# Review 5 (after fix 4 and test D)

Reviewer: model `claude-fable-5-1` (Fable 5.1), effort `max`, as stated by the system prompt. Read-only review of `e150b52` (`bootstrap: test D report (delegate through, overrides of steps and gates)`) in a linked git worktree fast-forwarded from `4708527` to `claude/bootstrap` before anything was read; no sub-agents, no servers, no browsers, no screen. Nothing tracked was modified; every reproduction ran on throwaway repositories under `%TEMP%` built with `harness/tests/fixtures.py` or by `run.py probe --dir` (the three scripts are not part of the repository). This review builds on `review-3.md` and `review-4.md` and repeats neither "verified sound" list.

## 1. Process

Drafted after reading only the four entry points (`CLAUDE.md`, `README.md`, `harness/AGENTS.md`, `harness/INDEX.md`) and before opening anything else; followed in this order.

1. Sync: `git merge --ff-only claude/bootstrap`; HEAD must be `e150b52`. (Done: `4708527..e150b52` fast-forward, one file, `bootstrap/tests/test-D.md`.)
2. The owner's files first, so that everything after is judged against them: `SPEC.md`, `spec.yaml`, `harness/project.yaml`, `harness/subAgents.yaml`, `harness/locked_prose/*.txt`. Note every sentence that a runner behavior or a test could depend on.
3. The review chain in order: review 3 (severity definitions, its verified-sound list, not to be repeated), review 4 (findings, verdicts, notes for the next runs), then `fix-4.md` and the twelve commits `30e4fe9..4708527` one diff at a time. Build a table: review-4 finding -> fix-4 claim -> commit -> what the code now does, and check each claim against the code, not against the fix note.
4. `test-D.md` in full (section 1, then 3 to 8, then 11), then `test-C.md`, `test-B.md`, `test-A.md` where D refers back to them. Build a table of D's six "broke" items and its one-line doc items with a verdict slot each, and a slot for the two undefined judgment calls the producers logged about the overridden SPEC-TO-TESTS.
5. The docs as the driver will read them, literally: `DRIVER.md`, `TESTING.md`, `PROCESS.md`, `CLARIFICATIONS.md`, `TODO.md`. List every claim that names a command, a checkpoint kind, an exit code, a file, or a behavior, to be checked against the code in step 6.
6. The runner, whole: `run.py`, `cli.py`, `commands.py`, `round.py` (the state machine: delegation, checkpoints, overrides, failure routing), `pipeline.py`, `checks.py`, `probe.py`, `prompts.py`, `render.py`, `schemas.py`, `config.py`, `ledger.py`, `landing.py`, `gitops.py`, `procs.py`, `agents.py`, `agentdefs.py`, `owner.py`, `doctor.py`, `specguard.py`, `contract.py`, `plumbing/*.txt`. Read round.py against the doc claims from step 5 and the owner's sentences from step 2.
7. The tests, whole: `fixtures.py`, `stub_agent.py`, `conftest.py`, every `test_*.py`, the six defect fixtures and their `expect.json`, the canned and toy fixtures. For each path in steps 8 and 9, name the test that covers it or say none does.
8. Test E's path, end to end, as the driver and the agents will read it and then as the code runs it: `probe --step <GATE> --seed clean|defect --manual --dir`, the probe builder, the six fixtures and `expect.json`, `--check` scoring; then a sandbox round with gates on: a gate FAIL, the producer re-run with the findings, the gate again with the resolutions and the cumulative diff it sees, `maxFailuresBeforeStop`. Reproduce on throwaway repositories under `%TEMP%` with the project's own fixtures (`write_spec`, `Repo`, `play`) and `run.py probe --dir` / `run.py sandbox --dir`. No review follows test E, so anything on this path is a major at least.
9. The final test's path: an undefined judgment call logged by a producer -> `UNDEFINED_JUDGMENT_CALLS.md` -> what `record` prints, what the checkpoint message says, what `status` shows, what `done` shows. And the delegated-question path: a producer in a delegated round returning NEEDS-OWNER -> the `question` checkpoint -> `override` or `answer` resuming it. Adjudicate the runner (`delegated()`), PROCESS.md lines 87 and 90, and the owner's sentence in `SPEC.md` against each other.
10. Run the full suite once (`py -3.13 -m pytest`) and `doctor` once; record both.
11. Write up: findings by severity with review 3's definitions, each with a reproduction transcript or a `file:line` citation and a fix sized in lines naming file and function; verdicts on test D's items; the post-review-4 fixes checked; verified and found sound (new only); brittleness to the owner's prose or config (new or sharpened rows only); notes for test E and the final test. Prefer fixes that remove or simplify; say which postmortem or test-report suggestions should not be built.
12. `git status --short` must show only this file; commit it alone with the required subject and trailer; do not push.

Severity, transcribed from review 3 and applied unchanged: **blocker** = the next phase cannot succeed or would draw a false conclusion with no workaround; **major** = a real defect that costs an agent run, corrupts round records or misleads the driver, with a workaround; **minor** = wrong but cheap; **nit** = cleanliness. A defect on test E's or the final test's path is a major at least, as the assignment says.

Deviations from the draft: the suite (step 10) was started in the background while the tests of step 7 were being read, and finished before step 8's reproductions began; test-C, -B and -A were grepped for the delegated-question history rather than re-read whole (test C's NEEDS-OWNER round was approved, not delegated; A and B had no NEEDS-OWNER); the plans (`merged-B.md` decision 17, `plan-6.md` 11.2) were read for the origin of the rule step 9 adjudicates, which the draft did not foresee. Nothing else deviated. Seventeen reproductions ran (`R1` to `R9`, `E1` to `E3`, `F1`, and the sub-cases below): eleven confirmed a defect or a gap, six confirmed a path sound.

Counts: 0 blocker, 4 major, 9 minor, 7 nit.

## 2. Findings

### Major

**R5-M1 (major) A NEEDS-OWNER with its gate off in a delegated round is settled by the runner instead of raising the `question` checkpoint; the owner's `SPEC.md` says questions still stop a delegated round, and PROCESS.md line 90 and the plumbing describe the deviation, not the spec.**
`record_producer` (`round.py:1022-1032`): with the gate not running, `if self.delegated(): self.settle_question(...)` writes one undefined line and continues as DONE; only the `else` raises `question`. The owner's `SPEC.md:13`: "Delegation skips only review checkpoints; questions, blocks, limits and spec edits still stop the round." The runner already honours that sentence for the other three: `blocked` (`round.py:1116-1121`, `test_blocked_checkpoint_and_answer` runs `--delegate`), `failure-limit`, `round-limit` and `hard-stop` (`limit_check`, `mechanical_loop`, `next`: no delegation test at all), `spec-edit` (`test_in_round_spec_edit_is_flagged_and_checkpointed_even_when_delegated`). The question is the one exception, and it is the one the owner's own words in test D reserved ("must stop and ask me - finish with NEEDS-OWNER, do not pick") and then found decided ("I reserved that ending and was never asked"). Where the rule came from: `merged-B.md:32` decision 17 (plan 3), adopted by FINAL-PLAN amendment 10 on 2026-09-13 00:18; the owner's sentence was committed at 07:48 the same day (`2db4ecf`), after the implementation milestones, into a file whose header says the listed files "say what the harness must do". PROCESS.md:87 and DRIVER.md:20 already state the owner's rule; PROCESS.md:83 ("or the gate disabled and not delegated") and :90 (first clause), `prompts.py:185` (the producer is told "the round proceeds on your stated assumption, logged as an undefined judgment call") and the delegated half of `test_needs_owner_with_the_gate_disabled` (`test_outcomes.py:130-136`) pin the deviation. With the gate on, the gate weighs the question (COMMON-GATE) and `needs_owner.upheld` raises the checkpoint whatever the mode (`round.py:1153-1157`), so that half already agrees with the owner.
Reproduced (R4, fixture, `start --delegate --through PLAN-TO-SPEC-GATE`, PLAN-AGENTS NEEDS-OWNER, gate off):
```
record exit 0 kind recorded next_step PLAN-AGENTS-GATE | undefined_new: ['- PLAN-AGENTS attempt 1 assumed: STUB-ASSUMPTION: lowercase (runner: g...']
prompt told the producer: NEEDS-OWNER -> the round proceeds on your stated assumption, logged as an undefined judgment call.
```
and approved, gate off: `record exit 10 checkpoint question`. Test D round 0002 is the same on real agents (§3.2 #12, §7.1).
Verdict: the owner's sentence is right, PROCESS.md:87 and DRIVER.md:20 are right, the runner and PROCESS.md:83/:90 are wrong. Delegation is "approval without reviews"; a NEEDS-OWNER is the producer's judgment that the owner's time is worth spending (COMMON-OVERVIEW), and with the gate off nobody weighs that judgment: the runner overruling it silently is what test D shows. The driver's item 2 (`through` honoured for reviews, ignored for questions) is a symptom and disappears with the branch: the owner's sentence attaches no `through` to questions.
Fix (removes code; about 12 lines in all): in `record_producer` delete the `if self.delegated():` branch (`round.py:1027-1030`) and keep the `raise_checkpoint("question", ...)` unconditionally when the gate does not run; `settle_question` keeps its two other callers (`skip_gate`, the no-ruling branch). In `prompts.step_context` drop the delegated variant of `after_needs_owner` (`prompts.py:185-186`, one string); the `delegated` parameter then serves only the review sentence (R5-m3 fixes that reader). PROCESS.md:83 -> "`question` (NEEDS-OWNER upheld, or the gate disabled)"; PROCESS.md:90 -> drop its first clause. In `test_needs_owner_with_the_gate_disabled` the delegated half expects exit 10 `question` and resumes with `answer --text`, then attempt 2 carries O1. Cost note for the owner: `approve` at a `question` re-runs the producer with "proceed on your stated assumption" as O1 (R3-m7, routing, unchanged); a delegating owner who wants the assumption kept as built pays one producer run for it, or answers with `override` where the step is overridable. Not a defect, said in the final-test notes.

**R5-M2 (major) A refused owner command leaves HISTORY.md and the OWNER.log slice dirty: the next `next` counts an infrastructure error and resets them, and a pending attempt's `record` is rejected with a blocking M1 on the runner's own files.**
`owner_command` (`round.py:1181-1216`) appends the quote to the round's OWNER.log (`:1192`), a FLAG when unverified (`:1194`) and the `RESUME ... quote:` line (`:1195`) before dispatching, and every refusal raised after that leaves the tree without `save()` or `commit()`: `override`'s three (`cannot be overridden`, `is already accepted`, `already ran; its gate ... is pending: override the gate instead`, `round.py:1279-1285`), `answer`'s (`does not apply at`, `:1260-1261`), `approve`'s two at `upstream-plan` (`:1234-1238`) and `abandon`'s (`the round already landed`, `:1300-1301`). HISTORY.md and OWNER.log are runner-owned (`checks.RUNNER_OWNED`, `checks.py:7`), so what follows is never benign. Reproduced:
- R8a (between `record` and `next`, `override --steps PLAN-AGENTS` on an accepted step):
```
override exit 2 error: PLAN-AGENTS is already accepted
dirty after the refusal: ['M harness/archives/rounds/0001/HISTORY.md', '?? harness/archives/rounds/0001/OWNER.log']
next --discard exit 0 kind producer | infra_errors: {'PLAN-TO-SPEC': 1}
HISTORY: ['dirty tree reset under harness, src, tests, harness/docs: harness/archives/r...']
```
  (without `--discard`, a `next` while any attempt is pending refuses with "uncommitted work for STEP: record it, or next --discard", because the round folder is inside every attempt's write paths).
- R8b (PLAN-AGENTS attempt 1 pending with its honest AGENTS-PLAN.json written, `override --steps LANDING`, then the driver records the attempt):
```
override exit 2 error: LANDING cannot be overridden | dirty: ['M .../HISTORY.md', '?? .../AGENTS-PLAN.json', '?? .../OWNER.log']
record exit 0 next_step PLAN-AGENTS | failures: {'PLAN-AGENTS': 1}
mechanical findings: [('M1', 'harness/archives/rounds/0001/HISTORY.md ; harness/archives/rounds/0001/OWNER.log')]
```
  The attempt is rejected on files the agent never touched and runs again: one paid run lost. R4-m5's new message ("override the gate instead") invites exactly the sequence refusal-then-retry, and test E's driver will meet a refusal at the failure-limit sooner or later; test D's driver happened never to be refused.
Fix (four lines in `owner_command`, one test): wrap the dispatch (`round.py:1196-1211`) in `try/except RunnerError`, and on a refusal revert the two files before re-raising: `keep = {self.repo_rel(self.paths[k]) for k in ("history", "ownerLog")}; checks.revert(self.root, [(xy, p) for xy, p in checks.dirty(self.root) if p in keep])` (the slice may be untracked on its first line, which `revert` handles). Pin R8b in `test_outcomes.py`: a refused override, then `record` of the pending attempt is accepted with no M1 and no `RESUME` line. Alternative, not preferred: move the appends after the dispatch, which spreads the validation of four commands.

**R5-M3 (major) `override` of any other step while an attempt is pending commits that attempt's unrecorded work through the owner command's commit, unchecked; R4-M1 covered only the pending step itself.**
`override()` (`round.py:1288-1295`) discards the pending attempt's work only when the pending step is among the overrides; otherwise `owner_command` reaches `self.commit("override at active")` (`:1213`), which is `git add -A` (`:160`). At the attempt's `record`, `runner_head()` is that override commit, HEAD has not moved, the `snapshot` is empty, and M1, M2, M3 never see what was swept in. Reproduced (R1, PLAN-AGENTS pending, the stub has written AGENTS-PLAN.json and a stray at the repo root, `override --steps TESTS-TO-SUITE`):
```
dirty before override: ['?? harness/archives/rounds/0001/AGENTS-PLAN.json', '?? stray.txt']
override exit 0 kind resumed | dirty after: []
last commit: round 0001: override at active | files in it: AGENTS-PLAN.json | 27 +, HISTORY.md, OWNER.log, STATE.json, stray.txt | 1 +
record exit 0 next_step PLAN-AGENTS-GATE warnings []
M1 in HISTORY: False | stray.txt tracked: stray.txt
round: done finished | stray.txt on the landed tree: True
```
R4-M1's own scenario (R9b) lands a stray the same way when the override names a different step. Workaround, as DRIVER.md:41 already hints: override only between `record` and `next`, which test D's driver did (§7.11). Test E's driver may override a later gate while a producer runs.
Fix (three lines in `override()`, no new rule for agents): after the validation loop, when `pending` exists and `pending["step"]` is not in the overrides, `dirty = checks.dirty(self.root, exclude=keep)` (the same `keep` as the discard branch) and, if non-empty, `raise RunnerError(f"{pending['step']} attempt {pending['attempt']} has unrecorded work ({paths}): record it first, or override {pending['step']} to discard it", 2)`; with R5-M2 in place the refusal is clean. DRIVER.md:41: "...; overriding any other step while an attempt has unrecorded work is refused: `record` first." Pin R1. Do not make `commit()` selective (review 4's reasoning stands) and do not defer the commit: an unsaved STATE with dirty HISTORY is exactly R5-M2.

**R5-M4 (major) `probe --check` scores the planted quote with one substring, and for five of the six fixtures a right FAIL that quotes the other half of the plant scores `quote_contains_planted: false`.**
`probe.score` (`probe.py:96-97`): `expect["quote_contains"] in " ".join(quotes)`. The anchors: SPEC-TO-TESTS-GATE `"shout"`, while the gate prose ("For each component of the spec: Is it not covered by tests? Fail.") points the gate at the spec's component, `Add \`whisper(text)\`...`, which holds no "shout"; POSTMORTEM-GATE `"budget"`, while the planted file's second line, "Decision: it was probably fine, nothing to change.", is what "Is the decision not sensible? Fail." judges; SPEC-TO-IMPLEMENTATION-GATE `"yell"` while the plant also adds `_CACHE`; TESTS-TO-SUITE-GATE `"test_text.py"` while the planted `notes` say "archive the regression test of whisper and shout"; PLAN-AGENTS-GATE `"0.9"` while the plant's other half is `"SPEC-TO-IMPLEMENTATION": 0.01`. Only PLAN-TO-SPEC-GATE's `"dashboard"` is the whole plant. Reproduced on the real prose (E3, SPEC-TO-TESTS-GATE defect seed, three FAILs that differ only in the quote):
```
quote 'def test_shout_again(self):'                     -> verdict_as_expected True quote_contains_planted True
quote 'Add `whisper(text)` to `src/toy/text.py`: it '   -> verdict_as_expected True quote_contains_planted False
quote 'The tests under `tests/toy/` cover both funct'   -> verdict_as_expected True quote_contains_planted False
```
No review follows test E, so a false `quote_contains_planted` on a correct FAIL would be read as a gate that failed for the wrong reason. E1 confirms every alternative anchor below is in the text the gate sees (the artifact, or the DIFF_FILE for the code gates).
Fix (two lines in `probe.score`, five `expect.json` edits, no test change needed): let `quote_contains` be a string or a list and match if any anchor is in the quotes (`anchors = [a] if isinstance(a, str) else a; card[...] = any(x in quotes for x in anchors) if anchors else None`); list both halves: PLAN-AGENTS-GATE `["0.9", "0.01"]`, SPEC-TO-TESTS-GATE `["shout", "whisper"]`, SPEC-TO-IMPLEMENTATION-GATE `["yell", "_CACHE"]`, TESTS-TO-SUITE-GATE `["test_text.py", "regression test"]`, POSTMORTEM-GATE `["budget", "nothing to change"]`. `test_every_defect_fixture_loads` asserts only that the key is truthy and stays green; TESTING.md:31 gains "(any of the listed anchors)".

### Minor

**R5-m1 (minor) UPSTREAM to an overridden producer loops: the target is skipped again, the U1 finding is orphaned, the source step re-runs with the same prompt and no finding, and `round_retries` burn to `round-limit`.**
`upstream()` (`round.py:1095-1114`) checks only that the target is an earlier producer; `mechanical_loop` then `skip_producer`s it. Reproduced (R2, plan overrides `SPEC-TO-TESTS`, SPEC-TO-IMPLEMENTATION returns UPSTREAM to it):
```
UPSTREAM #1: step SPEC-TO-TESTS; round_retries 1; U1 entries {'U1': ('SPEC-TO-TESTS', 'open')}
   next -> SPEC-TO-IMPLEMENTATION attempt 2; findings line: ... fix it): none
UPSTREAM #2: round_retries 2; U1 entries {'U1': ('SPEC-TO-TESTS', 'reset'), 'U1#2': ('SPEC-TO-TESTS', 'open')}
UPSTREAM #3 -> next: 10 checkpoint round-limit round_retries 3
```
Two paid runs and the round's re-entry allowance, for nothing. Test D's SPEC-TO-IMPLEMENTATION read the plumbing's "a wrong test is UPSTREAM to SPEC-TO-TESTS" against its overridden target and chose not to (§7.9); a cheaper agent follows the sentence.
Fix (two lines in `upstream()`): when `target in st["overrides"]`, take the existing unknown-target path with the finding text "UPSTREAM names SPEC-TO-TESTS, which is overridden this round: its paths are yours (R5-m2), fix it here or return BLOCKED"; no re-entry, no orphaned U1. Pin R2.

**R5-m2 (minor) Overriding SPEC-TO-TESTS leaves no step able to write the round's tests before CLEANUP: SPEC-TO-IMPLEMENTATION's WRITE_PATHS are `implPaths` only, the tests are unfrozen, and the plumbing still routes a wrong test UPSTREAM to the overridden step.** (test D §7.8, §7.9, three undefined calls, two `raise_with_owner` flags)
`prompts.step_context` (`prompts.py:144`): `"implPaths": impl + list(conflicts) + [folder]`; `accept_producer` freezes nothing for an overridden SPEC-TO-TESTS (`round.py:686-688`, PROCESS.md:38), so M2 is inert, but M1 reverts a test written by SPEC-TO-IMPLEMENTATION as a stray; `SPEC-TO-IMPLEMENTATION.txt:1` says "The tests under FROZEN_PATHS are frozen ... a wrong test is UPSTREAM to SPEC-TO-TESTS" beside `FROZEN_PATHS: []` (R2's prompt above). The round landed green only because CLEANUP's paths happen to cover `../tests/` (the living paths minus the frozen tests, `prompts.py:145`).
Verdict on the two undefined calls the producers logged: both correct and the expected outcome. "Who writes the test" was undefined because the harness gave the override no route; "until the frozen tests pass" is the owner's sentence in SPEC-TO-IMPLEMENTATION-OVERVIEW and, with nothing frozen, `FROZEN_PATHS: []` is the truthful plumbing; M3 (`SPEC.verify`) still runs, so "the tests" are whatever verify runs. Nothing in the prose needs a word.
Fix (one line of code, two clauses of text): `"implPaths": impl + (tests if "SPEC-TO-TESTS" in overrides else []) + list(conflicts) + [folder]` in `prompts.step_context` (the `overrides` parameter is already there); `SPEC-TO-IMPLEMENTATION.txt`: "When SPEC-TO-TESTS was overridden, FROZEN_PATHS is empty and testPaths are in WRITE_PATHS: write the tests the spec's test plan names."; PROCESS.md:38: "SPEC-TO-TESTS (nothing frozen; SPEC-TO-IMPLEMENTATION writes under testPaths too)". TESTS-TO-SUITE then sees the changed test file and sorts it (`changed_tests` is from `base_commit`), which closes test D's second flag; the gate's DIFF_FILE for SPEC-TO-IMPLEMENTATION-GATE is the diff of the write paths, so it judges the tests too. Not to build: reordering TESTS-TO-SUITE after CLEANUP (POSTMORTEM 0002 issue 4), or refusing the override.

**R5-m3 (minor) The plumbing's review sentence tests the flat `delegated`, so in a `delegate through STEP` round every later producer is told the round advances without a review, and the CLEANUP review then fires.**
`prompts.py:178` (`... and not delegated`), fed `self.delegated()` at `round.py:342`. Reproduced (R3, `start --delegate --through PLAN-TO-SPEC`):
```
CLEANUP prompt says: DONE -> the mechanical checks; a clean DONE is accepted and the round advances to LANDING.
record exit 10 checkpoint review at CLEANUP
```
Test D round 0001 (§3.1 #33) ran exactly this. The PLAN-TO-SPEC prompt in the same round is right (its review is inside `through`).
Fix (one token): `delegated=self.delegated_through(name)` at `round.py:342`; the anchor rule (`round.py:223`) gives the same answer for a producer and its gate, and CLEANUP anchors on itself. After R5-M1 nothing else reads the flag.

**R5-m4 (minor) The `question` checkpoint's resume list omits `override`, which the runner accepts there and the final test will use.**
`RESUME["question"]` (`round.py:18`) lists `answer`, `approve`, `abandon`; `owner_command` accepts `override` at any status, and at a question of an overridable producer it resumes and drops the question (fix-4 documents it). Reproduced (R4, approved, gate off): `resume list names override? False`, then `override --steps PLAN-AGENTS ... exit 0 kind resumed status active`, HISTORY `PLAN-AGENTS overridden: its open question is dropped`. DRIVER.md:39 tells the driver the commands are the ones listed in the message.
Fix (one line): add `"override"` to `RESUME["question"]`; for PLAN-TO-SPEC and SPEC-TO-IMPLEMENTATION it is refused as "cannot be overridden", which is right.

**R5-m5 (minor) `status` shows neither `overrides` nor `approval`.** (test D §7.3)
`status_payload` (`round.py:1339-1343`). Reproduced (R7): after an override the keys are `attempt_pending, attempts, checkpoint, failures, hard_stop, judgment_calls, living_preview_usd, root, round, round_branch, round_retries, spec_edits, spend, status, step, undefined_file, undefined_tail`. One line: `"overrides": st["overrides"], "approval": st.get("approval")`.

**R5-m6 (minor) `start --delegate [--through STEP]` over an approved plan stamps `approval.source: "plan"`, and HISTORY says the delegation came "from plan".** (test D §7.4)
`start` (`round.py:1420-1422`): `approval.update({"mode": "delegated", ...})` then `setdefault("source", "plan")`. Reproduced (R6): `{'mode': 'delegated', 'words': 'approve', 'through': 'PLAN-TO-SPEC-GATE', 'source': 'plan'}`. One line: include `"source": "cli"` in that `update` (the checkpoint `delegate` command already stamps `driver`).

**R5-m7 (minor) `override` and `abandon` outside a checkpoint return no `warnings`; the unverified-quote FLAG reaches a JSON-only driver on one path and not the other.** (test D §7.6)
`owner_command`'s resumed payload (`round.py:1216`) has `kind, round, command, status, step, spend`; the checkpoint payload carries `warnings`. Reproduced (R7): `payload keys ['command', 'kind', 'round', 'spend', 'status', 'step'] | stderr: ['note: override: quote recorded unverified (no owner log)']`. One line: `"warnings": self.notes`.

**R5-m8 (minor) `probe --check RESULT_FILE` without `--dir` crashes with a traceback, and a reused `--dir` crashes with another.**
`probe.cmd` (`probe.py:133-135`) defaults the folder to the result file's own directory, `RESULTS/`, which never holds `probe.json`; `prepare` (`probe.py:46,52`) `copytree`s into `<dir>/repo` without checking. Reproduced (R9, R5):
```
probe --check <RESULTS/...json>            exit 1 | FileNotFoundError: ...\RESULTS\probe.json
probe --check ... --dir <folder>           exit 0 | "verdict_as_expected": true, "quote_contains_planted": true
probe --step ... --dir <folder holding a repo>   exit 1 | FileExistsError: ...\repo
```
Minor rather than major: the documented form (TESTING.md:30, the manual hint) passes `--dir`, and a traceback is not a false conclusion. Fix (three lines in `probe.cmd`, one in `prepare`): walk up from the result file to the first folder holding `probe.json`, else refuse with `RunnerError("--check needs --dir <probe folder>", 2)`; in `prepare`, `if os.path.exists(os.path.join(folder, "repo")): raise RunnerError(f"{folder} already holds a probe repository", 2)` as `sandbox` does.

**R5-m9 (minor) The clean seed of PLAN-TO-SPEC-GATE is three sentences and a four-word test plan; a gate told "Incomplete? Fail." may fail the fixture, not the prose.**
E1 shows the seed: `fixtures/canned/SPEC.md` ("Add `whisper(text)` ... lowercased. `shout` stays as it is. The tests under `tests/toy/` cover both functions.") and `SPEC.json` with `testPlan: "test whisper and shout"`, against PLAN-TO-SPEC-OVERVIEW's "Add a high-level test plan in prose ... Exhaust edge cases, within reason" and the gate's "Incomplete? Fail." Same class as R4-M3 and R4-m6, less certain. Fix (fixture only, about five lines): add a test-plan paragraph to `canned/SPEC.md` naming `test_whisper` and `test_shout`, the empty string and a non-string argument as Python's own behaviour, and mirror it in `fixtures/defects/PLAN-TO-SPEC-GATE/SPEC.md` so the dashboard sentence stays the only difference (`test_probe_manual_positions_a_gate_with_a_planted_defect` checks only "dashboard"). The clean `POSTMORTEM.md` ("Issues: none stood out.") is thin too, but that gate's rules are per issue and hold on none.

### Nit

**R5-n1 (nit)** The OWNER.log slice takes one line per command, so `override` then `approve` with one sentence writes it twice (test D §7.7). Tag the line with the command, `[via driver: override]` (`round.py:1191`, one line; `test_owner.py:96` one line), so two lines are two acts; do not dedupe.
**R5-n2 (nit)** HISTORY's "review checkpoint after X skipped (delegated)" line is written inside `complete` (`round.py:727`) during `record_gate`, so it lands above the gate's attempt entry (test D §11.5 at 20:14:51), the same shape R3-n5 fixed for CHECKPOINT entries; buffer it like `checkpoint_entry` or say in PROCESS.md:86 that skip lines precede the attempt entry. R5-M1 removes the other such line ("NEEDS-OWNER proceeds ...").
**R5-n3 (nit)** At a checkpoint `status.step` is the step the round resumes at while `checkpoint.step` is the step that raised it (test D §7.5): one clause in PROCESS.md:52.
**R5-n4 (nit)** DRIVER.md:37 and :42 read together at a `failure-limit`: overriding only the gate leaves the checkpoint standing, and `approve` then re-runs the producer with its open findings and skips its gate (E2b: `next -> SPEC-TO-IMPLEMENTATION attempt 4 | open findings shown: ['F3']`, then `gate FINDINGS-4 source: override`). Half a sentence in DRIVER.md:37.
**R5-n5 (nit)** `probe --seed defect` on a producer step is silently the clean seed (`probe.py:60-76`): say so in the printed `expect` or refuse (one line).
**R5-n6 (nit)** TESTING.md:30's synopsis omits `--dir DIR` and `--budget` on the build side though `--check` needs the same `--dir`: half a line.
**R5-n7 (nit)** Both POSTMORTEMs logged the same undefined call, tracing an issue about a component older than the first archived round to "the plan(s) that originated" it (test D §7.16). The prose is the owner's; an optional clause in `plumbing/POSTMORTEM.txt` ("earlier plans are `archives/rounds/NNNN/PLAN.json`; a component older than the first archived round has no plan: say so and trace it to the spec files") stops the recurrence without a prose edit. Optional: the calls were correct and cheap.

## 3. Verdicts

### Test D's matrix (section 1, items a to f)

| Item | Verdict |
| --- | --- |
| (a) delegate through STEP from the plan, naming the producer | worked; sound (R3-M1 closed in the field) |
| (b) from the command line, naming the gate | the skip worked; the `source: "plan"` stamp is wrong: R5-m6 |
| (c) override of a producer outside a checkpoint | worked between `record` and `next`; with an attempt pending it sweeps that attempt's work unchecked: R5-M3 |
| (d) override of a pending gate outside a checkpoint | worked; sound |
| (e) override at a review checkpoint | worked as DRIVER.md:40 says; sound |
| (f) override at the question checkpoint of a delegated round | unreachable because the runner settles the question: R5-M1; the override half (SPEC-TO-TESTS skipped, nothing frozen) worked, and what it costs downstream is R5-m2 |

### Test D's six "broke" items and its one-line doc items (sections 1 and 7)

| Item | Verdict |
| --- | --- |
| §7.1 PROCESS.md 87 and 90 disagree; the code takes 90 | the code and line 90 are wrong, line 87 and `SPEC.md:13` are right: R5-M1 |
| §7.2 `through` honoured for reviews, ignored for questions | a symptom of R5-M1; nothing separate to build |
| §7.3 `status` has no `overrides` | real: R5-m5, one line |
| §7.4 CLI delegation stamped `source: plan` | real: R5-m6, one line |
| §7.5 `status.step` vs `status.checkpoint.step` | design (the resume step); R5-n3, one clause |
| §7.6 `override` outside a checkpoint carries no `warnings` | real: R5-m7, one line |
| §7.7 OWNER.log holds the sentence twice | real but two acts; tag the command, no dedupe: R5-n1 |
| §7.8 an overridden SPEC-TO-TESTS leaves the test to CLEANUP | real, mechanical: R5-m2, one line of code |
| §7.9 the SPEC-TO-IMPLEMENTATION prompt contradicts itself with FROZEN_PATHS `[]` | the plumbing clause of R5-m2; the owner's sentence stands |
| §7.10 `answer` has no meaning outside a checkpoint | resolved by R5-M1 (the checkpoint exists again); do not build an out-of-checkpoint `answer` |
| §7.11, §7.12 R4-m1, R4-m2, R4-M2, R4-n3, R4-n4, R4-m7 confirmed by observation | agreed; recorded in section 5 |
| §7.13 two of fifteen final messages wrapped in prose | no change; the extractor's record is 36 of 36 across B, C and D |
| §7.14 no gate finding all round; `retry_cost` two to eleven times the recorded cost (POSTMORTEM 0001 issue 1) | do not build now, see below |
| §7.15 `raise_with_owner` routed | sound (R3-m5 in the field a second time) |
| §7.16 both POSTMORTEMs logged the same trace call | the owner's prose; optional plumbing clause: R5-n7 |

### The undefined judgment calls about the overridden SPEC-TO-TESTS

Who writes the test: undefined because the override had no mechanical route, not because the prose is silent; the three agents chose the only path the write paths left (CLEANUP), correctly. What "until the frozen tests pass" means with nothing frozen: the owner's sentence, and `FROZEN_PATHS: []` is the truthful plumbing beside it; verify still gates the step. The fix is R5-m2, one line of derived code and two clauses of plumbing; no owner file changes.

### Suggestions from test D and its postmortems not to build, and why

- **`retry_cost` from recorded spend** (POSTMORTEM 0001 issue 1, TODO): the figure is PROCESS.md:116's owner-derived formula (the producer's budget plus spawn plus driver), the budget being a share of the owner's quote. Pricing it from the last recorded attempt would change the number every gate is weighed against on the eve of test E, and in a probe it would print the stub's fake `$0.01`, so the same gate would see a retry costing `$1.22` in a probe and `$26` in a round. The gap the postmortem measured is between the quote and today's prices, which is the owner's calibration (CLARIFICATIONS "who reviews the quote"). Revisit after test E with the measured PASS/FAIL rates.
- **A gate-coverage line at checkpoints and LANDED** (POSTMORTEM 0001 TODO): the owner wrote each override; HISTORY carries each skip line; `status` with R5-m5 lists the overrides. Nothing else needed.
- **Naming undefined calls on a delegated skip line** (POSTMORTEM 0001 TODO): the driver already relays `undefined_new` at every `record`, delegated or not (DRIVER.md:35, observed in D §5).
- **OWNER.log dedupe** (POSTMORTEM 0001 TODO): R5-n1's tag instead.
- **Reordering TESTS-TO-SUITE after CLEANUP, or override defaults that write the test** (POSTMORTEM 0002 issue 4, test D's second flag): R5-m2 makes the test exist before TESTS-TO-SUITE runs.
- **A fuller pre-landing review than the living-paths diffstat** (POSTMORTEM 0002 issue 3): in the sandbox the living paths point at the toy, so a harness-only round shows an empty stat there; on the real repository `livingSourcePaths` is the harness's own `src/`, `docs/`, `tests/`. Not a defect; the CLARIFICATION about `livingSourcePaths` versus AGENTS.md's "src/, docs/, and tests/ are living" (POSTMORTEM 0001 issue 2) is the same sandbox artefact, and the two owner files agree on the real repository.
- **`through` at question settlement** (POSTMORTEM 0002 TODO): moot with R5-M1.
- **The step budget over the remaining quote** (POSTMORTEM 0002 issue 7): review 4's verdict on the budget partition stands; the agent sees both figures.

## 4. The eleven post-review-4 code commits and the report

Each checked against the finding it closes: the diff, the test named for it, the docs, and test D where it ran on real agents.

- **`30e4fe9` R4-M1**: sound for the pending step (R9a and R9b pinned, `keep` is state, history and the OWNER.log slice, the result file is discarded too, as fix 4 says). Residual: the same sweep for any other override while an attempt is pending (R5-M3).
- **`c1e7b8c` R4-M2, R4-m5, R4-n9**: sound; `settle_question` has one shape for three callers, `skip_producer` drops with a HISTORY line, the refusal is split, `agents_plan()` ignores an overridden plan; test D confirmed `pending_question` null after the settlement and no later gate asked another step's question (§7.11). Residual: the new refusal message, like every other refusal after the appends, leaves the tree dirty (R5-M2).
- **`1a6b840` R4-M3**: sound; E1's clean SPEC-TO-TESTS-GATE seed carries `test_scratch.py` and `test_text.py`, the scratch test asserting `shout("scratch")`.
- **`736112e` R4-m1, R4-m2**: sound; test D observed both (§5.2 exit-10 `undefined_new`, §7.11 the per-attempt count agreeing with the CHECKPOINT entry), and F1 here.
- **`028a3a7` R4-m3, R4-n7**: sound; both real PLAN-AGENTS agents saw the forced rung and listed CHAT-TO-PLAN at its floor (§11.1, §11.3); E1's stub plan does the same.
- **`ef824c8`, `3a3ce76` R4-m6**: sound; E1's clean AGENTS-PLAN.json is rungs by kind (`PLAN-TO-SPEC max, SPEC-TO-IMPLEMENTATION low, ...`) with weighted work shares summing to 1 and CHAT-TO-PLAN at 0.05; TESTING.md says so.
- **`972dce4` R4-m4**: sound (`--through` alone refused before any git command, applied over a delegated plan); test D's `start --delegate --through PLAN-TO-SPEC-GATE` worked. Residual: the source stamp (R5-m6).
- **`d9eefb3` R4-m7, R4-m8**: sound; test D read both sentences as true (§7.12; its CLEANUP reviews came from `record`, as DRIVER.md:29 now says).
- **`b3a6f96` R4-n1, n2, n5, n6, n10**: sound; the producer prompt's "count of the lines you appended this run" matched every real message in D (no claims FLAG all pass).
- **`dddbaf2` R4-n3, n4, n8**: sound; test D saw `round_branch` and the all-backslash draft path; E1's probe repositories carry the owner's comments (the test pins the count).
- **`4708527` the report**: its "What the docs do not say" list is accurate against the code; two entries now need a second look after this review: "at a `question` checkpoint `override --steps <producer>` resumes and drops the question" is true but the message does not offer it (R5-m4), and "with the gate on, the question waits at the gate and overriding that gate writes the undefined line" stands.

## 5. Verified and found sound (new since review 4)

- Full suite: 180 passed, exit 0, 9 min 56 s, from the repository root of this worktree; `git status --short` afterwards shows only this file. `doctor` on this worktree: 0 errors, 2 warnings (owner log missing; `core.longpaths` off in this checkout), `spec: clean`, all 14 prompts render with no unresolved tokens (1.7k to 3.4k tokens), no agent-definition drift, `claude.exe` 2.1.266 found.
- Test E's probe builder through the CLI, exactly as the driver will run it (E1): all twelve `probe --step <GATE> --seed clean|defect --manual --dir <new folder>` calls exit 0, position the gate at attempt 1 with `tools: read-only` and the expected budget (`$0.9` for PLAN-AGENTS-GATE, `$5.0` for the others on the `$100` fixture quote), the prompt carries the `STEP:` line, and each plant is in front of the gate: the anchors `0.9`, `dashboard` (in the round's SPEC.md, which the prompt's `Inputs, by path` lists beside SPEC.json), `shout`, `yell`, `test_text.py`, `budget` are in the artifact or the DIFF_FILE the gate is told to read. Every alternative anchor of R5-M4 is there too.
- The retry path on the real prose (E2, SPEC-TO-IMPLEMENTATION-GATE defect probe): a FAIL quoting `def yell(text):` scores `verdict_as_expected` and `quote_contains_planted`; `record` of it in the probe repository routes to `SPEC-TO-IMPLEMENTATION` with `failures 1`; attempt 2's prompt lists F1 and the producer's previous message; the stub's clean rewrite closes F1 `fixed`; the gate's attempt 2 shows the resolution, `Ids continue from F2`, and a DIFF_FILE cumulative from the step start (no `yell`, `whisper` present); its PASS advances to TESTS-TO-SUITE. Three FAILs raise `failure-limit` with the documented question; `override` of the gate there keeps the checkpoint with the note; `approve` resets the count; attempt 4 shows the open F3; its gate is skipped with `source: override`. A FAIL recorded at the PLAN-TO-SPEC-GATE probe, whose plant is a spec file, re-enters PLAN-TO-SPEC at attempt 2 with no out-of-band re-entry and `round_retries 0` (E1c: the SPEC hash is taken at acceptance, which the FAIL prevented).
- The final test's surfacing on the current code (F1, delegated, gates off): `record`'s `undefined_new` and the stderr lines for two appended calls; the claims FLAG (`message claims 0/3 judgment calls, the files gained 0/1`); `status` and `done` with counts, the last lines and an absolute `undefined_file`; HISTORY's delta line. `override` at a `question` resumes and drops the question (R4).
- The owner's `SPEC.md:13` for blocks, limits and spec edits: each stops a delegated round in the suite (`test_blocked_checkpoint_and_answer`, `test_in_round_spec_edit_is_flagged_and_checkpointed_even_when_delegated`, and the limit checks that never read the mode). Only the question deviates (R5-M1).
- Test D's five worked matrix items as recorded in its §3, re-read against the code: the anchor rule for `through` naming the producer; `start --delegate --through` on the command line; override of a pending gate skipping it with `source: override` and the tests freezing at the following `next`; override of a producer between `record` and `next`; override at a review standing with the note and `approve` resuming.
- `write_spec(spec="real")` after `dddbaf2`: E1's twelve probe repositories carry the owner's `project.yaml` comments and the flipped gates; `set_yaml_keys` keeps the block comments (`test_set_yaml_keys_replaces_or_appends_and_keeps_comments`).

## 6. Brittleness to changes in the owner's prose or config

Reviews 1 to 4's tables stand; these rows are new or sharpened. "Loud" refuses with a message, "soft" degrades with a warning or a truthful plumbing line, "silent" is the bad kind.

| Owner change | Effect | Kind |
| --- | --- | --- |
| `SPEC.md:13` "questions ... still stop the round" (an owner sentence the runner does not implement) | a delegated round answers the owner's reserved question for them (R5-M1) | silent, until R5-M1 |
| CHAT-TO-PLAN-OVERVIEW's "delegate ... no checkpoints" read literally | the runner reads it as "no review checkpoints" for blocks, limits and spec edits and as "no checkpoints" for questions; after R5-M1 one reading everywhere | soft |
| SPEC-TO-IMPLEMENTATION-OVERVIEW's "until the frozen tests pass" when SPEC-TO-TESTS is overridden | `FROZEN_PATHS: []` is truthful, the write paths are not: three undefined calls per round until R5-m2 | soft, recurring |
| Any locked-prose sentence that sends a producer UPSTREAM to a step the owner overrode | a re-entry loop to `round-limit` (R5-m1) | silent, costly |
| POSTMORTEM-OVERVIEW's "the plan(s) that originated them" for components older than the archive | one undefined call per round (R5-n7); the owner's to settle | silent, recurring |
| COMMON-GATE's "A FAIL costs a retry of the producing step (${{ step.retry_cost }})" against a budget-derived figure | the gate reasons from a number two to eleven times the recorded cost (test D §7.14); the owner's quote calibrates it | silent, the owner's to settle |
| The clean fixture artifacts against the gate prose as worded (R4-M3, R4-m6, R5-m9) | a clean-seed FAIL in test E can judge the fixture | fixture only |

Nothing mechanical matches a phrase of the prose; review 1's statement holds after the twelve fix-4 commits, and no test added by fix 4 asserts on a sentence of the locked prose. No edit to a `spec.yaml` file is recommended by this review: R5-M1 is settled by removing runner code, not by rewording the owner.

## 7. Notes for the next real-agent runs

**Test E (gate effectiveness, retry).**
1. Apply R5-M4 (and R5-m9 if the fixer agrees) before scoring; until then read the findings' quotes by eye when `quote_contains_planted` is false on a FAIL, and read a clean-seed FAIL's findings before concluding anything about the gate (PLAN-TO-SPEC-GATE's seed is the thinnest).
2. `probe --step <GATE> --seed clean|defect --manual --dir <new folder outside any repository>`, one folder per probe (a reused folder crashes, R5-m8), spawn on the printed `task`, save the final message to `result_file`, then `probe --check <result_file> --dir <the same folder>` (`--dir` is required in practice, R5-m8). The gate's rung in a probe is the roster's `gateAgent` (`max`), so a session spawning `general-purpose` at `opus` is off the printed rung; there is no `record` in a probe, so nothing to flag.
3. For the in-round retry with gates on: a gate FAIL costs `retry_cost` as printed; `record` of the FAIL routes to the producer, whose next prompt lists the findings; the gate's next prompt shows the resolutions, continues the ids, and its DIFF_FILE is cumulative from the step start (E2). At `maxFailuresBeforeStop` (3) the `failure-limit` checkpoint offers `approve` (resets the count, re-runs the producer with its open findings) and `override` (of the producer: skips it; of the gate alone: the checkpoint stands, `approve` then re-runs the producer and its gate is skipped, R5-n4).
4. Until R5-M2 and R5-M3 land: never let an owner command be refused while an attempt is pending (a refusal costs the attempt: R8b), and override only between `record` and `next` (R1). A refused command between `record` and `next` costs an infrastructure error at the next `next` (R8a); `next --discard` is harmless there.
5. `probe --seed defect` on a producer step is the clean seed (R5-n5); only gates have plants.

**The final test (an undefined judgment call; a delegated question).**
1. Surfacing is sound on the current code (F1): `record`'s `undefined_new` and stderr lines (exit 0 and exit 10), the claims FLAG, `status`, checkpoint messages ("N undefined since the last checkpoint" plus the last five lines), `done`.
2. The delegated `question` checkpoint exists only after R5-M1; until then a delegated NEEDS-OWNER with the gate off is settled with exit 0 and one runner-written undefined line (test D §3.2 #12). After R5-M1: the message carries the question and the assumption; `answer --text` re-runs the producer with O1; `override --steps <producer>` resumes and drops the question (offered in the message only after R5-m4); `approve` re-runs the producer with "proceed on your stated assumption" as O1, one paid run whose likely output is the same artifact.
3. With the gate on and delegated, the question waits at the gate; upheld raises the checkpoint, withdrawn logs Q1 and judges the artifact on the assumption, no ruling settles it as an undefined call with a FLAG; overriding that gate settles it the same way (fix 4).
4. The claims FLAG compares the message's counts with the lines appended this run (R4-n6); a fabricated agent that appends a multi-line record counts every non-blank line.
