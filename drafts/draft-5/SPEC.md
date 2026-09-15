# shackles_harness — recreation spec (draft 5)

This document is the entry point for rebuilding `shackles_harness` from scratch. It is
written top-down: this file is the map, and each component has its own file under
`components/`. A reader entering at any level should need almost nothing from the
other levels. Nothing here is implementation; it stops at file lists, function
signatures, data shapes, and test cases.

The requirements are the owner's spec files (listed by `spec.yaml`: `SPEC.md`,
`harness/AGENTS.md`, `harness/project.yaml`, `harness/subAgents.yaml`,
`harness/locked_prose/*`). Everything designed here serves them and must keep working
after arbitrary edits to them. Where the owner's files were silent or ambiguous, the
choice made is logged in `JUDGMENT-CALLS.md` and cited inline as `JC-nn`.

## 1. What the system is, in one screen

The harness runs **rounds** of software development on a git repository. A round is a
fixed sequence of **steps** (`project.yaml: steps`), each performed by an AI agent from a
rendered prompt, most followed by a **gate** (a read-only judging agent) and two of them
by a **checkpoint** (a pause for the owner). Three kinds of actor exist:

| Actor | What it is | What it may do |
|---|---|---|
| **Owner** | The human in the chat session. | Talks in chat. Edits the spec files. Approves, delegates, overrides, answers, abandons. |
| **Driver** | The top-level chat agent (Claude Code session opened in `harness/`). | Runs `src/run.py`. Performs `CHAT-TO-PLAN` itself. Spawns one fresh sub-agent per attempt with a prompt file, saves the sub-agent's final message, calls `record`. Hands the runner *verbatim* owner quotes. Never commits. |
| **Runner** | `src/run.py` and the modules under `src/shackles/`. A plain CLI with no LLM inside. | The only thing that commits, pushes, bills, and produces owner-facing text. Renders prompts, checks results mechanically, keeps `STATE.json`, enforces limits. Never parses prose. |
| **Sub-agents** | Fresh agents spawned by the driver per attempt (producers, gates, one conflict resolver). | Producers write inside their worktree, only in declared paths plus the round folder. Gates are read-only and answer in their final message. |

The **step table** (fixed, in code, lint-checked against `project.yaml` and
`locked_prose/`):

```
CHAT-TO-PLAN → PLAN-AGENTS → PLAN-TO-SPEC → CHECKPOINT-1 → SPEC-TO-TESTS →
SPEC-TO-IMPLEMENTATION → TESTS-TO-SUITE → CHECKPOINT-2 → LANDING → POSTMORTEM → CLEANUP
```

Git is the only lock and the only shared state: claiming a round is a compare-and-swap
push of a branch `round/NNNN`; every state change is a commit on that branch pushed
with a lease (the *fence*). A round lives in its own git worktree. Landing merges the
round into `main`; post-landing steps (POSTMORTEM, CLEANUP) are merged back through a
bounded sync so they are never orphaned.

