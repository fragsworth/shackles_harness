# Review 4 (after fix 3 and test C)

Reviewer: `claude-fable-5-1` (Fable 5.1), effort `max`, as the system prompt states them. Read-only review of `a44867e` (`bootstrap: test C report (approve run, review and question checkpoints)`), in a linked worktree fast-forwarded from `ca24820` to `claude/bootstrap` before anything was read. Nothing tracked was modified; every reproduction ran on throwaway repositories built with the project's own fixtures under `%TEMP%` (the scripts are not part of the repository). This review builds on `review-3.md` and does not repeat its "verified sound" lists.

## 1. Process

Drafted after reading only the entry points (`README.md`, `CLAUDE.md`, `harness/AGENTS.md`, `harness/INDEX.md`) and before anything else; followed in this order. Deviations are noted at the end of this section.

1. Confirm `HEAD` is `a44867e` after `git merge --ff-only claude/bootstrap`. Done before this draft.
2. Read the previous review (`bootstrap/reviews/review-3.md`) whole: its severity definitions (adopted here unchanged), its three majors, ten minors and seven nits, its "verified sound" lists (not repeated below), its brittleness table and its notes for the next runs.
3. Read `bootstrap/fixes/fix-3.md`, then the fifteen commits `7936c64..255461d` as diffs (`git log -p ca24820..255461d`), one at a time, checking each against the finding it claims to close: does the code do what the commit says, does a test pin it, and did the change reach the docs and prompts that describe it. Note every payload change the fixer listed under "What the docs do not say" and check whether the docs now say it.
4. Read `bootstrap/tests/test-C.md` whole, as evidence of how a real driver and real agents parse the prompts and the docs: section 1 (the summary and its "broke" items), sections 4 to 8 (checkpoint messages, `undefined_new` lines, errors, doc defects, deviations), section 11 (raw judgment-call files and HISTORY). Skim `test-B.md` and `test-A.md` for what carried over and what was already reported. List the items that need a verdict.
5. Read the owner's files (`SPEC.md`, `spec.yaml`, `harness/project.yaml`, `harness/subAgents.yaml`, `harness/locked_prose/*.txt`) and `bootstrap/FINAL-PLAN.md`, so that findings can be checked against what the owner asked for rather than against what the code happens to do.
6. Read the docs as the driver will: `harness/docs/DRIVER.md` literally, then `PROCESS.md`, `TESTING.md`, `CLARIFICATIONS.md`, `TODO.md`.
7. Read the whole runner (`harness/src/run.py`, every module under `harness/src/shackles/`, every `plumbing/*.txt`), in dependency order: config and schemas, pipeline and checks, prompts and render, round, commands and cli, ledger and landing, probe, doctor, agents. Read for what the next three runs will exercise first, then for anything else.
8. Read every test (`harness/tests/`), including the fixtures, the stub agent and the defect fixtures, asking what each asserts against what the code does, and whether any test asserts on a sentence of the locked prose.
9. Trace the three upcoming paths end to end, through `DRIVER.md`, the rendered prompts (`render --step ... --raw` on a fixture repository), the checkpoint messages, and the code:
   - Test D: `override` of a producer step and of a gate, at a checkpoint and outside one; "delegate through STEP" from the plan and from the command line, naming the producer and naming the gate.
   - Test E: `probe --step <GATE> --seed defect --manual` with the six planted fixtures (clean must PASS, defect must FAIL quoting the planted text); then the retry path in a round (gate FAIL, producer re-run with the findings, gate again with the resolutions and the cumulative diff).
   - The final test: an undefined judgment call recorded in `UNDEFINED_JUDGMENT_CALLS.md` and surfaced at `record`, at checkpoints, in `status` and at `done`.
   Reproduce what can be reproduced on throwaway repositories under `%TEMP%` built with `harness/tests/fixtures.py` (`write_spec`, `Repo`, `play`) and with `run.py sandbox --dir` / `run.py probe --dir`, never inside the worktree.
10. Run the full suite once (`py -3.13 -m pytest` from the repository root) and `doctor` once; report both.
11. Write the findings by severity, each with evidence (a reproduction transcript or a `file:line` citation) and a fix sized in lines naming the file and function; the verdicts asked for (test C's "broke" items, its eight one-line doc items, the sandbox postmortem's issue 1); the post-review-3 fixes checked one by one; verified and found sound (new since review 3 only); brittleness rows (new or sharpened only); notes for runs D, E and the final test. Prefer fixes that remove or simplify; say when a suggestion from a test report or postmortem should not be built.
12. Confirm `git status --short` shows only this file; commit it alone with the given subject and trailer; do not push.

Severity, transcribed from review 3 and applied unchanged: **blocker** = the next phase cannot succeed or would draw a false conclusion with no workaround; **major** = a real defect that costs an agent run, corrupts round records or misleads the driver, with a workaround; **minor** = wrong but cheap; **nit** = cleanliness. A defect on one of the three upcoming paths is a major at least, as the assignment says.

