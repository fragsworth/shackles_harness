# shackles_harness — recreation spec (draft 2)

This is the entry point. It is the map: what the harness is, what the owner's files
require of it, how it is shaped, and where each part is specified. Every part has its own
file under [`components/`](components/); each of those stands alone for its level.
Judgment calls made while drafting are logged in [`JUDGMENT-CALLS.md`](JUDGMENT-CALLS.md)
and referenced inline as `JC-nn`.

Inputs to this spec were only the owner's files listed by `spec.yaml` (`SPEC.md`,
`harness/AGENTS.md`, `harness/project.yaml`, `harness/subAgents.yaml`,
`harness/locked_prose/*.txt`). Nothing in the old implementation was consulted.

## 1. What the harness is

A **round** turns the owner's request into landed code through a fixed list of steps
(`CHAT-TO-PLAN … CLEANUP`). Each step is performed by one fresh agent from a prompt the
**runner** renders out of the owner's *locked prose*. The runner (`harness/src/run.py`) is
plain Python; it never talks to a model. The **driver** — the agent sitting in the owner's
chat — runs the runner's commands, performs the planning step and the checkpoints itself,
spawns every other agent with the prompt file the runner hands it, saves each agent's final
message, and records it. The owner's words reach the runner only as verbatim quotes that
the driver classifies and the runner verifies against a log the chat hook writes.

Three things the owner cares about shape every design choice here:

- **Judgment calls are tracked, not prevented.** Agents log defined and undefined judgment
  calls; the mechanical instructions the runner writes contain none.
- **The owner's files are the whole settings surface and change often.** Everything else
  must survive arbitrary edits to them: a hashed snapshot guards them, a test fails on drift
  until it is accepted, and `start` refuses to run on drift. Mechanics tests never read the
  owner's prose.
- **Git is the only lock and the only memory.** A compare-and-swap push claims a round; every
  state change is pushed as a fence; `STATE.json` in the round folder is the runner's only
  state.

## 2. Requirements inventory

Each line of the owner's *Architecture features* list, and each mechanical rule from
`AGENTS.md`, `project.yaml` and the prose, maps to the component that meets it. The full
traceability table is §9 at the end of this file. In short:

| Owner statement | Met by |
|---|---|
| Git is the only lock; CAS push claims a round; every state change pushes as a fence | `gitops`, `round` (04, 07) |
| Driver interprets owner words, runner takes verbatim quotes, never parses prose | `control`, `ownerlog` (03) |
| Step table is code, lint-checked; unknown inputs refuse to start | `steps`, `config`, `round.start` (01, 07) |
| Delegation skips only checkpoints | `round.next` (07) |
| Spec files guard: hashed baseline, failing test with diff, start refuses drift | `speclock`, `test_spec_drift` (01, 10) |
| Mechanical checks at record on the attempt's own diff; strays reverted | `worktree.triage`, `verify` (04, 05) |
| Landing conflict → one agent attempt, judged against the auto-merged tree | `landing` (04) |
| Post-landing commits merge back through a bounded sync | `sync` (04) |
| Gate's verdict wins; blocking flags follow it | `findings.reconcile` (05) |
| Mechanics tests use a generated one-line-per-file spec | `tests/specgen.py` (10) |
| Stub agent drives every path; real agents are probes with planted defects | `stub_agent`, `probes/` (10, 11) |
| doctor renders every prompt offline: unresolved tokens, unknown steps, defaulted keys | `doctor` (02) |
| Prompt hook logs owner chat to gitignored OWNER.log; quotes verified; no log → start refuses | `ownerlog`, hooks (00, 03) |
| Agent definitions generated per rung; loaded at session start | `agentdefs` (02) |
| Ledger bills what happened | `ledger`, `pricing` (06) |
| Nothing closes in silence: unresolved finding blocks; flags reach the owner; repeats of withdrawn are dropped | `findings`, `results.validate` (05) |
| Owner files are the whole settings surface; local.yaml generated, no user input | `config` (unknown/defaulted keys), `localyaml` (01) |
| Locked-prose words are not descriptions of enforced software | prose is rendered, never interpreted: `render`, `plumbing` (02) |
| Step list fixed | `steps.TABLE` + `lint` (01) |

## 3. Shape of the system

```
owner ──chat──> driver (Claude Code session)
                  │  run.py start / next / record / owner / judgment
                  ▼
              runner (src/, plain Python) ──git──> round branch, worktree, main, remote
                  │ renders prompts from locked_prose + config + STATE
                  ▼
        prompt file ──(driver hands verbatim)──> producer / gate sub-agent ──> final message ──> result file
```

**Layers, bottom-up.** Each layer depends only on layers below it.

