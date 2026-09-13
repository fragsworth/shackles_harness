# PROCESS

Normative rules of the shackles harness, one sentence per line; the code is the authority and this file describes it.

## Principles

The runner (`src/run.py`) owns mechanics; the spec files (`spec.yaml` and every file it lists) own judgment.
The runner never matches a phrase of the locked prose; it reads config keys, `{{ ns.key }}` tokens, prose file names and the pipeline table.
Unknown is a warning, never a crash: a missing key takes its `DEFAULTS` value, an unresolved token renders `[unresolved: ns.key]`, an unknown prose file is reported.
Every command prints one JSON object on stdout; humans read stderr.
Exit codes: 0 ok or finished, 1 error, 2 usage or guard refusal or invalid input, 3 check failed or spec drift, 10 checkpoint.
Every state change is a commit on the round branch; every command is idempotent or refuses with exit 2; rerunning the command that crashed resumes.
Git is the lock manager: a remote ref update is the compare-and-swap that claims an id, and a rejected push is the fence.

## Files and paths

`harness/` (H) holds `project.yaml`, `subAgents.yaml`, `AGENTS.md`, `locked_prose/`, `docs/`, `src/`, `tests/`, `archives/`.
Paths in config, artifacts, prompts, findings and STATE are H-relative POSIX; `..` is allowed so a target project beside `harness/` can be declared.
The runner alone converts H-relative paths to repo-relative for git and refuses a path that escapes the repository.
A round lives in `archives/rounds/NNNN/`, named by `roundPaths`; every file name in it comes from `roundPaths`.
Runner-owned round files, reverted when an agent changes them: `STATE.json`, `HISTORY.md`, `OWNER.log`, `PROMPTS/`, `RESULTS/`, `FINDINGS/`, `tests-archive/`, and for each producer the other steps' artifacts (`PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SPEC.md`, `SUITE.json`, `POSTMORTEM.md` belong to their own producer), so only the owner's committed edit of an artifact counts as out of band.
Agents write their artifact, the judgment-call files (append-only) and, for POSTMORTEM, the carry-forward files `docs/TODO.md` and `docs/CLARIFICATIONS.md`.
`archives/rounds/index.jsonl` gets one line per finished or abandoned round; `.gitattributes` merges it with `merge=union`.
The union attribute and the spec baseline are pinned to `harness/archives/` whatever `roundPaths.folder` or `archivesPath` say, so an owner who moves the rounds folder out of `archives/` moves the `.gitattributes` line with it.
Prose is pinned at `prose_commit` (HEAD at start) and read with `git show`; config is read live from the worktree.
Config layering is code `DEFAULTS` < `project.yaml` < `harness/local.yaml` (gitignored); `run.py config` prints the source of each key.
A worktree round reads the copy of `harness/local.yaml` that `start` takes from the checkout it runs in; edit the copy to change the round's local config.

## Steps and acceptance

