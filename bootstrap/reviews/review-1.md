# Review 1: shackles_harness at 14c1f8f

Reviewer: a fresh Fable 5.1 session, read-only, in a linked worktree. Nothing in the repository was modified; every reproduction below ran on throwaway repositories built with the project's own fixtures under `%TEMP%`.

## 1. Process

Designed before reading the implementation, then followed in this order:

1. **Spec-side fidelity first.** Read `spec.yaml` and all 21 owner files, then the runner, asking one question of every mechanism: does it depend on a *wording* of the prose, or only on names, keys and tokens? Judged the two spec edits in `9a13bb2` for necessity and minimality against the alternatives.
2. **The driver path end to end**, because the next phase drives a real round: `doctor`, `render`, `start`, the `next`/spawn/`record` loop, checkpoints, landing, `done`; ran every read-only command from the worktree and rendered real prompts (CHAT-TO-PLAN on the repo, a producer and a gate on the fixture round) and read them as an agent would.
3. **State machine correctness** in `round.py`, `checks.py`, `landing.py`, `ledger.py`: every routing row of merged-B 2.9, the caps, disputes, the merge attempt, crash recovery. Where reading raised a suspicion, reproduced it with a script (eight reproductions; six confirmed, one refuted, one refined).
4. **The test suite**: ran it in full (150 passed, 7 min 9 s, exit 0, worktree clean afterwards), then read every test for what it covers, what it does not, and whether any test reads the owner's prose.
5. **Docs versus code**: PROCESS.md, DRIVER.md, TESTING.md, INDEX.md, README claims checked against behaviour.
6. **Plan deviations**: FINAL-PLAN amendments 1-10 and the merged-B sections they modify, checked against the implementation; where the implementation deviated sensibly it is not a finding; where the plan itself was wrong it is said.

Severity scale: **blocker** = the next phase cannot succeed or would be misled into a false conclusion with no workaround; **major** = a real defect that costs an agent run, corrupts round records, or misleads the driver, with a workaround; **minor** = wrong but cheap; **nit** = cleanliness.

Counts: 0 blocker, 7 major, 12 minor, 5 nit.

## 2. Findings

### Major

**R1-M1 (major) Merge attempt: the sibling's own changes are reported as M1/M2 strays.**
`harness/src/shackles/round.py:750` takes the snapshot as `checks.dirty(self.root, exclude)`; on a merge attempt that snapshot contains every file the *sibling* changed (staged by `git merge --no-commit`), and `checks.py:57-75` (`m1_strays`) and `:78-93` (`m2_frozen`) report each one outside the step's write paths as a blocking stray. merged-B 2.10 specified the opposite ("compare ... against `merge_pending.automerge_tree` ... so the sibling's changes never count"); the implementation only uses the automerge tree to *restore* the files, which is why content stays correct while the attempt still fails.
Evidence (reproduction, sibling pushes a conflict in `src/toy/text.py` plus `harness/docs/SIBLING.md` and `tests/toy/test_more.py`; the agent resolves the conflict correctly):
```
dirty snapshot at the agent's start: [('A ', 'harness/docs/SIBLING.md'), ('UU', 'src/toy/text.py'), ('A ', 'tests/toy/test_more.py')]
mechanical findings: [('M2', 'tests/toy/test_more.py'), ('M1', 'harness/docs/SIBLING.md')]
failures: {'SPEC-TO-IMPLEMENTATION': 2}
```
The merge commit is made anyway, so attempt 3 (a full-price agent run that has nothing to do) passes and the round converges; the cost is one wasted attempt, one spurious `failures` increment toward `maxFailuresBeforeStop`, and a finding that tells the agent it changed files it never touched. The suite misses it because the only conflict test's sibling changes a file inside `implPaths`.
Fix (two lines in `record`, `round.py:750`): on a merge attempt, keep only the paths that differ from the automerge tree, `changed = set(gitops.git(root, "diff", "--name-only", automerge_tree, check=False).splitlines())` and `snapshot = [(xy, p) for xy, p in snapshot if p in changed or "?" in xy]`; conflicted files the agent resolved differ from the tree (which holds the markers) and stay in.

