# 02 — The round lifecycle

This file is behaviour, not code: what a round is, what each step does, which owner
words move it, and what pauses it. Modules that implement each part are named in
parentheses; their signatures live in files 03–15.

## 1. Round status and position (state.py)

A round is exactly one of:

| status | meaning |
|---|---|
| `PLANNING` | claimed; CHAT-TO-PLAN in progress in the owner's chat |
| `RUNNING` | approved; the runner advances through the table |
| `PAUSED` | waiting for the owner; `pause.reason` says why |
| `DONE` | CLEANUP recorded, charges booked, main synced |
| `ABANDONED` | ended without landing (or after landing, by owner word) |

`position` = `{step, phase, attempt}` where `phase` ∈ `produce | gate | checkpoint |
runner`. The step table (`steps.py`) is walked strictly in order; a step is left only
when it is **accepted** (producer DONE and gate PASS or gate off/overridden), **skipped**
(owner override, or a checkpoint under delegation), or the round pauses/ends.

## 2. Before a round: install, doctor, accept

- `install` generates `.claude/agents/*.md`, `.claude/settings.json` (the owner-log
  hook), `CLAUDE.md`, `INDEX.md`, and writes `local.yaml`. It is re-run after any change
  to `subAgents.yaml`; the session must then be restarted because the Agent tool reads
  definitions at session start.
- `doctor` reports, without network: config validation and defaulted keys, step-table
  lint, every prompt rendered with a sample round, unresolved tokens, unknown and
  unreferenced prose files, spec drift, generated-file staleness, hook installation,
  `OWNER.log` presence, prompt-size warnings.
- `spec status|diff|accept`: the drift guard. The drift test fails after any spec-file
  edit and prints the diff; the owner reviews and runs `spec accept`, which rewrites the
  hashes in `local.yaml` and the copies in `archives/spec-baseline/`.

## 3. Start (rounds.py, gitops.py)

`start --quote "<the owner's words that asked for this round>"` [JC-53] refuses (exit 3) when:
spec drift exists; generated files are stale relative to `subAgents.yaml`; the hook is
not installed; `OWNER.log` is missing or empty; the quote is not in the log; git has no
`origin`; another round is active (any `round/*` branch whose STATE.json is not
`DONE`/`ABANDONED`) [JC-05]; the step-table lint fails; `allowUpstream` is not `0`
[JC-06]; `gatesFraction + workFraction` is not 1.

Otherwise it: fetches; picks id `NNNN` = 1 + max over `archives/rounds/*` on
`origin/main` and remote `round/*` branches; creates `round/NNNN` from `origin/main`;
records `base_commit` = that commit; adds the worktree `.worktrees/round-NNNN`;
scaffolds the round folder (STATE.json `PLANNING`, empty HISTORY.md, empty judgment-call
files, the folders); commits; pushes the new branch (a plain push of a new branch is the
compare-and-swap; rejection means the id is taken → retry with the next id, at most
`maxRoundAttempts` times). The run clock starts.

## 4. The steps, one by one

