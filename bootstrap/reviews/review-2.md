# Review 2: shackles_harness at 6e98e69

Reviewer: a fresh Fable 5.1 session, read-only, in a linked worktree. Nothing tracked was modified; every reproduction ran on throwaway repositories built with the project's own fixtures under `%TEMP%` (the scripts are not part of the repository). This is the last review before real-agent testing; it builds on `review-1.md` and does not repeat that review's "verified sound" list.

## 1. Process

Designed before reading past the entry points, then followed in this order:

1. **The two fix commits first.** Read `6086792` and `6e98e69` against every R1 finding (M1-M7, m1-m11, n1-n5; m12 skipped by agreement): is each fix present, correct, complete, and does it introduce anything new? The M0 rework (`runner_head`) and the merge-attempt rework (abort and re-establish) got a full re-trace because both changed behaviour beyond the finding.
2. **The driver path as the next phase will walk it**, on this worktree and on fixture repositories: `doctor`, `render --step CHAT-TO-PLAN --raw`, a producer prompt and a gate prompt on the fixture round (`PLAN-AGENTS`, `SPEC-TO-IMPLEMENTATION-GATE`), read as the driver and the step and gate agents would read them; `sandbox`; `start` in worktree mode; the `next`/spawn/`record` loop; every checkpoint's resume commands; `done`. Everything that would mislead that driver or waste an agent run was ranked first.
3. **The record path with real-agent messages in mind.** `schemas.extract_json`, `validate`, `normalize_findings`, `record`, `record_producer`, `record_gate`, `apply_resolutions`, the checks and their order, with the question "what does a plausible real message do here that the stub never sends?".
4. **State machine and landing** (`round.py`, `landing.py`, `checks.py`, `ledger.py`) for what R1 missed: every path that creates a non-runner commit, every path that leaves state behind (`pending_question`, `merge_pending`, `resume_step`), every owner command at every checkpoint kind, and the self-hosting case where the repository under development is the harness itself.
5. **The suite**: ran it in full (155 passed, exit 0, worktree clean afterwards, no template folders left in `%TEMP%` by this run), then read every test for what the stub cannot send and what a real repository's suite would do differently from the toy's.
6. **Docs versus code**, plan deviations, brittleness to the owner's files.

Every suspicion that survived reading was reproduced with a script (eight reproductions: seven confirmed, one refuted and refined). Severity scale as in review 1: **blocker** = the next phase cannot succeed or would draw a false conclusion with no workaround; **major** = a real defect that costs an agent run, corrupts round records or misleads the driver, with a workaround; **minor** = wrong but cheap; **nit** = cleanliness.

Counts: 0 blocker, 2 major, 7 minor, 7 nit.

## 2. Findings

### Major

**R2-M1 (major) A final message with prose around the JSON is rejected whenever it carries `resolutions`, `rulings` or `needs_owner`: the extractor returns the nested object.**
`harness/src/shackles/schemas.py:221-229` scans the balanced `{...}` objects **from the last opening brace backwards** and returns the first dict that has a `status` or `verdict` key. Every entry of `resolutions` and `rulings`, and `needs_owner`, is a dict with a `status` key and starts *after* the outer object's brace, so it wins. The whole-message and fenced paths (`:207-220`) are fine; the defect hits exactly the messages the docs promise to tolerate (PROCESS.md:66 "the last balanced object"; R1's note 5 to the driver "extra prose around the JSON is tolerated") and exactly the attempts that matter: a producer after a gate FAIL (it must list resolutions) and a gate ruling on a dispute or a question.
Evidence (reproduction; then the same message through `record` at PLAN-AGENTS attempt 2 after a gate FAIL):
```
extracted: {"status": "fixed", "reason": "r"}
RESULT errors: ["RESULT: status should be one of DONE, NEEDS-OWNER, UPSTREAM, BLOCKED, got 'fixed'"]
gate extracted: {"status": "withdrawn", "quote": "q"}
FINDINGS errors: ['FINDINGS: $ missing required key verdict', 'FINDINGS: $ missing required key findings']
record code: 2 kind: invalid errors: ["RESULT: status should be one of ..., got 'fixed'"] | infra_errors: {'PLAN-AGENTS': 1}
```
The cost is a full producer rerun per occurrence (for a code step its work is reverted, R1-m12 as accepted) and, after `infraRetries`, an `infra` checkpoint blamed on the agent. The suite misses it because the stub's `prose_wrapped` mode runs at PLAN-TO-SPEC attempt 1 with `resolutions: {}`.
Fix (`schemas.py:221-229`, four lines): among the balanced objects that carry `status` or `verdict`, return the **longest** one (the outer object always contains its nested ones), e.g. collect `(end - start, obj)` over `starts` in forward order and return the max; keep the final any-dict fallback. Add the stub message of the reproduction (`prose_wrapped` at a producer attempt with a non-empty `resolutions`, and a gate with `rulings`) to `test_schemas.py`.

