# Final report to the owner: the bootstrap of shackles_harness

Written by the coordinating session that continued from `bootstrap/HANDOFF.md` (the second coordinating session; the first built the harness, ran tests A and B and review 3). Everything described here is committed on `claude/bootstrap` and `main`, which point at the same commit and are pushed.

## 1. One agent-made edit to the owner's files, flagged

Exactly one agent-made edit to a file `spec.yaml` lists exists in the whole history: commit `9a13bb2`, two one-token placeholder renames. Two prose files referenced `project.ownerReviewCostPerWord`, which `harness/project.yaml` does not define; each token was replaced by the owner's own, more specific key. Its baseline was re-accepted in the following commit. No fixer in this session touched an owner file; `git log -- SPEC.md harness/AGENTS.md harness/project.yaml harness/subAgents.yaml harness/locked_prose spec.yaml` lists only the owner's own commits (`9242842`, `cf065eb`, `2db4ecf`) and this one.

```diff
diff --git a/harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt b/harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
--- a/harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
+++ b/harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
@@ -3,7 +3,7 @@
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
diff --git a/harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt b/harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
--- a/harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
+++ b/harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
@@ -8,7 +8,7 @@
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```

## 2. Where things stand

- The harness is implemented, reviewed five times and exercised by six real-agent tests. The suite is `py -3.13 -m pytest` from the repository root: 184 tests, all passing, about 10 minutes (164 of 166 passed when this session started; fixes 3, 4 and 5 added 18 tests and repaired the two failures).
- `doctor` reports 0 errors and two warnings on the real checkout: the owner log does not exist yet (the hook creates it on the first prompt of a session started in this repository) and `git config core.longpaths` is not set there. Set it before the first real round.
- The trail is under `bootstrap/`: six plans, two merges, `FINAL-PLAN.md`, reviews 1 to 5, fix reports 3 to 5, test reports A to F, and this file.

## 3. The real-agent tests

Every round ran in a sandbox (`run.py sandbox --dir`, a local bare origin) driven by an Opus chat session that followed `harness/docs/DRIVER.md` literally and spawned one `general-purpose` Opus sub-agent per action. Ledger dollars are the harness's own cost model, not API spend; the token column is what the runs actually consumed.

| Test | Configuration | Outcome | Step-agent tokens | Ledger |
| --- | --- | --- | --- | --- |
| A | `delegate`, gates off | reached `done` | 845,901 | see test-A.md |
| B | `delegate`, all seven gates on | reached `done`; six LLM gates, six PASS | 1,487,730 | $86.19 of $150 |
| C | `approve`, gates off; one `question`, two `review` checkpoints | reached `done`; all three resumed (`answer`, `approve`) | 903,316 | $112.26 of $120 |
| D, round 1 | `delegate through PLAN-TO-SPEC` from the plan, gates on; overrides of a pending gate, of a producer, and of a later gate at a review | reached `done`; every override behaved as documented | 1,010,545 | $94.42 of $150 |
| D, round 2 | `--delegate --through PLAN-TO-SPEC-GATE` from the command line, gates off | reached `done`; a NEEDS-OWNER was settled by the runner instead of stopping (fixed as R5-M1) | 864,973 | $107.55 of $120 |
| E | six gates, clean and planted seeds through `probe --manual`; the retry path after a real FAIL | 12 of 12 cells as expected; both retry paths passed at attempt 2 with the findings, resolutions and cumulative diff carried | 1,214,263 | n/a |
| F | `delegate`, gates off; a plan with one detail to decide and one to ask | reached `done`; the undefined call surfaced at `record`, the checkpoint, `status`, HISTORY, `done` and the file (7 of 7); the `question` fired in a delegated round | 851,918 | $114.43 of $130 |

Gate effectiveness, from test E: every clean seed PASSed, every planted defect FAILed with the planted text quoted, on Opus gates; the printed probe rung is `max`, which the drivers could not run.

## 4. The review and fix cycle since the handoff

| Step | Result |
| --- | --- |
| Fix 3 (after review 3 and tests A, B) | 15 commits; the sandbox builder now copies `spec.yaml` and every file it lists; 3 majors, 10 minors, 7 nits fixed; 176 tests |
| Review 4 (after test C) | 0 blocker, 3 major, 8 minor, 10 nit |
| Fix 4 | 12 commits; 180 tests |
| Review 5 (after test D) | 0 blocker, 4 major, 9 minor, 7 nit |
| Fix 5 | 9 commits; 184 tests |