**R1-M2 (major) `inputs_hash.SPEC` goes stale when PLAN-TO-SPEC is accepted a second time; a plain `next` then re-enters the round.**
`round.py:628-633`: the hash is refreshed only inside the `not words_charged.spec` branch, so after an UPSTREAM back to PLAN-TO-SPEC (or an `answer` at its review) the re-accepted spec keeps the old hash. The next `next` whose step is past PLAN-TO-SPEC-GATE (`round.py:519-524`) then fires "SPEC changed out of band", resets downstream, clears `attempt_pending`, adds a round re-entry, and renders the same attempt again.
Evidence (delegated round, SPEC-TO-TESTS returns UPSTREAM to PLAN-TO-SPEC, the rerun writes a different SPEC.json, then two `next` calls):
```
inputs_hash.SPEC == current spec hash: False | round_retries 1
after one more next: step SPEC-TO-TESTS attempt 2 round_retries 2
HISTORY has 'SPEC changed out of band': True
prompt commits for SPEC-TO-TESTS attempt 2: 2
```
With `maxRoundAttempts: 2` one genuine UPSTREAM plus this phantom re-entry leaves the round one step from `round-limit`. `approve` at a review checkpoint happens to refresh the hash (`round.py:1088-1090`), which is why the non-delegated path hides it.
Fix: move `st["inputs_hash"]["SPEC"] = self.spec_hash()` out of the `if` so it runs on every acceptance of PLAN-TO-SPEC (`round.py:633`), and drop the `words_charged` guard from the hash only.

**R1-M3 (major) After an unresolved merge attempt (L3), the next `next` aborts the merge, books two infrastructure errors, and loses the L3 record's files.**
`round.py:543`: `expected = merge_pending and pending and pending["step"] == ...`, but `record` has already set `attempt_pending = None` (`round.py:761`), so the merge left in place by design is "unexpected": `git merge --abort` (+1 infra), then the tree is dirty with the uncommitted STATE/HISTORY/FINDINGS/RESULTS of the L3 record (nothing commits during a merge, `round.py:152-153`), so `tree_state` resets it (+1 infra) and `prepare_attempt` re-establishes the merge from scratch. The L3 findings file, the agent's result file and the HISTORY lines are gone; the agent's partial resolution is gone too.
Evidence:
```
after the L3 record: files exist {'SPEC-TO-IMPLEMENTATION-2.mechanical.json': True, 'SPEC-TO-IMPLEMENTATION-2.json': True} | HISTORY mentions L3: True
after next: files exist {...mechanical.json: False, ...-2.json: False} | HISTORY mentions L3: False
HISTORY: 'unexpected merge in progress: aborted (infrastructure error)', 'dirty tree reset under harness, src, tests, harness/docs (4 paths): infrastructure error at SPEC-TO-IMPLEMENTATION'
```
The plan is at fault here: merged-B 2.9 step 4(a) stated exactly this condition; the implementer followed it. The existing test passes because it asserts only that `MERGE_HEAD` exists afterwards.
Fix: `expected = bool(st.get("merge_pending")) and st["step"] == "SPEC-TO-IMPLEMENTATION"` (`round.py:543`), and in the `elif merging: return` branch keep the return. That preserves the merge and the uncommitted round files. Consequence to accept: the following attempt's prompt commit is then skipped by `commit()` while the merge is in progress, which is what PROCESS.md:124 already promises; `record` tolerates a missing prompt commit (`round.py:764` skips M0, `:848` falls back to `base_commit` for M4), and everything lands in the merge commit.