| Layer | Modules (file) | Owns |
|---|---|---|
| Roots & settings | `paths`, `config`, `steps`, `speclock`, `localyaml` (01) | where things are; the owner's numbers; the fixed step table; the spec snapshot |
| Text | `prose`, `agentsmd`, `render`, `plumbing`, `agentdefs`, `doctor` (02) | locked prose → prompts; offline health |
| Knowledge | `ownerlog`, `control`, `state`, `history`, `attempts`, `limits` (03) | what the owner said and decided; where the round is; bounds |
| Git | `gitops`, `worktree`, `landing`, `sync` (04) | the lock, the tree, landing, sync |
| Judgment of work | `results`, `findings`, `verify`, `suite` (05) | final messages; findings; tests; suite moves |
| Money | `tokens`, `pricing`, `quote`, `ledger` (06) | estimates; prices; shares; the bill |
| Sequencing | `round`, `run` (07) | the lifecycle; the CLI |

`round.py` is the only module that calls everything; it is a sequencer with no rules of
its own, and its section (07) lists the exact call order for each command so it can be
rewritten from that section alone. No other module is imported by more than its layer
above; `paths.py` (root discovery and the error base class) is imported everywhere but
holds no behaviour a rewrite could get wrong.

## 4. The round, end to end

1. **Claim.** `start` refuses on any drift, lint error, stale agent definitions, or empty
   owner log; else picks id = max+1 across landed folders and remote `round/*` branches,
   creates branch `round/NNNN` and worktree `.worktrees/round-NNNN/`, writes the round
   folder skeleton and pushes with a "must not exist" lease. (01, 03, 04, 07)
2. **Plan.** `next` hands the driver the rendered CHAT-TO-PLAN prompt (`self`). The driver
   chats, writes `PLAN.json` with every question answered by a verified quote, records; the
   gate (if on) judges; the owner's `approve`/`delegate` quote accepts the step. (02, 03, 06)
3. **Produce and judge.** For each producer step: `next` renders the prompt (overview prose
   + process instructions + STEP-END), opens the attempt, fences, and returns `spawn`; the
   driver spawns the rung's generated agent definition (read-only twin for gates) in the
   worktree, saves the final message, records. `record` triages the diff (strays reverted,
   refusals refused), validates the result, runs verification, books the cost, commits,
   fences. A gate FAIL opens a retry with the findings listed; PASS accepts and turns
   non-blocking findings into owner flags. (02, 04, 05, 06)
4. **Pause.** Checkpoints (unless delegated), questions, blocks, limits, hard stops,
   conflicts pause the round; `next` then returns `chat` with what to present; the owner's
   words come back as `owner --kind … --quote …`. (03, 07)
5. **Land.** LANDING merges the round branch into main in a landing worktree; a clean
   merge that passes the suite is pushed with a lease on main-before; a textual conflict
   becomes one agent attempt on the conflicted files, judged mechanically against the
   auto-merged tree. (04)
6. **Postmortem, cleanup, bill.** POSTMORTEM edits the carry-forward files; CLEANUP tidies;
   the runner books attempt spend, driver per-step charges, the living charge on
   main-before-landing → tip, and the frozen archive charges into `STATE.json.bill`; the
   post-landing commits sync into main (bounded); the worktree is removed; `next` returns
   `done` with bill, flags and the postmortem summary. (04, 06, 07)

## 5. Cross-cutting rules

- **Robust to owner edits.** Numbers, paths, prose, rung names and prices are read from the
  owner's files at every command; the only owner-shaped things in code are the step names
  (the owner says the list is fixed) and the token grammar. Everything the code needs that
  the owner may omit is in `config.DEFAULTS`, and `doctor` names each default in force.
  Unknown keys and unknown steps refuse to start rather than being silently ignored (JC-08).
- **No file is load-bearing.** Each module's section states its owns/depends/depended-on
  and its full public signature list; tests are one file per module. A module can be
  rewritten from its section without touching the rest.
- **Mechanical instructions carry no judgment.** `plumbing.py` writes paths, commands, lists
  and the JSON contract; the only judgment language an agent sees is the owner's prose,
  rendered verbatim.
- **Nothing is silent.** Strays are noted in HISTORY; refusals list every reason; PASS-time
  findings become flags; gate repeats of withdrawn findings are dropped with a note; every
  owner decision is a HISTORY event with its quote.
- **One token estimate.** `tokens.estimate` (bytes / `tokenBytes`, rounded up) is the only
  way text becomes tokens, for charges and prompt-size warnings alike.
- **Living paths are charged; everything generated lives outside them.** (00 §0.3)

## 6. Repository tree (summary; full tree in 00)

