# Review 3: shackles_harness at fd95394 (after tests A and B)

Reviewer: a fresh Fable 5.1 session, read-only, in a linked worktree. Nothing tracked was modified; every reproduction ran on throwaway repositories built with the project's own fixtures under `%TEMP%` (the script is not part of the repository). This is the first review with two real-agent rounds in hand; it builds on `review-1.md` and `review-2.md` and does not repeat their "verified sound" lists.

## 1. Process

Designed before reading past the entry points, then followed in this order:

1. **The owner's files and the two test reports first, in full.** `spec.yaml`, all 21 owner files, `test-A.md`, `test-B.md`, then the two earlier reviews and `FINAL-PLAN.md`. The test reports were read as evidence of how real agents parse the prompts and docs: every place an agent logged an undefined judgment call, worked around the runner, or misread a document was written down before any code was opened.
2. **The seven post-test-A commits** (`619b0a4` to `7c2486f`) checked against test-A's list 3.1 to 3.10 and deviations 1 and 3: the diff, the tests added for each, and sandbox B's archived prompts, which are the post-fix run.
3. **The four test-B items** judged against the code, each with a reproduction on a fixture repository rather than by reading alone.
4. **The four paths the next real-agent runs will walk**, traced through `DRIVER.md`, the rendered prompts and the checkpoint messages as the driver and the step and gate agents will read them, then through `round.py`: (a) `approve` with review checkpoints and every resume command; (b) `override` of steps and gates, at a checkpoint and outside one; (c) `delegate through STEP` from the plan and from the command line; (d) gate effectiveness through `probe --seed defect --manual` and the six planted fixtures; (e) a fabricated undefined judgment call and every place the runner surfaces it. Nine reproductions (`R1` to `R9` below): seven confirmed a defect or gap, two confirmed the path sound.
5. **Every runner module and every test read**; the suite run in full (166 passed, 8 min 52 s, exit 0, worktree clean afterwards); `doctor` (0 errors) and `render --step CHAT-TO-PLAN --raw` on this worktree.
6. **Docs versus code**, then brittleness to the owner's prose and config.

Severity scale as before: **blocker** = the next phase cannot succeed or would draw a false conclusion with no workaround; **major** = a real defect that costs an agent run, corrupts round records or misleads the driver, with a workaround; **minor** = wrong but cheap; **nit** = cleanliness. Findings that simplify or fix are preferred over findings that add; three suggestions from the sandbox postmortems are recommended *against* below for that reason.

Counts: 0 blocker, 3 major, 10 minor, 7 nit.

## 2. Findings

### Major

**R3-M1 (major) `delegate through STEP` skips a review only when STEP is the gate's name; the producer's name, the natural thing for an owner to say, leaves the checkpoint in place.**
`harness/src/shackles/round.py:210-216` compares `pipeline.index(name) <= pipeline.index(through)` where `name` is the `checkpointsAfter` entry, `PLAN-TO-SPEC-GATE` (index 5). "delegate through PLAN-TO-SPEC" (index 4) therefore fails the test and the review after the spec fires, which is the opposite of the owner's words; "through PLAN-TO-SPEC-GATE" works. The CHAT-TO-PLAN prose says only "no checkpoints up to and including STEP", DRIVER.md:18 repeats it, and nothing tells the driver that STEP must be the gate. The tests (`test_round.py:224-227,239-243`) use the gate name only.
Evidence (R1, fixture repo, `start --delegate --through PLAN-TO-SPEC`, then play):
```
reached: code=10 kind=checkpoint cp=review@PLAN-TO-SPEC-GATE
```
and with `--through PLAN-TO-SPEC-GATE`: `code=0 kind=producer step=SPEC-TO-TESTS`. This is on the path of the next run; a driver who sees the checkpoint fire will conclude delegation is broken again, as test A's did.
Fix (one line): anchor the comparison on the producer, `anchor = pipeline.producer_of(name) or name`, then `pipeline.index(anchor) <= pipeline.index(through)`: "through PLAN-TO-SPEC" gives 4 <= 4, "through PLAN-TO-SPEC-GATE" 4 <= 5, "through PLAN-AGENTS" 4 <= 2 (the review still fires), and CLEANUP anchors on itself. Add `PLAN-TO-SPEC` to the `through` cases in `test_delegation_from_the_plan`, and say in PROCESS.md:86 and DRIVER.md:18 that STEP may name the producer or its gate.