**R1-M4 (major) The gate's DIFF_FILE for a code step is mostly runner noise.**
`round.py:343-344` diffs `step_starts[producer]..HEAD` over the producer's write paths, and those include the round folder, so the file the gate is told is "the artifact" (`ARTIFACT: a diff under WRITE_PATHS`) carries STATE.json, HISTORY.md, the producer's own 2.5k-token prompt and its result JSON next to the real change. A gate whose prose says "Line by line: is it not sensible? Fail." is invited to judge STATE.json.
Evidence (stub round, all gates on): the diff for SPEC-TO-IMPLEMENTATION-GATE has five `diff --git` headers, four of them under `harness/archives/rounds/0001/` (`HISTORY.md`, `PROMPTS/SPEC-TO-IMPLEMENTATION-1.txt`, `RESULTS/SPEC-TO-IMPLEMENTATION-1.json`, `STATE.json`) and one for `src/toy/text.py`; 9,196 bytes total.
Fix (`round.py:343`): `declared = [self.repo_rel(p) for p in ... ["write_paths"] if p != self.paths["folder"]]`. If the judgment-call lines are wanted in the diff, add the two judgment files explicitly.

**R1-M5 (major) `start --accept-spec` in worktree mode runs the round on `origin/main`'s spec and leaves the main checkout drifted.**
`round.py:1254-1256` checks drift in the main checkout, `:1296` creates the worktree from `origin/<main>`, and `:1343-1344` accepts the baseline *in the worktree*, whose spec files are the pushed ones, not the edited ones. The owner (or the next-phase driver) who flips a gate in `project.yaml` and runs `start --accept-spec` gets a round with the gate still off and a green baseline that does not match their checkout.
Evidence:
```
start --accept-spec: code 0
gate PLAN-AGENTS-GATE enabled in the round's config: 0
worktree spec status clean: True | main checkout spec status clean: False
```
Fix: in worktree mode refuse when any spec file in `root` differs from `origin/<main>` ("commit and push the spec change first"), and reserve `--accept-spec` for `--no-branch` or for drift that is already committed on the target; one `git diff --quiet origin/<main> -- <spec files>` before the claim.

**R1-M6 (major) `harness/local.yaml` is invisible to worktree rounds, and the docs say the opposite.**
The round's config is `configmod.load(root)` with `root` the worktree (`round.py:1298` and every `open_round`); `local.yaml` is gitignored, so it never reaches the worktree. PROCESS.md:25 and DRIVER.md:34 present `local.yaml` as the place for `claudePath`, `agentCommand`, `agentOverride` and gate flips; `test_probe.py:72-76` quietly copies the file into the worktree by hand, which is the tell.
Evidence:
```
main checkout config: PLAN-AGENTS-GATE = 1 claudePath = C:/nowhere/claude.exe
round worktree config: PLAN-AGENTS-GATE = 0 claudePath = None
local.yaml exists in the worktree: False
```
Fix: in `start`, after `worktree add`, copy `<main_root>/harness/local.yaml` into the worktree when it exists (it stays ignored, so it is never committed); one `shutil.copyfile`. Say in PROCESS.md that a worktree round reads the copy taken at `start`.

**R1-M7 (major) `next` destroys the agent's in-scope work when a single stray path exists.**
`round.py:553-556` refuses (`uncommitted work ... record it, or next --discard`) only when *every* dirty path is inside the pending step's write paths; one stray anywhere flips the whole tree into the "dirty tree reset" branch (`:557-562`), which checks out and cleans `harness/` and the living paths. The in-scope artifact is deleted while a stray outside those scopes survives; `record` would have handled the same tree correctly (M1 reverts the stray, keeps the work).
Evidence (PLAN-AGENTS work plus `stray.txt` at the repo root, then `next`):
```
artifact exists before next: True stray exists: True
next code: 0 kind/error: producer
artifact exists after next: False stray exists: True
infra_errors: {'PLAN-AGENTS': 1}
```
This only bites when the driver runs `next` before `record`, but that is the guard's whole purpose. Fix: refuse when *any* dirty path lies inside the allowed paths (`all(` -> `any(` at `round.py:555`); let `record` sort the rest.

### Minor

**R1-m1 (minor) A gate's `Inputs, by path` names the producer's result file by the gate's attempt number.**
`harness/src/shackles/prompts.py:165` builds `RESULTS/{producer}-{attempt}.json` with the gate's `attempt`; after any mechanical retry of the producer the path is stale while the inline "previous final message" (`round.py:310`) is right. Reproduced: producer at attempt 2, gate attempt 1, inputs list `RESULTS/PLAN-AGENTS-1.json`. Fix: pass the producer's attempt (`st["attempts"][producer]`) into `step_context`, or drop the entry since the message is inlined.

