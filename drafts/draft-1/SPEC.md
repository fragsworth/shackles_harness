# shackles_harness — recreation spec (draft 1)

This is the entry point. It is the top of a tree: this file describes the whole
system and the repository root; each linked file describes one level below,
and each of those describes its own children. A reader entering at any file
should need little from the others. Everything here serves the owner's spec
files (`spec.yaml` and the files it lists); nothing here is allowed to break
when the owner edits them.

Judgment calls made while drafting are logged in `JUDGMENT-CALLS.md`; they are
cited inline as `[JC-nn]`.

## 1. What the system is

A **round-based software development harness**. A human **owner** talks in a
Claude Code chat session. The top-level agent in that session, the **driver**,
runs a deterministic program, the **runner** (`harness/src/run.py`), which
walks a fixed table of **steps**. Each step is either done by the driver in
chat (planning, checkpoints), done by a fresh **producer** sub-agent in its own
git worktree, judged by a read-only **gate** sub-agent, or performed by the
runner itself (landing, booking). The runner alone commits, pushes, decides
when the owner must be asked, prices what happened, and keeps the record of
every round under `harness/archives/rounds/NNNN/`.

Three ideas run through everything:

1. **The spec files are the whole settings surface.** Every number and every
   sentence the owner may edit lives in the files `spec.yaml` lists. The code
   reads them, never hard-codes their content, and refuses to start when they
   drift from a reviewed baseline.
2. **Git is the only lock and the only memory.** A round is claimed by a
   compare-and-swap push of its branch; every state change is a commit pushed
   as a fence; `STATE.json` in the round folder is the runner's only state.
3. **Judgment calls are tracked, not prevented.** Agents log DEFINED and
   UNDEFINED judgment calls; the runner never parses prose, only JSON and
   verbatim quotes; the ledger bills what happened, not what was planned.

## 2. Actors and roles

| Actor | Where it runs | What it does | What it may write |
|---|---|---|---|
| Owner | chat | speaks; approves, delegates, overrides, answers, abandons | nothing in the repo during a round |
| Driver | the chat session's top-level agent | runs `run.py`; performs CHAT-TO-PLAN and checkpoints itself; spawns sub-agents with prompt files verbatim; saves their final messages; relays runner messages to the owner verbatim | `PLAN.json`, result files, nothing else |
| Producer | fresh sub-agent per attempt, in a worktree | one step's work | its step's declared paths plus its artifact and the judgment-call files in the round folder |
| Gate | fresh read-only sub-agent per attempt | judges one artifact; PASS/FAIL with findings | nothing; reports in its final message |
| Runner | `harness/src/run.py` | state machine, prompts, checks, git, ledger, owner pauses | round folder, round branch, main (landing/sync), generated files |
| Stub agent | tests only | scripted behaviors standing in for driver, producers and gates | temp repos |

## 3. Repository tree (level 0)

```
<repo root>/
  spec.yaml, SPEC.md                 owner's spec files (untouched by the harness)
  harness/                           the harness root; every project.yaml path is relative to it
    AGENTS.md, project.yaml,         owner's spec files
    subAgents.yaml, locked_prose/
    INDEX.md                         one routing line per file or folder    -> 20-harness-root.md
    README.md                        what it is, how to run it              -> 20-harness-root.md
    pyproject.toml                   package manifest, pytest config        -> 20-harness-root.md
    local.yaml                       generated, gitignored, no user input   -> 20-harness-root.md
    OWNER.log                        gitignored owner-chat log (hook-written) -> 20-harness-root.md
    .worktrees/                      gitignored per-attempt git worktrees   -> 35-src-git.md
    archives/                        the record: rounds, ledger, spec baseline -> 25-archives.md
    src/                             living code: run.py + package shackles/  -> 30-src.md
    docs/                            living prose: PROCESS.md, CONTRACTS.md, TODO.md, CLARIFICATIONS.md -> 50-docs.md
    tests/                           living tests: unit, mechanics, lint, drift, live, stub -> 60-tests.md
  .claude/                           settings.json (hooks), agents/ (generated) -> 10-repository-root.md
  CLAUDE.md, .gitignore, .github/    pointer file, ignores, CI              -> 10-repository-root.md
```

Level-1 files (read in this order for a full picture):