**R3-M2 (major) A producer that edits an earlier, accepted artifact in the round folder is committed and then treated as the owner's out-of-band edit: a wording fix of SPEC.md by CLEANUP sends the round back to SPEC-TO-TESTS.**
Every producer's WRITE_PATHS include the round folder (`prompts.py:141-144`), so `m1_strays` (`checks.py:57-75`) lets `SPEC.md`, `SPEC.json`, `PLAN.json`, `AGENTS-PLAN.json` and `SUITE.json` through, `commit_work` commits them, and the next `next` runs `out_of_band` (`round.py:516-532`): a changed SPEC re-enters at SPEC-TO-TESTS with `round_retries += 1` and the tests unfrozen; a changed PLAN clears the approval and raises the `approval` checkpoint; a changed AGENTS-PLAN.json is read live by `agents_plan()` and silently re-plans every later budget and rung. Nothing in the prompt says the earlier artifacts are frozen. Test B avoided this only because the CLEANUP agent read `round.out_of_band` before deciding what to do with the carried F3/F4 (its undefined judgment call, test-B §9). A cheaper agent applies the gate's own suggestion ("Write 'a phrase with a trailing period and spaces at both ends'") and buys six steps.
Evidence (R2, delegated fixture round, CLEANUP appends one line to SPEC.md, `record`, then `next`):
```
record 0 recorded next_step LANDING warnings []
next code=0 kind=producer step=SPEC-TO-TESTS attempt 2
state step SPEC-TO-TESTS round_retries 1 tests_frozen_at None
HISTORY 'changed out of band': True
```
Fix (about five lines, no new rule for agents to learn): in `record_producer` (`round.py:930-931`) pass the other steps' artifact paths as runner-owned, e.g. `owned_extra=[self.paths[k] for k in ("plan", "agentsPlan", "spec", "specProse", "suite", "postmortem") if OWNER_STEP[k] != step]` with `OWNER_STEP` mapping `specProse` to `PLAN-TO-SPEC` and the rest through `pipeline`; extend `m1_strays` with an `owned_extra=()` parameter joined to `owned` at `checks.py:61`. The edit is then reverted with one M1 finding naming the file, `out_of_band` only ever sees the owner's committed edits (the tree reset already keeps uncommitted ones out), and the producer's own artifact is untouched on a re-run. Add one clause to `producer.txt:18`: "the artifacts of accepted steps are runner-owned after acceptance". Cover it with the R2 scenario.

**R3-M3 (major) In a delegated round an undefined judgment call reaches the owner nowhere: `record` prints counts, not lines, and DRIVER.md never tells the driver to relay them, at `record` or at `done`.**
FINAL-PLAN amendment 8 is implemented for checkpoints, `status`, `done` and HISTORY (`round.py:406-431,812-819`), but `delegate` removes every checkpoint, the `recorded` payload (`round.py:828-829`) carries only `judgment_calls` counts, and DRIVER.md's loop (:26-37) and "After" (:41-42) say nothing about relaying judgment calls; the driver is told to relay only checkpoint messages (:34). Test B's postmortem found it itself: "with no checkpoint, the round's five undefined judgment calls and this flag reached the owner nowhere. This postmortem is the first and only delivery" (sandbox B, POSTMORTEM.md issue 2; CLARIFICATIONS.md line 15). The last planned run fabricates an undefined judgment call "that the harness must surface"; today, in a delegated round, the harness writes it to files the owner does not read and the driver is not told to speak.
Fix (two lines of code, two sentences of doc): add `undefined_new` to the `recorded` payload, the lines the attempt appended (`self.undefined_tail(after["undefined"] - before["undefined"])` when positive), and to the `invalid` payload nothing; in DRIVER.md's loop say "relay `undefined_new` to the owner as it appears, delegated or not: the owner delegated the reviews, not the monitoring", and in "After" say "relay `done`'s `undefined_tail` and counts". Optionally print the same lines on stderr from `finish` (`commands.py:118-124`) so a driver reading the terminal sees them.