```
REPO_ROOT/  spec.yaml  SPEC.md  CLAUDE.md  .gitignore  .claude/{settings.json,agents/}  .github/workflows/ci.yml
  harness/  AGENTS.md  CLAUDE.md→AGENTS.md  project.yaml  subAgents.yaml  locked_prose/  README.md  INDEX.md
            pyproject.toml  requirements.txt  spec-baseline/  local.yaml*  OWNER.log*  .worktrees/*
            archives/rounds/NNNN/   src/*.py (31 modules)   docs/*.md (5)   tests/ (39 files + probes/)
```
`*` = gitignored, generated.

## 7. Component index

| File | Covers |
|---|---|
| [00 Repository layout](components/00-repo-layout.md) | roots, full tree, ownership rules, `.gitignore`, hooks, README, CI, pyproject, archives, spec-baseline |
| [01 Roots, config, steps, spec guard](components/01-paths-config.md) | `paths.py`, `config.py`, `steps.py`, `localyaml.py`, `speclock.py` |
| [02 Prompts](components/02-prompts.md) | template grammar, `prose.py`, `agentsmd.py`, `render.py`, `plumbing.py`, `agentdefs.py`, `doctor.py` |
| [03 Owner and state](components/03-owner-state.md) | `ownerlog.py`, `control.py`, `state.py`, `history.py`, `attempts.py`, `limits.py` |
| [04 Git](components/04-git.md) | `gitops.py`, `worktree.py`, `landing.py`, `sync.py` |
| [05 Record](components/05-record.md) | `results.py`, `findings.py`, `verify.py`, `suite.py` |
| [06 Money](components/06-money.md) | `tokens.py`, `pricing.py`, `quote.py`, `ledger.py` |
| [07 Round and CLI](components/07-round-cli.md) | `round.py`, `run.py`, exit codes, every subcommand |
| [08 File formats](components/08-schemas.md) | round folder layout, STATE.json, PLAN.json, AGENTS-PLAN.json, SPEC.json, SUITE.json, POSTMORTEM.md, judgment files, FINDINGS, local.yaml, OWNER.log |
| [09 Docs](components/09-docs.md) | `docs/PROCESS.md`, `MONEY.md`, `TESTING.md`, `TODO.md`, `CLARIFICATIONS.md` |
| [10 Tests part 1](components/10-tests-infra-and-units.md) | conftest, specgen, stub agent, drive loop, unit tests for 01–04, the drift test |
| [11 Tests part 2](components/11-tests-integration-and-probes.md) | unit tests for 05–07, 22 integration rounds, docs checks, live probes |

## 8. Glossary

**attempt** one spawn of one agent for one role of one step (`STEP-n`, `STEP-GATE-n`,
`LANDING-n`). **checkpoint** a driver pause for owner review, skipped under delegation.
**declared paths** what an attempt may edit; the rest is a stray. **fence** the push after
every state change. **finding** a gate's dated objection with quote and suggestion.
**flag** an item for the owner at the next pause. **living** under `livingSourcePaths`,
charged per token. **quote** (money) the round budget approved with the plan; (words) the
owner's verbatim text. **round folder** `archives/rounds/NNNN/`. **rung** a key of
`subAgents.yaml`. **stray** a change outside declared paths, reverted and noted.

## 9. Full traceability: every owner rule → where it is met

**From `AGENTS.md`**

| Rule | Where |
|---|---|
| "Your system prompt names your step, your inputs, where to write your artifact, and the JSON your final message must be" | `plumbing.process_instructions` (02); `results.schema_text` (05) |
| Driver: each `next` gives a prompt file; hand it verbatim to a fresh sub-agent (read-only for gates); save final message; `record` | `round.next`/`record` (07); `agentdefs` read-only twins (02); docs/PROCESS.md §Driver loop (09) |
| Living tokens charged/refunded | `ledger.living_charge` (06) |
| Only the runner commits, pushes, contacts the owner | `round` is the only committer/pusher (07); `plumbing` never tells a producer to push; `worktree.triage` refuses runner-only files (04) |
| Producers edit only in their worktree within declared paths + round folder | `worktree.declared_prefixes`, `triage`, `revert` (04) |
| Spec files never changed by agents | `worktree.triage` (`never` set) (04); `speclock` (01) |
| PROCESS-INSTRUCTIONS never require judgment calls | `plumbing` content rules (02); `test_plumbing` word check (10, JC-39) |
| Defined/undefined judgment calls recorded with the tool the process names; gates in the final message | `round.judgment`, `run.py judgment` (07); `results.judgment_calls` appended at record (05, 07); files 8.8 |

**From `project.yaml` (every key is used)**