- `10-repository-root.md` — root-level files: `.claude/`, `CLAUDE.md`, `.gitignore`, CI.
- `20-harness-root.md` — `harness/` top level: INDEX, README, manifest, local.yaml, OWNER.log.
- `25-archives.md` — `archives/`: round folders, project ledger record, spec baseline.
- `30-src.md` — the `shackles` package map; then one file per subpackage:
  `31-src-config.md`, `32-src-steps.md`, `33-src-prompts.md`, `34-src-round.md`,
  `35-src-git.md`, `36-src-checks.md`, `37-src-ledger.md`, `38-src-quote.md`,
  `39-src-agents.md`, `40-src-engine.md`, `41-src-commands.md`.
- `50-docs.md` — the living docs.
- `60-tests.md` — the test tree map; then `61-tests-stub.md`, `62-tests-unit.md`,
  `63-tests-mechanics.md`, `64-tests-lint-drift.md`, `65-tests-live.md`.
- `70-contracts.md` — the data contracts every component shares: JSON shapes of
  final messages, artifacts, `STATE.json`, `next` output, CLI conventions,
  prompt token namespaces. (Documentation of contracts; the code for each
  contract lives in the module that owns it.)
- `JUDGMENT-CALLS.md` — the judgment call log.

## 4. The round, at a glance

The step table is code (`32-src-steps.md`) and is assumed fixed:

```
CHAT-TO-PLAN -> PLAN-AGENTS -> PLAN-TO-SPEC -> CHECKPOINT-1 -> SPEC-TO-TESTS
-> SPEC-TO-IMPLEMENTATION -> TESTS-TO-SUITE -> CHECKPOINT-2 -> LANDING
-> POSTMORTEM -> CLEANUP -> (round ends, all agents stop)
```

1. **start** — the driver runs `run.py start`. The runner refuses on spec
   drift, on a missing owner log, on doctor errors, or on an open round.
   Otherwise it picks the next round id, creates branch `round/NNNN` from
   `main`, writes the round folder with `STATE.json`, and claims the round by a
   compare-and-swap push of that branch.
2. **next** — the driver runs `run.py next`, which returns one JSON action:
   `SELF` (the driver follows a prompt itself: CHAT-TO-PLAN), `SPAWN` (give a
   prompt file verbatim to a fresh sub-agent of a named rung; read-only for
   gates), `OWNER` (relay a message to the owner and wait), or `END`.
3. **record** — after a sub-agent finishes, the driver saves its final message
   to the named result file and runs `run.py record <attempt> --tokens N`. The
   runner parses the JSON, runs mechanical checks on the worktree's uncommitted
   diff (strays reverted, not failed), verifies tests where the step requires
   it, commits the attempt onto the round branch, pushes as a fence, bills the
   attempt, and decides what comes next: the step's gate, a retry with
   findings, a pause for the owner, or the next step.
4. **owner** — when the runner pauses, the driver relays the message, then
   hands the runner the owner's reply as an interpretation plus a verbatim
   quote: `run.py owner approve|delegate|override|answer|abandon|resume
   --quote "..."`. The quote must occur in the round's owner log slice; the
   runner never parses prose.
5. **landing** — the runner merges `main` into the round branch; a conflict
   becomes one producer attempt limited to the conflicted files and judged
   mechanically against git's auto-merged tree; tests must pass; the branch is
   pushed onto `main` with a lease.
6. **postmortem, cleanup** — producer steps after landing; their commits reach
   `main` through a bounded sync. At CLEANUP the runner books the round's
   living charge and archive costs once, on the net change to `main`.

Pauses: a checkpoint (unless delegated), a producer's NEEDS-OWNER or BLOCKED,
open questions, gate turn limits, run limits, hard budget stops, a lost lease.
Delegation skips only checkpoints.

## 5. Component map (owns / depends on / depended on by)

Each component below is one subpackage or folder, described in its own file.
The rule of the design: **any one file can be rewritten from its own section
without touching the rest**, because every cross-component exchange goes
through the small data contracts in `70-contracts.md` and through plain
function signatures.