### Minor

**R3-m1 (minor) `record --agent RUNG` re-prices the run and nothing says the plan's rung was not honoured; `start --agent`, the tool for a single-model session, is undocumented for drivers.** (test-B item 1)
`round.py:774,797` price at `--agent` and append `(rung X)` to the ledger note whenever the flag is passed, with no comparison to the action's rung (POSTMORTEM-GATE's F5 quoted exactly this); HISTORY gets no FLAG. Reproduced (R7): action rung `max`, `record --agent low` -> `warnings []`, no FLAG line, note `(rung low)`. Two halves: (a) the driver in test B spawned every fallback sub-agent at `model: opus` although DRIVER.md:27 says `model` = `model_alias` and the fallback does take a model per action, so the max and low rungs were never tried; that was the test's own instruction, not a harness defect, but the harness stayed silent about it; (b) `start --agent RUNG` (`commands.py:27`, `round.py:222-225`) forces one rung for every step and would have made the plan and the ledger agree, and DRIVER.md never mentions it.
Fix: one FLAG in `record` when `agent` differs from `self.rung_for(step)[0]` ("ran on rung X, the action named Y"); one sentence in DRIVER.md "What your session has": a session that can run one model only should `start --agent <that rung>` so PLAN-AGENTS plans for it; and drop the `(rung X)` suffix when the rungs match so the note means what the postmortem thought it meant. Do not build the "driver reports it before the round is planned" TODO from sandbox B; `start --agent` already is that.

**R3-m2 (minor) Carried non-blocking findings look like open findings to every later producer, and the prompt's resolution rule reads as though it covers them; two agents logged undefined judgment calls on exactly this.** (test-B item 2)
`producer.txt:15` says "every gate or owner finding id must appear in your resolutions", `:16` then lists `Carried notes and owner answers` with the same `F<n>` ids, `reason` and `suggestion` fields (`prompts.py:195`), and nothing says a carried note is closed. In the runner they are closed: a PASS's findings get status `carried` (`round.py:1116-1119`), `findings_for(..., OPEN)` never returns them, and `apply_resolutions` (`round.py:867-894`) rightly ignores a resolution from another step. So the runner is not defective and F1 to F4 did not "end the round open"; they ended it carried, which is their terminal state. The gap is the prompt. Verdict on the sandbox TODO "let POSTMORTEM close any open finding": do not build it; there is nothing to close, and it adds a resolution path for a state that does not need one.
Fix (one clause in `producer.txt:16`): "Carried notes and owner answers (already accepted with their artifact, or deferred, or the owner's answer; they need no resolution entry; act on one only inside your own WRITE_PATHS, otherwise leave it for POSTMORTEM): ...". With R3-M2 in place, "inside your own WRITE_PATHS" is also enforced.