**R2-M2 (major) On the real repository a round that edits a spec file cannot pass CLEANUP: M5 runs the permanent suite, whose baseline guard is red until the owner approves at a checkpoint that comes after CLEANUP.**
`suiteCommand` (`config.py:77`, not overridden by `project.yaml`) runs `harness/tests`, which includes `test_spec_baseline.py::test_spec_files_unchanged_since_baseline` (`:19-25`), reading the worktree's own baseline against its spec files. An in-round spec edit is kept by design (E1, `round.py:880-887`) and the baseline is accepted only by the owner's `approve` at the `spec-edit` checkpoint (`round.py:1126-1128`), which `landing_step` raises **after** CLEANUP (`:695-698`). So at CLEANUP `m5_suite` (`:925-926`, `checks.py:123-125`) is red with the guard's own message telling the agent to run `spec accept`; if it does, the baseline files under `harness/archives/` are outside CLEANUP's write paths (`prompts.py:136-138`) and M1 reverts them. The round loops to `maxFailuresBeforeStop`, then `failure-limit`, and `approve` there only resets the count. `abandon` or `override --steps CLEANUP` are the ways out; L2 at LANDING is fine because `approve` at `spec-edit` accepts the baseline first.
Evidence (fixture repo whose `suiteCommand` is the baseline guard's check, the stub edits `COMMON-OVERVIEW.txt` at SPEC-TO-IMPLEMENTATION, then CLEANUP twice, the second time after the agent ran `spec accept`):
```
CLEANUP attempt 1 mechanical: ['M5'] | BASELINE changed: harness/locked_prose/COMMON-OVERVIEW.txt
spec accept code: 0 | dirty:  M harness/archives/spec-baseline.json ;  M harness/archives/spec-changes.jsonl
CLEANUP attempt 2 mechanical: ['M1'] | M1 quote: harness/archives/spec-baseline.json, harness/archives/spec-changes.jsonl
failures: {'CLEANUP': 2} | spec status clean: False
```
Not reachable in the sandbox (its suite is the toy's), so the next phase only meets it if the tiny task runs on the real repository and an agent edits an owner file; but it is the harness's headline promise (PROCESS.md:139) and it deadlocks on its own repository.
Fix (`round.py:882-885`, one line): when E1 records a new or changed edit, provisionally accept the baseline on the branch, `specguard.accept(self.root, f"round {self.id}: agent edit of {path}, pending the owner's spec-edit checkpoint")`. The snapshot was taken before `record_producer` runs, so M1 never sees the baseline files, `commit_work` commits them, the branch's guard is green, and the owner's `approve` at `spec-edit` re-accepts with their words exactly as today; `abandon` discards the branch and main's baseline is untouched. Say in PROCESS.md:139 that the branch carries a provisional acceptance.

### Minor

**R2-m1 (minor) The CHAT-TO-PLAN prompt tells the driver to run `py -3.13 harness/src/run.py start --plan harness/DRAFT-PLAN.json` with no `--root`: on a sandbox round that starts a round in whichever repository the shell's cwd resolves to.**
`plumbing/CHAT-TO-PLAN.txt:4,10-11` hard-code cwd-relative paths; `cli.find_root` (`cli.py:35-42`) walks up from cwd when `--root` is absent. `planning_contexts` (`round.py:1438-1441`) already puts the absolute runner in `round.runner` but leaves `round.worktree` at "n/a" and the plumbing does not use either. Every other printed command (`record_command`, `record_hint`, the resume commands) carries `--root`. The real repository's origin is GitHub, so a `start` there claims `round/NNNN` on GitHub and LANDING pushes `main`.
Fix: in `planning_contexts` pass `worktree=root, harness_root=cfg.harness_root`; in CHAT-TO-PLAN.txt use `py -3.13 {{ round.runner }} --root {{ round.worktree }}` for both commands and `{{ round.harness_root }}/DRAFT-PLAN.json` for the plan path (update the assertion in `test_round.py:278`).

**R2-m2 (minor) A gate that PASSes or FAILs a NEEDS-OWNER producer without a `needs_owner` ruling leaves the question pending; every later gate is asked to rule on it.**
`round.py:1057-1067` handle `upheld` and `withdrawn`; the PASS branch (`:1068-1077`) and the FAIL tail (`:1078-1081`) never clear `st["pending_question"]`, and `step_context` (`:318-319`) renders it into every later gate prompt. The gate prompt says "Omit rulings, needs_owner and judgment_calls when empty", so a real gate that considers the assumption fine and PASSes without a ruling is likely. A later gate that then "upholds" raises a `question` checkpoint attributed to the wrong producer (`:1058-1061`), and the owner's `answer` lands on that producer.
Evidence (gates on; PLAN-AGENTS returns NEEDS-OWNER, its gate returns a plain PASS):
```
reached: PLAN-TO-SPEC-GATE | pending_question: {'question': 'STUB-QUESTION: which colour should whisper use?', 'assumption': 'STUB-ASSUMPTION: lowercase'}
PLAN-TO-SPEC-GATE prompt question line: ["The producer's question, if any: STUB-QUESTION: which colour should whisper use? (assumption: ...)"]
UNDEFINED lines: []
```
Fix (`round.py`, three lines before the PASS/FAIL routing in `record_gate`): when `st["pending_question"]` is set and `needs.get("status")` is neither ruling, flag `"{step} attempt {attempt}: no ruling on the producer's question; the assumption stands"`, append that line to `UNDEFINED_JUDGMENT_CALLS.md` (the runner already writes gate lines there), and clear `pending_question`.

**R2-m3 (minor) `override` at a checkpoint is listed as a resume command but does not resume.**
`RESUME` (`round.py:16-22`) lists `override` for `review`, `blocked`, `failure-limit` and `infra`, and every checkpoint message prints it under "Resume with one of:"; `owner_command` (`:1098-1099`) applies the override and returns the same checkpoint again with exit 10 (`:1111-1112`). The driver, following the message, gets the message back.
Evidence: `checkpoint: blocked | resume hints mention override: True` then `override code: 10 | kind: checkpoint | status: checkpoint | overrides: ['SPEC-TO-TESTS']`.
Fix (two lines in `owner_command` after `self.override(...)`): resume when the checkpoint's step, or its producer for a gate, is now overridden (`if st["status"] == "checkpoint" and cp.get("step") in st["overrides"]: self.resume()`); otherwise keep the checkpoint and say so in PROCESS.md:86 ("at a checkpoint, `override` of another step is followed by `approve`").

**R2-m4 (minor) A hand merge by the owner after L1 leads to a phantom merge attempt: the agent is told to resolve conflicts that no longer exist.**
PROCESS.md:128 promises "a hand merge by the owner in the worktree lands without any command"; that holds at LANDING (tested) but not after L1 has set `merge_pending` and moved the step to SPEC-TO-IMPLEMENTATION. `prepare_attempt` (`round.py:731-732`) re-runs `git merge --no-commit` (now "Already up to date", no `MERGE_HEAD`) and the prompt still lists `MERGE_IN_PROGRESS` (`:320-321`); only `landing_check` (`landing.py:69`) tests `is_ancestor`.
Evidence: `hand merge committed; MERGE_HEAD: False | target is ancestor: True` then `next -> producer SPEC-TO-IMPLEMENTATION 2 | MERGE_HEAD: False` with `MERGE_IN_PROGRESS: ["../src/toy/text.py"]` in the prompt. One paid, confused agent run; a DONE from it does land.
Fix (four lines in `mechanical_loop` before `return name` for SPEC-TO-IMPLEMENTATION): if `merge_pending` is set, no merge is in progress and `gitops.is_ancestor(root, merge_pending["target_sha"], "HEAD")`, clear `merge_pending`, write a HISTORY line, set `step` to `resume_step or "LANDING"` and continue the loop.

**R2-m5 (minor) "An out-of-band edit of PLAN.json/SPEC.md" is only detected when committed; an uncommitted one is silently reverted and booked as an infrastructure error.**
`tree_state` (`round.py:558-569`) runs before `out_of_band` (`:515-531`); with no attempt pending it checks out `harness/` and the living paths and increments `infra_errors`. With an attempt pending the edit is refused as "uncommitted work" instead (right, but the owner cannot tell). PROCESS.md:94 and DRIVER.md say "edit", the test (`test_outcomes.py:314-333`) commits.
Evidence (owner appends to `scope` in PLAN.json right after a record, no attempt pending): `next code: 0 kind/step: producer PLAN-TO-SPEC | owner edit survived: False | infra_errors: {'PLAN-AGENTS-GATE': 1} | HISTORY has 'changed out of band': False | 'dirty tree reset': True`.
Fix: one word in PROCESS.md:94 and DRIVER.md ("a **committed** out-of-band edit"), and the reset note in HISTORY should list the paths it reverted (`round.py:569` prints only the count) so an owner sees what happened. Exempting the plan and spec artifacts from the reset is the alternative; the doc fix is smaller.

**R2-m6 (minor) The gate's DIFF_FILE for a merge attempt includes the sibling's changes to the declared paths.**
`render_step` (`round.py:344-346`) diffs `step_starts[producer]..HEAD`; after a merge attempt HEAD is the merge commit, `step_starts` was reset at L1 (`:717`), and the automerge tree is gone (`:917-919`), so the sibling's edits to `implPaths` appear as the producer's work. SPEC-TO-IMPLEMENTATION-GATE's prose says "Line by line: is it outside of the spec? Fail." and the sibling's lines are, by construction, outside this round's spec. M1/M2 were fixed to measure against the automerge tree (R1-M1); the gate's view was not.
Fix (four lines): keep the automerge tree when the merge commit is made (`st["gate_diff_base"] = merge_pending["automerge_tree"]`), diff from it in `render_step` when present, and clear it when the gate completes. Acceptable to defer with a sentence in PROCESS.md:130 since W1 already warns when siblings share paths.

**R2-m7 (minor) On UPSTREAM and BLOCKED, strays are reverted with no record, and M2 is not applied.**
`round.py:894-896` calls `checks.m1_strays` and discards its return value (no findings file, no HISTORY line), and the `m2_frozen` call (`:904-907`) comes after the early return. A producer that edited a frozen test to demonstrate its UPSTREAM claim, or a stray it meant to keep, sees the file silently restored; its "previous final message" then refers to work that is gone. M2 matters only when a test path lies inside the step's write paths (CLEANUP's living `tests/` with a narrower `testPaths`), which is why the reproduction with CLEANUP's default paths found M1 doing the reverting.
Evidence: `record code: 0 | edit committed into HEAD: False | mechanical findings file exists: False`.
Fix (three lines): in that branch, run `m2_frozen` first when frozen, keep `m1_strays`' listed paths, and write one HISTORY line naming what was reverted.

### Nit

**R2-n1 (nit)** Dead STATE fields: `last_findings` (written at `round.py:714,937,1009,1079`, never read), `main_before` (`landing.py:68`, never read), `runner_commit` (`round.py:1369`, never read). Delete them and their `schemas.py:145-147` entries.
**R2-n2 (nit)** `validate_plan` (`round.py:1272-1275`) checks `provided_artifacts` for an overridden `PLAN-TO-SPEC`, which `NOT_OVERRIDABLE` already refuses at `:1262-1264`; dead branch.
**R2-n3 (nit)** `runner_head` (`round.py:181-183`) relies on `^` in a default-BRE `--grep`; a user with `grep.patternType = fixed` gets `None`, which silently disables M0 and makes M4 diff against `base_commit`. `prompt_commit` already uses `--fixed-strings`; do the same here (`--fixed-strings --grep="round NNNN: "`).
**R2-n4 (nit)** `step_table` (`prompts.py:99-106`) reports `gate_runs: true` for CHAT-TO-PLAN when its flag is 1, though it is mechanical and `ledger.shares` (`ledger.py:13,25`) never allocates a gate share to it; the PLAN-AGENTS prompt then asks for a share the ledger drops, and the owner's `defaultShares.gates.CHAT-TO-PLAN: 0.02` (`project.yaml:49`) is silently ignored for the same reason. Report the approval gate as not running (one condition in `step_table`); say in PROCESS.md:112 that only LLM gates take gate shares.
**R2-n5 (nit)** `sandbox` (`probe.py:182`) calls `fixtures.write_toy`, which overwrites the copied `docs/TODO.md` and `docs/CLARIFICATIONS.md` with one-line fixture headers (`fixtures.py:133-135`); the sandbox planner never sees the bootstrap items. Guard the two writes with `if not os.path.exists`.
**R2-n6 (nit)** PROCESS.md:132 lists "agents get no push credential" as an invariant; that holds for headless mode (`scrubEnv`) and not for driver mode, where sub-agents inherit the session and Git Credential Manager, and only the definition's `disallowedTools`, G1 and M0 stand in the way. Say so. TESTING.md:19's stub mode list omits `noop`.
**R2-n7 (nit)** `start`'s refusal "spec files differ from origin/main ...; commit and push them first" (`round.py:1329-1332`) also fires when the checkout is merely behind origin (someone else pushed a spec change); add "or pull".

## 3. The review-1 fixes

All present and correct; the suite's new tests cover each (`test_concurrency.py:113-142,269-323`, `test_outcomes.py:264-311`, `test_cli.py:56-72`, `test_schemas.py`, `test_round.py:100-103,156`). Specific notes:

- **R1-M1** (`round.py:808-815`): the snapshot keeps only what differs from the automerge tree plus untracked paths; conflicted files the agent resolved differ from the tree (which holds the markers) and stay in; untouched conflicted files drop out and L3 catches them. Correct.
- **R1-M3** (`round.py:546-557,817-824,911-919`): the merge is aborted and re-established, deviating from merged-B 2.12 for the reason the commit message gives (the runner's own uncommitted files would otherwise be M1 strays). The `abort_merge` pre-step (`gitops.py:49-54`) is needed and right. The `runner_head` rework for M0 is sound on every path that creates a non-runner commit (landing's clean merge, L2's merge commit, a hand merge): a runner prompt commit always follows before any `record`, so HEAD equals the runner's newest commit at record time. R2-n3 is the one residual dependency.
- **R1-M2, M4, M5, M6, M7, m1, m3, m5, m9, m11** verified by reading and by the tests named above; **m2, m6, m7, m8, m10, n1-n5** verified by reading (`schemas.py:121`, `fixtures.py:202-219`, `agents.py:137-138`, `config.py`, `specguard.INSTRUCTION`, PROCESS.md:24, `.gitignore`). The 78 `shackles-template-*` folders in `%TEMP%` predate the fix commit (newest 02:20, the commit is 03:17); this review's run left none.
- **m12** skipped as agreed; it makes R2-M1 more expensive than it needs to be, which is one more reason to fix R2-M1 first.

## 4. Verified and found sound (beyond review 1's list)

- Full suite: 155 passed, exit 0, about seven minutes; worktree clean afterwards. `doctor` on this worktree: 0 errors, 1 warning (owner log missing), all 14 prompts render with zero unresolved tokens, agent definitions match the roster, `claude.exe` 2.1.266 found.
- The rendered prompts read as an agent: CHAT-TO-PLAN (feeds TODO and CLARIFICATIONS verbatim, one plan destination, the mechanical-gate sentence), PLAN-AGENTS (roster, step table, minimum shares, budget split), SPEC-TO-IMPLEMENTATION-GATE (inputs name the producer's own attempt, DIFF_FILE without the round folder, the mechanical checks listed as already done). Contract lines are complete and absolute where the tools need them.
- `record` ordering: snapshot before any HISTORY write; M0 before booking; G1 for gates; resolutions applied before checks; M4, E1, M2, M1, commit, S1, M3, M5 in that order; non-blocking findings carried; blocking ones routed with `limit_check`.
- Routing re-traced: NEEDS-OWNER in all four combinations, UPSTREAM resets (`tests_frozen_at` cleared iff the target is at or before SPEC-TO-TESTS, `resume_step` cleared), BLOCKED, `answer` at `review` re-opening the producer and its gate, `approve` per checkpoint kind, `abandon` before landing only, overrides of each overridable step including PLAN-AGENTS falling back to `defaultShares`.
- Landing: the living charge is measured against the target tip and booked once; the push loop re-checks after a rejection; `sync_main` is idempotent on a finished round; two rounds' index lines merge through the union attribute.
- Sandbox: builds a repo whose `livingSourcePaths` and `suiteCommand` point at the toy, copies `.claude/agents`, accepts the baseline, pushes `main` to a local bare origin; a stub round runs there end to end (`test_probe.py:58-79`).
- Windows: `core.autocrlf=true` on this machine does not disturb the hash baseline (BOM and CRLF normalised) or `git status` (content-normalised).

## 5. Plan deviations worth knowing

- R1-M3's fix deviates from merged-B 2.12 deliberately and sensibly (see section 3). PROCESS.md:129 describes the new behaviour.
- merged-B's "the last balanced object" extraction rule (PROCESS.md:66) is the wrong rule for nested JSON (R2-M1); the plan is at fault, the implementer followed it.
- merged-B 2.13 and amendment 3 place the baseline guard in the permanent suite and the `spec-edit` checkpoint before LANDING; together they produce R2-M2 on the harness's own repository. Neither document considered the self-hosting case.
- Nothing else new; R1's list of sensible deviations stands.

## 6. Brittleness to changes in the owner's prose or config

Review 1's table stands; these rows are new or sharpened. "Loud" refuses with a message, "soft" degrades with a warning, "silent" is the bad kind.

| Owner change | Effect | Kind |
| --- | --- | --- |
| Any edit to a spec file made **by an agent inside a round on the real repository** | CLEANUP cannot pass until the owner approves, which happens after CLEANUP (R2-M2) | loud, but a deadlock |
| Adding files to `spec.yaml` | widens E1 and R2-M2 to those files; otherwise honoured | fine |
| `defaultShares.gates.CHAT-TO-PLAN` (present today, 0.02) | ignored by the ledger; the PLAN-AGENTS prompt still shows it as a minimum (R2-n4) | silent, harmless |
| `livingSourcePaths` including `src/` (today's value on the real repository) | the runner itself is living: a CLEANUP or SPEC-TO-IMPLEMENTATION that edits `src/shackles/` runs the edited runner for the rest of the round (the worktree's `run.py` is the driver's runner); a broken edit breaks `record` mid-round | silent |
| Removing `test_spec_baseline.py` from the suite, or changing `suiteCommand` | removes R2-M2; nothing else depends on it | fine |
| Rewording COMMON-GATE's "Omit ... needs_owner ... when empty" | a gate that omits the ruling triggers R2-m2 more often; the runner does not read the sentence | soft |
| `roundPaths` renames of `FINDINGS/`, `HISTORY.md`, `tests-archive/`, the judgment files | honoured by the runner; COMMON-ROUND and AGENTS.md name them by today's names (R1 noted the reverse direction); the stub hard-codes `archives/rounds/NNNN/` (tests only) | fine / tests only |
| `checkpointsAfter` versus the "Checkpoint after this step" sentences | still a runner default that mirrors the prose by hand | silent, documented |
| `modelAliases` for a new model id in `subAgents.yaml` | still a runner key the owner must extend, else `model_alias` is the raw id | silent for the driver |

Nothing mechanical matches a phrase of the prose; R1's statement holds after the fix commits.

## 7. Notes for the next phase (the driver of the tiny task)

Ordered by how badly each would mislead.

1. **Decide where the task runs, and always pass `--root`.** The real repository's origin is `github.com/fragsworth/shackles_harness`: a worktree `start` there pushes `round/NNNN` and LANDING pushes `main`. For a throwaway task use `sandbox --dir <folder outside any repository>` and run every command as `py -3.13 <sandbox>\repo\harness\src\run.py --root <sandbox>\repo ...` (then the worktree `start` prints). The rendered CHAT-TO-PLAN prompt's own `start` line lacks `--root` (R2-m1); do not run it literally from another folder.
2. **Quote generously or pass `--tokens`.** Without `--cost`/`--tokens`, every `record` books the whole step budget as an estimate, plan and spec words cost $0.1 each, and each checkpoint costs about $6.70; a $10 quote with a 300-word plan and a 500-word spec hits the `hard-stop` (6 x quote) before landing. Quote at least $50 for the sandbox task, or pass the Agent tool's token totals.
3. **If gates fail or messages are `invalid`, check R2-M1 first.** A producer after a FAIL, or a gate with `rulings`/`needs_owner`, that wraps its JSON in a sentence is rejected today with a misleading `status should be one of ...` error. Apply the four-line fix before the gates-on run, or expect one rerun per occurrence.
4. **Save the final message exactly to `result_file`**, nothing else under `RESULTS/`: any other file there is a runner-owned stray (M1 for producers, G1 for gates).
5. **Gates on**: edit `harness/project.yaml` in the sandbox repo, `spec accept --note "gates on"`, commit, `git push origin main`, then `start`; `start` now refuses otherwise (R1-M5 fixed). Verify with the worktree's `config`.
6. A later gate prompt that carries an earlier producer's question is R2-m2, not a confused gate; `override` at a checkpoint must be followed by `approve` (R2-m3); do not hand-edit PLAN.json or SPEC.md in the worktree without committing (R2-m5).
7. **On the real repository**: choose `implPaths` outside `src/shackles/` (self-hosting hazard, section 6), avoid any task that touches an owner file (R2-M2), and budget time: M5 at CLEANUP and L2 at LANDING each run the seven-minute harness suite.
8. No owner log exists in the sandbox, so every `--quote` records unverified with a FLAG; that is expected.
9. Agent types `shackles-producer-<rung>` / `shackles-gate-<rung>` exist only when the driving session's project directory has `.claude/agents/`; the action's `warnings` say when to fall back to `general-purpose` with `model: <model_alias>`. Never spawn with worktree isolation.
