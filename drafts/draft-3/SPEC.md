# shackles_harness — recreation spec (draft 3)

This is the entry point of a from-scratch specification for **shackles_harness**: a
loop-engineered software-development harness that runs an owner's request through a
fixed table of steps (plan, agents plan, spec, tests, implementation, suite selection,
landing, postmortem, cleanup), spawns one fresh agent per attempt, judges producers with
gates, tracks and distinguishes the judgment calls every agent makes, bills what
actually happened, and lands the result in git.

The spec is a tree of files. Root first (this file), then one file per area, then one
section per source file, class, function and test. Any file below can be read on its
own; each says what it owns, what it depends on and what depends on it.

Requirements come only from the owner's spec files listed in `spec.yaml`
(`spec.yaml`, `SPEC.md`, `harness/AGENTS.md`, `harness/project.yaml`,
`harness/subAgents.yaml`, `harness/locked_prose/*`). Those files change often; the
entire design below must survive arbitrary edits to them. Where a choice was not
forced by those files, it is logged in `JUDGMENT-CALLS.md` and cross-referenced from
the section it affects with a tag like `[JC-07]`.

## 1. Map of this spec

| File | What it specifies |
|---|---|
| `SPEC.md` | this map, the principles, the architecture in one page, conventions |
| `JUDGMENT-CALLS.md`, `JUDGMENT-CALLS-2.md` | every choice not forced by the owner's files, classified (two parts) |
| `01-repo-layout.md` | the full folder tree, ownership of every file, what is generated or gitignored |
| `02-lifecycle.md` | the round lifecycle: states, step semantics, owner words, pauses, limits |
| `03-cli.md` | `src/run.py`, `src/commands.py`, `src/errors.py`, `src/paths.py`: the command surface |
| `04-config.md` | `src/config.py`, `src/specfiles.py`, `src/localstate.py`, `src/tokens.py` |
| `05-steps-prose.md` | `src/steps.py` (the step table, the lint), `src/prose.py` (locked prose, AGENTS.md sections) |
| `06-templates-prompts.md` | `src/templates.py`, `src/context.py`, `src/prompts.py`: rendering and prompt assembly |
| `07-schemas.md` | `src/schemas.py` and the exact JSON of every artifact, result and findings file |
| `08-state-history-rounds.md` | `src/state.py` (STATE.json), `src/history.py` (HISTORY.md), `src/rounds.py` (claiming, discovery) |
| `09-gitops.md` | `src/gitops.py`: the git lock, fences, worktrees, merges |
| `10-engine.md` | `src/next_action.py`, `src/recording.py`, `src/pauses.py`: the `next`/`record` machine |
| `11-findings-checks-verify.md` | `src/findings.py`, `src/checks.py`, `src/verify.py` |
| `12-landing-suite.md` | `src/landing.py` (landing, conflicts, bounded sync), `src/suite.py` (test moves) |
| `13-ledger.md` | `src/ledger.py`: every price and how it is booked |
| `14-ownerlog-jc-agentdefs.md` | `src/ownerlog.py`, `src/hooks/`, `src/judgment_calls.py`, `src/agentdefs.py` |
| `15-install-doctor-index.md` | `src/install.py`, `src/doctor.py`, `src/index.py` |
| `16-docs.md` | every file under `docs/`, `INDEX.md`, the root `README.md` |
| `17-tests-infra.md` | test fixtures: the generated one-line spec, the stub agent, the fake driver, git fixtures, probes |
| `18-tests-unit.md` | unit test files, case by case |
| `19-tests-flows.md` | flow tests, the drift and lint tests, CLI tests, live probes |
| `20-tooling-ci.md` | `pyproject.toml`, `.gitignore`, CI, generated `.claude/` files |

Suggested reading order for an implementer: this file, `01`, `02`, `07`, `08`, then
the rest in numeric order; tests last.

## 2. The owner's requirements, restated as design principles