**R3-m3 (minor) CHAT-TO-PLAN-GATE at 1 leaves no attempt count, HISTORY line or FINDINGS file, so "every gate on" is unverifiable from `status`; the sandbox also strips the comment that says it is mechanical.** (test-B item 4)
`mechanical_loop` (`round.py:594-598`) completes the approval gate with `step_commits` only (R5: `attempts` keys `['CHAT-TO-PLAN']`, HISTORY silent, FINDINGS `.keep` only), while a disabled LLM gate writes a FINDINGS file and a HISTORY line (`skip_gate`). Design-wise the gate is mechanical and PROCESS.md:34 says so; the driver did not see that because `sandbox` rewrites `project.yaml` with `yaml.safe_dump` (`probe.py:192`), which drops every owner comment including "mechanical, run by the runner". The $4.50 budget the report attributes to SPEC-TO-TESTS-GATE (§5.4) is refuted: the archived prompt `PROMPTS/SPEC-TO-TESTS-GATE-1.txt:75` says `$6.75`, the plan's 0.15 share; the driver misread TESTS-TO-SUITE-GATE's line.
Fix (two lines): in the approval branch set `st["attempts"]["CHAT-TO-PLAN-GATE"] = 1` and `self.history("CHAT-TO-PLAN-GATE passed mechanically (PLAN.json valid; approval: <mode> '<words>')")`. For the sandbox, edit the two keys textually or append them, so the owner's comments survive the copy.

**R3-m4 (minor) The PLAN-AGENTS prompt prints a minimum gate share for CHAT-TO-PLAN that the ledger ignores; both real rounds logged an undefined judgment call on it.**
`PLAN-AGENTS.txt:3` renders `{{ project.defaultShares }}` raw, including `gates.CHAT-TO-PLAN: 0.02`, while the same line says shares.gates maps only producers whose gate runs and the step table says CHAT-TO-PLAN's gate never runs. `ledger.shares` (`ledger.py:10-25`) drops it. Round A: "nothing says what shares.gates should hold"; round B: "the prose names a minimum gate share for CHAT-TO-PLAN yet also says shares.gates maps only producers whose gate runs". R2-n4 fixed the step table and PROCESS.md:114, not the printed minimums.
Fix: a `minimum_shares` step-context key for PLAN-AGENTS filtered to the steps present (work: producers not overridden; gates: producers whose LLM gate runs), rendered in place of `project.defaultShares`; four lines in `prompts.step_context`, one token change in the plumbing.

**R3-m5 (minor) `SUITE.raise_with_owner` has no route: the prose says "flag it", the schema has the field, nothing reads it.** (test-B §5.13)
`schemas.py:113` defines it; no other code mentions it. TESTS-TO-SUITE-GATE read it as a flag, not a question, which was right for a DONE. With delegation the item reached the owner only through the postmortem.
Fix, the smaller of two: at TESTS-TO-SUITE's acceptance (`round.py:664-665`) write each item to HISTORY as "flagged for the owner: ..." and append it to `st["carried"]` with `source: "flag"`, so POSTMORTEM and the checkpoint reader see it; or delete the field from the schema and let NEEDS-OWNER be the only channel. Either is a few lines; the first keeps the owner's sentence honest.

**R3-m6 (minor) `override` at a review checkpoint cannot override the checkpoint's own step and does not resume; DRIVER.md does not say `approve` must follow, and the payload does not say it either.**
`override()` refuses the checkpoint's gate as "already accepted" (it is: `complete` set `step_commits` before raising), and any other override returns the same checkpoint with exit 10 (`round.py:1144-1147`); PROCESS.md:88 documents it, DRIVER.md:34 says "run the matching command" and stop. Reproduced (R4): `override --steps PLAN-TO-SPEC-GATE` -> exit 2 "already accepted"; `override --steps SPEC-TO-TESTS-GATE` -> exit 10, the checkpoint message again; `approve` -> resumed. The next run exercises exactly this.
Fix: one sentence in DRIVER.md's loop ("`override` at a review checkpoint records the overrides and prints the checkpoint again: follow it with `approve` and the same quote") and one note in the override payload when the checkpoint stands (`self.notes.append("overrides recorded; the checkpoint at X stands: approve to resume")`).

