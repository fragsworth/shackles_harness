# Plan 5: building `shackles_harness` from the spec

Planner: one of several independent planners. Written 2026-09-12 from the worktree at commit `31fe13b`.
Everything below is implementable by one agent in one session. Where the spec is silent or ambiguous, §3 records the interpretation this plan commits to; the implementer makes no further design decisions of consequence.

## 0. Contents

1. How this plan was developed
2. What the spec fixes and what it leaves open (facts the design rests on)
3. Interpretations: every ambiguity, resolved
4. Standard features missing from a new LLM-operated project, and which are included
5. Design
6. Implementation order, with acceptance per milestone
7. Test strategy (stub suite, spec-change test and its own test, real-agent tiers)
8. Spec files that need edits: the exact minimal diffs
9. Risks and open questions, each with a recommended resolution

## 1. How this plan was developed

1. Read every file in the worktree: `spec.yaml`, the three harness config/instruction files, all sixteen locked prose files, and `bootstrap/vision-harness-round-concurrency.md`.
2. Read the sibling project's original where the summary was not enough to decide a point: its `run.py` (rendering, mechanical checks, record routing, landing, driver charging), `schemas.json`, prose PROCESS files (the `STEP:`/`ARTIFACT:`/`RESULT_FILE:` contract its stub parses), `stub_agent.py`, the test fixture header, `owner_log_hook.py`, `.claude/settings.json`, the round 001 owner log (the owner's rationale for this class of harness), and the round 004/005 histories and postmortems (what actually failed with real agents and real money). Nothing was imported wholesale; §5 says where a mechanism is reused and where it deliberately differs.
3. Verified the machine facts the design depends on, in a scratch directory, never on the screen: `py -3.13` is Python 3.13.2 with PyYAML 6.0.3 and pytest 9.1.1; git is 2.45.2 (conda MinGW build) and on this build bare-repo `update` hooks run (`sh.exe` is on PATH), `git push --porcelain --force-with-lease=refs/heads/X:` yields `*` (new, exit 0), `=` (up to date, exit 0) and `!` (stale, exit 1) exactly as the summary describes, `git merge-tree --write-tree` exists and lists conflicted files, `git rev-parse --git-common-dir` distinguishes a linked worktree, and `git branch -f main` refuses while `main` is checked out. `claude` is not on PATH in a tool shell; the Claude Code binary is `C:\Users\twolf\AppData\Roaming\Claude\claude-code\2.1.266\claude.exe` and its `--help` shows `--output-format json`, `--max-budget-usd`, `--effort`, `--model`, `--tools`, `--disallowedTools`, `--permission-prompts none`, `--json-schema`, a hidden `--system-prompt-file` (named in the `--bare` help text) and no `--max-turns`.
4. Listed every `{{ }}` placeholder the locked prose uses and checked each against `project.yaml`; found one mismatch (§8).
5. Listed the sibling's recorded failures (conflict path that cannot converge, config skew between worktrees, manual landing order, phantom approval from a bad owner-log slice, gates unable to write their result file, unmeasured driver cost, byte-frozen tests blocking mid-round fixes) and designed each one out or documented it (§5.8, §5.9, §9).
6. Wrote the design bottom-up from the owner's hard constraints: nothing mechanical may depend on prose wording, spec files change arbitrarily, edits to them are minimal and loud, the spec-change test must exist and be tested, one implementing agent, Windows/PowerShell/`py -3.13`.

## 2. What the spec fixes, and the facts the design rests on

- `spec.yaml` lists 19 owner files: `harness/AGENTS.md`, `harness/project.yaml`, `harness/subAgents.yaml`, 16 `harness/locked_prose/*.txt`. They are the only owner-owned files; everything else is built.
- `harness/AGENTS.md` fixes: the runner is `src/run.py`; only it commits, pushes, contacts the owner; the system prompt names step, inputs, artifact location, and the JSON of the final message, which the runner parses; `locked_prose/` is frozen mid-round; `src/`, `docs/`, `tests/` are living; the driver runs `run.py next`, hands the prompt file verbatim to a fresh sub-agent (read-only for gates), saves its final message to the result file, runs `record`; `{{ plumbing.PROCESS-INSTRUCTIONS }}` is runner-generated mechanics; DEFINED and UNDEFINED judgment calls are appended by agents to two files in the round folder. Paths there are relative to `harness/` (the file is headed `# harness/` and says `grep INDEX.md`, `read docs/PROCESS.md`).
- `project.yaml` fixes the economics (budget, hard stop multiple, time cost, owner costs per checkpoint and per plan/spec word, living-token pricing with a per-file cap and base costs, refactor cap), the gate list and their enablement (all 0 today), default shares, the paths (`livingSourcePaths`, `lockedProsePath`, `archivesPath`, `roundPaths` with every round file named), limits (`maxSimultaneousSubAgentsPerRound`, `maxRoundAttempts`, `maxFailuresBeforeStop`, `maxTurnsPerRun`, `maxRunWallClockHours`, `verifyTimeoutSeconds`), fractions, `estOutputFraction`, `driverUsdPerStep`, and agent rungs (`maxAgent`, `gateAgent`, `systemTestAgent` keyed into `subAgents.yaml`).
- `subAgents.yaml` fixes the roster: rungs `max`, `high`, `medium`, `low`, each with model, effort, prices per MTok, and `spawnCost`.
- The locked prose fixes the template namespaces in use: `prose.*` (includes: `COMMON-PROJECT`, `COMMON-ROUND`, `COMMON-OVERVIEW`, `COMMON-GATE`), `plumbing.*` (`PROCESS-INSTRUCTIONS`, `GATE-PROSE`), `project.*` (`shackles`, `budget`, `remaining`, `lostValuePerHour`, `livingFileCostPerToken`, `livingFileTokenCap`, `livingFileCostPerTokenOverCap`, `livingFileBaseCost`, `testBaseCost`, `livingSourcePaths`, `tokenBytes`, `maxRefactorOverhead`, `gates`, `ownerReviewCostPerWord`), `round.*` (`id`, `folder`, `base_commit`, `plan`, `budget`, `spend`, `remaining`), `step.*` (`retry_cost`). Only `project.remaining` and `step.retry_cost` are computed; `project.ownerReviewCostPerWord` does not exist in `project.yaml` (§8).
- Producer final-message statuses are fixed by `COMMON-OVERVIEW`: DONE, NEEDS-OWNER, UPSTREAM, BLOCKED. Gate mechanics are fixed by `COMMON-GATE`: PASS/FAIL, blocking vs non-blocking findings, each finding carries a suggestion, disputes ruled by quotation, upheld twice is settled, needs-owner upheld or withdrawn with the answer to assume.
- Owner words are fixed by `CHAT-TO-PLAN-OVERVIEW`: approve/approved, delegate/delegated, delegate through STEP, override + steps or gates.
- Checkpoints named in the spec: after the plan (approval), after PLAN-TO-SPEC ("Checkpoint after this step"), after CLEANUP ("Checkpoint after this step"; `project.yaml` says "checkpoint before landing").
- The sibling summary fixes the concurrency model to reuse: git as the lock manager (CAS branch claim, worktree isolation, push fence, bounded landing loop, timid post-round sync), its invariants I1-I11, its non-invariants (no leases, no TTL), and its test technique (bare local origin, update hooks, narrowed fetch refspecs).
- Real-agent facts from the sibling's rounds: an interactive Claude Code session was the driver and spawned sub-agents with its Agent tool; the headless `claude -p` path ran only under the stub; gates ran read-only and could not write their result file; prompts reached 40-80 KB; per-step agent cost was $1-6 and a retry chain from implementation onward ~$12.

## 3. Interpretations: every ambiguity, resolved