Money: every attempt is billed from what actually happened (measured usage when the
driver reports it, otherwise an estimate, never below the rung's `spawnCost`), the
driver is billed `driverUsdPerStep` per step, and at CLEANUP the round is billed once for
its net effect on the living paths (`src/`, `docs/`, `tests/`) and for its archived
plan, spec and postmortem summary. Budgets are targets; the *hard stops*
(`hardStopBudgetMultiple`, `hardStopBudgetMultipleIndividual`) pause the round.

Judgment calls: every agent prompt ends with the owner's `COMMON-STEP-END` prose, and the
runner gives every agent a mechanical way to log DEFINED and UNDEFINED judgment calls into
the round folder (`run.py jc` for producers; a field of the final message for gates).

## 2. Vocabulary

- **Spec files** — the files `spec.yaml` lists. Owner-owned, edited often, never edited by
  agents. Guarded by a hashed baseline (§5.1).
- **Harness root** — the `harness/` directory; all `project.yaml` paths are relative to it.
- **Living paths** — `project.yaml: livingSourcePaths`; token-charged.
- **Round folder** — `archives/rounds/NNNN/` (from `project.yaml: roundPaths`).
- **Attempt** — one spawn of one agent for one step, numbered per step: `STEP-n`. Kinds:
  `producer`, `gate`, `conflict` (the single LANDING conflict resolver), `driver`
  (CHAT-TO-PLAN, done by the driver itself).
- **Result** — the agent's final message, JSON, saved by the driver to
  `RESULTS/STEP-n.json`.
- **Finding** — one item of a gate verdict, with a quote, an issue, a suggestion, and a
  blocking flag (which follows the verdict).
- **Pause** — the round is waiting for the owner. Kinds: `approval`, `checkpoint`,
  `needs-owner`, `blocked`, `limit`, `fence`, `landing`.
- **Owner verb** — a runner command the driver issues with a verbatim quote from the
  owner's log: `approve`, `delegate`, `override`, `answer`, `abandon`, `continue`,
  `raise-hard-stop`.
- **Rung** — a key of `subAgents.yaml: agents` (`max`, `high`, `medium`, `low` today).
- **Token** — `ceil(bytes / tokenBytes)`. The single estimate used everywhere.

## 3. Repository tree (top level)

```
shackles_harness/                    git repository root
├── spec.yaml                        OWNER. Lists the spec files.                → components/01-repo-root.md
├── SPEC.md                          OWNER. The implied spec + architecture list.
├── README.md                        What this is, install, first run, commands.
├── .gitignore                       OWNER.log, local.yaml, .worktrees/, caches.
├── .github/workflows/ci.yml         pytest + doctor on push/PR (probes excluded).
├── .worktrees/                      (gitignored) one worktree per round: round-NNNN/
└── harness/                         the harness root                             → components/02-harness-root.md
    ├── AGENTS.md                    OWNER. Agent-facing routing and invariants.
    ├── project.yaml                 OWNER. Settings, prices, step table, paths.
    ├── subAgents.yaml               OWNER. Agent roster (rungs, prices).
    ├── locked_prose/                OWNER. Prompt prose per step; tokens rendered by the runner.
    ├── INDEX.md                     Generated routing index, one line per file; committed.
    ├── local.yaml                   Generated, gitignored, derived facts only (no user input).
    ├── OWNER.log                    Gitignored JSONL of every owner chat prompt (hook-written).
    ├── pyproject.toml               pytest config + the two dependencies (pyyaml, pytest).
    ├── .claude/
    │   ├── settings.json            Hooks: UserPromptSubmit → OWNER.log; SessionStart → checks.
    │   └── agents/                  Generated per rung: shackles-<rung>-work.md, shackles-<rung>-gate.md
    ├── src/                         LIVING. The runner.                          → components/03..11
    │   ├── run.py                   Entry point; argv → shackles.cli.
    │   └── shackles/                One module per responsibility (listed in §4).
    ├── docs/                        LIVING. PROCESS.md, ARCHITECTURE.md, TODO.md, CLARIFICATIONS.md → components/12-docs.md
    ├── tests/                       LIVING. pytest suite, stub agent, fixtures, probes.       → components/13-tests.md, 14-probes.md
    └── archives/                    The record.
        ├── spec-baseline/           MANIFEST.json + files/… snapshot of the accepted spec files.
        └── rounds/NNNN/             One folder per round (layout fixed by project.yaml: roundPaths).
```

## 4. Component map (each is a file under `components/`)

| # | Component | Files | Owns |
|---|---|---|---|
| 01 | Repo root | `spec.yaml`, `SPEC.md`, `README.md`, `.gitignore`, `.github/workflows/ci.yml` | Repo-level scaffolding and CI. |
| 02 | Harness root | `AGENTS.md`, `project.yaml`, `subAgents.yaml`, `locked_prose/`, `INDEX.md`, `local.yaml`, `OWNER.log`, `pyproject.toml`, `.claude/`, `archives/` | The layout every other component addresses. |
| 03 | Runner CLI | `src/run.py`, `shackles/cli.py`, `shackles/output.py` | Commands, exit codes, all owner/driver-facing text. |
| 04 | Spec files & config | `shackles/paths.py`, `specfiles.py`, `config.py`, `agentsmd.py`, `localyaml.py` | Locating, loading, validating and guarding the spec files. |
| 05 | Steps & prose | `shackles/steps.py`, `prose.py`, `plumbing.py` | The step table, token rendering, mechanical instructions. |
| 06 | Owner channel & agent defs | `shackles/ownerlog.py`, `hooks.py`, `agentdefs.py` | OWNER.log, hooks, quote verification, generated agent definitions. |
| 07 | Git | `shackles/gitops.py` | Claim, fence, worktrees, diffs, reverts, merge-tree, bounded sync. |
| 08 | State, results, findings | `shackles/state.py`, `results.py`, `findings.py`, `judgmentcalls.py`, `history.py` | STATE.json, result validation, findings lifecycle, JC lines, HISTORY.md. |
| 09 | Money | `shackles/tokens.py`, `pricing.py`, `ledger.py` | Token estimate, pure prices, the ledger and hard stops. |
| 10 | Round engine | `shackles/round_start.py`, `round_next.py`, `round_record.py`, `round_owner.py`, `advance.py`, `mechanical.py`, `verify.py`, `suite.py`, `landing.py` | The state machine from claim to end. |
| 11 | Doctor & index | `shackles/doctor.py`, `shackles/index.py` | Offline lint/render report; INDEX.md generation. |
| 12 | Docs | `docs/PROCESS.md`, `docs/ARCHITECTURE.md`, `docs/TODO.md`, `docs/CLARIFICATIONS.md` | Rules for agents, map for maintainers, carry-forward files. |
| 13 | Tests | `tests/conftest.py`, `tests/fixtures/`, `tests/stub/`, `tests/test_*.py` | The permanent suite, including the spec drift test. |
| 14 | Probes | `tests/probes/` | Opt-in live-agent tests with planted defects. |
| 15 | Schemas | (data shapes used across components) | Every JSON/YAML/JSONL/Markdown shape the runner reads or writes. |

Dependency direction (arrows = "imports"): 03 → 10, 11 → {04, 05, 06, 07, 08, 09} → 04
(config/paths) only. Component 04 imports nothing but the standard library and PyYAML.
No module imports `cli.py`, `round_*.py` or `doctor.py`. Each `round_*.py` file imports
peers in 10 only through the narrow functions its section names.

## 5. Architecture, cross-cutting

### 5.1 Robustness to spec-file edits (the guard)
- `archives/spec-baseline/MANIFEST.json` holds a sha256 per spec file and the snapshot
  `archives/spec-baseline/files/<path>` holds the accepted content (JC-02).
- `tests/test_spec_guard.py` is the only test that reads the real spec files. It fails,
  printing a unified diff per file, whenever a listed file differs from its snapshot, is
  missing, or a new file matches `locked_prose/*` without a baseline entry.
- `run.py start` refuses while drift exists. `run.py accept-spec` re-baselines after the
  owner reviewed the change. The mechanics tests never read the real spec files; they
  use a generated one-line-per-file spec tree (component 13), so a prose rewrite fails
  only the guard test.
- Every setting the code reads comes from `project.yaml`/`subAgents.yaml`. The code's
  schema may hold a default for a key that is missing from the file; `doctor` names
  every defaulted key, and every key in the file that the schema does not know (JC-08,
  JC-09). Unknown steps, prose files naming unknown steps, and unknown config keys
  refuse `start`.

### 5.2 Git model
- `main` is the landed truth. `round/NNNN` is one round's branch, created from
  `origin/main` at claim time. The branch's first commit adds `STATE.json`; the push of
  that commit with `--force-with-lease=refs/heads/round/NNNN:` (expect: absent) is the
  compare-and-swap claim (JC-13).
- Every runner state change is a commit on the round branch pushed with
  `--force-with-lease=<branch>:<last fence sha>`. A rejected push means another runner
  holds the round: the local runner stops and pauses (`fence`).
- The round's working copy is a git worktree at `<repo>/.worktrees/round-NNNN/`. All
  prompt paths are absolute paths inside it. The driver's own checkout is never written
  by agents; the runner only fast-forwards it after the round ends when it is clean
  (JC-24).
- LANDING computes git's auto-merged tree (`merge-tree`) of `main` and the round head.
  No conflict: verify, then push `main` with a lease on the observed `main` sha; if the
  push loses the race, repeat, bounded by `maxRoundAttempts` (JC-15). Conflict: the
  worktree is set to the auto-merged tree with markers and one `conflict` attempt is
  spawned on the conflicted files only; at record the attempt is judged against the
  auto-merged tree (strays reverted to it, no markers left, verify passes).
- POSTMORTEM and CLEANUP commit on the round branch after landing; the round ends with
  the same bounded merge-and-push loop (the sync) so nothing is orphaned.

### 5.3 The round lifecycle (what the runner does at each step)
1. `start`: lint (5.1), check OWNER.log exists, agent definitions current, main checkout
   clean in living paths (JC-37), remote reachable; pick id; claim; create worktree; pause
   nothing; `next` yields the CHAT-TO-PLAN prompt for the driver itself.
2. CHAT-TO-PLAN (`driver` attempt): the driver writes `PLAN.json` (plain-English plan,
   scope, validation steps, non-goals, assumptions, quote, enumerated questions, accepted
   TODOs) and calls `record`. The round pauses (`approval`) until an owner verb arrives.
   `approve`/`delegate` require every question answered (`answer` verbs) and set the
   round's mode; `override` records skips; `abandon` ends it.
3. PLAN-AGENTS (producer + gate): `AGENTS-PLAN.json`. Validated mechanically at record
   (rungs exist and are at most `maxAgent`; work shares and gate shares each sum to 1;
   off gates carry 0). If skipped by override, the default plan applies (JC-34).
4. PLAN-TO-SPEC (producer + gate): `SPEC.json` + `SPEC.md` in the round folder.
5. CHECKPOINT-1: pause (`checkpoint`) unless delegated through it; the driver gets the
   rendered `CHECKPOINT-OVERVIEW` plus the runner's summary (spend, judgment calls, flags).
6. SPEC-TO-TESTS (producer + gate): new tests under `testPaths` in the worktree; the
   attempt's diff is committed ("frozen") on acceptance. Mechanical: existing suite still
   passes; new tests collect (JC-46).
7. SPEC-TO-IMPLEMENTATION (producer + gate): code under living paths except `testPaths`.
   Mechanical: verify (whole suite) passes within `verifyTimeoutSeconds`; a failure is a
   mechanical rejection that re-spawns the producer with the output (JC-14).
8. TESTS-TO-SUITE (producer + gate): `SUITE.json` decides suite vs archive per test file
   (or function). On acceptance the runner moves archived files to `tests-archive/`,
   re-runs verify (JC-47).
9. CHECKPOINT-2: as CHECKPOINT-1.
10. LANDING (runner-only, plus at most one conflict attempt per merge try): hard-stop
    check on `spent + projected living charge`; merge; verify; push; record
    `landing.main_before` and `landing.landed_commit`.
11. POSTMORTEM (producer + gate): `POSTMORTEM.md` with a `Summary` first section; may
    edit `docs/TODO.md` and `docs/CLARIFICATIONS.md` (charged at
    `postMortemFileCostPerToken`, never a stop).
12. CLEANUP (producer, no gate): tidy edits in living paths. Then the runner books the
    living charge, test base costs, archive charges; writes the round's OWNER.log slice;
    regenerates `INDEX.md`; syncs to main; marks the round ended; prints the bill.

At any point: `NEEDS-OWNER` or `BLOCKED` from a producer pauses regardless of
delegation; so do limits (`maxTurnsPerGate` rejections on a step, `maxTurnsPerRun`
attempts, `maxRunWallClockHours`, the hard stops). Delegation skips only checkpoints.

### 5.4 Prompts
A prompt is one file, `PROMPTS/STEP-n.txt`, assembled by the runner:
`render(<STEP>-OVERVIEW or <STEP>-GATE)` followed by `render(COMMON-STEP-END)` (JC-06).
Rendering resolves `{{ prose.X }}` (another prose file, recursive, cycle-checked),
`{{ project.X }}` (config values plus derived `remaining`, `gates`), `{{ round.X }}`
(from STATE.json and PLAN.json), `{{ agents.X }}` (a `##` section of AGENTS.md by
normalized heading) and `{{ plumbing.X }}` (`PROCESS-INSTRUCTIONS`, `GATE-PROSE`;
runner-generated, mechanical). An unresolved token is an error at run time and a named
item in `doctor`. The prompt's token estimate is compared with `promptTokenWarning`.

### 5.5 Results, verdicts, findings
The driver saves each final message verbatim as `RESULTS/STEP-n.json` and reports usage
through `record` flags. The runner validates the JSON shape (component 15). For gates:
the verdict wins; `blocking` flags are rewritten to follow it (PASS → none blocking;
FAIL → all remaining open findings blocking). Findings get runner-assigned ids; rulings
on disputed findings are applied before new findings; a new finding whose normalized
quote equals a withdrawn one is dropped with a HISTORY note; upheld twice is settled.
A producer's DONE must carry a resolution (`fixed`/`disputed`) for every finding it was
handed, else the attempt is rejected mechanically. `flags` in any result are kept in
STATE and shown at the next pause and at round end.

### 5.6 Money
`components/09-money.md` has the formulas. Summary: attempt cost =
max(`spawnCost`, priced usage) where usage is measured (from `record` flags) or
estimated (prompt tokens in, `estOutputFraction` × that out, cache columns 0);
`driverUsdPerStep` once per accepted step; at CLEANUP the living charge on the net
diff `main_before → cleanup tree` restricted to living paths (per-file price with cap,
base cost on create/delete, renames free, `testBaseCost` per test function joining or
leaving `testPaths`), the carry-forward files at their own rate, and archive charges
for `PLAN.json`, `SPEC.json`+`SPEC.md`, and the `Summary` of `POSTMORTEM.md`.
The ledger never bills a planned share; shares only size prompts and the individual
hard stop.

### 5.7 Where each owner-listed architecture feature lives
| SPEC.md feature | Component |
|---|---|
| Git is the only lock / fence | 07, 10 (`round_start`, `round_record`) |
| Driver interprets, runner verifies verbatim quotes | 06 (`ownerlog`), 10 (`round_owner`) |
| Step table is code, lint-checked; unknown inputs refuse | 05 (`steps`), 11 (`doctor`), 10 (`round_start`) |
| Delegation skips only checkpoints | 10 (`round_next`, `round_owner`) |
| Spec guard: baseline, failing test with diff, start refuses | 04 (`specfiles`), 13 (`test_spec_guard`) |
| Mechanical checks at record; strays reverted | 10 (`mechanical`), 07 |
| Landing conflict = one attempt judged vs auto-merge | 10 (`landing`, `mechanical`) |
| Post-landing bounded sync | 10 (`landing.sync`) |
| Verdict wins, blocking follows | 08 (`results`, `findings`) |
| Mechanics tests on generated spec | 13 (`fixtures/spec_tree.py`) |
| Stub agent drives every path; probes with planted defects | 13 (`stub/`), 14 |
| doctor renders offline | 11 |
| Prompt hook → OWNER.log; start refuses without log | 06, 10 |
| Agent definitions generated per rung | 06 (`agentdefs`) |
| Ledger bills what happened | 09 |
| Findings block, flags reach owner, withdrawn repeats dropped | 08, 10 |
| Whole settings surface; local.yaml generated | 04 (`config`, `localyaml`), 11 |

## 6. Reading order for a rebuild
1. `components/02-harness-root.md` (layout), then `15-schemas.md` (shapes).
2. `04` → `05` → `06` → `07` (leaf components; each buildable and testable alone).
3. `08` → `09` (state and money; pure functions over shapes).
4. `10` (engine) → `03` (CLI) → `11` (doctor/index).
5. `12` (docs), `13` (tests), `14` (probes), `01` (CI).

Every component file follows the same layout: **Purpose · Owns · Depends on · Depended on
by · Files · Signatures · Errors · Invariants · Covered by**.

## 7. Files of this spec
- `SPEC.md` — this map.
- `components/01-repo-root.md` — repo root files and CI.
- `components/02-harness-root.md` — the harness layout, generated files, archives.
- `components/03-runner-cli.md` — `run.py`, commands, exit codes, owner-facing text.
- `components/04-spec-and-config.md` — paths, spec-file guard, config and roster schemas, AGENTS.md sections, local.yaml.
- `components/05-steps-and-prose.md` — the step table, token rendering, mechanical instructions, prompt assembly.
- `components/06-owner-channel.md` — OWNER.log, hooks, quote verification, agent definitions.
- `components/07-git.md` — every git operation.
- `components/08-state-results-findings.md` — STATE.json, result parsing, findings lifecycle, judgment-call files, HISTORY.md.
- `components/09-money.md` — tokens, prices, the ledger, hard stops.
- `components/10-round-engine.md` — start, next, record, owner verbs, advance, mechanical checks, verify, suite moves, landing and sync.
- `components/11-doctor-index.md` — offline doctor report, INDEX.md generation.
- `components/12-docs.md` — the four living docs.
- `components/13-tests.md` — fixtures, the stub agent, every test file and its cases.
- `components/14-probes.md` — live-agent probes with planted defects.
- `components/15-schemas.md` — every data shape (S1–S17).
- `JUDGMENT-CALLS.md` — every choice not made with confidence, classified, cross-referenced.