**R3-m7 (minor) DRIVER.md:32 says a `record` exit 10 means "the attempt was accepted and committed"; at `question`, `blocked`, `failure-limit` and `infra` it is committed but not accepted, and `approve` re-runs the producer.**
`record_producer` raises `question` and `blocked` before `accept_producer` (`round.py:972-983,1061-1066`); `approve` at either becomes `answer("proceed on your stated assumption")` (`round.py:1192-1194`), which adds O1 and re-runs the producer at the next attempt (R8: `approve` -> `step PLAN-AGENTS`, `next` -> attempt 2 with O1). PROCESS.md:85 is right; DRIVER.md:32 is not, and a driver told the attempt was accepted will not expect to spawn the same step again (one paid run whose whole content is "carry on"; `test_outcomes.py:122-129` pins this design).
Fix: DRIVER.md:32 -> "the review after a `checkpointsAfter` step follows an accepted attempt; a question, blocked, failure-limit or infra checkpoint leaves the attempt pending, and `approve` or `answer` re-runs the producer with the answer as finding O1". If the re-run at `question` is judged too expensive, the smaller change is at `approve`: with the gate off, accept the attempt as built and log the assumption as an owner-approved defined call; with the gate on, re-run only the gate. Not recommended now: it is routing, not a defect.

**R3-m8 (minor) A producer's `judgment_calls` counts are validated and then ignored; a message that claims calls the files do not show is silent.**
`record` counts the files (`round.py:800,812-814`) and never compares. Reproduced (R3): message `{"defined": 2, "undefined": 3}`, files unchanged -> `counted {'defined': 0, 'undefined': 0}`, no warning, no HISTORY line. The fabricated-call run is the case where an agent reports a call and forgets the file, or the reverse.
Fix (three lines): when the message's counts (ints, or list lengths) differ from the file delta, `self.flag(f"{step} attempt {attempt}: message claims {d}/{u} judgment calls, the files gained {fd}/{fu}")`.

**R3-m9 (minor) `start --delegate` satisfies CHAT-TO-PLAN-GATE without any owner words.**
`validate_plan` (`round.py:1309`) requires `approval` only when `not delegate`; with the flag and no `approval` in the plan the round starts with `{"mode": "delegated", "through": None, "source": "plan"}`, no `words`, no verification and no FLAG (both flag branches at `:1419-1422` test `words`). The gate's own sentence in the CHAT-TO-PLAN prompt says start "requires the owner's word recorded in it".
Fix: drop `and not delegate` (the plan must carry the words when the gate is on; `--delegate` still overrides the mode). `probe` and `sandbox` are unaffected (their CHAT-TO-PLAN-GATE is 0).

**R3-m10 (minor) Three loop facts the driver learns only by surprise: a `next` can land the round, the tool's annotation is appended as well as prefixed, and `done` carries the judgment calls.** (test-B §5.6, §5.7)
DRIVER.md:28 says "a tool-side annotation prefixed to the message"; the Agent tool appends `agentId: ...` (extraction copes, `schemas.extract_json`). DRIVER.md:26-37 never says LANDING runs inside `next` and that the JSON returned is already the POSTMORTEM action, with the landing visible only as `living_usd` and a stderr note.
Fix: two sentences in DRIVER.md (the `done` half is R3-M3).

### Nit

