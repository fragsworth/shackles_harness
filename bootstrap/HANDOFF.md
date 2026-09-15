# Handoff: refactor the runner to the owner's files

Written 2026-09-14 by the coordinating session. It supersedes the bootstrap handoff kept below the rule.

## State

- The target is the owner's files as of commit 94b73e3 on `claude/bootstrap`: `spec.yaml`, `SPEC.md`, `harness/AGENTS.md`, `harness/project.yaml`, `harness/subAgents.yaml`, `harness/locked_prose/*`. They are the spec. The code, the derived docs (`harness/docs/*`, `harness/INDEX.md`, `CLAUDE.md`) and the tests describe the old behaviour and are not evidence of the owner's intent.
- 94b73e3 carries the owner's last three edits: a judgment call is now "any choice that lands in your finished work that you are not confident in making correctly for any reason"; the overhead comment in subAgents.yaml lost "should be considered in budgets"; the vision now reads "tracks and distinguishes judgment calls made by agents, reminding them of the big picture whenever they have to make them". PLAN.md was written against 20ed0df and adjusted for these; D35 in JUDGMENT-CALLS.md is the one addition the new vision made.
- `claude/bootstrap` is ahead of origin and unpushed; `main`, local and origin, is at 6cbfc97, the end of the bootstrap. The owner promotes main.
- Known defect in the owner's files, for the owner to fix: `spec.yaml` spells the roster file `harness/subAgetns.yaml`.
- `doctor` at 20ed0df, unchanged by the later edits: three errors (spec file missing `harness/subAgetns.yaml`; spec file missing `harness/locked_prose/*`, since globs are unsupported; spec drift since the accepted baseline) and five warnings (unknown prose file CHECKPOINT-OVERVIEW.txt; owner log missing in this checkout; `core.longpaths` not true; the words UPSTREAM and PASS absent from the prose). The suite last ran before 20ed0df: 8 of 184 failed, all from the glob (test_spec_baseline x2, test_spec_structure x3, test_probe x3). Expect the spelling to add failures until it is fixed.

## Read, in order

1. `bootstrap/refactor/PLAN.md`: what the harness does after the change, one page.
2. `bootstrap/refactor/JUDGMENT-CALLS.md`: the reading behind each sentence of the plan; D for defined, U for undefined.
3. The owner's files, in full.
4. `bootstrap/FINAL-REPORT.md` for how the bootstrap left the code, when needed.

## Rules

- The files `spec.yaml` lists are the owner's. No agent edits them, not even minimally; a needed change is a question for the owner with the exact text proposed. This replaces the bootstrap-era rule of a minimal flagged edit.
- Nothing mechanical may depend on the wording of the locked prose; the mechanics tests run on the generated fixture spec; a test that enforces a sentence of the owner's quotes that sentence in its docstring.
- Code names follow the owner's keys; there is no translation layer.
- One builder at a time, in a worktree under `.claude/worktrees` cut as `fragsworth/machines/TOM-HOME-PC/AGENT-COORDINATION.md` says; never a second agent in the main checkout.
- Each slice ends with `doctor` clean on the owner's files and the suite green, one commit per slice on `claude/bootstrap`; push `claude/bootstrap` only after a passing review or at a pause; the owner promotes `main`.
- Real-agent rounds only in a sandbox made by `run.py sandbox --dir`, driven from a session started inside the sandbox repo so the owner-log hook is live.
- A builder that finds a sentence of the owner's that two readings still fit stops and asks; it does not choose.

## Sequence

The six slices of PLAN.md, in order: owner files and config; step table and checkpoints; ledger; owner interaction and findings; judgment-call tooling and the step-end turn; docs regenerated and the stub extended. A reviewer against the owner's files after slice two and after slice six. Then the sandbox round with real agents and checkpoints on. Then the owner: fix the spelling, `spec accept`, commit, push, promote `main`.

## Settled with the owner, 2026-09-14

Asked whether the open readings were obvious under the vision, the owner ruled, and PLAN.md and JUDGMENT-CALLS.md carry the result: the driver overhead is booked per recorded attempt and once at start (D18); wall clock is measured at record in both modes and a breach pauses the round, while turns can be capped only in headless runs (D22); rejections by the mechanical checks count toward maxTurnsPerGate alongside gate FAILs (D21); the CHAT-TO-PLAN flag is inert and the approval word always required (D9); the quote includes the planner's living estimate and the fractions split the rest (D14); a run with no measurement books the spawn floor with a flag (U2). Nothing is open with the owner. A builder that finds a new ambiguity stops and asks.

---

## Superseded: the bootstrap handoff of 2026-09-13

The eight remaining steps of the previous handoff are done: fix 3, test C, review 4, fix 4, test D, review 5, fix 5, test E, the final test (F) and the final report. Read `bootstrap/FINAL-REPORT.md` for the state, the one flagged spec edit, the test results and the skipped findings. `claude/bootstrap` and `main` point at the same commit and are pushed.

Nothing is pending. The suite (`py -3.13 -m pytest`, about 10 minutes) passes in full; `doctor` reports 0 errors. What follows is the owner's: Level 3 of `harness/docs/TESTING.md`, a tiny task on the real repository from a session started in this checkout, after `git config core.longpaths true` there.

Rules that still apply to any later agent session here: the files `spec.yaml` lists are the owner's (smallest edit, own commit with the diff in the body, baseline re-accepted in the next commit, flagged loudly); nothing mechanical may depend on the wording of the locked prose; one sub-agent at a time in a worktree, fast-forwarded to the local `claude/bootstrap` before it reads anything; push only `main` and `claude/bootstrap`, after a passing review or at a pause; real-agent rounds only in a sandbox made by `run.py sandbox --dir`.