**R1-m2 (minor) A producer that returns `judgment_calls` as lists (the gate's shape) is an infrastructure error and its work is reverted.**
`schemas.py:121` requires ints; `round.py:803` reverts the whole snapshot on an invalid message. Reproduced: `record code: 2 errors: ['RESULT: judgment_calls.defined should be int, got list' ...]; artifact still there: False`. Two contracts with the same key name and different shapes is a foot-gun for real agents. Fix: accept `int` or `list` in RESULT and count a list (`schemas.py:121`); the revert itself is R1-m12.

**R1-m3 (minor) "every gate or owner finding id must appear in your resolutions" is not enforced.**
`plumbing/producer.txt:15` says must; `round.py:822-841` only applies what is given and nothing checks for omissions. Reproduced: F1 open, producer omits `resolutions`, `record` exits 0 and the round advances with F1 still open. Either enforce (one blocking S1-style finding listing the ids) or, cheaper, treat omitted ids as `fixed` with a HISTORY note and say so in the prompt.

**R1-m4 (minor) `check` is documented read-only but commits a merge at LANDING.**
PROCESS.md:48 ("`status`, `spend`, `rounds` and `check` are read-only"); `landing.py:77` runs `git merge --no-edit --no-verify` inside `landing_check`, which `check_payload` calls (`round.py:1206`), and then runs verify and the full suite. The plan and `test_concurrency.py:183` intend it. Fix the sentence: "`check` writes nothing shared; at LANDING it merges the target into the worktree and runs verify and the suite".

**R1-m5 (minor) Agent definitions register only when the driver's session has the repository as its project directory; DRIVER.md does not say so.**
DRIVER.md:18-19 covers the "written mid-session" case and the fallback, but a session started in the parent folder (this review's session lists `decisions-reader`, `opus-max`, `route-probe` and not one `shackles-*` type) never sees `.claude/agents/`. With the fallback, gates are not tool-restricted by construction; G1 is the only guard. Add one sentence to DRIVER.md:18 and print the fallback hint in the action's `warnings` when the definition folder is not under the session's cwd.

**R1-m6 (minor) The suite leaks about 70 template repositories per run into `%TEMP%`.**
`harness/tests/fixtures.py:201-209` (`template_repo`) uses `tempfile.mkdtemp` and never removes it; `agents.py:127` (`probe_cli`) likewise. Measured after one run: 73 `shackles-template-*` folders, about 360 KB each. Fix: `atexit.register(shutil.rmtree, ...)` next to the `mkdtemp`, or a session-scoped `tmp_path_factory` in `conftest.py`.

**R1-m7 (minor) `gitTimeoutSeconds` and `gitIdentity` are documented config keys that do nothing.**
`config.py:79,92` define them and PROCESS.md:146 lists them; `gitops.py:6-7` hard-codes `IDENTITY` and `TIMEOUT=[300]`, and `set_identity` (`gitops.py:16`) is never called. Either wire them (two lines in `config.load`) or delete both keys and the doc mentions; deleting is simpler.

**R1-m8 (minor) The blast radius of a step rename is understated.**
`specguard.INSTRUCTION` (`specguard.py:12-17`) and PROCESS.md:29 say "a step, gate or artifact key change means `pipeline.py`", but the step names are literals in `round.py` (38 occurrences), `prompts.py` (6), `landing.py`, `checks.py`, `config.py`, plus `stub_agent.py`, the tests and the defect fixture folders. It is loud (lint refuses `start`), never silent, so this is a documentation fix: name the files, or, if wanted later, hoist the per-step special cases in `prompts.step_context` and `round.py` behind `pipeline.Step` fields (`inputs`, `writes`), which would leave `pipeline.py` as the single place. Do not do the latter now.

**R1-m9 (minor) The CHAT-TO-PLAN prompt names two destinations for the plan.**
Rendered text: "Write the plan as PLAN.json to harness/DRAFT-PLAN.json: archives/rounds/0000/PLAN.json: JSON object with ...". `plumbing/CHAT-TO-PLAN.txt:10` inserts `{{ step.artifact_contract }}`, and `prompts.py:116` prefixes the contract with the round-0 path. Fix: for `kind == "plan"` return the description without the path prefix.

**R1-m10 (minor) The union-merge attribute is pinned to `harness/archives/` while `index.jsonl` follows `roundPaths.folder`.**
`.gitattributes:1` versus `round.py:1183` (`dirname(folder)/index.jsonl`). An owner who moves `roundPaths.folder` out of `archives/` silently loses the union merge and every second landing ends with `main_synced: false`. Same family: `specguard.py:10-11` fixes the baseline under `harness/archives/` regardless of `archivesPath`, which the runner otherwise ignores. Say so in PROCESS.md's "Spec files" section (one sentence), or derive the attribute path in `doctor` and warn when it does not cover the index.

**R1-m11 (minor) `--no-branch` from a linked worktree touches another checkout's `main`.**
`landing.py:91-103` (`ff_local_main`): in no-branch mode on a side branch, LANDING fast-forwards `main` in whichever worktree has it checked out, or refuses with "main is checked out and dirty at <other path>" until that other checkout is cleaned. Surprising for a round that promised "no claim, worktree or push". Fix: document that `--no-branch` is for the main checkout on `<mainBranch>`, and refuse it elsewhere (one check in `start`).

**R1-m12 (minor) The RESULT-shape rule for the headless envelope and the invalid-message path revert a producer's work before the raw message is even inspected by a human.**
`round.py:798-817` (`infra`) reverts every dirty path for producers and gates alike. For gates this is G1 and right. For producers it throws away paid work because of a formatting slip; merged-B decision 13 chose "rerun the same attempt" *because it is cheaper than a retry cycle*, and the revert cancels that saving. Fix: revert only for gates; for producers keep the tree and let the rerun's M-checks handle it (the rerun agent sees "previous final message: none" and a working tree that already contains the work, which is fine).

### Nit

**R1-n1 (nit)** `harness/tests/stub_agent.py:146` (`... if False else None`) and `:168-169` (`text_of`) are dead code.
**R1-n2 (nit)** `commands.py:14` `doctor --json` is a no-op flag "kept for symmetry"; delete it.
**R1-n3 (nit)** `procs.write_text` (`procs.py:112-124`) can leave `.tmp-*` files beside round files after a crash, and `git add -A` in `Round.commit` would commit them; a `.tmp-*` line in `.gitignore` or a `try/finally` unlink is enough.
**R1-n4 (nit)** `test_docs.py:41-46` asserts line counts of the docs (PROCESS ≤ 200, DRIVER ≤ 80 ...); this is ceremony from the plan, not a property of the software. Drop it, or keep only the one-sentence-per-line rule if that is wanted.
**R1-n5 (nit)** `round.py:436` builds `record_command` without quoting paths; fine here, breaks on a worktree path with a space.

## 3. The two spec edits (commit `9a13bb2`)

Necessary and minimal. Both prose files referenced `project.ownerReviewCostPerWord`, which no config file defines. The zero-edit alternative, a runner default or a derived context key, would render one number for both the plan and the spec sentence while the owner has deliberately split the two rates (`planCostPerWord`, `specCostPerWord`); the edit replaces each stale token with the owner's own key for that sentence, one token per file, in its own commit with the diff in the body, and the baseline was taken after it. Nothing smaller exists that keeps the owner's split. `spec_waivers.json` is empty, as it should be.

## 4. Plan deviations worth knowing

- **Followed the plan into a defect**: R1-M3 (merged-B 2.9 step 4(a) is wrong as written).
- **Deviated from the plan into a defect**: R1-M1 (merged-B 2.10's automerge-tree comparison was not implemented; the snapshot-plus-restore shortcut is what fails).
- **Sensible deviations, no action**: the 8-word prose/source overlap check is a `doctor` warning (`doctor.py:44-60`), not a test (merged-B 3.6 wanted a test; FINAL-PLAN amendment 6's spirit is the warning). `attempt_pending` has no `prompt_commit` field; the commit is found by `git rev-list --grep` on the message (`round.py:176-179`), which works and keeps STATE smaller. `tests/spec_baseline.json` moved to `archives/` per amendment 3. The suite takes 7 min, not merged-B's 4; TESTING.md says six and a half, README says "a few minutes"; both acceptable.
- **Amendments verified as implemented**: 1 (verdict authoritative, `schemas.normalize_findings`), 2 (carry-forward files, POSTMORTEM write paths, CHAT-TO-PLAN feed, living-charge exemption by construction since the charge is booked at LANDING), 3, 4 (eight generated definitions, drift test), 5, 6 (`doctor.wording_warnings`), 7 (stub-only suite; no real agent is ever spawned by a test), 8 (counts, tail and absolute path in checkpoint messages, `status`, `done`, HISTORY per attempt), 9 (headless loop exercised with the stub; the real `--probe-cli` could not run here, accepted), 10.

## 5. Notes for the next phase (the driver of the tiny task)

Ordered by how badly each would mislead the driver.

1. **Use the sandbox, not the repository.** `sandbox --dir <a folder outside any git repository, e.g. %TEMP%\shackles-sb>` builds `repo/` and `origin.git`; a `start` without `--no-branch` in the real repository pushes `round/NNNN` and later `main` to GitHub, and `--no-branch` from a linked worktree hits R1-m11. Run every command with `--root <sandbox>\repo` (or the worktree `start` prints).
2. **Gates on, the only way that works today** (R1-M5, R1-M6): in `<sandbox>\repo`, edit `harness/project.yaml` (`gates: ... 1`), run `spec accept --note "gates on"`, `git add -A && git commit`, `git push origin main`, then `start`. Neither `start --accept-spec` nor `harness/local.yaml` enables gates in a worktree round; both fail silently. Verify with `py -3.13 <worktree>\harness\src\run.py --root <worktree> config` that the gate values are 1 before spawning anything.
3. **Agent types**: `shackles-producer-<rung>` / `shackles-gate-<rung>` exist only if the driving session's project directory is the repository (R1-m5). Otherwise spawn `general-purpose` with `model: <model_alias>` and the wrapper text from `contract.WRAPPER`; effort then inherits the session. Never spawn with worktree isolation. Consider `start --agent low` (Sonnet) for the throwaway task; the action JSON carries `model_alias`.
4. **A gate that FAILs on STATE.json, HISTORY.md or a prompt file is R1-M4, not a bad agent.** Read the FINDINGS file before concluding anything about gate quality.
5. **Producer final messages**: `judgment_calls` must be `{"defined": <int>, "undefined": <int>}` for producers and lists of strings for gates; the wrong shape is an infrastructure error that also reverts the producer's work (R1-m2). Extra prose around the JSON is tolerated (`schemas.extract_json`).
6. **Always `record` before another `next`.** If `next` says "uncommitted work ... record it", record it. Running `next` on a tree with one stray outside the write paths deletes the agent's work (R1-M7).
7. **No owner log in the sandbox** (the hook writes to the real repository's `harness/OWNER.log` and only when the session's project is that repository): every `--quote` is recorded unverified with a FLAG. That is expected; do not pass `--unverified` unless `record`/`approve` exit 2 with "quote not found".
8. **Checkpoints**: relay `message` verbatim, then run one of the printed resume commands with the owner's exact words. With gates off and no delegation there are exactly two review checkpoints (after PLAN-TO-SPEC-GATE and after CLEANUP); `--delegate` removes both.
9. `record --tokens N` is optional; without it the step budget is booked as a flagged estimate.
10. A landing conflict cannot occur in a single sandbox round; if two rounds are run, expect R1-M1 once.

## 6. Verified sound (the next reviewer need not repeat)

- Full suite: 150 passed in 7:09 on this machine, exit 0; the worktree is clean afterwards except `__pycache__`. `doctor` on this worktree: 0 errors, 1 warning (owner log missing); it finds `claude.exe` 2.1.266 under `%APPDATA%`, the hook is configured, `worktreeDir` is ignored, every one of the 14 prompts renders with zero unresolved tokens (1.5k-3.2k tokens each), the eight agent definitions match the roster, spec baseline clean at `9a13bb2`.
- **No mechanical behaviour depends on prose wording.** The runner reads prose only through `{{ ns.key }}` tokens, the file-name convention (`pipeline.prose_file`/`prose_owner`), config keys and `roundPaths`. `AGENTS.md` is inserted raw (its literal `{{ plumbing.PROCESS-INSTRUCTIONS }}` never expands). The contract words come from `contract.py` and the plumbing block, not from the prose; `doctor.wording_warnings` only warns. `doctor.overlap_warnings` reports no shared 8-word window between `harness/src` and the prose.
- Rendering: once-per-document includes, embed mode for `GATE-PROSE` (nested `PROCESS-INSTRUCTIONS` renders empty), cycle and depth guards, unresolved markers collected and flagged into HISTORY, artifact text inserted after substitution (`test_fmt_of_artifact_text_never_expands`), process block appended when the token is absent, W2 size warning.
- Config: `DEFAULTS < project.yaml < local.yaml` with sources, unknown keys kept, missing keys defaulted, BOM/CRLF tolerated, `NNNN` width inferred, `roundPaths` filled with warnings, `repo_rel` refuses escapes and allows `..`, roster fallbacks warn.
- Structural lint: gate keys must name pipeline gates in pipeline order; every producer needs its prose file (error); an enabled gate without prose is disabled (warning); unknown prose files warn; spec files must exist. `start` and `doctor` both run it.
- Routing: FAIL re-entry with findings; dispute -> upheld twice -> settled, a further dispute ignored with a note; withdrawn never re-raised (quote match); non-blocking and deferred findings carried to every later producer and to POSTMORTEM; NEEDS-OWNER in all four combinations (gate on: upheld -> `question` even when delegated, withdrawn -> Q1 and a defined-judgment line; gate off: checkpoint, or delegated -> assumption logged to UNDEFINED_JUDGMENT_CALLS.md); UPSTREAM to each earlier producer, attempt numbers never restart, `tests_frozen_at` cleared when the target is at or before SPEC-TO-TESTS, CHAT-TO-PLAN target -> `upstream-plan` requiring an edited plan; BLOCKED -> checkpoint and `answer` -> O1; `failure-limit` with `approve` resetting the count; `round-limit` once; `hard-stop` once; `infra` after `infraRetries`; M0 soft reset of an agent commit; G1 discard; out-of-band PLAN/SPEC edits; in-round spec edit -> fenced diff in HISTORY and a `spec-edit` checkpoint even when delegated, `approve` accepting the baseline on the branch; crash recovery by rerunning `next`.
- Verdict-authoritative normalization both ways, id renaming, suggestion default, quote truncation, withdrawn-quote drop, all with HISTORY notes.
- Concurrency: the compare-and-swap claim (`--force-with-lease=<ref>:` plus the `*` line), the lost race creating nothing, the bounded claim loop, explicit `--branch` pushing once, the fence (`another runner owns this round`), `next` pushing when ahead, landing after a moved main, the move-and-reject-once retry inside one `next`, reject-all leaving the round at LANDING with no tag or living entry, the merge attempt with a two-parent commit and L3, a hand merge landing without a command, L2 re-entry from the merge commit, two rounds' `index.jsonl` merging through `merge=union`, `sync_main` false on a genuine conflict, W1, abandon tags, `rounds` reporting claimed-but-empty ids.
- Costs: shares with defaults and equal split, caps and retry cost, cost precedence and floors, owner charges, time on read, the living charge cases (cap crossing, added, deleted, new tests, `__pycache__` excluded), exactly one living entry per landed round measured against the tip merged.
- Windows: argv lists everywhere, `taskkill /T /F` on timeout (verified by the slow-agent test), atomic writes, `onexc` rmtree, `normcase` comparisons, `PYTHONUTF8=1`, `GIT_TERMINAL_PROMPT=0`, hermetic git config in tests.
- Headless: argv shape (`--print`, `--output-format json`, `--json-schema`, rung model/effort, tool flags before `--permission-mode`, task last, no `--max-turns`), env scrub and `SHACKLES_SUBAGENT`, `structured_output` preferred over `result`, garbage/exit/timeout -> infra -> checkpoint.
- Owner log: hook escaping round-trip, envelope prefixes shared between hook and runner (`test_hook_matches_the_runner_prefix_list`), main-checkout resolution from a worktree, the round slice from `owner_since`, quote verification windows, `[via driver]` lines.
- `gitops.show_many` copes with paths containing spaces (checked; `cat-file --batch` echoes the resolved oid, not the input).
- Documents: every CLI command appears in DRIVER.md or PROCESS.md, every `DEFAULTS` key in PROCESS.md, INDEX aliases resolve, carry-forward files exist with one header line.

## 7. Brittleness to changes in the owner's prose or config

Explicitly, since it is the owner's chief concern. "Loud" means the runner refuses with a message naming the cause; "soft" means it degrades with a warning; "silent" is the bad kind.

| Owner change | Effect | Kind |
| --- | --- | --- |
| Rewording any sentence of any prose file | none mechanically; the baseline test fails until `spec accept`; `doctor` warns only if a status/verdict word disappears | loud, by design |
| Removing `{{ plumbing.PROCESS-INSTRUCTIONS }}` from a prose file | block appended, warning flagged | soft |
| Removing or misspelling any other token | `[unresolved: ns.key]` in the prompt, HISTORY flag, `doctor` error unless waived | soft, visible |
| Renaming a prose file or a `COMMON-*` include | `start`/`doctor` error (producer) or the gate silently disabled with a lint warning (gate); a renamed `COMMON-X` include renders `[unresolved: prose.COMMON-X]` | loud / soft |
| Adding a prose file for a step that does not exist | "unknown prose file" warning; nothing else | soft |
| Renaming, adding or reordering a step or gate in `gates:` | `start` refuses (lint); fixing it is code in seven files, not just `pipeline.py` (R1-m8) | loud |
| Changing a config value | read live at every command (worktree copy); type mismatch against `DEFAULTS` refuses every command including `next` until fixed | loud |
| Changing `roundPaths` names or the `NNNN` width | honoured everywhere in the runner; `index.jsonl` moves with the folder but `.gitattributes` and the spec baseline paths do not (R1-m10); the stub and defect fixtures hard-code `archives/rounds/0001` | silent for the union merge |
| Changing `livingSourcePaths`, `lockedProsePath` | honoured | fine |
| Changing `archivesPath`, `currency`, `systemTestAgent` | ignored by the runner (owner keys read only for the prompt context); `systemTestAgent` is lint-checked against the roster but never used to choose an agent | silent, harmless today |
| Adding a rung or a new model id to `subAgents.yaml` | works, but the Agent tool needs an alias: `modelAliases` (a runner default) must be extended in `project.yaml`/`local.yaml`, else `model_alias` is the raw id and the driver must map it by hand; `agents --write` must be rerun and committed | silent for the driver |
| Moving the "Checkpoint after this step" sentences | nothing changes: `checkpointsAfter` is a runner default `["PLAN-TO-SPEC-GATE", "CLEANUP"]` documented as mirroring the prose (PROCESS.md:139, CLARIFICATIONS.md) | silent, documented |
| Renaming the owner words (approve/delegate/override) | none for the runner; the driver interprets | fine |
| Renaming the judgment-call files in `roundPaths.judgmentCalls` | honoured by the runner; the prose (`AGENTS.md`, `COMMON-PROJECT`) names them by their current names, so the owner would edit both | fine |
| Reverse direction: `AGENTS.md` and `COMMON-ROUND` name runner artefacts (`src/run.py`, `docs/PROCESS.md`, `INDEX.md`, `FINDINGS/`, `HISTORY.md`, `tests-archive/`) | a runner layout change would stale the owner's prose; nothing checks it | silent |

Nothing in the mechanics matches a phrase of the prose; the residual coupling is names (files, steps, keys) and it fails loudly except for the four rows marked silent, each covered by a minor finding or a one-sentence doc note above.