**R3-n1 (nit)** `round.py:1093` appends `(via runner, STEP-N)` to every gate judgment line; a gate that copied the file's format gets it twice (R6, and sandbox B line 5). Skip the suffix when the line already ends with `(via runner, ...)`.
**R3-n2 (nit)** `status` reports `"worktree": self.root` (`round.py:1280`), which is the main checkout when run there after `git pull`; call the key `root`.
**R3-n3 (nit)** `spec accept` prints `"commit": <HEAD before the acceptance was committed>` (`cli.py:53-55`, `specguard.py:71-86`), and `spec diff` later diffs against that commit, so it shows the accepted change itself again. Name the field `head_at_accept` and say in PROCESS.md that the acceptance lands in the next commit.
**R3-n4 (nit)** `record --tokens` and `--agent` have no help text (`commands.py:38-39`); the resume hint `delegate [--through STEP] --quote "<words>"` (`round.py:23`) is not a runnable line.
**R3-n5 (nit)** HISTORY writes the CHECKPOINT entry before the attempt entry that raised it (`raise_checkpoint` runs inside `record_gate`/`record_producer`, the attempt line at `round.py:818`); both sandboxes show "CHECKPOINT review at CLEANUP" above "CLEANUP attempt 1: DONE".
**R3-n6 (nit)** `retry_cost` in a gate's prompt uses the gate's rung `spawnCost`, not the producer's (`round.py:326`): sandbox B's SPEC-TO-IMPLEMENTATION prompt says a FAIL costs $24.12 (low, 0.02) and its gate's prompt $24.16 (medium, 0.06); cents, but the two prompts disagree.
**R3-n7 (nit)** PROCESS.md:85: `approve` at `blocked` "means proceed on your stated assumption"; a BLOCKED producer stated no assumption, it asked what to narrow. Say `answer --text` or `override` is the natural resume there.

### Verdicts on the four test-B items

1. **Silent rung substitution**: a real gap, small fix (R3-m1). The ledger was right; the plan was not honoured and nothing said so. The model deviation itself was the test protocol (the fallback takes a model per action; DRIVER.md:27 already says `model` = `model_alias`), and `start --agent` is the existing tool for a one-model session.
2. **Carried findings "cannot be closed"**: not a runner defect. A PASS's non-blocking findings are closed as `carried` and are information for later steps; the prompt's wording made them look open (R3-m2). Do not build the postmortem's proposed close path.
3. **The ledger pays to delete tests**: the owner's numbers and prose (COMMON-PROJECT's refund on removal against TESTS-TO-SUITE-OVERVIEW's cost-benefit rule); `ledger.living_charge` (`ledger.py:108-139`) implements the refund exactly as written and the archive move is a removal from the living paths. No harness change; the CLARIFICATION the postmortem filed is the right channel. If the owner wants a guard, the smallest is a few-line exemption in `living_charge` for the files SUITE.json archived (the runner knows them), which is theirs to decide.
4. **CHAT-TO-PLAN-GATE leaves no trace**: design (mechanical, PROCESS.md:34) plus a small trace gap and the sandbox's comment stripping (R3-m3). The $4.50 budget is refuted by the archived prompt.

## 3. The seven post-test-A fixes

All present, each covered by a test, and sandbox B (the post-fix run) shows them working:
- **3.1 delegation** (`619b0a4`): `not through` in `delegated_through`, the schema accepts null, `--through` of an unknown step refused at `start` and at a checkpoint, the CHAT-TO-PLAN prompt says to omit `through`; round B ran delegated with `"through"` absent and skipped both reviews. R3-M1 is the residual gap.
- **3.2 the spawn path** (`6b82c29`): the cwd heuristic is gone; the action carries `fallback_agent_type`, `task` and `rungs`; `doctor.agent_definitions` says what it measures; `record --agent` refuses non-roster names. Round B's driver followed it (13/13 spawns, 8 `--agent medium`).
- **3.3 S2 paths** (`0bcc8fa`): `Config.harness_rel`, the prompt prints the changed tests HARNESS-relative on their own line (`PROMPTS/TESTS-TO-SUITE-1.txt:103` in sandbox B: `["../tests/toy/test_text.py"]`), the S2 message and L1's list use the same form, the stub copies the printed list, and "advances to None" is gone. Round B's TESTS-TO-SUITE passed S2 at attempt 1 with the printed path.
- **3.4, 3.10 the sandbox** (`2d1387b`): `sandbox --help` and its JSON name the toy's content; `settings.json` copied; `core.longpaths` set on both repositories; `doctor` warns when it is off (it warned on this worktree, correctly).
- **3.5 to 3.9** (`9b282a9`): HISTORY marks a cut note and names the result file (visible in sandbox B); `status` stops previewing the living charge after landing; `start` prints its FLAGs as `warnings` (round B: `"warnings": ["approval words recorded unverified: no owner log"]`); PROCESS.md says `record` rewrites the result file; the two policy questions went to CLARIFICATIONS.
- **DRIVER.md** (`cd2be94`, `7c2486f`): the session section, approval filling, the gate-flip sequence, spawn and record rules, exit codes. Round B's driver reports no ambiguity in the gate-flip sequence ("under a minute"). R3-m6, R3-m7 and R3-m10 are what the second run then found missing.