Each principle below names the owner sentence it serves (from `SPEC.md`,
`AGENTS.md`, `project.yaml`, `subAgents.yaml` or the locked prose).

1. **The spec files are the whole settings surface.** Every owner-editable setting or
   text lives in the `spec.yaml` files, and each one is used. Nothing else asks the
   owner for input. `local.yaml` is generated and holds no user input.
2. **Everything else survives arbitrary edits to those files.** Code never depends on
   the wording of prose; it depends only on file names, config keys and a fixed step
   list. A change to any spec file fails exactly one test (the drift test) until the
   owner accepts it; `start` refuses to run on drift.
3. **The step table is code.** `src/steps.py` holds the eleven steps in order with
   their kinds, artifacts and write paths. It is lint-checked against
   `project.yaml`'s `steps:`, `roundPaths:` and the prose directory; unknown inputs
   refuse to start.
4. **Git is the only lock.** A round is claimed by pushing a new `round/NNNN` branch
   (compare-and-swap); every state change is committed on that branch and pushed with a
   lease, so two runners cannot both advance a round.
5. **The driver interprets, the runner verifies.** The driver (the agent in the
   owner's chat) turns owner words into structured decisions and hands the runner the
   owner's verbatim quote. The runner checks the quote exists in `OWNER.log`; it never
   parses prose.
6. **Only the runner commits, pushes and contacts the owner.** Producers edit only in
   their worktree, only inside their step's declared paths plus the round folder.
   Mechanical checks run at `record` on the attempt's own uncommitted diff; strays are
   reverted, not failed.
7. **Delegation skips only checkpoints.** Questions (NEEDS-OWNER), blocks (BLOCKED) and
   limits (turns, wall clock, hard stops) always pause the round.
8. **The gate's verdict wins.** Blocking flags follow the verdict. Unresolved findings
   block acceptance; flagged items reach the owner at the next pause; a finding that
   repeats a withdrawn one is dropped with a note; nothing closes in silence.
9. **The ledger bills what happened.** Measured usage when the driver reports it,
   an estimate otherwise, and the living charge on the round's real net change to
   main, booked once at cleanup.
10. **Every prompt is renderable offline.** `doctor` renders every prompt and names
    unresolved tokens, unknown steps and defaulted config keys.
11. **Tests do not depend on the owner's prose.** Mechanics tests run on a generated
    one-line-per-file spec; a stub agent with scripted behaviours drives every path;
    real agents run only as opt-in probes with planted defects.
12. **Agent definitions are generated per rung** from `subAgents.yaml` so the Agent
    tool can pick model and effort; they are loaded at session start, so a stale set
    makes `next` refuse to spawn.

## 3. Architecture in one page

```
owner ──chat──► driver (top-level agent, in the harness session)
                  │  runs `python src/run.py next|record|...` from the MAIN checkout
                  ▼
                runner (src/) ── owns STATE.json, HISTORY.md, git, ledger, prompts
                  │
                  ├─ next   : decides the next action, renders a prompt file, pushes the fence
                  ├─ record : validates the agent's final message, runs mechanical checks
                  │           on the worktree diff, reverts strays, commits, pushes
                  ├─ landing: merge into main, conflict → one agent attempt, bounded sync later
                  └─ cleanup: books living + archive charges, regenerates INDEX.md, syncs main
                  ▲
   fresh sub-agents (one per attempt), spawned by the driver with the prompt file verbatim,
   work in  <repo>/.worktrees/round-NNNN/harness/  on branch round/NNNN
```

Round folder `archives/rounds/NNNN/` (on the round branch, later on main) holds the
artifacts (`PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SPEC.md`, `SUITE.json`,
`POSTMORTEM.md`), the runner's state (`STATE.json`, `HISTORY.md`, `OWNER.log` slice),
one file per attempt under `PROMPTS/`, `RESULTS/`, `FINDINGS/`, the archived tests
under `tests-archive/`, and the two judgment-call trails.

Steps, in order, from `project.yaml`: CHAT-TO-PLAN (the driver itself), PLAN-AGENTS,
PLAN-TO-SPEC, CHECKPOINT-1, SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, TESTS-TO-SUITE,
CHECKPOINT-2, LANDING, POSTMORTEM, CLEANUP. `02-lifecycle.md` walks through them.

## 4. Component isolation rules

- Each `src/*.py` file has one owner section in this spec, listing **owns / depends on
  / depended on by**. A file may import only what its section lists.
- `run.py` is a thin dispatcher; `commands.py` is thin glue; domain logic never lives
  in either. No module is imported by all others: `config`, `paths`, `errors` and
  `tokens` are leaves; `next_action`, `recording`, `pauses`, `landing` are the only
  orchestrators and they call, never get called by, the domain modules.
- Runner state has exactly one home: `STATE.json` (`08`). HISTORY.md is append-only
  narrative, never read back by code.
- Text the owner edits is read only by `prose.py`, `config.py`, `specfiles.py`; every
  other module receives parsed objects.

## 5. Conventions used throughout

- Language: Python 3.11+, standard library plus `pyyaml`; tests with `pytest`. No build
  step [JC-58]; `python src/run.py ...` runs from the harness root.
- Signatures are written as `name(param: Type, ...) -> Return` with a one-line purpose
  and the errors raised. "Raises nothing" is implied when absent.
- All paths inside the harness are `pathlib.Path`, relative paths are relative to the
  **harness root** (`harness/`), the directory containing `project.yaml`.
- Times are UTC ISO-8601 strings with seconds (`2026-09-15T10:00:00Z`).
- Money is USD floats rounded to cents only when displayed; tokens are integers.
- The token estimate is one function (`tokens.estimate`): `ceil(bytes / tokenBytes)`.
- Every CLI command prints a human block and, with `--json`, a single JSON object.
- Exit codes: `0` ok · `2` usage · `3` refused (precondition) · `4` fence (round
  advanced elsewhere) · `5` invalid (result or artifact rejected, re-run the attempt).
- Errors are `errors.HarnessError` subclasses carrying `code` and an owner-readable
  message; the CLI maps them to exit codes; nothing prints a traceback by default.
- JSON files are written with 2-space indent, sorted keys, trailing newline.
- Identifiers: round ids are four digits `NNNN`; attempts are 1-based; findings are
  `F<n>` numbered per round (`R<n>` when the runner raises them) [JC-46]; files under `PROMPTS/`, `RESULTS/`, `FINDINGS/` are
  `<STEP>-<attempt>.<ext>` and gate prompts are `<STEP>-GATE-<attempt>.txt`.

## 6. Glossary

- **owner** — the human whose words start and steer a round.
- **driver** — the top-level agent in the owner's chat; runs the runner's CLI, spawns
  sub-agents, relays runner messages to the owner, is itself the CHAT-TO-PLAN producer.
- **runner** — `src/`; the code behind `run.py`.
- **producer** — an agent attempt that writes an artifact or code.
- **gate** — a read-only agent attempt that judges a producer attempt; returns findings.
- **attempt** — one spawn of one agent for one step, numbered per step.
- **turn** — one `next` call in a run (runner turns), or one gate rejection (gate turns).
- **run** — a stretch of unattended execution between two owner pauses.
- **round** — one pass through the step table; the unit of landing and billing.
- **spec files** — the files listed by `spec.yaml`; the owner's; read-only to agents.
- **living paths** — `livingSourcePaths`; per-token charged; default `src/ docs/ tests/`.
- **rung** — a key of `subAgents.yaml` (`max`, `high`, `medium`, `low`).
- **fence** — a lease-guarded push of the round branch after every state change.
- **stray** — an uncommitted change outside an attempt's declared paths; reverted.
- **flag** — a non-blocking item for the owner, delivered at the next pause.
- **finding** — one gate objection with a quote, text, suggestion and severity.