| Key(s) | Used by |
|---|---|
| `vision` | `{{ project.vision }}` via `config.project_view` (01, 02) |
| `budget`, `lostValuePerHour`, `currency` | rendered; `ledger.remaining_project` (06) |
| `hardStopBudgetMultiple`, `hardStopBudgetMultipleIndividual` | `limits.hard_stop_*` (03); `control` override (03); `landing.begin` (04) |
| `livingFileTokenCap`, `livingFileCostPerToken`, `livingFileCostPerTokenOverCap`, `livingFileBaseCost`, `testBaseCost`, `tokenBytes`, `postMortemFileCostPerToken` | `ledger.price_tokens`, `living_charge` (06); `tokens.estimate` (06) |
| `postMortemCostPerSummaryToken`, `planCostPerToken`, `specCostPerToken` | `ledger.archive_charges` (06); rendered into prose |
| `maxRefactorOverhead`, `defaultShares` | `quote.lint_agents_plan` warnings, `default_plan` (06); SPEC.json refactors warning (08) |
| `gatesFraction`, `workFraction` | `quote.lint_agents_plan` enforced caps (06); `config.load` sum check (01) |
| `steps` | `steps.lint`, `gated`, `checkpoints_on` (01) |
| `allowUpstream` | `config.load` refuses 1 (01) |
| `livingSourcePaths`, `lockedProsePath`, `archivesPath` | `worktree.declared_prefixes` (04), `ledger` (06); `prose.prose_dir` (02); `state.find_round_folders` (03) |
| `roundPaths.*` | `attempts.files_for`, `state.path_for` (03); `worktree.round_folder` (04); `suite.archive` (05); 08 |
| `maxSimultaneousSubAgentsPerRound` | `quote.helpers_for`, lint (06); HELPERS in `plumbing` (02) |
| `maxRoundAttempts`, `maxTurnsPerGate`, `maxTurnsPerRun`, `maxRunWallClockHours` | `limits` (03) |
| `verifyTimeoutSeconds` | `verify.run_tests` (05) |
| `subAgentsFile`, `defaultAgent`, `gateAgent`, `systemTestAgent`, `maxAgent` | `config.load` (01); `quote.rung_for` (06); probes (11); `doctor` roster check (02) |

**From `subAgents.yaml`**: `estOutputFraction`, `driverUsdPerStep` → `pricing.estimate_usage`,
`ledger.book_driver_step` (06); per-rung `name`, `model`, `effort` → `agentdefs` (02);
prices, `spawnCost` → `pricing` (06); `priceSource`, `priceDate` → carried in `Agent`,
shown by `bill` (07).

**From the locked prose (mechanical parts only; judgment parts are rendered verbatim)**

| Prose | Where |
|---|---|
| approve / delegate / delegate through STEP / override / "#." answers / abandon + reason | `control.KINDS` and `validate` (03); `round.owner` effects (07) |
| "no round starts with unanswered questions" | `quote.plan_problems` at CHAT-TO-PLAN record (06, 07) |
| "When a checkpoint is reached, wait in chat"; CHECKPOINT-OVERVIEW | `round.next` checkpoint pause with the rendered prose (07) |
| DONE / NEEDS-OWNER / BLOCKED endings | `results.validate_producer` (05); `round.record` pause reasons (07) |
| Gate: prior findings with resolutions, never the transcript; rule on disputes first; upheld twice settled; every finding carries a suggestion | `plumbing` gate instructions (02); `findings.reconcile` (05); `results.validate_gate` (05) |
| "Small imbalances are non-blocking findings" (and the verdict-wins rule) | `findings.reconcile` step 3 (05, JC-27) |
| PLAN-TO-SPEC: SPEC.json + SPEC.md; carry non-goals | 8.5 required fields (08); `verify.load_spec_json` (05) |
| SPEC-TO-TESTS from the spec alone, before the code; frozen tests | step inputs and `frozen_test_paths` (01, 04) |
| TESTS-TO-SUITE: suite vs archive; flag the middle ground | `suite` (05); SUITE.json flags → owner flags (08, 07) |
| POSTMORTEM: Summary first; TODOs and CLARIFICATIONS; runner charges the summary | `verify.load_postmortem` (05); carry-forward paths (04); `ledger.summary_section` (06); docs formats (09) |
| CLEANUP: "The runner books the round's charges" | `round.finish` (07); `ledger.make_bill` (06) |
| COMMON-ROUND's list of round-folder files | 8.1 (08) |
| COMMON-STEP-END produced at the end of every step | `plumbing.step_end_text`, `-END.txt` files (02, JC-14) |
| `{{ agents.DEFINED_AND_UNDEFINED_JUDGMENT_CALLS }}` | `agentsmd.section` (02) |