## 4. Verified and found sound

- Full suite: 166 passed, exit 0, 8 min 52 s; the worktree is clean afterwards (`git status --short` empty). `doctor` on this worktree: 0 errors, 2 warnings (owner log missing; `core.longpaths` off in this checkout), all 14 prompts render with no unresolved tokens (1.7k to 3.2k tokens), definitions match the roster, `claude.exe` 2.1.266 found.
- The rendered prompts of sandbox B, read as the agents did: contract lines absolute; the gate's `DIFF_FILE` holds only the artifact (248 and 544 bytes); `Ids continue from F5` after four carried findings; carried notes carried to every later producer and to POSTMORTEM; budgets match the accepted AGENTS-PLAN for every step and gate ($3.15, $1.35, $21, $12.15, $15.75, $6.75, $23.10, $12.15, $8.40, $4.50, $12.60, $15.75, $8.10); the retry cost the gate is shown equals the producer's budget plus spawn plus driver (with the gate's rung's spawn, R3-n6).
- Extraction with prose before the JSON and with the tool's `agentId` suffix after it (2 of 13 messages in round B, and every message in both rounds recorded valid at attempt 1); the top-level-object rule from R2-M1 (`test_extract_json_prefers_the_top_level_object_over_nested_ones`).
- Routing for the next runs, re-traced and reproduced: review checkpoints raised from `record` (gates on) and from `next` (gates off) with the two-path artifact line; `approve` at review re-hashing the inputs; `answer` at review re-opening the producer and its gate; `delegate` at a review skipping the later one; `override` outside a checkpoint and at `failure-limit` (`test_outcomes.py:198-208`), of PLAN-AGENTS falling back to `defaultShares`, of SPEC-TO-TESTS freezing nothing, of TESTS-TO-SUITE keeping every test, of CLEANUP with the review still raised; gate FAIL -> producer re-run with the findings -> gate again with the resolutions and a cumulative diff (R9); NEEDS-OWNER in all four combinations; the `question` checkpoint's message carrying question and assumption.
- Gate effectiveness tooling: `probe --seed defect --manual` positions the gate after a runner prompt commit with the planted commit inside the gate's diff, M0 does not fire on it, `--check` scores verdict and planted quote (`test_probe.py:27-44`); the six fixtures load and each plants something the gate prose names (beyond the plan, uncovered component, outside the spec, archived regression test, untraced issue, misallocated budget).
- Surfacing of judgment calls where a checkpoint exists: HISTORY per attempt with the delta and the last five undefined lines and the absolute path; `status`; every checkpoint message ("N undefined since the last checkpoint"); `done`. R3-M3 covers the delegated case.
- Owner log path for a session started in the sandbox repository: the hook resolves the main checkout from a worktree, the round slice starts at `presented_at`, quotes are verified against lines dated after the checkpoint, `[via driver]` lines land in the slice (`test_owner.py`, `test_concurrency.py:145`).
- Landing and concurrency unchanged since R2 and still green (claims, fence, moved main, conflicts converging through the merge attempt, hand merges, L2 re-entry, union merge of the index, `sync_main`).
- The provisional baseline acceptance (R2-M2) keeps M5 and L2 green on the branch and is re-accepted by the owner's `approve` (`test_outcomes.py:377-403`).