| Component | Owns | Depends on | Depended on by |
|---|---|---|---|
| `config/` (31) | reading spec.yaml, project.yaml, subAgents.yaml, local.yaml; path resolution; defaulted keys; drift hashes | filesystem, PyYAML | everything else |
| `steps/` (32) | the step table as code; lint of the table against project.yaml and locked_prose | config | prompts, engine, quote, checks |
| `prompts/` (33) | token namespaces, recursive rendering, plumbing text, AGENTS.md sections | config, steps | engine, commands.doctor |
| `round/` (34) | STATE.json, HISTORY.md, OWNER.log slice, judgment-call files, artifact schemas, result and finding schemas, owner-verb transitions | config, steps | engine, commands, ledger |
| `git/` (35) | git wrapper, lease (CAS push), worktrees, landing merge, bounded sync | subprocess git | engine, checks, ledger |
| `checks/` (36) | mechanical checks at record, test verification, suite moves | config, steps, git | engine |
| `ledger/` (37) | token estimate, pricing, living charge, agent costs, round ledger, hard stops, project remaining | config, git | engine, prompts (round/project numbers), commands.status |
| `quote/` (38) | budget pools, shares, per-attempt budgets, run limits | config, steps, round | engine |
| `agents/` (39) | generated agent definitions per rung, hook installation and the owner-log hook handler | config | commands.setup/doctor/hook |
| `engine/` (40) | the advance decision, attempt lifecycle, landing step, booking, pause messages | all of the above | commands |
| `commands/` (41) | one module per CLI verb; `cli.py` dispatch; `run.py` entry | engine and the rest | the driver, hooks, tests |
| `docs/` (50) | PROCESS.md, CONTRACTS.md, TODO.md, CLARIFICATIONS.md | — | agents (read them), lint tests |
| `tests/` (60) | unit, mechanics (stub-driven), lint, drift, live probes, stub agent | src | CI, verify |
| `archives/` (25) | round folders, LEDGER.md, spec-baseline.yaml | — | config (baseline), ledger (remaining), round |

## 6. Technology and conventions

- Python 3.12+, standard library plus PyYAML; pytest for tests. No build step;
  `python harness/src/run.py <verb>` runs from any cwd inside the repo.
- All runner output the driver must act on is one JSON object on stdout; human
  text goes to stderr. Exit code 0 = done, 2 = refused (with a JSON reason),
  1 = crashed.
- Every module is small and single-purpose; no module reaches into another's
  files on disk — it calls its functions. Only `git/repo.py` runs git; only
  `checks/verify.py` runs the test suite; only `round/state.py` writes
  `STATE.json`; only `round/history.py` writes `HISTORY.md`.
- Language of tests: the harness counts a test as a `def test_` function in a
  `.py` file under `testPaths` (defaulted key, `tests/`) `[JC-05]`.
- Dates in UTC ISO-8601; money in `project.yaml`'s `currency`, two decimals when
  shown, full float in JSON.

## 7. Defaulted config keys (code defaults, named by doctor)

The owner's `project.yaml` is the settings surface, but the prose refers to a
few things it does not define, and the code needs a few knobs to be general.
These have code defaults, are read through `config/project.py` like any key,
and `doctor` names every one that is defaulted `[JC-03]`:

| key | default | used for |
|---|---|---|
| `testPaths` | `["tests/"]` | what counts as a test file (living charge, suite moves, verify) |
| `carryForwardFiles` | `["docs/TODO.md", "docs/CLARIFICATIONS.md"]` | POSTMORTEM's declared paths and its special token price |
| `verifyCommand` | `python -m pytest -q {testPaths}` | test verification |
| `collectCommand` | `python -m pytest --collect-only -q {testPaths}` | collectability check after SPEC-TO-TESTS |
| `promptWarnTokens` | `30000` | prompt-size warning |
| `mainBranch` | `main` | landing target |
| `remoteName` | `origin` | lease and fence pushes |
| `syncAttempts` | `3` | bounded post-landing sync retries |
| `stepEndDelivery` | `inline` | how COMMON-STEP-END reaches an agent (`inline` or `follow-up`) |
| `quoteMatch` | `normalized` | owner-quote verification (`exact` or whitespace-normalized) |

## 8. Robustness to spec-file edits (the design rule behind every file)

- Prose is never parsed for meaning. Prose files are included by name; tokens
  are resolved by namespace; unknown tokens are named, never guessed.
- Numbers are read by key; a missing key falls back to a code default and is
  named; an unknown key is a lint error that refuses `start`.
- The step table is code; `project.yaml`'s `steps` is validated against it:
  unknown step names refuse `start`; a gate switched on for a step that has no
  gate prose refuses `start`; switching a gate on for a step that has no gate
  in the table is ignored with a doctor note.
- Any edit to a spec file fails `tests/drift/test_spec_files_guard.py` with a
  diff until `run.py accept-spec` is run, and `start` refuses until then.
- Mechanics tests never read the real prose: they run on a generated
  one-line-per-file spec, so a rewrite of prose fails only the drift test.