The table (today's `project.yaml`): CHAT-TO-PLAN, PLAN-AGENTS, PLAN-TO-SPEC,
CHECKPOINT-1, SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, TESTS-TO-SUITE, CHECKPOINT-2,
LANDING, POSTMORTEM, CLEANUP. Kinds: **chat** (driver produces), **producer** (spawned
agent), **checkpoint** (owner pause), **runner** (no agent unless a conflict).

### CHAT-TO-PLAN (chat; artifact `PLAN.json`)
`next` renders `PROMPTS/CHAT-TO-PLAN-1.txt` and answers `action: chat`: the driver reads
the prompt itself, talks to the owner, and writes `PLAN.json` in the worktree round
folder (plain-English plan text, quote, numbered questions with lettered options,
answers with the owner's verbatim quotes, accepted TODOs, non-goals, validation steps).
Approval is `record CHAT-TO-PLAN --decision approve|delegate [--through STEP]
[--override X,Y] --quote "..."`. The runner verifies every quote (approval and each
answer) against `OWNER.log`, refuses if any question lacks an answer, validates
overrides (see §5), stores the approval in STATE.json, and moves to `RUNNING`.
The gate for this step is judged like any other if the owner turns it on and a
`CHAT-TO-PLAN-GATE.txt` exists; if it is on without prose, lint refuses to start [JC-07].

### PLAN-AGENTS (producer; `AGENTS-PLAN.json`)
Rung `defaultAgent`; its gate uses `gateAgent`. The artifact assigns to every
agent-bearing step and every gate-capable step a rung, a share of the quote, allowed
sub-agents, and a rationale. `record` validates: rungs exist and are at or below
`maxAgent` on the ladder; work shares sum to `workFraction` (±0.001) and on-gate shares
to at most `gatesFraction`; sub-agents per step ≤ `maxSimultaneousSubAgentsPerRound`;
shares below `defaultShares` only warn (advisory) [JC-08]. After acceptance every later
attempt takes its rung and budget from this artifact; LANDING's contingent attempt takes
`defaultAgent` if the plan omits it.

### PLAN-TO-SPEC (producer; `SPEC.json` + `SPEC.md`)
`SPEC.json` is machine-read (components with ids, implementation steps, a test plan
with ids, non-goals carried from the plan); `SPEC.md` is the owner-read prose. The gate
prompt carries both.

### CHECKPOINT-1 / CHECKPOINT-2 (checkpoint)
Skipped when the approval mode covers it (`delegate`, or `delegate through STEP` with
STEP at or after the checkpoint). Otherwise `next` answers `action: checkpoint` with an
owner message composed by the runner (work so far, spend vs quote, judgment calls
recorded since the last pause, undelivered flags, open non-blocking findings). The
driver relays it and waits. `record CHECKPOINT-n --decision approve|delegate|abandon
[--through STEP] --quote "..."` continues, widens delegation, or ends the round.

### SPEC-TO-TESTS (producer; writes under `testPaths`)
Declared paths: `testPaths` + round folder. Mechanical verify: the suite **collects**
(`pytest --collect-only`) without error [JC-70]. On acceptance the runner records
`frozen_tests` (the commit and the list of test files touched) — from here on test
edits are strays until landing.

### SPEC-TO-IMPLEMENTATION (producer; writes living paths minus `testPaths`)
Mechanical verify: the whole suite passes within `verifyTimeoutSeconds`. A failing
suite is a runner-generated blocking finding (`R<n>`, quote = the failure tail) and the
producer is retried like after a gate FAIL.

### TESTS-TO-SUITE (producer; `SUITE.json`)
The plumbing lists this round's tests (test functions added or changed under
`testPaths` since `base_commit`, found by `suite.py` with `ast`). `SUITE.json` gives
each one `suite` or `archive` and may add flags. `record` refuses a missing decision,
then applies the moves (archived functions are cut out and appended to
`tests-archive/<same relative path>`), commits, and verifies the suite passes.
If the step was overridden, nothing moves: every round test stays in the suite [JC-09].

### LANDING (runner; contingent attempt)
1. Fetch; `pre_landing_main` = `origin/main`. Projected living charge =
   `ledger.living_charge(pre_landing_main, round tip)`. If spend + projected exceeds
   `hardStopBudgetMultiple × quote` (or the round's override) → pause `HARD_STOP`.
2. Merge `origin/main` into the round branch in the worktree. Clean merge → verify
   suite → push branch → push `round/NNNN:main` with a lease on the fetched main sha.
   Rejected (main moved) → repeat from 1, at most `maxRoundAttempts` loops, then pause.
3. Conflict → **one** agent attempt `LANDING-1`: the prompt lists the conflicted files
   and the auto-merged tree is the baseline (git's merge result with markers). Declared
   paths: the conflicted files only. `record LANDING 1` checks: no conflict markers, no
   strays relative to the auto-merged tree, suite passes. Then continue at step 2's
   push. A second conflict, a BLOCKED/NEEDS-OWNER result or a failed verify → pause
   `LANDING_FAILED`.
4. On success STATE.json records `landed_commit`; `next` then fast-forwards the main
   checkout so the runner code in use is the landed one [JC-10].

### POSTMORTEM (producer; `POSTMORTEM.md`, `docs/TODO.md`, `docs/CLARIFICATIONS.md`)
Runs after landing, on the round branch. Declared paths: round folder + the
carry-forward files (`carryForwardFiles`, default the two above [JC-11]). Verify: suite
passes. Its charges never pause the round.

### CLEANUP (producer, no gate; then the runner books)
Declared paths: living paths + round folder. Verify: suite passes. Then the runner:
regenerates `INDEX.md`; copies the round's `OWNER.log` slice; books the living charge
(`pre_landing_main` vs the tree cleanup leaves), the archive charges (plan, spec,
postmortem Summary), the test base costs; writes the final ledger and the owner
message (POSTMORTEM Summary verbatim, charges, undelivered flags); sets `DONE`;
commits; runs the **bounded sync** (§7); removes the worktree.

## 5. Owner words (the driver interprets, the runner verifies)

The words that count are in `CHAT-TO-PLAN-OVERVIEW.txt`; the runner never reads them.
The driver maps them to these structured decisions, always with a verbatim `--quote`:

| decision | where | effect |
|---|---|---|
| `approve` | CHAT-TO-PLAN, checkpoints | continue; checkpoints stop |
| `delegate [--through STEP]` | CHAT-TO-PLAN, checkpoints | continue; checkpoints at or before STEP are skipped (no STEP = all) |
| `--override A,B-GATE,...` | CHAT-TO-PLAN only | skip step A; skip B's gate. CHAT-TO-PLAN, LANDING and CLEANUP cannot be skipped [JC-12] |
| answers | inside `PLAN.json` | each question carries `answer` and `quote` |
| `abandon` | anywhere (`abandon --quote`) | status `ABANDONED`; nothing lands; the worktree is removed; the branch stays as a record |
| `resume` | while `PAUSED` | records the quote for the next prompt's OWNER DECISIONS block; grants another run |

Quote verification: whitespace-normalised substring of any entry in the local
`OWNER.log` or the round's committed slice [JC-13]. No keyword check of any kind.

## 6. Pauses and limits (pauses.py)

Every pause sets `status: PAUSED` and `pause = {reason, step, attempt, message,
questions}`; `next` answers `action: paused` with the message for the owner. Reasons:

| reason | trigger |
|---|---|
| `NEEDS_OWNER` | a producer or the landing attempt ended `NEEDS-OWNER`; its questions are relayed verbatim |
| `BLOCKED` | a producer ended `BLOCKED`; its `narrow` text is relayed |
| `GATE_LIMIT` | a gate FAILed the producer `maxTurnsPerGate` times |
| `INVALID_LIMIT` | a step produced `maxRoundAttempts` invalid results in a row [JC-56] |
| `HARD_STOP` | round spend (+ projected living charge at landing) > `hardStopBudgetMultiple × quote` |
| `HARD_STOP_INDIVIDUAL` | one attempt's cost > `hardStopBudgetMultipleIndividual × its share × quote` [JC-71] |
| `TURN_LIMIT` | `maxTurnsPerRun` `next` calls in the current run [JC-14] |
| `WALL_CLOCK` | `maxRunWallClockHours` elapsed in the current run |
| `LANDING_FAILED` | see LANDING §4 |
| `SYNC_FAILED` | see §7 |
| `FENCE` is not a pause: it is exit 4, "the round advanced elsewhere, run next again" |

`resume --quote "..." [--hard-stop-multiple N] [--hard-stop-multiple-individual N]
[--extend]` clears the pause, starts a new run (turn counter and clock reset), records
the quote, increments `restarts`; beyond `maxRoundAttempts` restarts it refuses unless
`--extend` is given [JC-15]. A resumed `GATE_LIMIT` step gets a fresh allowance of
`maxTurnsPerGate` turns. Hard-stop overrides are round-scoped and logged with the quote.

Delegation never suppresses any pause above.

## 7. After landing: the bounded sync (landing.py)

At the end of CLEANUP (and at `abandon` after a landing) the round branch holds commits
main does not have. The sync loop, at most `maxRoundAttempts` times [JC-16]: fetch;
merge `origin/main` into the branch; on a clean merge push the branch and push
`round/NNNN:main` with a lease; on rejection loop; on a textual conflict run one
LANDING-kind attempt exactly as in landing (`LANDING-<n>`); on failure pause
`SYNC_FAILED` with the state `DONE_PENDING_SYNC` recorded in the pause, so the owner can
finish by hand or `resume`. Success removes the worktree; the remote branch is kept.

## 8. Findings, flags and silence (findings.py)

- A gate FAIL sends the producer a retry prompt with every open finding, verbatim, and
  the producer must return a `resolution` (`fixed` or `disputed` + note) for each
  blocking one; a missing resolution makes the result **invalid** (exit 5, re-run).
- The next gate rules `upheld`/`withdrawn` on each disputed finding with a quote.
  Upheld twice → `settled`: a later `disputed` resolution is invalid. Withdrawn →
  closed; a new finding whose normalised quote equals a withdrawn one's is dropped and
  a note is appended to HISTORY.md [JC-17].
- Verdict wins: `FAIL` with only non-blocking findings marks them all blocking; `PASS`
  with blocking findings downgrades them to flags.
- Non-blocking findings, producer `flags`, and dropped-finding notes are queued as
  flags; every checkpoint, pause message and the final owner message lists undelivered
  flags and marks them delivered on record.

## 9. Judgment calls (judgment_calls.py)

Producers append one line per call through `run.py jc --kind defined|undefined ...`
into the round's two `.md` trails; gates and any agent may also list them in the final
message's `judgment_calls`, which `record` appends with the step and attempt. The
checkpoint and pause messages count them since the last pause.

## 10. Multi-machine behaviour

STATE.json on the round branch is the only state. On any machine, `next` fetches,
discovers the active round from `round/*` branches, creates the worktree if missing,
and proceeds. Every state-changing command pushes with a lease on the branch sha it
read; a rejected push is a fence (exit 4). `OWNER.log` is per machine; quotes said on
another machine are found in the round's committed slice.
