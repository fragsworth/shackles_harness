# shackles_harness — recreation spec (draft 4)

This document is the top-level map for rebuilding `shackles_harness` from scratch. It is written top-down: this file describes the whole; each component file under `components/` describes one isolated part down to file, class, function signature and test case. A reader may enter at any level.

The **requirements** are the owner's spec files, listed by `spec.yaml` at the repository root: `spec.yaml`, `SPEC.md`, `harness/AGENTS.md`, `harness/project.yaml`, `harness/subAgents.yaml`, `harness/locked_prose/*`. They are not reproduced here; they are read, verbatim, by the software this spec describes. Nothing below overrides them. Every choice in this spec that the requirements do not settle is logged in `JUDGMENT-CALLS.md` and cross-referenced by ID (`JC-nn`).

---

## 1. What the harness is

`shackles_harness` is a loop-engineered software-development harness. A human **owner** talks to a Claude Code session; the top-level agent in that session is the **driver**. The driver runs a small Python program, the **runner** (`harness/src/run.py`), which walks a fixed list of **steps** called a **round**: plan, assign agents, write a spec, write tests, implement, pick the permanent tests, land, post-mortem, clean up. For each step the runner renders a **prompt** from the owner's locked prose, the driver hands the prompt verbatim to a fresh sub-agent (a **producer**, or a read-only **gate** that judges a producer's artifact), saves the sub-agent's final JSON message, and calls the runner to **record** it. The runner does everything mechanical: git, budgets, limits, checks, findings, the ledger, and the record of what happened. Agents do everything that needs judgment, and are made to log their judgment calls, split into *defined* (made from the prompt alone) and *undefined* (needed something outside the prompt).

The project the harness develops is, for now, itself: the living source paths are the harness's own `src/`, `docs/`, `tests/`.

### 1.1 The properties the requirements demand (and where each lives)