The majors, in one line each: delegate-through anchored on the gate's name only; a producer's edit of an earlier artifact re-entering the round as an owner edit; undefined judgment calls unseen in delegated rounds; `override` committing unrecorded work unchecked (twice, the pending step and then any other); a stale question misattributed after an override; an unpassable clean probe seed; a NEEDS-OWNER settled silently in a delegated round against `SPEC.md`; a refused owner command leaving the tree dirty; probe scoring that missed a correct FAIL quoting the other half of a plant.

## 5. Findings the fixers skipped or left unbuilt, with the reason

Each reviewer ruled on suggestions from the sandbox postmortems and the test reports; the fixers followed those verdicts. Detail is in `bootstrap/fixes/fix-3.md`, `fix-4.md` and `fix-5.md`, section "Items".

- Agents putting prose before the final JSON (test B): skipped; extraction coped in every one of about 60 messages, a stronger wrapper is a guess.
- The ledger paying to archive a test file (test B): no harness change; the owner's numbers (COMMON-PROJECT's refund on removal against TESTS-TO-SUITE-OVERVIEW's cost-benefit rule); a `living_charge` exemption is the owner's to decide.
- A close path for carried non-blocking findings (test B postmortem): not built; a PASS's findings are closed as `carried`, the prompt now says so.
- "The driver reports its model before the round is planned" (test B postmortem): not built; `start --agent <rung>` is that.
- A `cleanupPaths` key, a per-test archive unit, an `--agent` hint on the printed `start` line, a POSTMORTEM close path (test C): not built per review 4.
- Step budgets partition the whole quote while the same quote also pays owner, living and time (test C postmortem): the owner's question; unchanged.
- `retry_cost` from actual spend, a coverage line, undefined calls on skip lines, OWNER.log de-duplication, reordering TESTS-TO-SUITE, a fuller pre-landing review, `through` at settlement, budgets over the remaining quote (test D): not built per review 5.
- R5-n4 was fixed but its DRIVER.md sentence landed in the R5-M1 commit, whose subject omits the id.

## 6. Questions the rounds raised for the owner

These reached CLARIFICATIONS.md in the sandbox rounds and were judged the owner's to settle, not harness defects: whether archiving a test file should earn the ledger's refund; what "expect one or two rejections per gated step and size for them" means when a share is a per-run target re-issued on every retry; "one unit test" against "exhaust edge cases, within reason"; and whether step budgets should partition the whole quote when the quote also pays the owner, living and time charges.

## 7. Facts about the build the owner should know

- All six planners independently proposed simulated agents for the test suite; the stub agent carries the suite and no test spawns a real agent.
- The plans' probe ladder (the stub suite, per-step real-agent probes with planted defects, sandbox rounds) was adopted as the documented testing loop in `harness/docs/TESTING.md`, alongside the owner's end-to-end runs (Level 3).
- The standalone Claude CLI on this machine is not logged in (per the first session's check; `doctor` finds `claude.exe` 2.1.266), so headless mode is stub-verified only; `claude auth login` fixes it and `doctor --probe-cli` then confirms.
- `.claude/settings.json` in the repository adds a prompt hook that logs the owner's chat lines to the gitignored `harness/OWNER.log`; the runner verifies quoted owner words against it. It registers only for a session started in this repository.
- Three generic agent definitions were added under `C:\Users\twolf\.claude\agents\`: `fable-max.md`, `opus-high.md`, `opus-max-generic.md`. The per-rung `shackles-producer-<rung>` and `shackles-gate-<rung>` definitions live in the repository's `.claude/agents/` and register only for a session started there.
- Every agent worktree cut by the Agent tool was based on the remote branch, not the local one; each sub-agent was told to fast-forward first and every report records the commit it tested.

## 8. Cost of this session's coordination

Sub-agent tokens, excluding the step agents counted in section 3: fixer 3 416,710; test-C driver 296,236; review 4 538,159; fixer 4 405,119; test-D driver 409,825; review 5 568,534; fixer 5 395,381; test-E driver 284,977; test-F driver 266,117. Total about 3.58 million, over about nine hours of wall clock.

## 9. What is next

Level 3 of `harness/docs/TESTING.md`: the owner's tiny task on the real repository, driven from a session started in `C:\Users\twolf\Claude\shackles_harness` so the definitions and the hook register, after `git config core.longpaths true` there. The `SPEC.md` architecture lines were honoured by every fix; nothing mechanical matches a phrase of the locked prose.