The pipeline is code (`pipeline.py`), cross-checked against `project.gates`, the prose file names and the artifact keys by lint, `doctor` and `start`.
Renaming, adding or reordering a step or gate is loud (lint refuses `start`) and touches the step names in `pipeline.py`, `round.py`, `prompts.py`, `landing.py`, `checks.py`, `config.py`, the stub and the fixtures.
Steps in order: CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, PLAN-AGENTS, PLAN-AGENTS-GATE, PLAN-TO-SPEC, PLAN-TO-SPEC-GATE, SPEC-TO-TESTS, SPEC-TO-TESTS-GATE, SPEC-TO-IMPLEMENTATION, SPEC-TO-IMPLEMENTATION-GATE, TESTS-TO-SUITE, TESTS-TO-SUITE-GATE, CLEANUP, LANDING, POSTMORTEM, POSTMORTEM-GATE.
CHAT-TO-PLAN is done by the driver in chat before `start`; CHAT-TO-PLAN-GATE is mechanical (PLAN.json valid, the owner's word recorded) and passes inside `next` with one attempt counted and one HISTORY line, no prompt and no FINDINGS file; LANDING is mechanical.
An LLM gate runs iff its `gates` flag is 1, its prose file exists at `prose_commit`, and neither it nor its producer is overridden; otherwise it is skipped with `FINDINGS/<GATE>-<n>.json` of source `disabled`, `override` or `no-prose`.
A producer with no `<STEP>-OVERVIEW.txt` at `prose_commit` is a `start` error; an enabled gate without prose is disabled with a warning.
Acceptance of a producer is its gate's PASS, or its clean DONE when the gate does not run; acceptance effects: PLAN-TO-SPEC charges the spec words, SPEC-TO-TESTS freezes the tests at HEAD, TESTS-TO-SUITE moves `archive` files into `tests-archive/` (collisions get a numeric suffix).
Overridable: every gate, PLAN-AGENTS (default shares and rungs), SPEC-TO-TESTS (nothing frozen; SPEC-TO-IMPLEMENTATION writes under `testPaths` too), TESTS-TO-SUITE (every test kept), CLEANUP (skipped, the pre-landing review still happens), POSTMORTEM (the round finishes after LANDING).
Not overridable: CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, PLAN-TO-SPEC, SPEC-TO-IMPLEMENTATION, LANDING.
`checkpointsAfter` names the steps whose completion raises a `review` checkpoint unless the round is delegated through them.
Attempt numbers of a step never restart, so `PROMPTS/`, `RESULTS/` and `FINDINGS/` names stay unique even after UPSTREAM or an out-of-band edit.

## Runner commands

`doctor` checks the environment, config, lint, drift, hook, `claude` resolution, agent definitions and renders every prompt on a fixture round; `--probe-cli` makes one capped real call.
`config`, `render --step S [--fixture] [--raw]`, `spec status|diff|accept --note T` and `agents [--write]` read or regenerate files without touching a round.
`start --plan F` validates the plan before any git command, refuses on spec drift unless `--accept-spec`, claims an id on origin, adds the worktree and makes the start commit, and prints its FLAGs as `warnings`; `--no-branch` runs in the main checkout (refused from a linked worktree); `--delegate [--through STEP]` overrides the plan's mode, and `--through` alone is refused unless the plan is delegated.
A worktree round starts from `origin/<mainBranch>`, so `start` refuses while a spec file, `spec.yaml` or the baseline differs from it: commit and push the change first (`--accept-spec` then covers drift that is already on origin).
`next` does mechanical work until an agent run is due and prints the action, a checkpoint (exit 10) or `done`; `--discard` resets unrecorded work of the pending attempt, which `next` otherwise refuses to touch while any dirty path lies inside that attempt's write paths.
`record --step S --attempt N --result F [--cost USD | --tokens N [--agent RUNG]] [--spawns K]` validates the final message, runs the checks, routes the outcome, books the cost, commits and pushes; `--agent` names the roster rung that actually ran, priced instead of the action's, and is refused unless it is a roster key.
`approve`, `delegate [--through STEP]`, `answer --text T`, `override --steps A,B` and `abandon --reason R` carry the owner's words in `--quote` and are verified against the owner log when it exists (`--unverified` records them with a FLAG); a refused command writes nothing (its quote line and `RESUME` entry are undone), and a `resumed` payload carries `warnings` as a checkpoint payload does.
`status`, `spend [--project]` and `rounds` are read-only; `status` carries `living_preview_usd`, the charge the diff from `base_commit` would book, until the round lands (then the booked `living_usd` is the figure); `check` writes nothing shared: it runs the current step's checks, or at LANDING merges the target into the worktree and runs verify and the suite, and exits 3 on findings.
`run --until checkpoint|step|done` is the headless loop (next, agent command, record); `probe` and `sandbox` are the real-agent testing tools of docs/TESTING.md.
A `record` whose push is rejected stops with `another runner owns this round (push rejected)`; any other push failure exits 1 and `next` pushes again when the branch is ahead.

## The driver

The driver runs `next`, spawns one fresh sub-agent per action with the prompt file as its whole instruction, saves the final message to the result file and runs `record`; docs/DRIVER.md has the exact loop.
The driver never judges, never edits an artifact or result, never commits or pushes, and drives a round with the worktree's own `run.py` (a `runner_skew` warning names the right one).
The prompt handed to a sub-agent is the file's entire content, unaltered, referenced by path with the fixed one-line wrapper in `contract.WRAPPER`, which the action prints filled in as `task`.
The action names the sub-agent as `agent_type` (`shackles-producer-<rung>` or `shackles-gate-<rung>`) and, for a session that registered no such definition, `fallback_agent_type` (`general-purpose`) with `model_alias`; the runner cannot see the session's agent list, so it never guesses which applies.

## Contracts

A prompt is `harness/AGENTS.md` verbatim, a blank line, then the rendered `<STEP>-OVERVIEW.txt` or `<GATE>.txt`; the process block is appended when the prose lacks the `plumbing.PROCESS-INSTRUCTIONS` token.
The machine-readable lines are the last `STEP:`, `KIND:`, `ROUND:`, `ATTEMPT:`, `WORKTREE:`, `HARNESS:`, `ARTIFACT:`, `RESULT_FILE:`, `DIFF_FILE:`, `WRITE_PATHS:`, `FROZEN_PATHS:` and `MERGE_IN_PROGRESS:` lines of `src/shackles/plumbing/producer.txt` and `gate.txt`.
A producer ends with `{"status": DONE|NEEDS-OWNER|UPSTREAM|BLOCKED, ...}` and a gate with `{"verdict": PASS|FAIL, "findings": [...], ...}` as `schemas.py` defines; the JSON is extracted from the whole message, the last fence, or the last top-level balanced object that carries `status` or `verdict` (a nested resolution, ruling or `needs_owner` never wins).
`record` rewrites `RESULTS/<STEP>-<n>.json` as the parsed object, pretty-printed (a gate's findings normalized), and HISTORY quotes the first 2000 characters of its `notes`, marking a cut.
An invalid final message is saved raw as `RESULTS/<STEP>-<n>.raw-<k>.txt`, counted as an infrastructure error with its cost booked, and the same attempt is rerun; `infraRetries` invalid results at one attempt raise the `infra` checkpoint.
The producer's `judgment_calls` are counts, and a gate-shaped list of lines is tolerated; the runner counts the files, not the message.
The gate's verdict is authoritative: a PASS with blocking findings makes them non-blocking, a FAIL without a blocking finding keeps the findings as given, and either mismatch is one HISTORY line.

## Findings, disputes, settlement

Gate findings enter the ledger as `open`; a producer resolves each as `fixed`, `disputed` or `deferred`, and an open gate or owner finding it omits from `resolutions` counts as `fixed` with a HISTORY line.
A disputed finding is ruled `upheld` or `withdrawn` by the next gate; upheld twice is `settled` and a further dispute is ignored with a note; withdrawn is closed and a re-raised copy (same quote) is dropped.
`deferred` findings are carried to every later producer and to POSTMORTEM; non-blocking findings of a PASS are carried the same way, and so is each `raise_with_owner` item of an accepted SUITE.json (source `flag`), which HISTORY records as `flagged for the owner: ...`.
Mechanical findings (M*, S*, L*) are not disputable; they close when the producer's next attempt passes its checks.
Routing findings: `U1` (UPSTREAM, attached to the target; an overridden target is refused as `S1` on the source, which never re-enters), `B1` (BLOCKED), `O1` (the owner's answer, blocking), `Q1` (a withdrawn question, the answer to assume), `W1` (a live sibling declares an overlapping path).

## Checkpoints and owner commands

Checkpoint kinds: `review` (after a `checkpointsAfter` step), `question` (NEEDS-OWNER upheld by the gate, or the gate not running), `blocked`, `failure-limit`, `round-limit`, `hard-stop`, `spec-edit` (before LANDING, never skipped), `upstream-plan`, `approval` (the plan changed), `infra`.
Every checkpoint message carries the spend versus the quote, the counts of defined and undefined judgment calls, the count added since the last checkpoint and the last five undefined lines with the file's absolute path, and the exact resume commands.
`approve` continues; at `failure-limit` it resets that step's failures, at `spec-edit` it accepts the baseline on the branch, at `upstream-plan` it needs an edited PLAN.json, at `question` it means "proceed on your stated assumption", and at `blocked` it says the same words although a BLOCKED producer stated no assumption, so `answer --text` or `override` is the natural resume there.
The CHECKPOINT entry reaches HISTORY after the attempt entry that raised it (`save` writes it).
`delegate` is approve plus delegation; delegation skips only `review` checkpoints, and `--through STEP` skips those at or before STEP, where STEP may name the producer or its gate (`PLAN-TO-SPEC` and `PLAN-TO-SPEC-GATE` skip the same reviews); a `through` that is absent, null or empty (in the plan or on the command line) skips every review, and one naming no step is refused.
`answer --text T` turns the text into finding `O1` for the producer of the checkpoint, which runs again with it.
`override --steps A,B` skips overridable steps not yet accepted, at any time (a producer that already ran and waits for its gate is refused: override the gate, which accepts the artifact as it is), and discards the unrecorded work of a pending attempt of a step it names (HISTORY lists the reverted paths), while unrecorded work of a pending attempt of any other step refuses it (`record` first); at a checkpoint it resumes the round when the checkpoint's own step is now overridden, otherwise the checkpoint stands and `approve` follows; `abandon --reason R` tags `round/NNNN-abandoned` and writes the index line, before landing only.
A gate verdict that neither upholds nor withdraws the producer's question proceeds on the stated assumption and appends it to `UNDEFINED_JUDGMENT_CALLS.md`; so does an `override` of the gate the question waits at; an `override` of the producer drops its question with a HISTORY line.

## Caps and stops

`maxFailuresBeforeStop` counts FAILs per producer step (gate or mechanical) and raises `failure-limit`.
`maxRoundAttempts` caps `round_retries`, the count of re-entries (UPSTREAM, out-of-band plan or spec edits, landing L1 and L2); one more raises `round-limit` once.
`hardStopBudgetMultiple` times the quote is the hard stop on the total spend, raised once as `hard-stop` before the next render.
A committed out-of-band edit of PLAN.json returns the round to CHAT-TO-PLAN-GATE and clears the approval; a committed edit of SPEC.json or SPEC.md after acceptance returns it to SPEC-TO-TESTS; an uncommitted one is reset with the dirty tree (HISTORY names the paths) or refused as unrecorded work.

## Mechanical checks

S1: the artifact is readable and valid (schema and rules); S2: every changed test file is in exactly one of `keep` and `archive`, by the H-relative path the prompt prints.
M0: HEAD moved during the attempt (an agent commit is undone by a soft reset; on a merge attempt it is an infrastructure error).
M1: changed paths outside WRITE_PATHS, the round folder and the spec files, or inside runner-owned files (the other steps' artifacts included), are reverted and listed.
M2: a change under `testPaths` after the tests froze is reverted; on a merge attempt a conflicted test is the non-blocking `T1` instead.
M3: `SPEC.verify` runs from H under its timeout at SPEC-TO-IMPLEMENTATION and CLEANUP; M5: `suiteCommand` runs at CLEANUP (and as L2 at LANDING).
M4: the judgment-call files only grew since the prompt commit; a rewrite is restored.
E1: a change to a spec file is never reverted; its diff goes to HISTORY, `spec_edits` lists the spec files that differ from `base_commit`, the branch's baseline is accepted provisionally, and the `spec-edit` checkpoint fires before LANDING.
G1: a gate run that changed files is discarded as an infrastructure error.
W1 and W2 are warnings: an overlapping sibling path, and a prompt over `promptTokenWarn` tokens.
L1: the round conflicts with the landing target; L2: verify or the suite is red on the merged tree; L3: conflicted files were left unresolved.
Checks run at `record` on the uncommitted diff of the attempt; strays are reverted before the commit, so the committed tree is always within scope; on UPSTREAM and BLOCKED, M2 and M1 revert the same way with one HISTORY line naming the paths.

## Costs

Step budget: producers get `quote x workFraction x shares.work[step]`, gates `quote x gatesFraction x shares.gates[producer]`; shares come from AGENTS-PLAN.json once accepted, else `defaultShares`, else an equal split of the remainder over unassigned steps; only LLM gates take gate shares (CHAT-TO-PLAN-GATE is mechanical, so a `CHAT-TO-PLAN` gate share is ignored).
The per-run cap is `max(minRunUsd, budget x hardStopBudgetMultiple)`; `retry_cost` is the producer's budget plus `spawnCost` plus `driverUsdPerStep`.
An agent run costs `--cost` (source `agent-cli`), else `--tokens` priced by the rung with the `estOutputFraction` blend plus `spawnCost` per spawn (`agent-tokens`), else the step budget as a flagged estimate; never below `spawnCost`.
The driver costs `driverUsdPerStep` per `record` and once at `start`.
The owner costs `costToWaitForOwner + ownerHourlyRate x ownerMinutesPerCheckpoint / 60` per checkpoint raised, `planCostPerWord` per plan word at `start`, and `specCostPerWord` per SPEC.md word at PLAN-TO-SPEC's acceptance.
Time costs `lostValuePerHour` per hour from `created_at` to `landed_at`, `abandoned_at` or now, computed on read.
The living charge is booked once at LANDING against the tip actually merged: per living file, `ceil(bytes / tokenBytes)` tokens priced at `livingFileCostPerToken` up to `livingFileTokenCap` and `livingFileCostPerTokenOverCap` beyond, the delta charged, `livingFileBaseCost` added per new file and refunded per deleted file, `testBaseCost` per net new match of `testFunctionPattern` in kept test files.
Living paths are `livingSourcePaths`; `__pycache__` and `*.pyc` are excluded; edits to the carry-forward files after LANDING are merged by `sync_main` and never charged.
`spend --project` sums `index.jsonl`, every unindexed local round and every live sibling read from origin; `project.remaining` is `budget` minus that.

## Landing and concurrency

Rounds start from `origin/<mainBranch>` in a worktree at `<worktreeDir>/round-NNNN` (`worktreeDir` must be gitignored) on branch `round/NNNN`, claimed by a lease push that must create the ref; `pushAttempts` bounds the claim loop.
LANDING's check phase fetches, computes `git merge-tree --write-tree` against the target and merges cleanly or raises `L1`, then runs verify and the suite (`L2`); it never pushes, tags or charges.
The land phase pushes `HEAD:refs/heads/<mainBranch>` in a loop of `pushAttempts`, re-running the check phase after a rejection, then books the living charge once, tags `round/NNNN-landed` and sets `landed_at`.
On `L1` the round re-enters SPEC-TO-IMPLEMENTATION as a merge attempt: the prompt lists the conflicted files, the merge is established in the worktree after the prompt commit, M1 and M2 see only what differs from the automerge tree (the sibling's changes never count), L3 rejects unresolved files, and the commit has two parents; acceptance returns to LANDING where the target is already contained.
A hand merge by the owner in the worktree lands without any command, before or after L1 has raised the merge attempt (`next` sees the target already in HEAD and returns to LANDING); `L2` re-enters the same way without a pending merge.
A merge attempt ends in the merge commit or not at all: on L3, an invalid result, M0, UPSTREAM or BLOCKED the runner aborts the merge, commits the record as usual, and the next attempt re-establishes the merge from the conflicted state.
The gate's `DIFF_FILE` for a code step is the diff of the producer's write paths since the step started, without the round folder; after a merge commit the step starts at the automerge tree, so the sibling's changes never appear in it.
`sync_main` after the last commit merges `origin/<mainBranch>` and pushes in a bounded loop; a conflict leaves `main_synced: false` and the tail arrives with the next landing.
Invariants: one round per id, nothing created before the claim wins, one worktree per round, nothing touches main before LANDING, one runner per round (the fence), main only fast-forwards, no auto-resolved conflict, one living entry per landed round, `check` writes nothing shared, headless agents get no push credential, crash recovery by rerun.
In driver mode a sub-agent inherits the session's git credentials (`scrubEnv` applies to headless runs only), so only the agent definition's `disallowedTools`, G1 and M0 stand between it and a push.
Landing conflicts converge because the merge attempt is measured against the automerge tree, not against the step start.

## Spec files

`spec.yaml` lists the owner's files; `archives/spec-baseline.json` holds their accepted hashes (BOM stripped, newlines normalized) and `archives/spec-changes.jsonl` one line per acceptance.
`tests/test_spec_baseline.py` fails on any drift with the categorized list, the diff and the review instruction; `start` refuses drift unless `--accept-spec`.
`spec accept` rewrites the baseline and appends the audit line in the working tree and prints `head_at_accept`, the HEAD it was accepted at: the acceptance itself lands in the next commit, so a later `spec diff` (against that HEAD) shows the accepted change once more.
A round that edits a spec file keeps the edit; HISTORY shows the fenced diff, the branch carries a provisional acceptance of the baseline (so the guard stays green when M5 and L2 run the suite on the branch, and an edit undone later needs no approval), and the owner approves at the `spec-edit` checkpoint, which re-accepts the baseline with their words.
Nothing mechanical depends on the wording of the prose; the mechanics tests run on a generated fixture spec.

## Wording-adjacent rules

Settled after two upholds mirrors COMMON-GATE; the status and verdict words mirror COMMON-OVERVIEW and COMMON-GATE (`doctor` warns when a word is missing from the prose).
`checkpointsAfter` mirrors the "checkpoint after this step" sentences and the `gates` comments; the step order mirrors the `gates` order.
Gates are read-only by construction (agent definitions, tool flags, G1) as AGENTS.md says; gates return judgment calls in their verdict and the runner appends them.
The owner's words are interpreted by the driver and passed with `--quote`; the runner only verifies the quote against the owner log.
The carry-forward files mirror POSTMORTEM's TODOs and CLARIFICATIONS; the runner never parses them.

## Config keys

`mainBranch`, `worktreeDir`, `pushAttempts`, `infraRetries`, `checkpointsAfter`, `ownerMinutesPerCheckpoint`, `minRunUsd`, `promptTokenWarn`, `postmortemFeedRounds`, `findingQuoteMaxChars`, `testFunctionPattern`, `suiteCommand`, `suiteTimeoutSeconds`, `agentCommand`, `agentTask`, `claudePath`, `gateToolFlags`, `producerToolFlags`, `scrubEnv`, `modelAliases`, `envelopePrefixes`, `agentOverride` and `carryForwardFiles` are runner keys with defaults in `config.DEFAULTS`, overridable in `project.yaml` or `local.yaml`.
`budget`, `hardStopBudgetMultiple`, `lostValuePerHour`, `ownerHourlyRate`, `costToWaitForOwner`, `planCostPerWord`, `specCostPerWord`, `livingFileTokenCap`, `livingFileCostPerToken`, `livingFileCostPerTokenOverCap`, `livingFileBaseCost`, `testBaseCost`, `tokenBytes`, `maxRefactorOverhead`, `gates`, `defaultShares`, `livingSourcePaths`, `lockedProsePath`, `archivesPath`, `roundPaths`, `maxSimultaneousSubAgentsPerRound`, `maxRoundAttempts`, `maxFailuresBeforeStop`, `maxTurnsPerRun`, `maxRunWallClockHours`, `verifyTimeoutSeconds`, `gatesFraction`, `workFraction`, `estOutputFraction`, `driverUsdPerStep`, `subAgentsFile`, `maxAgent`, `gateAgent`, `systemTestAgent`, `shackles` and `currency` are the owner's keys, read with today's values as defaults.
`maxRefactorOverhead` is enforced on the SPEC's declared `refactor` budgets; `maxSimultaneousSubAgentsPerRound` on AGENTS-PLAN's `subAgents`; `maxTurnsPerRun` is advisory text; `maxRunWallClockHours` is the headless timeout.

## Windows notes

Subprocesses are argv lists, never a shell; child Pythons get `PYTHONUTF8=1`; timeouts kill the process tree with `taskkill /T /F`.
Files are written atomically (temp then replace, retried on `PermissionError`); `shutil.rmtree` clears read-only bits; paths are compared with `os.path.normcase`.
Round worktrees carry long paths, so `doctor` warns when `core.longpaths` is not true and `sandbox` sets it on the repositories it creates.
The hook command is `py -3.13 harness/src/owner_log_hook.py`; `claude.exe` is found under `%APPDATA%\Claude\claude-code\` when it is not on PATH.