| # | Question the spec leaves open | Resolution committed to |
| --- | --- | --- |
| I1 | What are `src/`, `docs/`, `tests/`, `archives/`, `locked_prose/` relative to? | The harness root `harness/`. The repository root is `git rev-parse --show-toplevel`. Verify and suite commands run from the repository root. Every path in state files and artifacts is POSIX, relative to the repository root (`harness/src/...`). |
| I2 | Round id width and names | `roundPaths.folder` contains `NNNN`; the id is zero-padded to the count of N's (4). Branch `round/NNNN`, worktree `<main_root>/.worktrees/NNNN`, tags `round/NNNN-landed`, `round/NNNN-abandoned`. The runner substitutes the literal `NNNN` token, so a future `NNN` or `NNNNN` needs no code change. |
| I3 | Step order and checkpoints | CHAT-TO-PLAN (P) > CHAT-TO-PLAN-GATE (approval, checkpoint) > PLAN-AGENTS (P) > PLAN-AGENTS-GATE (G) > PLAN-TO-SPEC (P) > PLAN-TO-SPEC-GATE (G, checkpoint after) > SPEC-TO-TESTS (P) > SPEC-TO-TESTS-GATE (G, freezes tests) > SPEC-TO-IMPLEMENTATION (P) > SPEC-TO-IMPLEMENTATION-GATE (G) > TESTS-TO-SUITE (P) > TESTS-TO-SUITE-GATE (G) > CLEANUP (P, checkpoint after) > LANDING (M) > POSTMORTEM (P) > POSTMORTEM-GATE (G) > finished. The table lives in `harness/src/runner.yaml` (§5.2), not in code and not in a spec file. |
| I4 | A gate with `gates: X: 0` | The gate step is skipped: recorded in HISTORY as `skipped (disabled)`, no findings, no spend, `step_commits` set. Mechanical checks still run (they are the runner's, not the gate's). The producer's prompt says the gate is disabled this round (§5.4). |
| I5 | `maxFailuresBeforeStop` vs `maxRoundAttempts` | `failures[step]` counts gate FAILs, mechanical FAILs, schema failures, BLOCKED and landing findings routed to a step; reaching `maxFailuresBeforeStop` raises checkpoint `failure-limit`. `round_attempts` counts owner resumes of `failure-limit` and `round-limit` checkpoints; when a resume would exceed `maxRoundAttempts` the runner refuses and re-raises the checkpoint saying only `abandon` or a plan/spec change can proceed. |
| I6 | What `costToWaitForOwner` and `ownerHourlyRate` charge | `costToWaitForOwner` is booked once per checkpoint raised (owner bucket). `ownerHourlyRate` is not booked by the runner (no decision-time estimate exists in `project.yaml`); it is exposed to prose and to the postmortem, which also receives measured owner wait hours per checkpoint. |
| I7 | `planCostPerWord`, `specCostPerWord` | Booked to the owner bucket as net deltas: at approval, words of the rendered plan text times `planCostPerWord`; at each PLAN-TO-SPEC-GATE PASS (or skip), words of `SPEC.md` plus `SPEC.json.summary` times `specCostPerWord`, minus what was already charged for the spec this round. |
| I8 | Living charge formula | Per living file f, tokens `t = ceil(bytes / tokenBytes)`, `cost(t) = min(t, cap) * rate + max(t - cap, 0) * rateOver`; charge `cost(after) - cost(before)`; `+livingFileBaseCost` for a file created, `-livingFileBaseCost` for a file deleted; `+testBaseCost` per new test function (regex `testFunctionPattern`, default Python `def test_`) in kept files under `testPaths` that lie under `livingSourcePaths`. Tests archived into the round folder are not living. Computed once at LANDING against the tip actually merged (I8 of the summary). |
| I9 | Unknown template keys | Never fatal at render time. `{{ ns.key }}` that cannot be resolved renders as `«unresolved: ns.key»`, is listed in the prompt's HISTORY line and by `lint`. `start` dry-renders every step and refuses only on a missing prose file or include, not on an unresolved value. |
| I10 | Value rendering | strings verbatim; ints as is; floats with up to 4 decimals, trailing zeros trimmed; bools `true`/`false`; `None` as `none`; lists and maps as compact JSON (so `{{ project.gates }}` renders `{"CHAT-TO-PLAN-GATE": 0, ...}` and `{{ project.livingSourcePaths }}` renders `["src/", "docs/", "tests/"]`). |
| I11 | Computed `project.*` keys | `remaining` (project budget minus project-wide spend) and `spent`; added only when `project.yaml` lacks the key, never shadowing an owner value. |
| I12 | Which agent runs what | Gate: `AGENTS-PLAN.json.gateAgents[STEP]`, else `project.gateAgent`, else `project.maxAgent`. Producer: `AGENTS-PLAN.json.agents[STEP]`, else `project.maxAgent`. A candidate counts only if it is a key of `subAgents.yaml.agents`. PLAN-AGENTS and its gate run before the plan exists and use the fallbacks; their budgets come from `defaultShares`. |
| I13 | `maxTurnsPerRun` | Advisory (stated in the prompt); the CLI in use has no `--max-turns`. Enforced caps are `--max-budget-usd` and the wall clock `maxRunWallClockHours`. |
| I14 | Sub-agents | PLAN-AGENTS declares `subAgents[STEP] <= maxSimultaneousSubAgentsPerRound`; the runner prints `subagents_allowed` in the action and in the prompt; the driver enforces it. A sub-agent's tokens are recorded with `record --tokens N --agent KEY --spawns K`. |
| I15 | Judgment-call files | Created empty at `start`; append-only (mechanical check M4); their line counts are logged per attempt in HISTORY, carried into `index.jsonl`, and both files are named as inputs to POSTMORTEM. |
| I16 | An agent edits a spec file | Allowed, never silent: after every recorded attempt the runner diffs the spec files (the list in `spec.yaml`) from the step's start commit to HEAD; any change is appended to HISTORY as a fenced unified diff under `## SPEC EDIT`, added to `STATE.spec_edits`, and the round cannot land until the owner has approved at checkpoint `spec-edits`, delegation or not. The round-level manifest ack (§5.10) is folded into that approval. |
| I17 | `override` | `override` followed by step or gate names (any names from the step table found in the message after the word), or the words `gates` (every gate) or `checkpoints` (every review checkpoint); recorded in `STATE.overrides` and HISTORY; CHAT-TO-PLAN and LANDING cannot be overridden. An overridden gate auto-passes like a disabled one; an overridden producer step is skipped and its artifact, if the runner needs it, is the previous round's or the defaults (PLAN-AGENTS skipped means default shares and agents). |
| I18 | Where CHAT-TO-PLAN runs | In the owner's chat, by the driver, following `run.py prompt --step CHAT-TO-PLAN` (rendered without a round: `round.*` values read `none yet`). The driver writes `PLAN.json` and runs `start --plan`; approval is read only from the owner log. |
| I19 | Owner log slice | From `min(previous round's landed_at or abandoned_at, PLAN.json.presented_at)` (fixes the sibling's phantom approval). Approval words count only after `presented_at`. |
| I20 | `LANDING` position vs POSTMORTEM | Landing after CLEANUP as the spec says; the POSTMORTEM and its gate commit after landing and reach `main` by the fast-forward-only sync (§5.8); when a sibling moved `main` first they arrive with the next landing merge. |
| I21 | Tests frozen after SPEC-TO-TESTS-GATE | Kept, byte-frozen from the gate's PASS commit through LANDING, except for the merge attempt (§5.8) where the frozen reference is the auto-merged version. A wrong test is UPSTREAM to SPEC-TO-TESTS. |
| I22 | `SPEC.md` errata | `inputs_hash` covers `SPEC.json` and `SPEC.md` with a trailing `## Errata` section stripped; any later step may append errata lines there without triggering re-entry. |
| I23 | CLEANUP's allowed paths | `implPaths`, plus living paths that are not `testPaths` (so `docs/`), plus `harness/INDEX.md`, plus the round folder. |
| I24 | TODO and CLARIFICATIONS feed | `round.todos` is every `- ` line under a heading starting with `TODO` or `CLARIFICATION` (case-insensitive) in the `POSTMORTEM.md` of every landed round, minus lines quoted verbatim in any later `PLAN.json.todos`. `round.history` is the last five `index.jsonl` rows as `round N: quoted X actual Y (outcome)`. |
| I25 | Living paths for the harness's own rounds | `harness/src/`, `harness/docs/`, `harness/tests/` per I1; `harness/INDEX.md`, `harness/AGENTS.md`, `spec.yaml`, `bootstrap/` are not living (uncharged). |

## 4. Standard features a project of this kind needs, and what is included

Found missing (nothing exists yet) and included, grouped:

Entry and routing: root `AGENTS.md` (entry: where the runner, rules, routing and spec files are) with root `CLAUDE.md` containing only `@AGENTS.md` (symlinks are off on this machine; Claude Code imports `@file`); `harness/INDEX.md` alias-to-path routing (grep-friendly, one route per line); `harness/docs/PROCESS.md`, the normative mechanics, one sentence per line (merge-friendly; the sibling's one-paragraph line was the file that conflicted); `run.py --help` and `--version`.

Operability: `status`, `spend`, `check`, `lint` (config, prose, placeholders, hooks, preconditions), `prompt` dry-render, `prune`, `agents` (roster and tool flags), JSON on stdout, errors on stderr, fixed exit codes, crash recovery by re-entry, runner identity check (the copy driving a round vs the round's own copy), config read with defaults so a newer runner never `KeyError`s on an older branch.

Contracts: `schemas.json` for every artifact and message with exact error messages; the machine-readable prompt tail (`STEP:`, `ATTEMPT:`, `ARTIFACT:`, `RESULT_FILE:`) that stub and real agents both follow; `--json-schema` passed to headless agents so the final message is structurally valid before it reaches `record`.

Spec robustness (the owner's hard constraint): the spec manifest with a pytest test that flags any change to a `spec.yaml` file and a test of that test; the runner-side check at `next` and at landing; loud, diffed, owner-approved agent edits; placeholders resolved by name only, never parsed for meaning; step table outside the spec; dry-render at `start`.

Agents: `.claude/agents/shackles-gate.md` (tools `Read, Grep, Glob`) and `.claude/agents/shackles-producer.md` (`disallowedTools` for git commit/push/tag/reset) so the driver's Agent tool applies the right restrictions; a `shackles-round` skill describing the driver loop; headless `agentCommand` with `agentExecutable` override for this machine; `scrubEnv`; a stub agent for tests; replay fixtures recorded from real runs.

Owner interaction: `UserPromptSubmit` hook appending the owner log, `SessionStart` hook writing `DRIVER.json` (the sibling's delegated rounds went unmeasured because only prompts wrote it); both `py -3.13` and shell-neutral.

Economics: full ledger (agent by cost or tokens, spawn cost, driver flat or measured, owner per checkpoint and per plan/spec word, time, living with cap/base/test costs), hard stop, project tally across live rounds, quote-versus-actual feed, per-run prompt-size guard.

Concurrency and landing: everything in the summary plus the fixes for its recorded failures: a merge attempt that can converge on conflicts, landing that needs no local `main` checkout state, `start` preconditions, sibling path-overlap warning, `prune`.

Deliberately excluded: any daemon, database, lease/heartbeat/TTL, web UI, SMS/email contact, auto-resolution of merge conflicts, non-git VCS, LLM-judged assertions in the permanent suite, transcript-measured driver cost as a requirement (it is an optional phase-2 feature behind `DRIVER.json`).

## 5. Design

### 5.1 Repository layout

```
AGENTS.md                      entry (built)          CLAUDE.md: "@AGENTS.md" (built)
spec.yaml, bootstrap/          owner's
.gitignore                     .worktrees/  harness/OWNER.log  harness/DRIVER.json  __pycache__/  .pytest_cache/  *.pyc
.claude/settings.json          hooks (§5.11)
.claude/agents/shackles-gate.md, shackles-producer.md      sub-agent definitions (§5.13)
.claude/skills/shackles-round/SKILL.md                     the driver loop, for the owner's session
harness/
  AGENTS.md, project.yaml, subAgents.yaml, locked_prose/   spec files (owner's)
  INDEX.md                     routing
  docs/PROCESS.md              normative mechanics
  src/run.py                   entry shim: sys.path insert, `from shackles.cli import main`
  src/runner.yaml              runner-owned config and the step table (§5.2)
  src/owner_log_hook.py        stdlib-only hook script
  src/shackles/                package: config.py render.py gitops.py artifacts.py schemas.json
                               ledger.py checks.py round.py landing.py specwatch.py agents.py cli.py
  tests/conftest.py            sys.path, hermetic git env, fixtures import
  tests/harness_fixtures.py    Repo, Origin, View, play(), stub driving
  tests/stub_agent.py          scripted agent (§7.1)
  tests/test_*.py              the permanent suite
  tests/fixtures/              toy project, round snapshots, planted-defect artifacts, replays
  archives/rounds/NNNN/        round folders (runner-written)
  archives/rounds/index.jsonl  one line per finished or abandoned round
  archives/spec-manifest.json  hashes of the spec files (§5.10)
  archives/spec-acks.jsonl     one line per acknowledgment (append-only, merge-friendly)
```

Stdlib plus PyYAML in the runner; pytest only in tests. Module sizes should land near: `round.py` 600, `cli.py` 250, `render.py` 200, `config.py` 200, `gitops.py` 200, `ledger.py` 200, `checks.py` 200, `landing.py` 200, `specwatch.py` 150, `artifacts.py` 200, `agents.py` 150 lines. Every file UTF-8; every subprocess `text=True, encoding="utf-8", errors="replace"`; every written file goes through one `write()` that writes a temp file and `os.replace`s it.

### 5.2 Configuration

`config.py` loads, in order: `spec.yaml` (file list), `harness/project.yaml`, `harness/subAgents.yaml` (path from `project.subAgentsFile`, default `subAgents.yaml`), `harness/src/runner.yaml`. Every `project.*` key the runner reads goes through `cfg.project(key)` with a documented default in a `DEFAULTS` table (the sibling broke an in-flight round on a new key; here a missing key is a default plus a `lint` warning, never a crash). Unknown keys are fine and are exposed to templates.

`runner.yaml` (built, living, editable by rounds; not a spec file):

```yaml
mainBranch: main
worktreeDir: .worktrees
suiteCommand: "py -3.13 -m pytest -q harness/tests"
agentExecutable: claude          # overridden on this machine with the absolute path of claude.exe
agentCommand: ["{exe}", "-p", "--output-format", "json", "--system-prompt-file", "{prompt_file}",
               "--model", "{model}", "--effort", "{effort}", "--max-budget-usd", "{budget_usd}",
               "--permission-mode", "bypassPermissions", "--permission-prompts", "none",
               "--no-session-persistence", "--json-schema", "{result_schema}", "{tool_flags}", "{task}"]
agentTask: "Do the task in your system prompt. Your final message must be exactly the JSON it asks for."
gateToolFlags: ["--tools", "Read,Grep,Glob"]
producerToolFlags: ["--disallowedTools", "Bash(git commit:*)", "Bash(git push:*)", "Bash(git tag:*)", "Bash(git reset:*)", "Bash(git merge:*)"]
scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]
maxPromptBytes: 120000
testFunctionPattern: '^\s*(async\s+)?def\s+test_'
pushAttempts: 5
infraRetries: 3
steps:
  - {name: CHAT-TO-PLAN, kind: producer, artifact: plan}
  - {name: CHAT-TO-PLAN-GATE, kind: approval, checkpoint: true}
  - {name: PLAN-AGENTS, kind: producer, artifact: agentsPlan}
  - {name: PLAN-AGENTS-GATE, kind: gate}
  - {name: PLAN-TO-SPEC, kind: producer, artifact: spec}
  - {name: PLAN-TO-SPEC-GATE, kind: gate, checkpoint: true}
  - {name: SPEC-TO-TESTS, kind: producer, paths: testPaths}
  - {name: SPEC-TO-TESTS-GATE, kind: gate, freezes: testPaths}
  - {name: SPEC-TO-IMPLEMENTATION, kind: producer, paths: implPaths, verify: true}
  - {name: SPEC-TO-IMPLEMENTATION-GATE, kind: gate}
  - {name: TESTS-TO-SUITE, kind: producer, artifact: suite}
  - {name: TESTS-TO-SUITE-GATE, kind: gate, archives: true}
  - {name: CLEANUP, kind: producer, paths: cleanup, verify: true, checkpoint: true}
  - {name: LANDING, kind: landing}
  - {name: POSTMORTEM, kind: producer, artifact: postmortem}
  - {name: POSTMORTEM-GATE, kind: gate}
```

Conventions the table relies on: a gate's producer is its name minus `-GATE`; a producer's prose file is `locked_prose/<NAME>-OVERVIEW.txt`; a gate's is `locked_prose/<NAME>.txt`; `artifact` keys index `project.roundPaths.artifacts`. `lint` cross-checks the table against `project.gates` (every gate in either place is in both, else a warning), against the prose folder (missing prose file for a table step is an error; a prose file with no table step is a warning: "owner added a step?"), and against `spec.yaml` (every listed file exists).

### 5.3 Rendering

`render(text, ctx)` substitutes `{{\s*([A-Za-z0-9_.\-]+)\s*}}`, recursively for `prose.*` includes (depth limit 8, a cycle renders as `«include cycle: NAME»`). Namespaces: `prose.NAME` = `locked_prose/NAME.txt` read with `git show <prose_commit>:<path>` when a round exists (the working tree otherwise); `plumbing.NAME` = runner blocks (§5.4); `project.*` = `project.yaml` with dotted access for nested maps plus computed keys (I11); `round.*`, `step.*`, `agent.*` = runtime values listed below; anything else = unresolved marker (I9). Values render per I10.

Runtime values: `round`: `id` (padded), `folder`, `base_commit`, `prose_commit`, `plan` (plain-English rendering of `PLAN.json`: summary, then Scope, Validation, Non-goals, Assumptions as bullets, then quote), `budget`, `spend`, `remaining`, `history`, `todos`, `branch`, `worktree`. `step`: `name`, `attempt`, `kind`, `budget`, `retry_cost` (the producer's step budget; for a gate that judges step S it is S's work budget), `max_turns`, `wall_clock_hours`, `gate_enabled`. `agent`: `artifact_path`, `result_file`, `inputs` (list), `declared_paths`, `frozen_paths`, `findings` (JSON of the latest findings file for the producer plus carried non-blocking findings), `previous` (the previous final message, or `none`), `question`, `verify`, `diff_base`, `subagents_allowed`, `judgment_files`.

Prompt files are written to `PROMPTS/<STEP>-<attempt>.txt` and are the whole system prompt. A prompt over `maxPromptBytes` is not an error: embedded artifacts (the plan text, findings JSON) are replaced by their paths, a HISTORY line records it, and the prose's own "too large to review? Fail" judgment stays with the gate.

### 5.4 The `plumbing` blocks

`plumbing.PROCESS-INSTRUCTIONS` is generated per step from the step table and the round state; it is the only place mechanics are stated, so it must be complete. Producer block, in this order:

```
PROCESS INSTRUCTIONS (mechanical; written and parsed by the runner).
STEP: <name>
ATTEMPT: <n>
KIND: producer
ROUND_FOLDER: <folder>
ARTIFACT: <path>                          | for code steps: "the files under: <declared paths>"
RESULT_FILE: <folder>/RESULTS/<STEP>-<n>.json
BUDGET_USD: <x>  MAX_TURNS: <n> (advisory)  WALL_CLOCK_HOURS: <h>  SUBAGENTS_ALLOWED: <k>
INPUTS: <comma list of paths this step reads>
DECLARED_PATHS: <paths you may create or change>   FROZEN_PATHS: <paths you must not change, or none>
VERIFY: <command, run from the repository root> (code steps only)
MERGE IN PROGRESS: <conflicted files> (merge attempts only, §5.8)
Findings to resolve, with their status (every id must appear in your resolutions as fixed or disputed; a settled id cannot be disputed): <JSON or none>
Your previous final message: <text or none>
Rules: write only under DECLARED_PATHS and ROUND_FOLDER. Never run git commit, push, tag, reset or merge; the runner commits your work. Files listed in spec.yaml are the owner's: edit one only when genuinely necessary, minimally; every such edit is shown to the owner as a diff before the round lands. Append one line per judgment call to <defined file> or <undefined file>; never rewrite their existing lines.
Artifact contract: <per-step sentence, e.g. "AGENTS-PLAN.json, schema AGENTS_PLAN: agents {STEP: agent key}, gateAgents {GATE: agent key}, subAgents {STEP: count <= k}, shares {work: {...}, gates: {...}} each summing to 1, notes.">
Checked mechanically before any gate: <per-step list, e.g. schema; diff confined to DECLARED_PATHS plus the round folder; frozen paths unchanged; verify green within <t>s>. A failure returns to you as a finding without spending a gate.
Final message: exactly one JSON object and nothing else:
{"status": "DONE" | "NEEDS-OWNER" | "UPSTREAM" | "BLOCKED", "notes": "<one paragraph>", "question": "<NEEDS-OWNER only>", "target": "<UPSTREAM only: an earlier producer step>", "resolutions": {"<id>": {"status": "fixed" | "disputed", "reason": "<why>"}}, "cost_usd": <optional, if you know it>}
Then: DONE, the gate runs (or is skipped: <gate name> is disabled this round); NEEDS-OWNER, the gate rules on the question; UPSTREAM, the round returns to the target with your notes as a finding; BLOCKED, the round pauses for the owner.
```

Gate block: same header with `KIND: gate`, `ARTIFACT` (a path, or for code steps `git diff <base> -- <paths>`), `INPUTS`, `Already checked mechanically: ...`, `Prior findings with the producer's resolutions`, `The producer's question, if any`, `The producer's final message`, then: `You are read-only. You write nothing; your final message is the verdict and the driver saves it to RESULT_FILE.` and the verdict contract `{"verdict": "PASS"|"FAIL", "findings": [{"id": "F<n>", "quote", "reason", "suggestion", "blocking": true|false}], "rulings": {"<id>": {"status": "upheld"|"withdrawn", "quote"}}, "needs_owner": {"status": "upheld"|"withdrawn", "reason"}, "notes"}` with `Ids continue from the highest prior id. Verdict is FAIL exactly when a finding is blocking or needs_owner is upheld.`

`plumbing.GATE-PROSE` (inside a producer prompt): the gate's prose file rendered with the gate's context, its own `plumbing.PROCESS-INSTRUCTIONS` replaced by `(the gate's process instructions are omitted here)`, prefixed by `(This gate is disabled this round.)` when so. For CHAT-TO-PLAN, whose gate is mechanical, it renders the runner's sentence: `CHAT-TO-PLAN-GATE is mechanical: the runner reads the owner's words from the owner log after the plan's presented_at and proceeds on approve or delegate; abandon ends the round.`

The four `STEP:`/`ATTEMPT:`/`ARTIFACT:`/`RESULT_FILE:` lines are the machine-readable contract the stub agent and the systemtest harness parse (last occurrence wins).

### 5.5 Artifacts and messages (`schemas.json`, validated by `artifacts.py`)

Validation returns a list of exact messages (`"SPEC: implPaths and testPaths overlap: 'a' / 'b'"`), used verbatim in findings and tested verbatim.

- `PLAN` (written by the driver, copied in by `start`): required `presented_at` (UTC `...Z`), `quote_usd` (number), `summary`, `scope[]`, `validation[]`, `non_goals[]`; optional `assumptions[]`, `todos{key: {status: taken|deferred, todo, reason, budget_usd (taken)}}`, `title`, `text`. `round` is set by `start`.
- `AGENTS_PLAN`: required `round`, `agents{STEP: key}`, `shares{work{STEP: f}, gates{STEP: f}}`; optional `gateAgents{GATE: key}`, `subAgents{STEP: n}`, `notes`. Checks: keys are steps of the right kind; agent keys exist in the roster; each shares map sums to 1 within 0.01 and every share is in [0, 1]; `subAgents` values are integers within the limit.
- `SPEC`: required `round`, `summary`, `verify` (string), `implPaths[]`, `testPaths[]`; optional `verifyTimeoutSeconds`, `refactorShare` (0..1, `<= maxRefactorOverhead`), `nonGoals[]`, `notes`. Checks: non-empty POSIX relative paths; disjoint by prefix; none inside the round folder, `lockedProsePath`, or a `spec.yaml` file; `SPEC.md` exists beside it.
- `SUITE`: required `round`, `keep[]`, `archive[]`, `notes`. Checks: every test file added or modified this round under `testPaths` (`git diff --name-only <base_commit> -- <testPaths>`) appears exactly once; every listed path exists.
- `POSTMORTEM.md`: free markdown; the runner reads TODO/CLARIFICATION sections (I24).
- `RESULT` (producer final message): required `status` in the four; optional `notes`, `question`, `target`, `resolutions{id: {status: fixed|disputed, reason}}`, `cost_usd`.
- `FINDINGS` (gate final message): required `verdict` (PASS|FAIL), `findings[]` each with `id`, `quote`, `reason`, `suggestion`, `blocking`; optional `rulings`, `needs_owner`, `notes`, `cost_usd`. The runner adds `source` (`gate`, `mechanical`, `upstream`, `blocked`, `owner`, `owner-assumed`, `landing`).
- `STATE`: required `round`, `branch`, `created_at`, `status` (active|checkpoint|finished|abandoned), `step`, `attempts{}`, `failures{}`, `infra_errors{}`, `step_commits{}`, `step_starts{}`, `inputs_hash{}`, `budget_usd`, `spend{entries[], agent_usd, driver_usd, owner_usd, living_usd}`; optional `base_commit`, `prose_commit`, `delegated`, `approval`, `checkpoint`, `pending_question`, `carried_findings[]`, `last_findings{}`, `findings_ledger{}`, `mech_ok{}`, `overrides[]`, `spec_edits[]`, `spec_edits_approved_at`, `merge_pending{}`, `round_attempts`, `hard_stop_raised`, `round_limit_raised`, `landed_at`, `abandoned_at`, `owner_since`, `words_charged{plan, spec}`, `driver_cursor`, `driver_session`, `runner_version`. Validated on every save; the round folder is the only state.

`record --result FILE` accepts the file the driver saved: raw text is allowed; the runner strips a code fence and extracts the first top-level JSON object; anything else is an infrastructure error (§5.6).

### 5.6 The state machine (`round.py`)

Statuses and transitions as in the summary's lifecycle (active, checkpoint, finished, abandoned). Commands:

`start --plan F [--budget X] [--branch NAME] [--no-branch] [--delegated all|through:STEP]`: validate the plan before any git; preconditions (§5.8); claim the id (or `--no-branch`); create the worktree; write `PLAN.json` (with `round`), `STATE.json` (`base_commit = prose_commit = HEAD`, step `CHAT-TO-PLAN-GATE`, attempts `{CHAT-TO-PLAN: 1}`), `HISTORY.md`, `OWNER.log` slice (I19), the two empty judgment-call files, `words_charged.plan`; book CHAT-TO-PLAN's default share as an estimate and the plan words; commit `round NNNN: start`, push when branched; print `{round, folder, branch, worktree}`.

`next [--no-push]`: (1) finished/abandoned: sync main, print `done`, exit 0. (2) runner identity warning. (3) out-of-band edits: re-hash `PLAN.json` and `SPEC.json`+`SPEC.md` (I22); a changed plan re-enters at CHAT-TO-PLAN-GATE with approval cleared; a changed spec after its gate re-enters at SPEC-TO-TESTS; downstream counts reset. (4) spec manifest check (§5.10): a mismatch not explained by this round's own recorded `spec_edits` raises checkpoint `spec-changed`. (5) dirty-tree recovery: `git merge --abort` if `MERGE_HEAD` exists, `git checkout -- .`, `git clean -fdq`, `infra_errors[step] += 1`, HISTORY line. (6) refresh the owner-log slice. (7) at a checkpoint, look for a newer owner word after the checkpoint's timestamp and resume, else print the checkpoint and exit 10. (8) loop over mechanical work: approval step; disabled or overridden gates (auto-pass); mechanical checks before a gate of a code step (once per producer attempt, tracked in `mech_ok`); review checkpoints after a step marked `checkpoint` unless delegated through it; LANDING (§5.8); hard stop; then for the first step that needs an agent: set `step_starts[step]` if absent, establish the merge state if `merge_pending` (§5.8), render the prompt, save, commit (no push), print the action `{round, step, kind, attempt, prompt_file, result_file, artifact, agent, agent_type, model, effort, budget_usd, max_turns, wall_clock_hours, subagents_allowed, spend}`, exit 0.

`record --step S --attempt N --result F [--cost USD] [--tokens N --agent KEY]... [--spawns K] [--no-push]`: guards (status active, `S == state.step`, `N == attempts[S] + 1`, else exit 2, nothing written); parse the result (a failure writes `RESULTS/<S>-<N>.raw.txt`, `infra_errors[S] += 1`, commits, exits 2 with `re-run the same attempt`; after `infraRetries` failures raises checkpoint `infra`); copy to `RESULTS/`; book spend (agent cost, tokens, spawns, driver flat); M0 (agent commits folded back with `git reset --soft`); route: producer statuses DONE (schema check S1; artifact-specific checks; advance; CLEANUP and SPEC-TO-IMPLEMENTATION run their mechanical checks at the gate half), NEEDS-OWNER (store the question, advance to the gate; a disabled gate means the runner asks the owner directly: checkpoint `needs-owner`), UPSTREAM (target must be an earlier producer; reset downstream; finding U1 to the target; a target of CHAT-TO-PLAN raises checkpoint `upstream-plan`), BLOCKED (finding B1 to the same step, failure counted); gate verdicts PASS (settle rulings, carry non-blocking findings, `step_commits`, freeze or archive as the table says, advance, review checkpoint if marked) and FAIL (findings to the producer, failure counted, limit check); spec-edit detection (I16) and judgment-file checks (M4) on every recorded attempt; save; commit `round NNNN: <S> attempt <N>`; push, and a rejected push aborts with `another runner owns this round (push rejected)` (the fence); when the round just finished, sync main.

Findings ledger: `rulings` upheld count per id; two upholds settle; disputing a settled id is rejected at `record` (exit 2, so the driver can correct the message). `carried_findings` are pruned when a later attempt marks them fixed.

Checkpoints (`checkpoint` status, exit 10, one owner charge each): `approval`, `review`, `failure-limit`, `round-limit`, `hard-stop`, `needs-owner`, `upstream-plan`, `blocked`, `infra`, `spec-changed`, `spec-edits`. Resume words: `approve` resumes (failure-limit resets that step's failures and counts a round attempt; needs-owner passes the owner's whole message to the producer as finding O1; spec-changed/spec-edits approve = ack); `delegate`/`delegate through STEP` approve and set delegation; `abandon` abandons. Delegation skips only `review` checkpoints.

`abandon --reason R`, `status`, `spend [--project]`, `check`, `lint`, `prompt --step S [--attempt N]`, `spec status|diff|ack --note T`, `prune [--apply]`, `agents`, `run --until checkpoint|step|done`, `systemtest ...` (§7.3), `--version`. Exit codes: 0 ok/finished, 1 error, 2 usage or rejected record, 3 check failed, 10 checkpoint.

### 5.7 Mechanical checks (`checks.py`)

All produce findings with `source: mechanical` and go to the producer as a new attempt without spending a gate; ids are stable and tested:

| id | when | check |
| --- | --- | --- |
| S1 | DONE of an artifact step | artifact readable and valid per §5.5 |
| M0 | every record | HEAD moved during the attempt: `git reset --soft <prompt commit>`, non-blocking finding, HISTORY line |
| M1 | gate half of code steps, CLEANUP; every record for path scope | `git diff --name-only <step_starts[step]> HEAD` confined to the step's allowed paths plus the round folder (merge attempts: plus the conflicted files, measured against the auto-merged tree, §5.8) |
| M2 | SPEC-TO-IMPLEMENTATION, CLEANUP | frozen paths byte-identical to the freeze commit (`step_commits[SPEC-TO-TESTS-GATE]`); merge attempts compare against the auto-merged version |
| M3 | SPEC-TO-IMPLEMENTATION, CLEANUP | `SPEC.verify` green within `verifyTimeoutSeconds` (spec's value, else project's) |
| M4 | every record | the two judgment-call files only grew: existing lines unchanged (`git diff <step_starts> HEAD -- <files>` has no `-` lines) |
| M5 | every record | spec files changed: not a failure; diff to HISTORY, `spec_edits` entry (I16) |
| M6 | before spawning | prompt over `maxPromptBytes`: shrink and warn, never fail |
| S2 | TESTS-TO-SUITE DONE | suite consistency (§5.5) |
| L1, L2 | LANDING | merge conflict; verify or suite red on the merged tree |

Timeouts: on Windows `subprocess.run(timeout=)` kills only the shell, so commands run via `Popen` and on timeout the runner calls `taskkill /T /F /PID` (POSIX: `killpg`), then reports `M3`/`L2` with `timed out after Ns`.

### 5.8 Concurrency and landing (`gitops.py`, `landing.py`)

Reused from the summary unchanged: `main_root`, the id claim (fetch; `1 + max(local folders, origin round branches)`; up to `pushAttempts` CAS pushes with an empty lease; win only on exit 0 plus a `*` porcelain line; explicit `--branch` pushes exactly once), `git worktree add -b`, everything after the claim done with the worktree as root, `--no-branch` mode, the record push fence, `check` never pushing or charging, the landing check phase (fetch, merge target, verify, suite), the bounded land loop that re-checks against the new tip after a rejected push, one living entry per landed round priced against the tip actually merged, the `-landed` tag, the timid fast-forward-only `sync_main`, prompts rendered from `prose_commit`.

Changed deliberately:

1. Landing pushes `HEAD:refs/heads/<main>` to origin and then updates local `main` best-effort with `git fetch origin <main>:<main>` (a checked-out `main` only costs a warning). Without an origin, `git branch -f <main> HEAD` is used and `start` refuses up front if `main` is checked out in any worktree (`git worktree list --porcelain`).
2. `start` preconditions: `.gitignore` contains `<worktreeDir>/` (refuse otherwise; the dirty-tree `git clean` would delete sibling worktrees), the no-origin rule above, `core.longpaths` unset on Windows is a warning with the command to set it, and a warning listing live sibling rounds whose `SPEC.json` (`git show origin/round/X:<path>`) declares paths overlapping this round's once its spec exists (re-checked at PLAN-TO-SPEC-GATE PASS and written to HISTORY).
3. The conflict path converges. On L1 the runner records the finding for SPEC-TO-IMPLEMENTATION and sets `merge_pending = {target: <sha>, conflicted: [<files from git merge-tree --write-tree --name-only HEAD target>]}`. The next `next` for that attempt, after dirty-tree recovery, runs `git merge --no-commit --no-ff <target>` (the tree now holds conflict markers) and renders the prompt with the `MERGE IN PROGRESS` line and the instruction to resolve exactly those files, keep both sides' intent, run verify, and never run git merge or commit. `record` commits with `MERGE_HEAD` present, producing a merge commit. M1/M2 for that attempt compare HEAD's tree against the auto-merged tree from `merge-tree`: only conflicted files may differ beyond the allowed paths; a frozen test that was itself conflicted is a non-blocking M2 note. UPSTREAM, BLOCKED or an infrastructure error aborts the merge. When the attempt passes its gate and the round reaches LANDING again, the merge finds the target already merged (or a newer tip, and the loop repeats, bounded by `pushAttempts`).
4. Runner and config skew: the runner reads config with defaults (§5.2); `next` and `record` compare the sha256 of the running package with the copy at `<root>/harness/src/shackles/` and warn `driving with a different runner than the round's`; `docs/PROCESS.md` states the rule: a round is driven by the runner on its own branch, `py -3.13 <worktree>/harness/src/run.py --root <worktree>`.
5. `prune [--apply]` lists origin `round/*` branches with no commit after their start commit (claimed, never used), local worktrees of finished or abandoned rounds, and stale remote-tracking refs; `--apply` removes worktrees only.
6. Landing order is free: because the conflict path converges, either of two parallel rounds may land first.

### 5.9 Spend (`ledger.py`)

Entry `{step, attempt, usd, source, at, extra}`; buckets `agent_usd` (sources `cli`, `tokens`, `estimate`, `spawn`), `driver_usd` (`driver-flat`, `driver-measured`), `owner_usd` (`checkpoint`, `plan-words`, `spec-words`), `living_usd` (`living`), and `time_usd` computed on read as hours open (from `created_at` to `landed_at`/`abandoned_at`/now) times `lostValuePerHour`. Formulas: tokens priced at `N * (f*out + (1-f)*in) / 1e6` with `f = estOutputFraction` and the agent's prices; `spawnCost * spawns` per record; `driverUsdPerStep` per record (replaced by a measured entry when `DRIVER.json` names a readable transcript: the sibling's per-session cursor, de-duplicated by message id, priced per model with cache read/write rates); owner and living per I6-I8. Hard stop: after every entry and before every prompt, if `total > hardStopBudgetMultiple * budget_usd` raise `hard-stop` once. `spend --project` sums `index.jsonl` plus every round folder not yet indexed. `index.jsonl` line: `{id, quote_usd, spend, attempts, failures, outcome, prose_commit, landed_at|abandoned_at, judgment_calls: {defined, undefined}, spec_edits, checkpoints}`.

### 5.10 Spec manifest and change detection (`specwatch.py`)

`harness/archives/spec-manifest.json` = `{"spec_yaml_sha256", "files": {"<path>": {"sha256", "bytes"}}}` over LF-normalized content of every `spec.yaml` file and of `spec.yaml` itself. `check(repo_root)` returns `{changed, added, removed, spec_yaml_changed}` (all empty means clean); `ack(repo_root, note, by)` rewrites the manifest and appends `{"at", "by", "note", "changed": [...]}` to `spec-acks.jsonl`; `diff(repo_root)` prints unified diffs of changed files against `git show HEAD~` when available, else a summary.

Three consumers share `check`: the pytest test `test_spec_manifest.py::test_spec_files_match_manifest` (fails with the list of changes, the per-step impact hint — which prose files map to which steps — and the exact ack command); `next` and `landing_check` (a mismatch raises checkpoint `spec-changed` unless it is exactly this round's own `spec_edits`, which are pending `spec-edits`; approving either acks and commits the manifest on the round branch); `lint`. The acks file is append-only JSONL so two rounds acking different changes merge cleanly; the manifest is a pure map that the winner regenerates. The test of the test is in §7.2.

### 5.11 Owner log and driver pointer (`owner_log_hook.py`, `.claude/settings.json`)

`UserPromptSubmit` and `SessionStart` hooks both run `py -3.13 harness/src/owner_log_hook.py` (cwd is the project dir; the script also honours `CLAUDE_PROJECT_DIR`). It resolves the main checkout with `git rev-parse --git-common-dir` so a session in a worktree appends to the shared `<main_root>/harness/OWNER.log` (`<UTC Z>\t<message with \ and newlines escaped>`, envelopes such as `<system-reminder` skipped) and writes `<main_root>/harness/DRIVER.json` (`session_id`, `transcript_path`, `updated_at`) on both events. `lint` warns when the hook is not configured or the log does not exist. The runner never reads chat transcripts for approval; only the log.

### 5.12 Driver loop and documents

`docs/PROCESS.md` (one sentence per line) states: principles (mechanical before judgment; budgets are targets; spend definition), the round (branch, worktree, folder contents), the runner (commands, exit codes, re-entry, fence), the driver loop, agents (fresh per run, restrictions, how results are saved and costs recorded), failure and dispute rules, checkpoints and owner words, spec and code rules (declared paths, freeze, refactor cap, errata), landing and the merge attempt, the spec manifest and the edit rule, testing tiers, this machine's specifics (`py -3.13`, `agentExecutable`, `core.longpaths`).

`INDEX.md` routes aliases to paths: process, config, runner, schemas, prose, rounds, index, owner log, hooks, agents, skill, suite, fixtures, spec manifest.

`.claude/skills/shackles-round/SKILL.md`: the driver's checklist: render CHAT-TO-PLAN, settle the plan in chat, write `PLAN.json`, `start`, then loop `next` → spawn `shackles-producer` or `shackles-gate` with the prompt file verbatim → save the final message to `result_file` → `record` with `--tokens`/`--agent`/`--spawns`; what to do on exit 10; never do a gate's job.

### 5.13 Agent invocation (`agents.py`)

Interactive driver (the primary mode here): `next` prints `agent_type` (`shackles-gate` or `shackles-producer`), `model` and `effort`; the driver spawns the Agent tool with that type, the prompt file's content as the prompt, and records the reported token total. The two agent definitions carry `tools: Read, Grep, Glob` (gate) and `disallowedTools: Bash(git commit:*), Bash(git push:*), Bash(git tag:*), Bash(git reset:*), Bash(git merge:*)` (producer); the implementer verifies both keys are honoured by spawning one of each on a scratch task.

Headless (`run --until ...` and `systemtest`): `agentCommand` with substitutions, `agentExecutable` from `runner.yaml` (on this machine set to the absolute `claude.exe` path), `--json-schema` carrying the RESULT or FINDINGS schema, env scrubbed of `scrubEnv`, cwd the round worktree, wall clock `maxRunWallClockHours`; stdout JSON's `result` is the message and `total_cost_usd` the cost; a crash, timeout or non-JSON result resets the tree and counts an infrastructure error, up to `infraRetries`.

## 6. Implementation order and acceptance

One agent, one branch (`claude/build`), commits per milestone, never touching `main`. Each milestone ends with the whole suite green (`py -3.13 -m pytest -q harness/tests`).

M1 Foundations. Layout, `.gitignore`, root `AGENTS.md`/`CLAUDE.md`, `runner.yaml`, `config.py` with `DEFAULTS`, `render.py`, `artifacts.py` + `schemas.json`, `specwatch.py`, `owner_log_hook.py`, `.claude/settings.json`, agent definitions, `cli.py` with `lint`, `prompt`, `spec`, `agents`, `--version`. Acceptance: `lint` runs clean on the real spec except the one placeholder warning of §8; `prompt --step X` dry-renders all 16 steps; manifest tests pass, including the test of the test; hook verified by piping a JSON payload into the script from PowerShell and by one real prompt in a session.

M2 Round core in `--no-branch` mode. `round.py`, `checks.py`, `ledger.py` (all sources), stub agent, fixtures, `start/next/record/status/spend/check/abandon`. Acceptance: a full round with gates off and with gates on through the stub; every result status and verdict path; disputes and settlement; out-of-band edits and errata; overrides; disabled gates; failure and round limits; hard stop; spec-edit loudness; judgment-file checks; owner-word parsing; checkpoint resume; idempotent `record`; dirty-tree recovery.

M3 Concurrency. `gitops.py` claim/worktrees/fence, `landing.py`, merge attempt, `sync_main`, preconditions, overlap warning, `prune`. Acceptance: the summary's assertion list in §7.2 plus the merge-attempt convergence test.

M4 Headless and system tests. `agents.py`, `run`, `systemtest` with fixtures and reports, replay fixture support. Acceptance: `run --until done` with the stub as `agentExecutable`; `systemtest --dry-run` builds the temp repo and prints the actions without spawning.

M5 Documents and hand-off. `docs/PROCESS.md`, `INDEX.md`, the skill, `runner.yaml` pinned for this machine, the two spec edits of §8 applied and reported with diffs, `spec ack --note "bootstrap"`, final `lint`, suite timing recorded in `PROCESS.md`. The final report to the owner lists: every spec edit as a diff, every interpretation of §3 that a real run could contradict, and the commands for the real-agent tiers.

## 7. Test strategy

### 7.1 Principles and fixtures

Partial integration, no mocks of git, every test in a throwaway repo under `tmp_path`, hermetic git env (`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed identity), `sys.executable` for every runner and stub invocation, files written with `newline="\n"`. Fixtures: `Repo` (temp repo holding a copy of `spec.yaml` and its files, `runner.yaml` with `agentExecutable` pointed at the stub, the runner package, a toy project `toy/src`, `toy/tests`, generated `.gitignore`), `Repo.add_origin()` (bare, absolute path), `Repo.clone()`, `Repo.view(worktree)`, `Origin` (truth via `git -C origin.git`; `install_reject_hook(pattern, n|all)`, `install_move_and_reject_once_hook()`, both verified to run on this machine), `Repo.play(until=STEP, modes={...})` driving `next`/stub/`record` in-process so a whole round runs in seconds, and `Repo.cli(*args)` for the commands under test as subprocesses. The stub agent parses the four contract lines and switches on `STUB_MODE=pass|fail|dispute|needs_owner|upstream|blocked|garbage|edit_spec|commit|rewrite_judgment_file|slow`, `STUB_FENCE`, `STUB_ARCHIVE`, `STUB_LOG`. Budget: suite under 4 minutes on this machine; tests that spawn subprocess git in loops are marked `slow` and kept under 40% of the total.

### 7.2 What is asserted

- Rendering: every namespace; include depth and cycles; unresolved markers; value formatting per I10; prompts rendered from `prose_commit` not the tree (change prose mid-round, prompt unchanged); the four contract lines present in every prompt; `GATE-PROSE` embedding and the disabled note; prompt-size shrink.
- Spec robustness (the owner's constraint, tested directly): rename a placeholder in a prose copy → prompt renders with a marker and `lint` names it; delete an include file → `start` refuses with the file named; add a `NEW-STEP-OVERVIEW.txt` → `lint` warns, rounds unaffected; change `project.yaml` values → prompts and ledger follow without code changes; remove a `project.yaml` key → default used and `lint` warns; change `roundPaths` names → files land under the new names; change `NNNN` width → ids re-pad.
- Spec manifest: clean tree passes; changed content, added, removed, and `spec.yaml` list change each reported exactly; CRLF vs LF equal; `ack` rewrites and appends; the runner raises `spec-changed` at `next` and at landing; a round's own edit raises `spec-edits` before LANDING even when delegated; approve acks and commits. The test of the test: run the real `test_spec_files_match_manifest` function against a mutated temp copy (fixture parameter `spec_root`) and assert it fails naming the file and the ack command, and passes on an untouched copy; assert the test is collected (`pytest --collect-only` contains it).
- State machine: every transition in §5.6 with the stub; `record` guards (exit 2, nothing written); garbage result counts an infrastructure error and re-runs the same attempt; disputes, settlement, rejection of disputing a settled id; carried findings pruned when fixed; disabled and overridden gates; checkpoints and every resume word; approval only after `presented_at`; owner-log slice from `min(...)`; delegation through STEP; `maxRoundAttempts` refusal; out-of-band plan and spec edits, errata not counted; UPSTREAM resets; BLOCKED counts; NEEDS-OWNER with the gate disabled goes to the owner; M0-M6, S1, S2 with exact ids and messages; tests archived by `git mv`; judgment files created and checked.
- Ledger: each source and bucket; living charge with cap, base and test costs on a constructed diff (numbers computed by hand in the test); plan and spec word charges as net deltas; hard stop once; time frozen after finish; `spend --project` including a live sibling; `index.jsonl` fields.
- Concurrency (the summary's list, kept): claim wins and loses (`!` and `=` via a narrowed fetch refspec), nothing created on a lost race (no folder anywhere, no commit, one local branch, clean tree), bounded claim with reject-all (exactly `round/0001..0005` logged), explicit branch pushes once, `worktree add` failure leaves the claim, id sourcing ignores `round/0003-x` and tags, worktree operation (owner log from the main checkout, `--root` commands, push from the worktree), landing after a sibling moved main (`check` merges only; `run --until done` leaves `origin/main == local main == round tip` with both rounds' files and one living entry equal to this round's diff), rejected main push then acceptance (`attempts[LANDING] == 1`), reject-all leaves state at LANDING and a rerun lands, conflict yields an L1 finding and attempt 2, fence stops a second runner, post-round sync true/idempotent/false.
- Merge attempt: a conflicting sibling; after L1 the next `next` leaves the tree merging with markers in exactly the conflicted file; the stub resolves it; `record` produces a two-parent commit; M1/M2 pass against the auto-merged tree; a resolution that also edits an unconflicted frozen test fails M2; `run --until done` then lands with both rounds' content; UPSTREAM during a merge attempt aborts the merge and leaves a clean tree.
- Preconditions and prune: missing `.gitignore` entry refuses `start`; `main` checked out without origin refuses; overlap warning text; `prune` output and `--apply`.
- Headless: `run --until done` through the stub as executable; stub log shows argv with `--tools`/`--disallowedTools`, no scrubbed env keys, the schema flag; fenced output unwrapped; crash retried `infraRetries` times then `infra` checkpoint; wall-clock timeout kills the process tree (a `slow` stub mode that sleeps).
- Windows specifics: paths POSIX in state; CRLF-agnostic hashing; `taskkill` path exercised; `py -3.13` in `suiteCommand`.
- Replays: a fixture directory of recorded `RESULTS/` and artifacts from a real run drives the runner through `STUB_MODE=replay` and asserts the same state transitions; recorded once the first real run exists (§7.3), asserted thereafter.

### 7.3 Real-agent testing: a cheaper and more comprehensive loop than one end-to-end run

The owner's plan (a tiny throwaway task end to end, gates off then on) is kept as tier T2 but preceded by a tier that costs a tenth as much and covers more, and followed by free replays.

T0, free: the stub suite above. It proves the mechanics; it cannot prove that a real agent understands a prompt.

T1, per-step isolation, ~$1-3 per run on `project.systemTestAgent` (medium): `run.py systemtest --step STEP --fixture NAME [--manual]`. The command builds a temp clone with a local bare origin, installs the toy project and the fixture round folder (`harness/tests/fixtures/rounds/<NAME>/`: a real `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`/`SPEC.md`, `STATE.json` positioned at STEP, HISTORY), runs `next`, spawns the real agent headless (or, with `--manual`, prints the action for the driver to spawn with the Agent tool and waits for the result file), runs `record`, then checks `fixture.yaml` expectations (`expect.status`, `expect.verdict`, `expect.finding_quote_contains`, `expect.files_exist`, `expect.no_files_outside`) and prints cost and duration. Fixtures ship for every producer step (clean inputs, expect DONE and a valid artifact) and for every gate twice: a clean artifact (expect PASS) and a planted-defect artifact (a contradictory `SPEC.md`, an implementation with an off-spec extra, a suite selection archiving a needed test, a postmortem with an incomplete trace; expect FAIL with a quote containing the planted text). That last pair is the owner's "gate effectiveness" run, cheaply and repeatably. `systemtest --changed` runs only the fixtures of steps whose prose the spec manifest reports changed, so a prose edit is validated for a few dollars the same day.

T2, end to end on the toy project in a temp clone: `run.py systemtest --e2e --gates off` then `--gates on` (the temp copy of `project.yaml` is toggled; the real one is never written), with checkpoints answered by a scripted owner log (`--owner-words auto` appends approve lines) or by the driver (`--manual`). Cost ~$10-25 per pass on `systemTestAgent`. Nothing lands on the real `main`; the temp origin is the only origin.

T3, the owner's real run on the harness itself, only after T1 and T2 are green; its `RESULTS/` and artifacts are copied into `harness/tests/fixtures/replays/` so the runner's handling of real messages is asserted forever at zero cost.

Why this is cheaper and more comprehensive: per-step runs exercise every step, every result status and every gate verdict with known inputs, in parallel, for the price of one or two steps of an end-to-end round; an end-to-end run exercises one path once and its failures are hard to attribute. It also directly measures what the sibling's rounds could not: whether a gate fails a planted defect, whether a producer writes only where declared, and whether the prompt tail is followed.

## 8. Spec files needing edits: the exact minimal diffs

One genuine defect: two prose files reference a `project.yaml` key that does not exist. Without the edit the prompt reads `Assume a cost of $«unresolved: project.ownerReviewCostPerWord» per word`. The runner tolerates it, but the sentence is false to the agent. The recommended fix is in the prose, because `project.yaml` deliberately splits the cost into `planCostPerWord` and `specCostPerWord`:

```diff
--- harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
```

```diff
--- harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```

The alternative (adding `ownerReviewCostPerWord: 0.1` to `project.yaml`) is rejected because it duplicates a value the owner already split. Both edits are applied in M5, acked in the manifest with note `bootstrap: placeholder rename`, and reported to the owner as the diffs above. No gate language is edited: gate strictness is measured first by T1's planted-defect and clean pairs; if clean artifacts fail on wording alone, the report proposes the smallest relaxation with a diff rather than pre-empting it.

No other spec file needs a change. `harness/AGENTS.md` references `INDEX.md` and `docs/PROCESS.md`, which M5 creates.

## 9. Risks and open questions, with recommended resolutions

1. Hook execution on Windows (shell quoting, `py` on PATH inside the hook shell). Resolution: the command is the bare `py -3.13 harness/src/owner_log_hook.py`; M1 verifies it with one real session prompt; fallback is the absolute Python path in `settings.json`. `lint` reports a missing log as the first thing to fix.
2. `claude.exe` not on PATH; `--system-prompt-file` hidden; no `--max-turns`. Resolution: `agentExecutable` set to the absolute path in `runner.yaml`; M4 smoke-tests one headless call with a 60 KB prompt file (command-line limits forbid passing prompts inline); turns are advisory (I13). If `--system-prompt-file` is rejected, `--append-system-prompt-file` is the fallback, tried automatically once and recorded in HISTORY.
3. The Agent tool takes a prompt, not a system prompt, and cannot cap budget. Resolution: accepted; the prompt file is the whole instruction; the driver records tokens; `BUDGET_USD` in the prompt is the target, as the prose already says budgets are.
4. Gates are read-only and cannot write `RESULT_FILE`. Resolution: the contract says so and the driver saves the message (§5.4); `record` accepts raw text.
5. Suite speed on Windows (subprocess git is slow). Resolution: in-process `play()` for most tests, subprocess CLI only where the CLI is the subject, `slow` marker, a 4-minute budget checked in M5 and written into `PROCESS.md`.
6. Interpretation I3 (checkpoint placement) and I5 (`maxRoundAttempts`) may not match the owner's intent. Resolution: both live in `runner.yaml`/`DEFAULTS`, are named in the hand-off report, and change without touching spec files.
7. The owner may change a `roundPaths` or `gates` key name. Resolution: names are read from `project.yaml`, defaults cover absence, `lint` reports drift; nothing is hardcoded but the `NNNN` token rule.
8. Two live rounds declaring the same paths. Resolution: the overlap warning at `start` and at spec PASS, and the converging merge attempt; not prevented, by design (I3 of the summary).
9. Driver cost double-counting when one session drives two rounds. Resolution: flat `driverUsdPerStep` is the default charge; measured driver cost is optional (phase 2) and keyed by session and round cursor; the postmortem sees both.
10. Long paths on Windows in nested worktrees. Resolution: `worktreeDir` stays `.worktrees`, `core.longpaths` warning at `start`.
11. Living charge could penalise the test suite the bootstrap writes. Resolution: the bootstrap is not a round and is uncharged; later rounds pay for what they add, as the owner intends.
12. Should checkpoints or the step table move into `project.yaml`? Recommendation: no, keep them in `runner.yaml`; offer the four-line `project.yaml` addition in the report and let the owner decide.
13. The `override` word could match ordinary conversation. Resolution: it requires a step or gate name (or `gates`/`checkpoints`) after it in the same message; the quote is logged; the driver confirms in chat.
14. Real-agent runs on the harness's own repo could damage it. Resolution: T1/T2 run in temp clones with a temp origin; T3 runs as the harness intends, on a round branch in a worktree, with `main` untouched until landing.