Deviations from the draft: steps 4 and 5 were read in one batch (test C alongside the owner's config and prose) rather than strictly in sequence; the suite (step 10) was started in the background while the tests of step 8 were being read, and finished before step 9's reproductions ended. Nothing else deviated. Twelve reproductions ran (`R1` to `R9b`, `E1` to `E3` below): nine confirmed a defect or a gap, three confirmed a path sound.

Counts: 0 blocker, 3 major, 8 minor, 10 nit.

## 2. Findings

### Major

**R4-M1 (major) `override` outside a checkpoint commits the pending attempt's unrecorded work through the owner command's own commit, with no mechanical check; the overridden producer is then not "skipped with defaults" but skipped with whatever the agent had written.**
`override()` (`round.py:1273-1274`) clears `attempt_pending` when the overridden step is the pending one, and `owner_command` then calls `self.commit(f"{command} at {kind or 'active'}", push)` (`round.py:1200`), which is `git add -A` plus a commit (`round.py:154-163`). Nothing in between reverts or checks the tree. So an agent's files written before the driver runs `override` are committed as `round NNNN: override at active` and never pass M1, M2, M3 or M5. Two consequences, both reproduced:
- R9a (fixture, `next` prints PLAN-AGENTS, the stub writes AGENTS-PLAN.json with rung `low`, no `record`, then `override --steps PLAN-AGENTS`):
```
dirty before override: ['?? harness/archives/rounds/0001/AGENTS-PLAN.json']
override exit 0 | dirty after: [] | last commit: round 0001: override at active
files in that commit: [AGENTS-PLAN.json | 26 ++++, HISTORY.md, OWNER.log, STATE.json]
next -> PLAN-TO-SPEC attempt 1 agent low budget 10.0
agents_plan() used by the round: True | PLAN-AGENTS in attempts: False
HISTORY: 'PLAN-AGENTS overridden: skipped with defaults', 'PLAN-AGENTS-GATE skipped (override)'
```
  The unrecorded plan drives every later rung and budget (`agents_plan()` reads the file once the gate is in `step_commits`, `round.py:96-97`) while HISTORY and PROCESS.md:38 say the step was skipped with defaults.
- R9b (delegated fixture round at CLEANUP: the stub writes a stray `stray.txt` outside WRITE_PATHS and an unchecked function into `src/toy/text.py`, no `record`, then `override --steps CLEANUP`):
```
dirty before override: ['M src/toy/text.py', '?? stray.txt']
override exit 0 | dirty after: [] | last commit: round 0001: override at active
files in that commit: [HISTORY.md, OWNER.log, STATE.json, src/toy/text.py | 4 ++++, stray.txt | 1 +]
round: done finished | stray.txt on the landed tree: True | unchecked() in text.py: True
mechanical findings for CLEANUP: False | M1 anywhere in HISTORY: False
```
  A stray and an unchecked edit landed on `main` without M1, M3 or M5 (L2 would still catch a red suite, not a stray or a passing but unwanted change).
This is on test D's path ("override of a producer step ... outside a checkpoint"): the natural moment for a driver to override a running step is after the agent came back and before `record`. Workaround until fixed: override only between `record` and `next`, or right after `next` before spawning; if the agent already ran, `record` it first, or run `next --discard` after the override (the discard resets the tree, but only if `override` has not committed it yet, which it has).
Fix (about six lines in `round.py:override`, no new rule for agents): when the pending attempt's step is being overridden, discard its unrecorded work before `owner_command` commits: `runner_files = [self.repo_rel(self.paths[k]) for k in ("state", "history", "ownerLog")]` (the files this command has already appended to), `dirty = checks.dirty(self.root, exclude=runner_files)`, `checks.revert(self.root, dirty)`, and one HISTORY line `override: unrecorded work of {step} attempt {n} discarded: {paths}`; then clear `attempt_pending` as today. Add a sentence to PROCESS.md:89 ("unrecorded work of that step's pending attempt is discarded") and pin the R9b scenario in `test_outcomes.py` (stray plus a `src` edit, override, `next`: nothing committed, the step skipped, the tree clean). Do not make `commit()` selective: the sweep is right for every other owner command (an edited PLAN.json at `upstream-plan` is meant to be committed by `approve`).

**R4-M2 (major) An `override` at a `question` checkpoint, or of the gate a producer's question is waiting at, leaves `pending_question` set: the next gate that runs is asked the wrong producer's question, and when it does not rule the runner writes a false undefined judgment call under the later producer's name.**
`record_producer` sets `pending_question` on NEEDS-OWNER (`round.py:1012`) and clears it only through `answer` (`round.py:1251`), the delegated branch (`round.py:1016-1019`), a gate's ruling (`round.py:1142-1152`), `upstream` or `out_of_band`. `skip_producer` (`round.py:656-665`) and `skip_gate` (`round.py:645-654`), the two paths an `override` takes, never touch it, and `step_context` renders it into every gate prompt as "The producer's question, if any" (`round.py:331-332`, `gate.txt`). Reproduced:
- R3 (fixture, gates `{SPEC-TO-TESTS-GATE: 1}`, approved; PLAN-AGENTS NEEDS-OWNER, `question` checkpoint, `override --steps PLAN-AGENTS`):
```
checkpoint: question at PLAN-AGENTS   resume: ['answer', 'approve', 'abandon']
override exit 0 kind resumed status active step PLAN-AGENTS
STATE.pending_question after override: {'question': 'STUB-QUESTION: which colour should whisper use?', 'assumption': 'STUB-ASSUMPTION: lowercase'}
reached SPEC-TO-TESTS-GATE
gate prompt question line: ["The producer's question, if any: STUB-QUESTION: which colour should whisper use? (assumption: STUB-ASSUMPTION: lowercase)"]
gate record exit 0 warnings: ["SPEC-TO-TESTS-GATE attempt 1: no ruling on the producer's question; the assumption stands"]
UNDEFINED lines added by the gate record: ['- SPEC-TO-TESTS assumed: STUB-ASSUMPTION: lowercase (runner: SPEC-TO-TESTS-GATE attempt 1 gave no ruling on the question: STUB-QUESTION: which colour should whisper use?)']
```
  SPEC-TO-TESTS assumed nothing; the round's record now says it did, and the count the final test will check is off by one.
- R3b (gates on, delegated; PLAN-AGENTS NEEDS-OWNER with its gate on, so the question waits at the gate; `override --steps PLAN-AGENTS-GATE` outside any checkpoint): the gate is skipped with `source: override`, the question is never ruled on, no undefined line is written (the delegated NEEDS-OWNER path at `round.py:1017` would have written one), and PLAN-TO-SPEC-GATE's prompt carries PLAN-AGENTS's question.
PROCESS.md:85 and R3-n7 tell the driver that `override` is a natural resume at `blocked`; `blocked` sets no question, so that case is clean, but `question` is one `override` away and test D will override at a checkpoint. Workaround: at a `question`, use `answer` or `approve`; never override the gate a question is waiting at.
Fix (about six lines in `round.py`): a small `settle_question(step, attempt, why)` used three times: the existing delegated branch (`round.py:1016-1019`, unchanged text), `skip_gate` when `pending_question` is set (append `- {producer} assumed: {assumption} (runner: {gate} skipped ({source}); question: {question})` to UNDEFINED_JUDGMENT_CALLS.md, one HISTORY line, clear), and `skip_producer` (clear with one HISTORY line: an overridden producer's question is moot, its artifact is not used, see R4-n9). Pin R3 in `test_outcomes.py`.

**R4-M3 (major) The clean seed of `SPEC-TO-TESTS-GATE` is not a sensible artifact: it contains `test_scratch.py` with `self.assertTrue(True)`, which the gate's prose tells it to fail; test E's "a clean seed must PASS" cannot be expected to hold for that gate.**
`probe.prepare` (`probe.py:42-81`) plays the stub to the producer and accepts its attempt; for SPEC-TO-TESTS the stub writes `canned/test_text.py` and `canned/test_scratch.py` (`stub_agent.py:98-100`), the latter a `ScratchTest` whose only method asserts `True`. The gate's DIFF_FILE is the diff of `testPaths` since the step started, so both files are in front of the gate, and SPEC-TO-TESTS-GATE.txt says "For each test: Is it not sensible? Fail." Reproduced on the real prose (E1):
```
--- SPEC-TO-TESTS-GATE: expect PASS; budget $5.0; ARTIFACT a diff under WRITE_PATHS
DIFF_FILE files: ['diff --git a/tests/toy/test_scratch.py ...', 'diff --git a/tests/toy/test_text.py ...']
test_scratch.py body in the diff: ['+class ScratchTest(unittest.TestCase):', '+        self.assertTrue(True)']
```
A gate that FAILs this seed is right, and test E would either report "the gate fails clean seeds" or the driver would have to argue the fixture away by hand. The scratch file exists so that TESTS-TO-SUITE has something to archive (`STUB_ARCHIVE`), and the suite refers to it by name only (`test_round.py:191,299`, `test_checks.py:45-55,74`, `test_headless.py:45`).
Fix (one file, about nine lines): give `harness/tests/fixtures/canned/test_scratch.py` the same import header as `test_text.py` and one real but redundant assertion, e.g. `test_shout_scratch` asserting `text.shout("scratch") == "SCRATCH"`; it stays a test worth archiving (redundant with `test_shout`) and becomes a test worth passing. Keep one `def test_` so the living charge's test count is unchanged. Update the one-line `planted` wording of `fixtures/defects/TESTS-TO-SUITE-GATE/expect.json` and the `notes` of its `SUITE.json` ("the empty scratch test" becomes "the redundant scratch test"); the planted defect (the regression test archived) stands. No other test changes.

### Minor

**R4-m1 (minor) HISTORY's per-attempt "(N undefined since the last checkpoint)" reads 0 on the attempt that raised the checkpoint.** (test C §7.9, POSTMORTEM issue 5)
`raise_checkpoint` composes the checkpoint message and then sets `undefined_at_checkpoint` to the current count (`round.py:410-411`); `record` writes the attempt entry after routing (`round.py:841-842`) with `judgment_report()`, which subtracts the freshly reset baseline (`round.py:132-135`). Reproduced (R1, PLAN-AGENTS NEEDS-OWNER with two undefined lines): the attempt entry says `(0 undefined since the last checkpoint)`, the CHECKPOINT entry below it `(2 ...)`, and the checkpoint message is right. Cosmetic; the message the driver relays is correct.
Fix (three lines in `round.py`): `judgment_report(self, base=None)` using `base` when given; in `record` capture `base = st.get("undefined_at_checkpoint", 0)` next to `before` (`round.py:823`) and pass it at `round.py:842`.

**R4-m2 (minor) `record` exit 10 carries no `undefined_new`; the lines the attempt appended reach the driver only inside the checkpoint's last-five tail.** (test C §7.8)
`record` returns `checkpoint_payload()` at `round.py:847-848` before computing `new`; `finish` prints `undefined_new` only when the key exists (`commands.py:121-122`). Reproduced (R2): `payload keys: [... 'undefined_file', 'undefined_tail', 'warnings']`, no `undefined_new`, no `undefined judgment call:` line on stderr. DRIVER.md:35 says to relay `undefined_new` "as it appears"; on this path it never appears. With more than five lines appended at the attempt that raises a `question`, some reach nobody.
Fix (three lines in `round.py:record`): compute `new` before the checkpoint return and add `"undefined_new": self.undefined_tail(new) if new > 0 else []` to that payload; `finish` then prints them too.

**R4-m3 (minor) The PLAN-AGENTS prompt says `shares.work` maps every producer step and shows a CHAT-TO-PLAN minimum, S1 requires every producer but CHAT-TO-PLAN, and the arithmetic differs by which the agent believes; both real rounds logged the same undefined judgment call.** (test C §7.12, §1 bullet 7)
`PLAN-AGENTS.txt:3` ("every producer step", `minimum_shares` including `CHAT-TO-PLAN: 0.05` from `prompts.py:186-189`) against `checks.s1_agents_plan` (`present` excludes CHAT-TO-PLAN, `checks.py:146,154-155`). Both shapes pass S1 (R4). What differs is money: `start` books CHAT-TO-PLAN's share at the owner's floor before any plan exists (`round.py:1465-1466`, `$3.5` on a `$100` quote), and after acceptance `ledger.shares` gives a plan that omits CHAT-TO-PLAN the whole work budget for the seven other steps (R4b: `CHAT-TO-PLAN budget 0.0; sum of producer budgets 70.0; booked estimate [3.5]`), while a plan that lists it at 0.05 keeps the sum honest (`CHAT-TO-PLAN budget 3.5; sum 70.0`). Test C's agent chose the honest shape and logged it as undefined; the stub and a literal reader of S1 choose the other.
Fix (one line of plumbing): in `PLAN-AGENTS.txt` say that CHAT-TO-PLAN's share is already spent (booked at `start` from the minimum shown) and must be listed in `shares.work` at that minimum so the map still sums to 1. If a mechanical check is wanted instead, `s1_agents_plan` can require the `shares.work` entry for CHAT-TO-PLAN (two lines: keep `agents` exempt, add it to the shares loop) with the stub listing it (`stub_agent.py:77-84`, one line); the prose fix alone is enough for the agents that logged it.

**R4-m4 (minor) `start --through STEP` without `--delegate` is validated and then silently ignored.**
`start` validates `through` (`round.py:1383`) and applies it only inside `if delegate:` (`round.py:1397-1398`). Reproduced (R5g): `start --through PLAN-TO-SPEC` gives exit 0, `warnings []`, `approval: {'mode': 'approved', 'source': 'gate-disabled'}`, and the PLAN-TO-SPEC-GATE review fires. A driver following DRIVER.md:22 ("`--delegate [--through STEP]`") who drops the first flag gets an approved round and no word about the second.
Fix (two lines in `round.py:start`): refuse `--through` when neither `--delegate` nor a delegated plan is present (`RunnerError("--through needs --delegate or a delegated plan", 2)`).

**R4-m5 (minor) `override` of a producer whose gate is pending is refused as "already accepted".**
`override()` folds two cases into one message (`round.py:1268-1270`): a step accepted by its gate, and a step that ran but whose gate has not. Reproduced (R5c, gates on, at PLAN-AGENTS-GATE attempt 1 pending): `override --steps PLAN-AGENTS` -> exit 2 `PLAN-AGENTS is already accepted`; `override --steps PLAN-AGENTS-GATE` -> accepted, and `next` skips the gate with `source: override` beside the rendered `PROMPTS/PLAN-AGENTS-GATE-1.txt`. The refusal is right (the artifact exists); the wording sends test D's driver looking for an acceptance that did not happen.
Fix (two lines): split the condition and say `PLAN-AGENTS already ran; its gate PLAN-AGENTS-GATE is pending: override the gate instead` for the `index < current` case.

**R4-m6 (minor) The clean seed of `PLAN-AGENTS-GATE` is the stub's equal split with every step on the max rung; a real gate reading "Is anything about it not sensible? Fail." may fail it, and test E would then be measuring the fixture.**
E1 on the real prose: `agents` all `max`, `shares.work` 1/7 each, `shares.gates` 1/6 each, `notes: STUB-AGENTS-PLAN-NOTES`, for a one-line toy task on a `$100` quote. PLAN-AGENTS-OVERVIEW asks the planner to choose by cost and strengths; an equal split on the dearest rung is the plan a gate is told to reject. "Small imbalances are non-blocking findings" may save it; nothing guarantees that.
Fix (about six lines in `stub_agent.write_artifact`, PLAN-AGENTS branch): unless `STUB_RUNG` is set, choose rungs by kind (`max` for PLAN-TO-SPEC and POSTMORTEM, `medium` for PLAN-AGENTS and TESTS-TO-SUITE, `low` for the code steps) and weight the shares (PLAN-TO-SPEC and SPEC-TO-IMPLEMENTATION larger); the only tests that read a post-plan rung use `STUB_RUNG` (`test_round.py:230-234`), the rest assert before the plan or on `--agent`. Alternatively say in TESTING.md that this seed is an equal split and that a FAIL there judges the fixture; the stub change is the one that keeps the probe honest for the TODO.md item ("measure whether clean artifacts pass the gates as worded").

**R4-m7 (minor) PROCESS.md:35 "A gate runs iff its `gates` flag is 1 ... otherwise it is skipped with `FINDINGS/<GATE>-<n>.json`" is false for CHAT-TO-PLAN-GATE, which line 34 just said passes mechanically with no FINDINGS file.** (test C §7.1)
Fix: "An LLM gate runs iff ..." (one word); the same one word in the driver's head when reading `status` and finding six skips for seven flags.

**R4-m8 (minor) DRIVER.md's loop never says a `review` can arrive from `next`.** (test C §7.2)
With the gates off the PLAN-TO-SPEC-GATE review is raised inside `next` (`skip_gate` -> `complete` -> `raise_checkpoint`, `round.py:645-654,706-719`) and the CLEANUP review inside `record`; DRIVER.md:29 lists what `next` does mechanically without the review, and DRIVER.md:36 describes only the `record` half. Test C's driver derived it from PROCESS.md:40.
Fix (one clause in DRIVER.md:29): "... and raises the `review` after a `checkpointsAfter` gate it skipped, so with the gates off the spec review comes from `next` and the CLEANUP review from `record`".

### Nit

**R4-n1 (nit)** `record --help` says of `--agent` "the run is priced at it and HISTORY flags it" (`commands.py:39`); the code flags only when the rung differs from the action's (`round.py:794,812-813`) and DRIVER.md:32 says so. Reword the help: "when it differs from the action's rung, the run is priced at it and HISTORY flags it" (one line). (test C §7.3)
**R4-n2 (nit)** DRIVER.md:12 tells a one-model session to `start --agent <rung>` but not that every action then names that rung and `record --agent` is never needed; test C's driver inferred it. Half a sentence. (test C §7.4)
**R4-n3 (nit)** `status` prints `"branch": st["branch"]` (`round.py:1322`), the round's branch, beside `root`, the checkout it read; from the main checkout after `done` that reads as the checkout's branch (test C §7.6; R8 shows `main` in a no-branch round, `round/0001` in test C). Name the key `round_branch` (one line; DRIVER.md and PROCESS.md name no status keys).
**R4-n4 (nit)** The CHAT-TO-PLAN plumbing prints the draft as `"{{ round.harness_root }}/DRAFT-PLAN.json"` (`CHAT-TO-PLAN.txt:9-10`), a backslash path with one forward slash (test C §7.7). A `round.draft_plan` key built with `os.path.join` in `round_context` and `planning_contexts` (three lines) fixes the line a driver copies. The report's other half, an `--agent` hint on that line: do not add it; DRIVER.md:12 is the place, and the printed command is the common case.
**R4-n5 (nit)** PROCESS.md:84 promises "the undefined lines added since the last checkpoint"; the message carries the count of those and the last five lines of the file (`round.py:132-140`, FINAL-PLAN amendment 8). Three words: "the count added since the last checkpoint and the last five undefined lines".
**R4-n6 (nit)** `producer.txt`'s final-message line asks for `"judgment_calls": {"defined": <count>, "undefined": <count>}`; R3-m8's comparison (`round.py:921-931`) is against the lines this attempt appended, so a producer on attempt 2 that reports its round total earns a false `message claims` FLAG. Say `<lines you appended this run>` (one line). The final test's fabricated agent is exactly the one that will report a count.
**R4-n7 (nit)** PLAN-AGENTS is not told when `start --agent` forces one rung for the round (`round.py:229-231`); test C's agent found `STATE.agent_override` itself and planned rungs that cannot run. A `round.agent_override` key (`prompts.ROUND_KEYS`, `round_context`) and one clause in `PLAN-AGENTS.txt` (three lines) let it skip that judgment.
**R4-n8 (nit)** `fixtures.write_spec(spec="real")` still rewrites `project.yaml` with `yaml.safe_dump` (`fixtures.py:100-106`), so probe repositories lose the owner's comments that the sandbox now keeps (`7936c64`); a PLAN-AGENTS-GATE probe that reads `project.yaml` sees no "mechanical, run by the runner". Reuse `probe.set_yaml_keys` (three lines).
**R4-n9 (nit)** `agents_plan()` returns a committed AGENTS-PLAN.json whenever PLAN-AGENTS-GATE is in `step_commits` (`round.py:96-97`), including when PLAN-AGENTS is overridden after a recorded attempt (the R3 scenario, and R9a until R4-M1); PROCESS.md:38 says an overridden PLAN-AGENTS means default shares and rungs. One line: `and "PLAN-AGENTS" not in self.state["overrides"]`.
**R4-n10 (nit)** POSTMORTEM's prompt prices its carry-forward edits as living tokens (COMMON-PROJECT, the owner's sentence) while PROCESS.md:122 and FINAL-PLAN amendment 2 exempt them; PLAN-AGENTS in test C sized its 0.20 share on the charge (POSTMORTEM issue 4). One sentence in `plumbing/POSTMORTEM.txt`: "these edits land after LANDING and are not charged as living tokens; be dense anyway".

## 3. Verdicts

### Test C's "broke" items (section 1 and the three TODOs POSTMORTEM filed)

1. **HISTORY's "(0 undefined since the last checkpoint)" on the attempt that raised the checkpoint** (§7.9, POSTMORTEM issue 5): real, cosmetic, reproduced; R4-m1, three lines.
2. **`record` exit 10 swallows `undefined_new`** (§7.8): real; the checkpoint message carries the last five lines, so nothing was lost this round; R4-m2, three lines.
3. **S1 excludes CHAT-TO-PLAN while the prompt states its minimum** (§7.12): real, in derived code, and it has a money side the report did not see (R4b); R4-m3, one line of plumbing.
4. **POSTMORTEM issue 2, `cleanupPaths` from the plan's scope**: do not build. CLEANUP's paths are wide by design (COMMON-PROJECT invites refactoring within the cap; the owner's CLEANUP-OVERVIEW is one sentence), the runner never parses a plan's scope or non-goals (SPEC.md's architecture list, PROCESS.md:8), and a new SPEC field plus a check plus a prose obligation adds a rule for agents to learn in order to enforce a non-goal that judgment, the living charge and the gate (when on) already hold. Test C shows the judgment holding.
5. **POSTMORTEM issue 4, carry-forward pricing**: one sentence of plumbing, R4-n10; nothing mechanical.

### The eight one-line doc items (section 1)

| Item | Verdict |
| --- | --- |
| PROCESS.md:35 "a gate runs iff" | wrong; R4-m7, one word |
| DRIVER.md never says a review comes from `next` | missing; R4-m8, one clause |
| `record --help` vs DRIVER.md:32 on when `--agent` flags | the help is wrong, the code and DRIVER.md agree; R4-n1 |
| DRIVER.md:12 stops one sentence short | R4-n2, half a sentence |
| `status` prints `branch: round/0001` from the main checkout | misleading key name; R4-n3 |
| CHAT-TO-PLAN's `start` line: mixed separator, no `--agent` | separator R4-n4; the `--agent` hint should not be added |
| "expect one or two rejections per gated step" with every gate off, and S1 vs the 0.05 minimum | the first is the owner's sentence and, with no gated step, vacuous rather than contradictory: no change, the agents' logged call is the right outcome; the second is R4-m3 |
| POSTMORTEM issue 1 is an owner question | agreed; below |

### The sandbox postmortem's issue 1 (step budgets partition the whole quote)

The owner's numbers: `workFraction: 0.7` and `gatesFraction: 0.3  # sums to 1 with workFraction` in `project.yaml`, and PROCESS.md:115 implements exactly that (`quote x fraction x share`), while `totals` (`ledger.py:87-92`) and every "Spend $X of quote $Y" line count owner, living and time in the same quote. So either the quote is the agent-work envelope and the spend line compares more than it, or the quote is all-in and the shares over-allocate; only the owner can say which, and the CLARIFICATION POSTMORTEM filed is the channel. Nothing to build now, and two things not to build: a "remaining-aware" step budget (it would shrink late steps by the owner's own checkpoint costs and encode a policy nobody stated), and a renormalisation of the fractions (the owner's comment says they sum to 1 on purpose). The agent already sees both figures: COMMON-ROUND prints quote, spent and remaining beside the step budget. Budgets are targets, not gates (COMMON-OVERVIEW), and the hard stop is on the total; test C spent 11% of the quote on agents.

### Suggestions from the reports not to build, collected

`cleanupPaths` (above); a per-test archive unit for TESTS-TO-SUITE (POSTMORTEM issue 3: the file is the unit the runner moves and `suiteCommand` discovers; the owner's prose says "each test" and the CLARIFICATION is filed; a finer unit is a design change, not a fix); an `--agent` hint in the CHAT-TO-PLAN start line (R4-n4); a stronger JSON wrapper (test C §7.11: 1 of 8, extraction coped, fix 3's reasoning stands); a "let POSTMORTEM close carried findings" path (test C §7.15 confirms it did not recur; review 3's verdict 2 stands).

## 4. The fifteen post-review-3 commits

Each checked against the finding it closes: the diff, the test named for it, and the docs.

- **`7936c64` sandbox and probe builders**: sound. `specguard.spec_files` drives both copies; `set_yaml_keys` keeps the comments in the sandbox and the real-repository sandbox test pins `spec status` clean and `doctor` with no errors. Residual: the probe's `write_spec(spec="real")` still dumps `project.yaml` (R4-n8). `doctor` on this worktree and `sandbox` in test C confirm the SPEC.md copy.
- **`2aea88d` R3-M1**: sound; the anchor is the producer, the test runs both names and an earlier one. Reproduced here beyond the suite: "delegate through PLAN-TO-SPEC" at the PLAN-TO-SPEC-GATE review (R5e) and on the `start` command line (R5f) both leave exactly the CLEANUP review. DRIVER.md:20 and PROCESS.md:87 say STEP may be either name.
- **`366da07` R3-M2**: sound; `owned_artifacts` covers the six artifacts for every producer but their own, on the DONE and the UPSTREAM/BLOCKED paths; the R2 scenario is pinned; `producer.txt` and PROCESS.md:21 say it. Note for the fixer's list: the round's `SPEC.md` is distinct from the owner's root `SPEC.md`, which stays an E1 exemption; both work as intended.
- **`4c4cf1e` R3-M3**: sound on exit 0 (R7: `undefined_new` in the payload and on stderr, `done`'s tail and counts, DRIVER.md:35 and :47). Residual: the exit-10 path (R4-m2).
- **`3c3f077` R3-m1**: sound; `off_plan` compares with the plan's rung, the FLAG reaches HISTORY and `warnings`, the ledger note is plain when the rungs agree; DRIVER.md:12 documents `start --agent`, which test C used (`--agent` then needed nowhere). Residual: the help text (R4-n1).
- **`1849698` R3-m2**: the prompt clause is there and says what review 3 asked; test C's CLEANUP left the carried flag alone "for POSTMORTEM", as the clause says.
- **`b8c4433` R3-m3**: sound; the attempt is counted per pass (the fixer's reason is right: attempt numbers never restart), the HISTORY line names mode, words and source; the sandbox half is in `7936c64`. Residual: PROCESS.md:35 (R4-m7).
- **`9edb5ca` R3-m4**: mechanically sound (filtered to the steps present, the mechanical gate never listed, pinned in `test_render.py`). Residual: the CHAT-TO-PLAN entry it keeps is what test C's agent logged (R4-m3); the money reading (R4b) says the fixer's choice to keep it was right and the prompt should say why.
- **`403f237` R3-m5**: sound; test C exercised it end to end (`flagged for the owner:` in HISTORY, the `flag` carried note in CLEANUP's and POSTMORTEM's prompts, §7.14).
- **`1e567e5` R3-m6, R3-m7, R3-m10, test-B 5.3**: sound; the override note under `warnings` is pinned twice and reproduced (R5d); DRIVER.md:36-40 now match the code sentence by sentence (re-read here against `approve`, `answer`, `override` and `infra`). Residual: the review-from-`next` clause (R4-m8).
- **`adf7bb0` R3-m8**: sound (R7: `message claims 0/0 judgment calls, the files gained 0/1`); the comparison runs after M4 as the fixer notes. Residual: the prompt's `<count>` should say per run (R4-n6).
- **`1ac860a` R3-m9**: sound; `validate_plan` no longer takes `delegate`, the test pins `--delegate` without words refused.
- **`5acf17a` R3-n1 to R3-n7**: all present and pinned where a test was promised (n1 regex, n5 ordering in two tests, n6 producer rung); n2 to n4 and n7 are the key renames and words described. The n5 ordering fix is what exposed R4-m1: the CHECKPOINT entry now follows the attempt entry, and the attempt entry is rendered after the counter reset.
- **`7b45814` R3-m7, R3-m10**: sound; the `invalid` payload carries `warnings`, DRIVER.md:29 names spec-edit, L1/L2 and the overridden-POSTMORTEM `done`.
- **`255461d` the report**: its "What the docs do not say" list is accurate; the payload changes it names (`root`, `head_at_accept`, `undefined_new`, `undefined_file`, `warnings` on `checkpoint` and `invalid`, the `CHAT-TO-PLAN-GATE` attempt key, the stderr line) are all observed in test C or here. None of them is in DRIVER.md or PROCESS.md by name; the driver of test C did not miss them, and PROCESS.md:52 names `living_preview_usd` only. Not a finding: the payloads are read by drivers who see them, and the test reports document them for the next driver.

## 5. Verified and found sound (new since review 3)

- Full suite: 176 passed, exit 0, 617.85 s (10 min 17 s), started from the repository root of this worktree; `git status --short` afterwards shows only this file. `doctor` on this worktree: 0 errors, 2 warnings (owner log missing; `core.longpaths` off in this checkout), all 14 prompts render with no unresolved tokens (1.7k to 3.3k tokens), agent definitions match the roster, `claude.exe` 2.1.266 found.
- Test E's probe path on the real prose (E2, E3): `probe.prepare` positions `SPEC-TO-IMPLEMENTATION-GATE` and `SPEC-TO-TESTS-GATE` after a runner prompt commit with the planted commit inside the DIFF_FILE (`yell`, `test_shout_again`); `probe --check` scores a FAIL that quotes the planted text as expected; `record` of that FAIL in the probe repository works (no M0, no G1, `failures` 1, F1 open); the producer's attempt 2 prompt lists F1; the stub's resolution closes it `fixed`; the gate's attempt 2 prompt shows the prior finding with its resolution, ids continue from F2, and the DIFF_FILE is cumulative from the step start (the rewritten `text.py` without `yell`); the second PASS advances the round. Review 3 traced this with the stub only; here it ran on the owner's prose with the planted fixtures.
- Test D's override paths (R5a, R5c, R5d): a plan whose `overrides` names a gate (`SPEC-TO-TESTS-GATE`) skips it with `source: override` while the tests still freeze; override of a pending gate outside a checkpoint skips it at the next `next`; override of the next producer at a review records it, prints the checkpoint again with the note, `approve` resumes, the producer is skipped and nothing is frozen (`tests_frozen_at: None`, `FROZEN_PATHS: []` downstream).
- Test D's delegation paths (R5e, R5f): `delegate --through PLAN-TO-SPEC` at the PLAN-TO-SPEC-GATE review and `start --delegate --through PLAN-TO-SPEC` both leave exactly `[('review', 'CLEANUP')]`; `approval.through` is stored as given.
- The final test's surfacing (R7): `recorded.undefined_new` and the stderr line at `record`; the claims FLAG when the message's counts differ from the files' delta; `status`'s `undefined_tail` and counts; `done`'s tail and counts; HISTORY's per-attempt delta and report (correct when no checkpoint was raised by that attempt).
- The CHECKPOINT entry ordering (R1): the attempt entry precedes the CHECKPOINT entry it raised.
- R3-M2 in the field: test C's CLEANUP changed nothing under the round folder and read the carried flag as the clause says.

## 6. Brittleness to changes in the owner's prose or config

Review 1's, 2's and 3's tables stand; these rows are new or sharpened. "Loud" refuses with a message, "soft" degrades with a warning or a truthful plumbing line, "silent" is the bad kind.

| Owner change | Effect | Kind |
| --- | --- | --- |
| `defaultShares.work.CHAT-TO-PLAN` (the 0.05 floor) | booked at `start` before any plan; whether the plan lists it decides whether the seven later budgets over-commit by that amount (R4-m3) | soft, until the plumbing says which |
| COMMON-OVERVIEW's NEEDS-OWNER sentence ("build on your best assumption meanwhile") when the owner overrides the step or its gate at the question | the assumption is used silently and, with a later gate, misattributed (R4-M2) | silent |
| PLAN-AGENTS-OVERVIEW's "Expect one or two rejections per gated step" with every gate off | vacuous, logged as undefined by both gates-off rounds; nothing mechanical | silent, the owner's to settle |
| SPEC-TO-TESTS-GATE's "For each test: Is it not sensible? Fail." against the fixture's scratch test | the clean seed fails as worded (R4-M3) | fixture only |
| `gatesFraction` "sums to 1 with workFraction" against the all-in spend line | the postmortem's issue 1; the owner's numbers | silent, the owner's to settle |
| TESTS-TO-SUITE-OVERVIEW's "each test" against the file as the unit the runner moves | a one-file suite has no choice; CLARIFICATION filed in the sandbox; nothing mechanical | silent, the owner's to settle |
| A locked-prose sentence that invites an owner to "override" a running step (none today) | unrecorded work of that step is committed unchecked (R4-M1) | silent, costly |

Nothing mechanical matches a phrase of the prose; review 1's statement holds after the fifteen fix commits, and no test added by fix 3 asserts on a sentence of the locked prose (the real-repository sandbox test counts `#` lines only). No edit to a `spec.yaml` file is recommended by this review.

## 7. Notes for the next real-agent runs

**Test D (override, delegate through).**
1. Apply R4-M1 before overriding any step whose agent has already run; until then, override only between `record` and `next`, or right after `next` before spawning, and `record` a finished agent before overriding its step. Never `next --discard` after an override (the override has already committed the work).
2. Overriding a producer whose gate is pending is refused as "already accepted" (R4-m5): override the gate instead, or `record` first. At a `review` the checkpoint's own step cannot be overridden; another override prints the checkpoint again and `approve` with the same quote resumes (DRIVER.md:40, reproduced R5d).
3. At a `question` checkpoint use `answer` or `approve`, not `override`, and never override the gate a question is waiting at, until R4-M2 is applied; otherwise expect a false `<later producer> assumed: ...` line at the next gate that runs.
4. "delegate through PLAN-TO-SPEC" and "delegate through PLAN-TO-SPEC-GATE" skip the same reviews, from the plan, from the command line and at a checkpoint (R5e, R5f); write `--delegate` with `--through` on the command line (R4-m4) and, at a checkpoint, `delegate --through STEP` without any plan edit.
5. A gate named in the plan's `overrides` is skipped with `source: override` and its producer's acceptance effects still happen (the tests froze in R5a); an overridden producer gets none of them.

**Test E (gate effectiveness, retry).**
1. Apply R4-M3 first; decide R4-m6. Until then a FAIL of the SPEC-TO-TESTS-GATE clean seed (or of PLAN-AGENTS-GATE's) judges the fixture: read the findings before concluding anything about the gate.
2. `probe --step <GATE> --seed clean|defect --manual --dir <folder outside any repository>` (a new folder per probe), spawn on the printed `task`, save the final message to `result_file`, then `probe --check <result_file> --dir <folder>`. The gate's budget in the probe is the default share (`$5.0`, `$0.9` for PLAN-AGENTS-GATE on the `$100` fixture quote); pass `--budget` to size it.
3. For the in-round retry, `record` of a FAIL works in the probe repository after the planted commit (E2), so a probe folder can double as the retry fixture: `next` prints the producer's attempt 2 with the finding, and after its `record` the gate's attempt 2 prompt carries the resolution and the cumulative diff.

**The final test (an undefined judgment call).**
1. With review checkpoints on, the message carries "N undefined since the last checkpoint" and the last five lines; with delegation, `recorded.undefined_new` and the stderr lines (R7). At a `record` that raises a `question`, the lines are in the message's tail only (R4-m2).
2. HISTORY's per-attempt "(N undefined since the last checkpoint)" reads 0 on the attempt that raises a checkpoint (R4-m1); read the CHECKPOINT entry's count instead.
3. The claims FLAG (`message claims d/u judgment calls, the files gained fd/fu`) compares the message with the lines appended this run (R4-n6): a fabricated agent that reports its round total on a second attempt earns a false FLAG; one that appends to the wrong file earns a true one.
4. `status` and `done` show the last five lines; `undefined_file` is absolute in every payload; an agent's line need not start with `- ` to be counted (any non-blank line after the header is).