## 5. Brittleness to changes in the owner's prose or config

Review 1's and 2's tables stand; these rows are new or sharpened. "Loud" refuses with a message, "soft" degrades with a warning or a truthful plumbing line, "silent" is the bad kind.

| Owner change | Effect | Kind |
| --- | --- | --- |
| The owner's phrasing of "delegate through STEP" naming a producer rather than its gate | the review after that producer's gate still fires (R3-M1) | silent |
| Any prose that invites a later step to "clean up" or "fix" an earlier artifact (CLEANUP-OVERVIEW is one sentence and could say so) | the edit is committed and re-enters the round as an out-of-band edit (R3-M2) | silent, costly |
| "Checkpoint after this step, with the owner." in PLAN-TO-SPEC-OVERVIEW and CLEANUP-OVERVIEW, rendered in a delegated round | the prose says a checkpoint follows, the plumbing line says the round advances; agents in round B trusted the plumbing | soft |
| `defaultShares.gates.CHAT-TO-PLAN` (0.02 today) | printed as a minimum, ignored by the ledger; an undefined judgment call every round until R3-m4 | silent, recurring |
| PLAN-AGENTS-OVERVIEW's "Expect one or two rejections per gated step and size for them" | a share is a per-run target re-issued on every retry; F1 in round B, a CLARIFICATION is filed; nothing mechanical to fix | silent, the owner's to settle |
| TESTS-TO-SUITE-OVERVIEW's "flag it" | no route for the flag (R3-m5) | silent |
| COMMON-PROJECT's refund on removal against archiving a test file | the ledger pays for archiving; a CLARIFICATION is filed | silent, by the owner's numbers |
| `livingSourcePaths` including `src/` on the real repository | the runner is living code: a CLEANUP edit of `src/shackles/` runs the edited runner for the rest of the round (R2, still true) | silent |
| Comments in `project.yaml` (e.g. "mechanical, run by the runner") | lost in the sandbox copy (`yaml.safe_dump`), so a sandbox postmortem quoting "owner words" from `project.yaml` quotes a comment-stripped file | sandbox only |
| The owner's word typed with different case or punctuation than the driver quotes | `verify_quote` normalizes whitespace only; the command is refused until `--unverified` | loud |
| `checkpointsAfter` versus the "Checkpoint after this step" sentences | still a runner default mirroring the prose by hand | silent, documented |

Nothing mechanical matches a phrase of the prose; R1's statement holds after the seven fix commits. No edit to a `spec.yaml` file is recommended by this review.

## 6. Notes for the next real-agent runs

1. Apply R3-M1 before the "delegate through STEP" run, or use the gate's name in the plan's `through`.
2. Apply R3-M2 before any run whose agents see carried findings on SPEC.md (every gates-on run does); until then expect a possible six-step re-entry from a well-meaning wording fix.
3. For the fabricated undefined judgment call: with review checkpoints the message carries the lines; delegated, read `done`'s `undefined_tail` and HISTORY, and relay them (R3-M3).
4. At a review checkpoint, `override` of later steps prints the checkpoint again; `approve` with the same quote resumes (R3-m6). `approve` at a `question` re-runs the producer (R3-m7).
5. Start the driving session in the sandbox repository to get the agent definitions and the hook; then the plan's rungs run as planned and every quote is verified. If the session is elsewhere, pass `model` = `model_alias` per action (the fallback takes it), or `start --agent <rung>` for a one-model session (R3-m1).
6. For gate effectiveness use `probe --step <GATE> --seed defect --manual --dir <folder outside any repository>`, spawn on the printed `task`, save to `result_file`, then `probe --check <result_file> --dir <folder>`; a clean seed must PASS and a defect seed must FAIL with the planted text quoted.