| Requirement (paraphrased from the owner's SPEC.md / AGENTS.md / project.yaml) | Where it is designed |
|---|---|
| Spec files are the only settings surface; every setting is used; changes are detected (hashed baseline, failing test with diff), and `start` refuses drift until accepted | [03 Spec files & config](components/03-spec-files-and-config.md), [10 Tests](components/10-tests.md) §`test_spec_drift` |
| Git is the only lock: a CAS push claims a round; every state change pushes the branch as a fence | [06 Git, checks, landing](components/06-git-checks-landing.md) §gitops |
| The driver interprets owner words; the runner takes verbatim quotes and never parses prose; a prompt hook logs the owner's chat to a gitignored OWNER.log; quotes are verified against it; no log → start refuses | [05 Round state & records](components/05-round-state-and-records.md) §ownerlog, §decisions; [08 Doctor, invoke, hook](components/08-doctor-invoke-hook.md) §hook |
| The step table is code, lint-checked against `project.yaml`; unknown inputs refuse to start | [04 Steps, prose, prompts](components/04-steps-prose-prompts.md) §steps |
| Delegation skips only review checkpoints; questions, blocks and limits still stop the round | [05](components/05-round-state-and-records.md) §decisions, [07 Money & limits](components/07-money-and-limits.md) §limits |
| Mechanical checks run at record on the attempt's own uncommitted diff; strays are reverted, not failed | [06](components/06-git-checks-landing.md) §checks |
| A landing conflict becomes one agent attempt on the conflicted files, judged against git's auto-merged tree; post-landing commits merge back into main through a bounded sync | [06](components/06-git-checks-landing.md) §landing |
| The gate's verdict wins; blocking flags follow it; unresolved findings block; flags reach the owner at the next pause; a repeat of a withdrawn finding is dropped with a note; upheld twice is settled | [05](components/05-round-state-and-records.md) §findings |
| Mechanics tests use a generated one-line-per-file spec; a stub agent with scripted behaviours drives every path; real agents run as probes with planted defects | [10 Tests](components/10-tests.md) |
| `doctor` renders every prompt offline and names unresolved tokens, unknown steps and defaulted config keys; `local.yaml` is generated and holds no user input; agent definitions are generated per rung | [08](components/08-doctor-invoke-hook.md) §doctor, [04](components/04-steps-prose-prompts.md) §agentdefs, [03](components/03-spec-files-and-config.md) §localcfg |
| The ledger bills what happened, not what was planned; the living charge is booked once per round at cleanup on the net change to main; the hard stop is checked against the projected charge before landing | [07 Money & limits](components/07-money-and-limits.md) |
| Only the runner commits, pushes and contacts the owner; producers edit only their worktree, only within declared paths plus the round folder; spec files are never changed by agents | [06](components/06-git-checks-landing.md) §checks, [04](components/04-steps-prose-prompts.md) §steps (declared paths) |
| Owner words in locked_prose are not literal descriptions of enforced software until approved | [09 Docs](components/09-docs.md) `PROCESS.md` states it; nothing in code parses prose for behaviour |
| The step list is fixed and changed only with major consideration | [04](components/04-steps-prose-prompts.md) §steps lists every consumer of the table |

### 1.2 How the design survives arbitrary edits to the spec files

The owner demands that everything outside the spec files "stay robust to arbitrary changes in them". The design does this in five ways, each owned by exactly one component:

1. **Every read of a spec file goes through one loader** with a declared key registry (`config`), a generic template engine (`prose`) and a generic section extractor for `AGENTS.md`. A key or token the code does not know is *reported* (doctor) and, if it would be needed to run, *refused* (start). Nothing else in the tree reads those files.
2. **Defaults are explicit and named.** A key the code needs but the file lacks gets a registered default and is listed by `doctor` as "defaulted". An unregistered key present in the file is an error ("unused setting"), because the owner says every setting is used.
3. **Drift is a first-class state.** A committed hashed baseline plus a permanent test that fails with a diff, plus a refusal to start (or, mid-round, a pause) while drift exists, plus one command to accept it.
4. **The step table is code** and is linted against `project.yaml`'s `steps` map at every start; mismatch refuses.
5. **Mechanics tests never touch the real prose.** They generate a one-line-per-file spec from the code's own step table, so a prose rewrite fails only the drift test.

---

## 2. Architecture in one page

```
owner ──chat──► driver (top-level Claude Code agent in harness/)
                  │  runs                                   ┌───────────────────────┐
                  ▼                                         │ Claude Code sub-agents│
   harness/src/run.py  ◄──── verbatim quotes ───            │ (Agent tool, one per  │
   ┌────────────────────────────────────────────┐           │  rung, generated)     │
   │ commands: doctor start next record owner   │  prompt   │  producer  (r/w wt)   │
   │           status judgment spawn spec-drift │ ────────► │  gate      (read-only)│
   │           accept-spec                      │ ◄──────── │                       │
   │ mechanics: config prose steps plumbing     │ final msg └───────────────────────┘
   │   prompts state findings messages ownerlog │
   │   decisions gitops checks suite landing    │      git: main + shackles/round-NNNN
   │   charges ledger budget limits doctor      │      round worktree: harness/.worktrees/round-NNNN
   └────────────────────────────────────────────┘      round folder: archives/rounds/NNNN/ (on the branch)
```

**Round lifecycle** (each transition is a runner command; every state change is committed to the round branch and pushed — the fence):

1. `start` — preflight (doctor checks, drift, owner log present, step-table lint), then a CAS push claims branch `shackles/round-NNNN`, creates the round worktree and folder, writes `STATE.json`, renders the CHAT-TO-PLAN prompt for the driver itself.
2. The driver plans with the owner, writes `PLAN.json`, records it (`record`), hands owner answers and the approval as verbatim quotes (`owner`). No round proceeds with unanswered questions.
3. `next` / `record` loop: PLAN-AGENTS → PLAN-TO-SPEC → CHECKPOINT-1 → SPEC-TO-TESTS → SPEC-TO-IMPLEMENTATION → TESTS-TO-SUITE → CHECKPOINT-2 → LANDING → POSTMORTEM → CLEANUP. Producers get a rendered prompt and edit the round worktree; gates (when on) judge the artifact read-only; the runner checks, commits, books, and decides: accept, retry, or pause.
4. Pauses (checkpoint, NEEDS-OWNER, BLOCKED, limit, mechanical limit, hard stop, drift) return control to the owner through the driver; `owner` decisions resume, override, raise a limit, or abandon.
5. LANDING merges main into the branch, verifies, fast-forwards main. POSTMORTEM and CLEANUP commit after landing; at CLEANUP's record the runner books the living and archive charges, then runs the bounded sync so those commits reach main, and removes the worktree. The round folder on main is the permanent record.

**Roles.** *Owner*: a human; only the driver speaks to them. *Driver*: interprets owner words, spawns sub-agents, passes prompts and messages verbatim, never edits living files itself except as the CHAT-TO-PLAN producer of `PLAN.json`. *Producer*: an agent doing one step's work in the round worktree. *Gate*: a read-only agent judging one producer artifact. *Runner*: `run.py`; the only thing that commits, pushes, moves files between suite and archive, and computes money.

---

## 3. Folder structure

Paths are relative to the git repository root. Files marked **(owner)** are the spec files and are not part of this recreation. Files marked **(gen)** are generated by the runner. Files marked **(ignored)** are gitignored.

```
<repo root>/
  spec.yaml                          (owner)
  SPEC.md                            (owner)
  .github/workflows/harness.yml      CI: doctor --check --offline, then pytest -m "not live"      → [01]
  harness/                           the harness root; the driver's working directory
    AGENTS.md  project.yaml  subAgents.yaml  locked_prose/*.txt                    (owner)
    INDEX.md                         routing: one line per file/dir                              → [09]
    README.md                        what it is, prerequisites, setup, running, testing          → [09]
    pyproject.toml                   package `shackles` (src layout), deps, pytest config        → [01]
    .gitignore                       /OWNER.log /local.yaml /.worktrees/ caches                  → [01]
    spec.baseline.json               hashed baseline of the spec files + accepted commit         → [03]
    local.yaml                       (gen, ignored) detected environment + effective config      → [03]
    OWNER.log                        (ignored) written by the prompt hook, JSON lines            → [08]
    .worktrees/round-NNNN/           (ignored) git worktree of the round branch                  → [06]
    .claude/
      settings.json                  UserPromptSubmit hook → src/hooks/owner_log.py             → [01]
      agents/shackles-<rung>.md      (gen, committed) producer definitions, one per rung         → [04]
      agents/shackles-<rung>-gate.md (gen, committed) read-only gate definitions                 → [04]
    scripts/check.sh                 doctor --check + pytest, for humans and CI                  → [01]
    src/
      run.py                         CLI entry; argument parsing; dispatch; exit codes           → [02]
      hooks/owner_log.py             the prompt hook (standalone, no imports from shackles)      → [08]
      shackles/                      the package
        __init__.py  errors.py                                                                   → [02]
        commands/  start.py next_.py record.py owner.py status.py judgment.py spawn.py
                   doctor.py spec_drift.py accept_spec.py                                        → [02]
        paths.py  specfiles.py  config.py  localcfg.py                                           → [03]
        steps.py  prose.py  plumbing/{builder.py, templates/*.txt}  prompts.py  agentdefs.py     → [04]
        state.py  history.py  messages.py  artifacts.py  findings.py  judgment.py
        ownerlog.py  decisions.py                                                                → [05]
        gitops.py  checks.py  suite.py  landing.py                                               → [06]
        charges.py  ledger.py  budget.py  limits.py                                              → [07]
        doctor.py  invoke.py                                                                     → [08]
    docs/
      PROCESS.md  ARCHITECTURE.md  FORMATS.md  TODO.md  CLARIFICATIONS.md                        → [09]
    tests/
      conftest.py  support/  fixtures/  test_*.py  probes/                                       → [10]
    archives/
      rounds/.gitkeep                one folder per round appears here after landing/abandon
```

Living source paths (charged per token, editable by producers within their declared paths): `src/`, `docs/`, `tests/`, as `project.yaml` lists them. Everything else under `harness/` is uncharged and, except `INDEX.md` and `README.md` at CLEANUP, not editable by agents.

---

## 4. Component index

Each component file states, per source file: what it **owns**, what it **depends on**, what **depends on it**, its classes and functions (name, parameters with types, return type, one-line purpose, errors raised), and, in [10], per test file the cases and assertions. Components are designed so that any one file can be rewritten from its own section without touching the rest.

| # | File | Components |
|---|---|---|
| 00 | [components/00-contracts.md](components/00-contracts.md) | Cross-component contracts: CLI I/O convention, error taxonomy, attempt identifiers, `STATE.json`, final-message schemas, artifact schemas, `FINDINGS`, `HISTORY.md`, `OWNER.log` lines, `spec.baseline.json`, `local.yaml`, `next` outputs |
| 01 | [components/01-root-and-tooling.md](components/01-root-and-tooling.md) | `pyproject.toml`, `.gitignore`, `.claude/settings.json`, `scripts/check.sh`, CI workflow, `archives/` |
| 02 | [components/02-runner-cli.md](components/02-runner-cli.md) | `src/run.py`, `shackles/errors.py`, `shackles/commands/*` — one thin module per command |
| 03 | [components/03-spec-files-and-config.md](components/03-spec-files-and-config.md) | `paths.py`, `specfiles.py` (baseline, drift), `config.py` (registry, defaults, roster), `localcfg.py` |
| 04 | [components/04-steps-prose-prompts.md](components/04-steps-prose-prompts.md) | `steps.py` (the fixed table), `prose.py` (template engine), `plumbing/` (PROCESS-INSTRUCTIONS, GATE-PROSE), `prompts.py`, `agentdefs.py` |
| 05 | [components/05-round-state-and-records.md](components/05-round-state-and-records.md) | `state.py`, `history.py`, `messages.py`, `artifacts.py`, `findings.py`, `judgment.py`, `ownerlog.py`, `decisions.py` |
| 06 | [components/06-git-checks-landing.md](components/06-git-checks-landing.md) | `gitops.py` (CAS, fence, worktrees, diffs, merges), `checks.py` (mechanical checks, strays), `suite.py` (test enumeration, suite/archive moves), `landing.py` (landing, conflicts, bounded sync, abandon) |
| 07 | [components/07-money-and-limits.md](components/07-money-and-limits.md) | `charges.py` (living/archive charges, pure), `ledger.py` (booking what happened), `budget.py` (shares), `limits.py` (pauses) |
| 08 | [components/08-doctor-invoke-hook.md](components/08-doctor-invoke-hook.md) | `doctor.py`, `invoke.py` (Cli/Stub invokers, `spawn`), `hooks/owner_log.py` |
| 09 | [components/09-docs.md](components/09-docs.md) | `INDEX.md`, `README.md`, `docs/PROCESS.md`, `docs/ARCHITECTURE.md`, `docs/FORMATS.md`, `docs/TODO.md`, `docs/CLARIFICATIONS.md` |
| 10 | [components/10-tests.md](components/10-tests.md) | `tests/conftest.py`, `tests/support/*` (fake spec, fake remote, stub agent, stub driver), `tests/fixtures/*`, every `test_*.py` with its cases, `tests/probes/*` |

### 4.1 Dependency direction (no cycles)

```
run.py → commands/* → {landing, checks, suite, ledger, limits, findings, decisions, prompts, doctor, invoke}
                       → {gitops, state, history, messages, artifacts, judgment, ownerlog, charges, budget, plumbing, prose, steps, agentdefs}
                       → {config, specfiles, localcfg, paths, errors}
```
Lower layers never import higher ones. `errors.py` and `paths.py` import nothing from the package. `steps.py` imports nothing but `errors` (it is data plus a lint). `charges.py` is pure (no I/O, no git). `hooks/owner_log.py` imports nothing from the package at all.

---

## 5. Cross-cutting rules (apply to every component)

- **One place per spec-file read.** `config.py` reads `project.yaml` and `subAgents.yaml`; `prose.py` reads `locked_prose/*` and `AGENTS.md`; `specfiles.py` reads `spec.yaml` and hashes the rest. No other module opens those files.
- **Runner-only side effects.** Only `gitops.py` runs git. Only `commands/*` orchestrate; every other module is callable without a round (tests rely on this).
- **Mechanical means no judgment.** A check in `checks.py` either has a deterministic answer or it is not a check; anything needing judgment is rendered into a prompt for an agent or a question for the owner.
- **Quotes, not prose.** Any command that changes the round on the owner's behalf takes `--quote TEXT` and verifies the text against `OWNER.log`. The runner classifies nothing; the driver passes `--decision KIND`.
- **Every command prints exactly one JSON object** on stdout (`--human` renders it readably) and uses the exit codes in [00]. Errors are JSON too.
- **Estimated tokens = ceil(bytes / project.tokenBytes)** everywhere text size becomes tokens (charges, prompt-size warning, usage estimates).
- **Time is UTC ISO-8601** with seconds; every record carries a timestamp.
- **Round paths come from `project.yaml` `roundPaths`**, resolved by `paths.RoundPaths`; no module spells `PROMPTS/` or `STATE.json` itself.
- **Living files only in living paths.** Producers' declared paths are the intersection of the step's table entry with `livingSourcePaths` (+ the round folder); everything else in a diff is a stray and is reverted.
- **Nothing in code decides behaviour from the wording of locked prose.** Prose is rendered into prompts and otherwise opaque.

---

## 6. Glossary

- **Spec files** — the files `spec.yaml` lists. The owner's; never edited by agents.
- **Round** — one pass through the step table; id `NNNN` (zero-padded to the width of the `NNNN` placeholder in `roundPaths.folder`).
- **Step** — one entry of the fixed table in `steps.py`. Kinds: `driver` (CHAT-TO-PLAN), `producer`, `checkpoint`, `landing`, `cleanup`.
- **Attempt** — one prompt handed to one agent (or the driver) and one recorded result. Ids: `STEP-n` (producer/driver/conflict attempt n of the step), `STEP-GATE-n` (gate attempt n of the step).
- **Gate turn** — one accepted gate verdict for a producer attempt. Rejections per step (FAIL verdicts + mechanical rejections) are bounded by `maxTurnsPerGate`.
- **Mechanical rejection** — the runner refuses an attempt without an agent's judgment (bad JSON, missing artifact, failing suite, unresolved findings); the step retries.
- **Finding** — one gate objection with a quote, text and suggestion; states `open`, `fixed`, `disputed`, `withdrawn`, `settled`, `note`.
- **Flag** — an item an agent raises for the owner; delivered at the next pause.
- **Pause** — the round waits for the owner (checkpoint, NEEDS-OWNER, BLOCKED, limit, hard stop, drift, sync failure).
- **Fence** — the push of the round branch after every state change; a rejected push means another runner owns the round.
- **Living charge** — the once-per-round price of the net change under living paths, booked at CLEANUP.
- **Rung** — a key of `subAgents.yaml` `agents`; the ladder order is the file order, top = highest.

## 7. Reading order for an implementer

[00 contracts] → [03 config] → [04 steps & prose] → [05 state] → [06 git] → [07 money] → [02 commands] → [08 doctor] → [01 tooling] → [09 docs] → [10 tests]. Each file is self-contained enough to be implemented in that order with the earlier files as its only context.
