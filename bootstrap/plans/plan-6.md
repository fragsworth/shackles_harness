# Plan 6: building `shackles_harness` from the owner's spec

Deliverable of one planner; written for one implementing agent (Python 3.13, PyYAML, pytest, git,
Windows 11 / PowerShell, `py -3.13`). Everything the runner does mechanically is defined here; the
owner's spec files supply judgment prose only. Where this plan and a spec file disagree on a
*mechanical* fact, this plan is wrong and section 21 (spec edits) or section 23 (open questions) is
where that goes; where they disagree on *judgment wording*, the spec wins and nothing in the code
should care.

## 1. How this plan was developed

1. Read every file in the worktree: `spec.yaml`, `harness/AGENTS.md`, `project.yaml`,
   `subAgents.yaml`, all 18 locked prose files, `bootstrap/vision-harness-round-concurrency.md`, and
   the git history (3 commits). The second commit is instructive: the owner changed AGENTS.md's
   judgment-call wording and dropped "never work around it" from COMMON-OVERVIEW. Pure wording
   changes with zero mechanical consequence are the normal kind of spec edit; the build must shrug
   at them and the drift test must still surface them.
2. Checked ten specific points against the original `vision_harness` (read-only): `run.py`'s
   renderer, `next`/`record`/`landing`/`sync_main`, `claim_round`, `validate`, `schemas.json`, the
   process prose (`COMMON-PROCESS`, `COMMON-GATE-PROCESS`, a `*-PROCESS` pair), `project.json`
   (agent command, tool flags, env scrub), the owner-log hook and `.claude/settings.json`, the test
   fixtures (`Repo`/`Origin`/hooks/`stub_agent`), one real rendered gate prompt from round 005, and
   round 005's postmortem (the recorded failures: non-converging conflict path, runner/config skew,
   phantom approval from the owner-log slice, gates unable to write their result file, hand-typed
   costs, freeze rules blocking in-round fixes). Nothing is imported wholesale; what is adopted and
   what is changed is stated per item in section 14.
3. Established machine facts by running commands (nothing on screen, nothing outside the scratchpad):
   `py -3.13` = Python 3.13.2 with PyYAML 6.0.3 and pytest 9.1.1; `git` = 2.45.2.windows.1, the conda
   env's MinGW build, no bash on PATH; the Claude Code CLI is 2.1.266 at
   `%APPDATA%\Claude\claude-code\2.1.266\claude.exe`, **not on PATH**, and its `--help` confirms
   `--print`, `--output-format json`, `--system-prompt-file`, `--model`, `--effort`,
   `--max-budget-usd`, `--json-schema`, `--tools`, `--allowedTools`, `--disallowedTools`,
   `--permission-mode`, `--no-session-persistence`, `--bare`, `--setting-sources`, and **no
   `--max-turns`**; the repo has `origin = https://github.com/fragsworth/shackles_harness.git`, local
   `main` at cf065eb, and the main checkout is parked on `claude/bootstrap` (so `main` is not
   checked out anywhere). PyYAML parses `project.yaml` and `subAgents.yaml` as expected (ints stay
   ints, `gates` is a dict of ints, `roundPaths` nests).
4. Ran an empirical probe in the scratchpad (a temp bare origin plus a clone) for the four facts the
   concurrency design rests on: `git push --porcelain --force-with-lease=refs/heads/X:` prints
   `*` for a newly created ref, `=` for up-to-date, `!` for a hook-declined push, exactly as the
   summary says; **origin `update` hooks run on this git** with `#!/bin/sh`, with
   `#!/usr/bin/env python`, and with an absolute-interpreter shebang; `git worktree add` and
   `rev-parse --git-common-dir` behave as the `main_root` helper assumes; and `shutil.rmtree` of a
   git repo raises `PermissionError` on Windows (read-only objects) unless an `onexc` handler
   chmods first. The tests in section 19 are designed around these results.
5. Enumerated every `{{ token }}` in the locked prose (section 8.2) and found the one unresolvable
   token: `{{ project.ownerReviewCostPerWord }}` in two files, while `project.yaml` defines
   `planCostPerWord` and `specCostPerWord`. That is the only spec edit this plan proposes
   (section 21).
6. Designed, then re-read the hard constraints and the vision_harness postmortem against the design,
   and wrote the risks (section 23) as the residue.

## 2. Principles that decide everything below

- **The spec owns judgment; the runner owns mechanics.** Every machine-parsed word (statuses,
  verdicts, finding fields, file names, the `STEP:`/`ARTIFACT:` lines) is emitted by runner code
  into the `{{ plumbing.PROCESS-INSTRUCTIONS }}` block and parsed by runner code. The runner never
  greps a locked prose file for a phrase. The prose is text with tokens, nothing more.
- **Structure from data, never from wording.** The runner learns step names from its own process
  graph (`src/process.yaml`), gate on/off from `project.yaml`'s `gates`, agents from
  `subAgents.yaml`, paths from `project.yaml`, and prompt text from `locked_prose/<STEP>-*.txt` by
  file name. Tests tie the graph to the spec's *data* (gate keys and order, prose file names,
  agent keys, token names) so a structural spec change fails a test and a wording change fails
  only the drift test.
- **Unknown is a warning, never a crash.** Unknown config keys are ignored; missing keys take
  documented defaults with a `doctor` warning; an unresolvable prompt token renders as a visible
  `[unresolved: key]` marker and is reported; a new prose file that the graph does not know is
  reported, not loaded.
- **Everything the runner knows is in files committed after every step.** No daemon, no database,
  no lock server; git is the lock manager (section 14).
- **Agents never commit, push, or contact the owner; gates write nothing.** Each attempt's final
  message is saved by whoever spawned the agent (the driver session, or the headless loop).
- **Windows first.** `sys.executable`-free commands (`py -3.13` is the interpreter name), UTF-8
  everywhere, no `sh` dependence, list-form commands, `onexc` rmtree, process-tree kill on timeout.

## 3. Repository layout after the build

```
spec.yaml                          owner's (unchanged)
bootstrap/                         owner's (unchanged; plans live here)
.gitignore                         + .worktrees/  harness/OWNER.log  harness/runner.local.yaml  __pycache__/  .pytest_cache/
.claude/settings.json              UserPromptSubmit hook -> harness/src/owner_log_hook.py
.claude/agents/shackles-producer.md, shackles-gate.md   sub-agent definitions for the session driver
README.md                          what it is, quick start, the four test levels
harness/
  AGENTS.md project.yaml subAgents.yaml locked_prose/   owner's spec (one flagged edit, section 21)
  INDEX.md                         routing: alias -> canonical path
  runner.yaml                      runner-owned plumbing config (committed; section 5.3)
  docs/PROCESS.md                  the normative rules, one sentence per line
  src/                             the runner (living)
    run.py                         CLI entry: argparse, dispatch, exit codes
    config.py process.py process.yaml gitops.py render.py contract.py schemas.py ledger.py
    owner.py round.py landing.py agent.py specdrift.py doctor.py owner_log_hook.py
    (contract.py = the plumbing blocks of 8.3/8.4 and the STATUSES/VERDICTS constants)
  tests/                           pytest suite (living); conftest.py, stub_agent.py, fixtures/
  archives/
    spec-baseline/                 MANIFEST.json + files/<spec paths>   (the drift baseline; not living)
    rounds/index.jsonl             one line per finished or abandoned round (created by the first)
    rounds/NNNN/                   round folders, exactly as project.yaml roundPaths says
```

Path conventions, fixed here so nobody decides them twice: the **harness root** is the directory
holding `project.yaml` (`harness/`); the **repo root** is `git rev-parse --show-toplevel`. Every
path in `project.yaml`, in every artifact (`SPEC.json` `implPaths`/`testPaths`, `SUITE.json`),
in every prompt, and in every finding is **relative to the harness root**, because `AGENTS.md` is
titled `# harness/` and says `src/`, `docs/`, `tests/` are living and `roundPaths` are "from the
harness root". Agents are spawned with cwd = harness root. The runner alone converts to
repo-relative paths for git (`harness/` + path, normalized, refused if it escapes the repo).
Round ids are four digits (`0001`), from `roundPaths.folder`'s `NNNN`.

## 4. The process graph (`src/process.yaml`)

The graph is runner data derived from the spec once and re-derived whenever the drift test fires.

| # | step | kind | notes |
|---|---|---|---|
| 1 | CHAT-TO-PLAN | producer, `inChat: true` | the driver is the agent; artifact `plan` (PLAN.json), schema PLAN; never spawned |
| 2 | CHAT-TO-PLAN-GATE | mechanical `approval` | owner word; `checkpoint: approval` |
| 3 | PLAN-AGENTS | producer | artifact `agentsPlan`, schema AGENTS_PLAN; skippable by `override` (falls back to `defaultShares` and `maxAgent`) |
| 4 | PLAN-AGENTS-GATE | gate | |
| 5 | PLAN-TO-SPEC | producer | artifacts `spec` + `specProse`, schema SPEC |
| 6 | PLAN-TO-SPEC-GATE | gate | `checkpointAfter: spec-review` |
| 7 | SPEC-TO-TESTS | producer, code | may change `testPaths` |
| 8 | SPEC-TO-TESTS-GATE | gate | `freezesTests: true` on PASS |
| 9 | SPEC-TO-IMPLEMENTATION | producer, code | may change `implPaths`; verify must pass |
| 10 | SPEC-TO-IMPLEMENTATION-GATE | gate | artifact = diff file |
| 11 | TESTS-TO-SUITE | producer | artifact `suite`, schema SUITE |
| 12 | TESTS-TO-SUITE-GATE | gate | `onPass: archiveTests` |
| 13 | CLEANUP | producer, code | `implPaths`; `mechanicalGateOnly: true`; `checkpointAfter: pre-landing` |
| 14 | LANDING | mechanical `landing` | section 14.4 |
| 15 | POSTMORTEM | producer | artifact `postmortem` (POSTMORTEM.md); gate follows |
| 16 | POSTMORTEM-GATE | gate | round finishes on PASS (or when disabled) |

Rules: a gate whose `project.yaml` `gates[<name>]` is `0`, or that the owner said `override` for,
is skipped with a HISTORY line "gate skipped (disabled|override)"; mechanical checks (section 11.3)
still run. A producer named in `override` is skipped with its defaults. CHAT-TO-PLAN, its gate,
and LANDING are not overridable. Checkpoints happen only when the round is not delegated through
that step. The graph loader validates: unique names, `-GATE` suffix iff kind gate, each gate
immediately follows its producer, kinds in the allowed set.

Consistency tests (section 19.4): every gate in the graph is a key of `project.yaml` `gates` and
appears there in the same relative order; every key of `gates` is in the graph; every spawned
producer has `locked_prose/<NAME>-OVERVIEW.txt`; every gate has `locked_prose/<NAME>.txt`; every
`locked_prose/*.txt` is either `COMMON-*` or named by a graph step (else "unknown prose file"
fails the test so the graph gets updated); `maxAgent`, `gateAgent`, `systemTestAgent` are keys of
`subAgents.yaml` `agents`; `subAgentsFile` resolves.

## 5. Configuration model

### 5.1 `project.yaml` (owner's) is read with defaults and tolerance

`config.load_project(harness_root)` returns a dict: `PROJECT_DEFAULTS` (every key the runner reads,
with the value currently in the file as its default) updated by the YAML. Unknown keys are kept
(the renderer exposes them as `project.*`). Type mismatches and missing keys become `doctor`
warnings, never exceptions, except a structurally unusable file (not a mapping) which is an error.
`gates` is normalized to `{name: bool}`. `roundPaths` is normalized to absolute-within-repo
paths with `NNNN` substituted per round. `livingSourcePaths`, `lockedProsePath`, `archivesPath`
are harness-relative. `subAgentsFile` is loaded the same way into `project["agents"]` (a dict
keyed by rung: `max`, `high`, `medium`, `low`, each with `name`, `model`, `effort`, prices,
`spawnCost`); missing price keys default to 0 with a warning.

### 5.2 Keys the runner reads and what each does

`shackles` (vision text), `budget` (project target; `project.remaining` = budget − tally),
`hardStopBudgetMultiple` (round stops at multiple × quote), `lostValuePerHour` (time cost),
`ownerHourlyRate` (rendered only), `costToWaitForOwner` (charged per checkpoint), `planCostPerWord`
/ `specCostPerWord` (charged at the approval / spec-review checkpoints × words of PLAN text /
SPEC.md), living-token keys (section 13.4), `testBaseCost`, `tokenBytes`, `maxRefactorOverhead`
(rendered; not enforced, the spec says it limits scope), `gates`, `defaultShares` (shares before
PLAN-AGENTS), paths, `roundPaths`, `maxSimultaneousSubAgentsPerRound` (validates AGENTS-PLAN),
`maxRoundAttempts` (how many failure-limit resumes a round gets; comment: "round retries"),
`maxFailuresBeforeStop` (gate/mechanical FAILs across the round before a `failure-limit`
checkpoint; approval resets it), `maxTurnsPerRun` (rendered as advisory; the CLI has no turn cap),
`maxRunWallClockHours` (subprocess timeout for one headless run), `verifyTimeoutSeconds`,
`gatesFraction`/`workFraction` (budget pies), `estOutputFraction` (pricing a bare token count),
`driverUsdPerStep` (charged per `record`), `subAgentsFile`, `maxAgent` (producer default),
`gateAgent` (all gates), `systemTestAgent` (real-agent tests, section 20).

### 5.3 `harness/runner.yaml` (runner-owned, committed) and `runner.local.yaml` (gitignored)

Defaults live in `config.RUNNER_DEFAULTS`; `runner.yaml` overrides; `runner.local.yaml` overrides
again (machine paths only). Keys: `mainBranch: main`, `worktreeDir: .worktrees`,
`branchPrefix: round/`, `pushAttempts: 5`, `suiteCommand: ["py", "-3.13", "-m", "pytest", "tests", "-q", "-m", "not real"]`
(cwd = harness root), `suiteTimeoutSeconds: 1800`, `agentCommand` (section 15), `gateToolFlags`,
`producerToolFlags`, `scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]`, `runBudgetMultiple: 2`
(hard CLI cap = step budget × this; budgets are targets), `maxPromptBytes: 200000`,
`gitIdentity: {name: shackles-runner, email: runner@shackles.local}`, `ownerWords` (section 12.1),
`envelopePrefixes` (hook filter), `claudeSearchPaths` (section 15.2), `historyNoteChars: 2000`.
Commands are list-form (no shell); a string is accepted and run through `cmd.exe` on Windows /
`sh` elsewhere, documented as the less portable form.

## 6. Round files and state

The round folder is exactly `project.yaml` `roundPaths`: `PLAN.json`, `AGENTS-PLAN.json`,
`SPEC.json`, `SPEC.md`, `SUITE.json`, `POSTMORTEM.md`, `STATE.json`, `HISTORY.md`, `OWNER.log`,
`PROMPTS/STEP-attempt.txt` (plus `PROMPTS/STEP-attempt.diff` for code-step gates: the runner-made
diff the gate judges, so gates need no git), `RESULTS/STEP-attempt.json`,
`FINDINGS/STEP-attempt.json`, `tests-archive/`, `DEFINED_JUDGMENT_CALLS.md`,
`UNDEFINED_JUDGMENT_CALLS.md` (both created empty-with-header at `start`), and `ERRATA.md`
(append-only, unhashed, section 11.6). If the owner renames a key in `roundPaths`, the runner
follows; the names above are defaults.

`STATE.json`, validated on every save. Required: `round` int, `branch`, `created_at` (UTC
`%Y-%m-%dT%H:%M:%SZ`, all timestamps), `status` ∈ active|checkpoint|finished|abandoned, `step`,
`attempts` {step: int}, `failures` {step: int}, `infra_errors` {step: int}, `step_commits` {step:
sha at PASS}, `step_starts` {step: sha when first rendered}, `inputs_hash` {PLAN, SPEC},
`budget_usd`, `spend` {entries[], agent_usd, driver_usd, owner_usd, living_usd},
`base_commit`, `prose_commit` (= base commit; prose is `git show`n from it), `approval` {word,
quote, at, source} | null, `delegated` null|"all"|"through:STEP", `overrides` [], `checkpoint`
{reason, step, question, artifact, at} | null, `pending_question`, `last_findings` {producer:
path}, `carried_findings` [], `deferred_findings` [], `findings_ledger` {id: {upheld_count,
settled}}, `mech_ok` {gate: producer attempt checked}, `tests_frozen_at` (sha at
SPEC-TO-TESTS-GATE PASS; M2 applies from then on), `resumes` int, `hard_stop_raised` bool,
`owner_since`, `landed_at`, `abandoned_at`, `main_before`, `runner_commit` (the commit whose
`run.py` last wrote the state, for skew diagnosis), `judgment_calls` {defined, undefined} (line
counts). No lock, lease, pid, or owner field exists anywhere.

`HISTORY.md` is append-only: one `## STEP attempt N (STATUS|VERDICT) <time>` entry per attempt with
the agent's notes (truncated to `historyNoteChars`), one line per mechanical finding, checkpoint,
resume, skip, infra error, spend entry summary. `index.jsonl` gets one line per finished or
abandoned round: `{id, quote_usd, spend, attempts, failures, outcome, prose_commit,
landed_at|abandoned_at, judgment_calls}`.

## 7. Round lifecycle

```
start (claim id, worktree, PLAN.json, STATE) -> CHAT-TO-PLAN-GATE (approval)
  -> [PLAN-AGENTS -> gate] -> [PLAN-TO-SPEC -> gate] -> checkpoint spec-review
  -> [SPEC-TO-TESTS -> gate] -> [SPEC-TO-IMPLEMENTATION -> gate]
  -> [TESTS-TO-SUITE -> gate] -> [CLEANUP -> mechanical checks] -> checkpoint pre-landing
  -> LANDING -> [POSTMORTEM -> gate] -> finished (sync main)
status: active <-> checkpoint; either -> abandoned; active -> finished
```

Dynamic checkpoints: `approval`, `spec-review`, `pre-landing`, `failure-limit`, `round-limit`,
`hard-stop`, `needs-owner`, `blocked`, `upstream-plan` (UPSTREAM targeting CHAT-TO-PLAN),
`landing-conflict`, `landing-red` (verify or suite red after a hand merge, section 14.5). A
checkpoint returns exit code 10 with `{kind: checkpoint, reason, step, question, artifact, spend}`
and the driver waits in chat (or the headless loop exits).

## 8. Prompt rendering

### 8.1 Engine

`render.render(text, ctx)`: tokens `{{ a.b-c }}` (regex `\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}`).
`prose.NAME` → `locked_prose/NAME.txt` at `prose_commit` (via `git show`), rendered recursively,
depth ≤ 5, cycle → marker. `plumbing.X` → runner-generated block (8.3, 8.4). Anything else →
dotted lookup in the context; strings verbatim; floats `0.25`-style; lists and dicts as compact
JSON; missing → `[unresolved: key]` plus a warning collected in the render result and written to
HISTORY and to the `next` action (`warnings: [...]`). `AGENTS.md` is never rendered (it mentions a
token by name to explain it); agents read it from disk.

### 8.2 Namespace

Every token the prose uses today resolves as follows; new `project.*` tokens resolve
automatically against the loaded config, so the owner can add config keys and reference them
without any code change.

- `project.*`: every key of the loaded `project.yaml` plus computed `remaining`, `spent`, `agents`
  (roster), `harnessRoot`. Today's prose uses `shackles budget remaining lostValuePerHour
  livingFileCostPerToken livingFileTokenCap livingFileCostPerTokenOverCap livingFileBaseCost
  testBaseCost livingSourcePaths tokenBytes maxRefactorOverhead gates ownerReviewCostPerWord`.
  The last is not a config key (section 21); until the spec edit lands it renders as
  `[unresolved: project.ownerReviewCostPerWord]`.
- `round.*`: `id` (NNNN), `folder`, `base_commit`, `plan` (PLAN.json rendered as text: summary,
  Scope/Validation/Non-goals/Assumptions bullets, quote), `budget`, `spend`, `remaining`,
  `budgets` (per step), `history` (last 5 index lines as quote-vs-actual), `todos` (TODO lines
  of every landed round since the last plan that triaged them; section 17), `judgment_calls`
  (both files' contents), `owner_log` (the slice), `spec` (SPEC.json + SPEC.md text or "none yet"),
  `agents_plan`, `findings` (latest findings file for the producer + carried + deferred), `errata`.
- `step.*`: `name`, `attempt`, `budget`, `budget_cap`, `max_turns`, `retry_cost` (for a gate:
  its producer's work budget; for a producer: its own), `agent` (name/model/effort),
  `sub_agents` (allowed count), `tools` ("read-only"|"all"), `gate` (name or "none"),
  `gate_enabled`.
- `plumbing.PROCESS-INSTRUCTIONS`, `plumbing.GATE-PROSE`.

### 8.3 `plumbing.GATE-PROSE` (in producer prompts)

The producer's gate file (`<STEP>-GATE.txt`) rendered with these generic rules: `prose.*` includes
already present in the producer's own prompt (COMMON-PROJECT, COMMON-ROUND) are dropped, other
includes (COMMON-GATE) are expanded, `plumbing.PROCESS-INSTRUCTIONS` inside it renders as
`(gate mechanics omitted)`, all other tokens render normally. If the gate is disabled or overridden
this round: `(This gate is disabled this round. The runner's mechanical checks still apply.)`
followed by the text anyway (the standard is still the standard). If no gate file exists (a
mechanical gate, e.g. CHAT-TO-PLAN's): a one-line runner description from the graph.

### 8.4 `plumbing.PROCESS-INSTRUCTIONS` (generated by `contract.instructions(kind, ctx)`)

Producer block, in this order, each line generated from data:
```
PROCESS INSTRUCTIONS (mechanical; written and parsed by the runner; follow exactly).
STEP: <name>. ATTEMPT: <n>. ROUND: <NNNN>. ARTIFACT: <path or declared paths>. RESULT_FILE: <path>.
Working directory: <harness root>; paths are relative to it. Read AGENTS.md first; INDEX.md routes.
Inputs: <bullet list of paths: PLAN.json; AGENTS-PLAN.json; SPEC.json and SPEC.md; FINDINGS/<latest>; PROMPTS/<prev>.diff; ...>
You may create or change files only under: <declared paths>, and the round folder <folder>. Frozen (do not touch): <test paths, once frozen>.
Never run git commit, push, reset, checkout, clean, merge or rebase; the runner commits your work.
Budget for this run: $<budget> (a target; hard cap $<cap>). Turns: about <maxTurnsPerRun>. Sub-agents allowed: <k>.
Judgment calls: append one line per call to DEFINED_JUDGMENT_CALLS.md or UNDEFINED_JUDGMENT_CALLS.md in the round folder: `- <STEP> attempt <n>: <decision>; <why>`.
Findings to resolve (every id must appear in your resolutions as fixed, disputed or deferred; settled ids cannot be disputed): <json | none>
Previous attempt: <none | "your previous artifact is in place at ARTIFACT; revise it" | "your previous changes are in the working tree; fix them in place">
Artifact: <kind text: "write JSON validated against schema SPEC: {fields}" | "code under the declared paths; verify command `<verify>` must pass" | ...>
Checked mechanically before any gate: <list of check ids and one-line meanings>; a failure returns to you as a finding without spending a gate.
Final message: exactly one JSON object and nothing else:
{"status": "DONE" | "NEEDS-OWNER" | "UPSTREAM" | "BLOCKED", "notes": "...", "question": "<NEEDS-OWNER only>", "target": "<UPSTREAM only: an earlier producer step>", "resolutions": {"<id>": {"status": "fixed" | "disputed" | "deferred", "reason": "..."}}, "cost_usd": <optional>, "tokens": {<optional>}, "sub_agents": [<optional>]}
The runner saves it to RESULT_FILE; you do not write RESULT_FILE.
Then: DONE -> <gate name and whether enabled | "mechanical checks, then the next step">. NEEDS-OWNER -> the gate rules on the question (withdrawn: judged on your assumption; upheld: the round pauses and the owner's answer returns to you as a finding). UPSTREAM -> the round returns to the target step with your notes as a finding. BLOCKED -> the round pauses for the owner.
```
Gate block: same header; `You are read-only: read anything, write nothing, run nothing that
changes files.`; inputs (artifact or `PROMPTS/<step>-<n>.diff`, its inputs, the prior findings
file, the producer's final message at `RESULTS/<producer>-<n>.json`); `The producer's question,
if any: <...>`; `Already checked mechanically: <...>. Do not repeat them.`; `A FAIL costs
$<retry_cost> (the producer's retry) plus this gate again.`; the verdict contract
`{"verdict": "PASS"|"FAIL", "findings": [{"id": "F<n>", "quote", "reason", "suggestion",
"blocking": bool}], "rulings": {"<id>": {"status": "upheld"|"withdrawn", "quote"}},
"needs_owner": {"status": "upheld"|"withdrawn", "reason"}, "notes"}`; `Ids continue from F<max
prior>; verdict is FAIL exactly when a finding is blocking or needs_owner is upheld.`; `Then:
PASS -> ...; FAIL -> the producer runs again with your findings, then this gate again.`

The status and verdict words are runner constants (`contract.STATUSES`, `contract.VERDICTS`) that
happen to match the spec's prose today; a test asserts each word appears somewhere in the locked
prose so a rename by the owner fails a test (section 19.4) rather than silently diverging.

### 8.5 Prompt size guard

Before rendering a gate prompt the runner sums the prompt plus every input it lists; over
`maxPromptBytes` it raises mechanical finding `P1` ("artifact and inputs exceed one context;
narrow or split into sequential rounds") to the producer instead of spending the gate.

## 9. Artifact schemas (`schemas.py`; dicts, no jsonschema dependency; also emitted as JSON Schema for `--json-schema`)

- **PLAN** required: `round` int, `presented_at`, `quote_usd` number, `summary`, `scope[]`,
  `validation[]`, `non_goals[]`; optional `assumptions[]`, `todos {T1: {todo, status taken|deferred,
  reason, budget_usd if taken}}`, `owner_words` (verbatim approval text).
- **AGENTS_PLAN** required: `round`, `shares {work {STEP: fraction}, gates {STEP: fraction}}`
  (keys are graph steps; `work` over producers, `gates` keyed by the *producer's* name as
  `defaultShares` is; each sums to 1 ± 0.001); optional `agents {producer STEP: roster key}`,
  `subAgents {STEP: int ≤ maxSimultaneousSubAgentsPerRound}`, `notes`.
- **SPEC** required: `round`, `summary`, `verify` (string or list), `implPaths[]`, `testPaths[]`
  (harness-relative, disjoint by prefix, inside the repo), `nonGoals[]`; optional
  `verifyTimeoutSeconds`, `refactor [{what, budget_usd}]`, `testPlan`, `body` (default `SPEC.md`).
- **SUITE** required: `round`, `keep[]`, `archive[]`, `notes`; optional `raise_with_owner[]`.
- **RESULT** and **FINDINGS** as in 8.4; `FINDINGS` additionally enforces the FAIL-iff rule and
  unique ids; a `RESULT.target` must be an earlier producer.
- **STATE** as in section 6.
Validation errors are lists of `NAME: message` strings; artifact errors become mechanical finding
`S1` to the producer; result/verdict errors make `record` exit 2 with the list (nothing recorded;
the driver fixes the file and re-runs `record`).

## 10. CLI (`py -3.13 harness/src/run.py <cmd>`; global `--root DIR` = repo root or a round worktree, `--round N`)

| command | does | exit |
|---|---|---|
| `doctor [--probe-cli]` | environment and config report (section 18.4) | 0 ok/warnings, 1 errors |
| `brief` | prints the rendered CHAT-TO-PLAN prompt (project facts, history, TODOs) for the planning session | 0 |
| `start --plan F [--budget] [--approval approved\|delegated\|delegate-through:STEP] [--quote TEXT] [--base REF] [--branch NAME] [--no-branch]` | claim id, worktree, round folder, first commit + push; prints `{round, folder, branch, worktree}` | 0/1/2 |
| `next [--no-push]` | mechanical steps, then the next action JSON | 0 action/done, 10 checkpoint |
| `record --step S --attempt N --result F [--cost USD] [--tokens N --agent KEY]... [--no-push]` | validate, ledger, route, commit, push (fence) | 0, 2 usage/invalid, 1 |
| `run [--until checkpoint\|step\|done] [--no-push]` | headless loop next → agent → record | as next |
| `owner --say TEXT [--at TS]` | append an owner line to the main checkout's OWNER.log (hookless environments, tests) | 0 |
| `status [--verbose]`, `log [-n]`, `spend [--project]`, `cost` (living charge preview of the current diff) | read-only | 0 |
| `check` | current step's mechanical checks / landing check, nothing recorded | 0 pass, 3 fail |
| `render --step S [--attempt N] [--all] [--out DIR]` | render prompts without touching state (for prose work) | 0 |
| `abandon --reason R` | tag, index line, commit | 0 |
| `rounds [--prune]` | every round: id, status, step, spend, worktree; claimed-but-empty ids; `--prune` removes worktrees of finished/abandoned rounds | 0 |
| `clean --round N` | remove one finished round's worktree | 0 |
| `spec check\|diff\|accept [--note]` | drift baseline (section 16) | 0 clean, 3 drift |
| `selftest [--keep]` | full stub round in a temp repo (runs `tests/test_smoke.py`) | pytest's |
| `probe --step S [--agent KEY] [--seed clean\|defect] [--budget USD]` | one real agent on one canned step (section 20) | 0/1 |

Exit codes: 0 ok, 1 error, 2 usage or invalid input, 3 check failed / drift, 10 checkpoint. Every
command prints exactly one JSON object on stdout (human text goes to stderr), so the driver parses
stdout blindly. `sys.stdout.reconfigure(encoding="utf-8")` at startup.

## 11. `next` and `record`

### 11.1 `next`

1. `finished`/`abandoned` → `sync_main` → `{kind: done, main_synced}`.
2. Warn if `spec check` drifts (`warnings`), never block.
3. Out-of-band edit check: hash PLAN.json → changed: approval cleared, step ← CHAT-TO-PLAN-GATE,
   downstream counts reset; hash SPEC.json + SPEC.md → changed after PLAN-TO-SPEC-GATE: step ←
   SPEC-TO-TESTS, downstream reset. `ERRATA.md` is not hashed.
4. Dirty tree (`git status --porcelain`, ignored files excluded) → `checkout -- .`, `clean -fdq`
   (never `-x`), `infra_errors[step] += 1`, HISTORY line. If HEAD moved past the last runner commit
   (an agent committed): `git reset --soft <last>` first, HISTORY "agent commit undone" (`M0`).
5. Refresh the OWNER.log slice from the main checkout (`owner_since` = min(previous landed_at,
   plan `presented_at`), the round-005 fix).
6. `status == checkpoint` → scan words after `checkpoint.at` (section 12) → resume, or return the
   checkpoint (exit 10).
7. Loop: mechanical step → do it (approval / landing); checkpoint-after → raise unless delegated;
   gate disabled/overridden → skip; gate of a code producer → mechanical checks once per producer
   attempt (`mech_ok`); hard stop → checkpoint; else render the prompt (and the diff file for a
   code gate), write `step_starts`, save, commit (no push), return the action:
   `{round, step, kind, attempt, prompt_file, result_file, artifact, tools, budget_usd,
   budget_cap_usd, max_turns, agent, model, effort, sub_agents, spend, warnings}`.

### 11.2 `record`

Guards: `status == active`, `state.step == step`, `attempt == attempts[step] + 1` (exit 2 on any
mismatch: idempotency). Save the result to `RESULTS/`; validate; cost (13.1); driver charge; then
producer or gate routing; save; commit `round NNNN: STEP attempt N`; push = the fence (14.3);
finished/abandoned → `sync_main`.

Producer: apply resolutions (a `disputed` on a settled id is exit 2; `deferred` moves the finding
to `deferred_findings`, rendered to POSTMORTEM). `DONE` → for code steps run mechanical checks on
the *uncommitted* diff (11.3) before committing, findings → `fail_producer`; JSON artifacts →
schema (S1); CLEANUP → checks then advance; POSTMORTEM → `finished` + index line;
otherwise advance (PLAN-TO-SPEC additionally warns `X1` on overlap with live siblings, 14.6).
`NEEDS-OWNER` → `pending_question`, advance to the gate (a disabled gate cannot rule: the
question becomes a `needs-owner` checkpoint directly). `UPSTREAM` → target must be an earlier
producer; downstream reset; target CHAT-TO-PLAN → `upstream-plan` checkpoint; else finding `U1`
to the target. `BLOCKED` → finding `B1` and a `blocked` checkpoint.

Gate: rulings update `findings_ledger` (upheld twice = settled); findings file written; a
pending question with `needs_owner.upheld` → `needs-owner` checkpoint; `withdrawn` → finding `Q1`
("assume this answer") to the producer with the verdict's findings. `PASS` → `step_commits`,
non-blocking findings appended to `carried_findings`, `onPass` hooks (archive tests: `git mv` each
`archive` entry into `tests-archive/`; freeze tests: record `tests_frozen_at`), advance, then
`checkpointAfter` unless delegated. `FAIL` → `failures[producer] += 1`, step ← producer,
`limit_hit`.

### 11.3 Mechanical checks (ids are stable strings; each carries quote/reason/suggestion)

`S1` artifact fails schema · `M0` agent committed (undone, infra) · `M1` diff touches paths outside
the declared ones plus the round folder (computed from the uncommitted diff at `record`, so
merges from main never trip it) · `M2` diff touches frozen test paths after SPEC-TO-TESTS-GATE
passed (per attempt; the fix for a wrong test is UPSTREAM) · `M3` verify failed or timed out
(cwd = harness root) · `P1` prompt too large · `L1` landing merge conflict · `L2` landing verify
or suite red · `U1` upstream · `B1` blocked · `Q1` needs-owner withdrawn · `O1` owner's answer ·
`X1` path overlap with a live sibling (non-blocking, informational).

### 11.4 Limits

`limit_hit(producer)`: `sum(failures) >= maxFailuresBeforeStop` → `failure-limit` checkpoint
("approve to retry: resets the count; change PLAN/SPEC; or abandon"); on approval `resumes += 1`;
`resumes > maxRoundAttempts` → `round-limit` checkpoint whose only exits are `abandon` or an
out-of-band edit of PLAN/SPEC. Hard stop: any ledger entry pushing `total_usd` over
`hardStopBudgetMultiple × budget_usd` → `hard-stop` checkpoint once per round, and never while a
checkpoint is being raised.

### 11.5 Crash recovery

All writes go through `write()` (temp file + `os.replace`, retried 5× on `PermissionError` for
Windows AV locks). Every state change is committed. Re-running the command that crashed resumes:
`next` after a crashed render re-renders the same attempt; `record` after a crashed commit sees
the result already in `RESULTS/` and `attempts` unchanged and redoes the routing idempotently.

### 11.6 Errata

`ERRATA.md` in the round folder is append-only and unhashed. A producer that finds a defect in a
frozen input it may not change (a spec sentence, a plan item) records it there and proceeds on the
stated reading; the gate sees `round.errata`; POSTMORTEM reads it. This replaces vision_harness's
"hash everything, fix nothing in-round" trap without loosening the freeze.

## 12. Owner words, checkpoints, and the hook

### 12.1 Words (`runner.yaml` `ownerWords`, defaults)

Ordered regexes; the first that matches a line wins the line; the newest qualifying line after the
relevant timestamp wins: `abandon` `\babandon\b`; `delegate-through`
`\bdelegated?\s+through\s+([A-Z][A-Z0-9-]+)` (group must be a graph step); `delegated`
`\bdelegated?\b`; `approved` `\bapproved?\b`; `override` `\boverride\b` with every graph step or
gate name found in the line as `overrides`. Envelope-prefixed lines (`<task-notification`,
`<system-reminder`, `[SYSTEM NOTIFICATION`, ...) are ignored. Words are read only from the round's
OWNER.log slice and only after the plan's `presented_at` (approval) or the checkpoint's `at`.

### 12.2 Approval

`start --approval WORD --quote TEXT` records the driver's transcription of the owner's word; when
`harness/OWNER.log` exists the quote must match a line after `presented_at` or `start` exits 2.
Without `--approval`: if CHAT-TO-PLAN-GATE is enabled, `next` waits for the word in the log
(checkpoint `approval`); if disabled (today's config) `start` records
`{word: approved, source: gate-disabled}`, so a gates-off round runs with checkpoints unless
`--approval delegated` says otherwise.

### 12.3 The hook

`.claude/settings.json`: `{"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "py -3.13 harness/src/owner_log_hook.py"}]}]}}`.
The hook reads the JSON on stdin, ignores empty/envelope prompts, ignores everything when env
`SHACKLES_SUBAGENT` is set (the headless loop sets it, so sub-agent prompts never masquerade as
owner words), resolves the main checkout via `git rev-parse --git-common-dir` from `cwd` (so a
driver session opened inside a worktree still logs to the shared file), and appends
`<UTC>\t<message, backslash and newline escaped>` to `<main_root>/harness/OWNER.log`. `doctor`
verifies the hook is configured and the log path is gitignored. `owner --say` is the fallback.

### 12.4 Checkpoint charges

Each checkpoint charges `costToWaitForOwner`; `approval` adds `words(plan text) ×
planCostPerWord`; `spec-review` adds `words(SPEC.md) × specCostPerWord`. Words = whitespace-split
tokens. `ownerHourlyRate` is rendered for agents' cost-benefit reasoning and not charged (no
attention measurement exists; open question 23.6).

## 13. Costs and budgets

### 13.1 Ledger entries `{step, attempt, usd, source, at, extra}`

Agent run cost precedence: `--cost` → `result.cost_usd` → `--tokens/--agent` or `result.tokens`
priced by the roster (input/output/cache rates; a bare total uses the `estOutputFraction` blend)
→ else the agent's `spawnCost`; always `max(cost, spawnCost)`. Sources: `agent`, `driver`
(`driverUsdPerStep` per `record`), `owner`, `living`; `time_usd` = `lostValuePerHour × hours` from
`created_at` to now (frozen at finished/abandoned) is computed, not stored. `total_usd` sums all.

### 13.2 Budgets

Step budget = `budget_usd × workFraction × shares.work[step]` (producers) or `budget_usd ×
gatesFraction × shares.gates[producer]` (gates); shares from AGENTS-PLAN.json once it exists, else
`defaultShares`, else 0 (rendered as "unbudgeted"). `budget_cap_usd = budget × runBudgetMultiple`
is the hard CLI cap. `retry_cost` of a gate = its producer's budget.

### 13.3 Quote versus actual

`round.history` renders the last five index lines; POSTMORTEM's context includes the full ledger;
`spend --project` tallies index lines plus live rounds (reads sibling round folders only, never
their worktrees' code).

### 13.4 Living charge (at LANDING, against the tip actually merged; exactly one entry per landed round)

For every file under `livingSourcePaths` present at HEAD or at the target: `n = ceil(bytes /
tokenBytes)`; `cost(n) = min(n, cap) × livingFileCostPerToken + max(n − cap, 0) ×
livingFileCostPerTokenOverCap` with `cap = livingFileTokenCap`; charge `cost(after) −
cost(before)`, `+ livingFileBaseCost` per created file, `− livingFileBaseCost` per deleted file,
`+ testBaseCost × Δ(test functions)` counted with regex `^\s*(async\s+)?def\s+test_\w+` over files
matching `test_*.py` under the tests living path. `__pycache__`, `*.pyc` excluded. `cost` previews
the same number against `base_commit` mid-round. `maxRefactorOverhead` is rendered, not enforced.

## 14. Rounds in parallel (adopted from the summary; deviations marked **changed**)

### 14.1 Invariants kept

I1–I11 of the summary hold verbatim, with I3's exception widened to two read/write points in
the main checkout: the owner log (read) and, without an origin, the fast-forward of a clean main
checkout (14.4). No lease, no heartbeat, no TTL, no takeover.

### 14.2 `start`

Validate the plan file **before any git command**. `--no-branch`: id = highest local folder + 1,
current branch, no worktree, no push (tests, offline). Otherwise: `git fetch origin`; base =
`--base` or `origin/<main>` (**changed**: not the checkout's HEAD, per the machine's own rule "cut
from origin, never from what the checkout sits on") or local `<main>` without an origin; ids from
origin `round/*` branches (ASCII digits only) and local folders; then the CAS loop, verbatim:

```
for attempt in 1..pushAttempts:
    branch = explicit or f"round/{rid:04d}"
    git push --porcelain --force-with-lease=refs/heads/<branch>: origin <base>:refs/heads/<branch>
    won = exit == 0 and any(line.startswith("*") for line in stdout.splitlines())   # "=" and "!" lose
    if won: break
    if explicit: error "round id taken"        # exactly one push for an explicit name
    rid += 1
```
Preconditions refused up front (**changed**, the summary's item 5): `<worktreeDir>/` must be
gitignored (`git check-ignore`), `harness/OWNER.log` ignored, worktree path and local branch
absent. On a win: `git worktree add -b <branch> <main_root>/<worktreeDir>/NNNN <base>`, then
everything else with the worktree as root: folder, PLAN.json (`round` set), STATE (`base_commit =
prose_commit = base`), HISTORY, judgment-call files, owner slice, the CHAT-TO-PLAN estimate entry,
commit `round NNNN: start`, `git push -u origin <branch>`; print `{round, folder, branch,
worktree}`. A failed `worktree add` leaves the claim claimed (ids are cheap).

### 14.3 The fence

`record` ends with `git push -u origin <branch>` (non-forced); rejection → `RunnerError("another
runner owns this round (push rejected)")`, exit 1, state saved and committed locally but not
advanced further. The driving runner is the round branch's own `run.py` (`runner_commit` in STATE;
`status` prints it; `doctor` warns when the invoked `run.py` differs from the worktree's).

### 14.4 LANDING

Check phase (also `check` at LANDING; never pushes, moves main, tags, or charges): target =
`origin/<main>` after fetch if it exists, else local `<main>`, else none; `git merge --no-edit
<target>`; conflict → `git merge --abort` → **changed**: checkpoint `landing-conflict` (14.5), not a
producer re-entry; then verify and `suiteCommand` under their timeouts → red → `L2` → **changed**:
checkpoint `landing-red` if HEAD contains a hand merge (the failure is not the agent's), else a
SPEC-TO-IMPLEMENTATION attempt with `L2`.

Land phase, only inside `next` after a clean check:
```
for attempt in 1..pushAttempts:
    living = living_charge(target or base_commit)               # priced against the tip merged
    if target is None: break
    if has_origin: ok = git push origin HEAD:refs/heads/<main>  # non-forced: a fast-forward CAS on origin
    else:          ok = fast_forward_local_main()               # 14.4b
    if ok: break
    if attempt == pushAttempts: raise "landing: push of main rejected N times"
    findings, target = landing_check()                          # re-fetch, re-merge, re-verify, re-suite
    if findings: return findings
add_spend("LANDING", attempt, living, "living"); git tag -f round/NNNN-landed; landed_at = now
```
**changed**: with an origin, main is landed by pushing `HEAD:refs/heads/main` rather than moving a
local `main` first, so a `main` checked out in the main checkout never blocks landing; the local
`main` (if any and not checked out) is then `branch -f`'d as a convenience. 14.4b, no origin:
if `<main>` is not checked out in any worktree → `git branch -f <main> HEAD`; if the main checkout
is on `<main>` and clean → `git -C <main_root> merge --ff-only <branch>`; otherwise fail with the
instruction to park the main checkout on another branch.

### 14.5 Conflicts converge (**changed**, the summary's item 1)

`landing-conflict` question: "`git merge <target>` conflicts in the worktree. Resolve by hand
there (merge, fix, `git add`, `git commit`), then say approve; the runner never resolves
conflicts." On resume `next` re-runs LANDING: the merge is a no-op, verify and suite run on the
merged tree, then the land phase. Because M1/M2 are per-attempt uncommitted-diff checks, a hand
merge never trips them. The living charge is still against the target, so the sibling's diff is
never billed.

### 14.6 The rest

`sync_main` after the last commit exactly as the summary (fast-forward only, never raises,
`main_synced` reported; with an origin it pushes `HEAD:refs/heads/main` and only then moves a
local main). `index.jsonl` append-only. `abandon` tags `round/NNNN-abandoned`. `rounds --prune`
lists claimed ids with no committed round folder and removes worktrees of finished/abandoned
rounds (`git worktree remove --force`, then `prune`). `X1`: at PLAN-TO-SPEC `record`, read
`SPEC.json` from every `origin/round/*` branch whose round is neither landed nor abandoned
(`git show`) and warn on prefix overlap of `implPaths`/`testPaths`. Prose determinism: rendered
from `prose_commit`. Config skew: every config read has a default (section 5).

## 15. Headless agent invocation (`agent.py`)

### 15.1 Command template (`runner.yaml` default; every element is one argv entry, no shell)

```
agentCommand: ["{claude}", "--print", "--output-format", "json", "--system-prompt-file", "{prompt_file}",
               "--model", "{model}", "--effort", "{effort}", "--max-budget-usd", "{budget_cap_usd}",
               "--json-schema", "{result_schema}", "{tool_flags}", "--permission-mode", "bypassPermissions", "{task}"]
gateToolFlags:     ["--tools", "Read", "Grep", "Glob"]
producerToolFlags: ["--disallowedTools", "Bash(git push:*)", "Bash(git commit:*)", "Bash(git reset:*)", "Bash(git checkout:*)", "Bash(git clean:*)", "Bash(git merge:*)", "Bash(git rebase:*)"]
task: "Do the task in your system prompt. Your final message must be exactly the JSON object it specifies."
```
`{tool_flags}` expands in place; both tool flags are variadic, so they sit before a non-variadic
option and the task is last. `{result_schema}` is the RESULT or FINDINGS JSON Schema (one argv
element). `--max-turns` does not exist in 2.1.266: turns are advisory in the prompt; the hard caps
are `--max-budget-usd` and the wall clock (`maxRunWallClockHours`, `subprocess.run(timeout=...)`
with `CREATE_NEW_PROCESS_GROUP` and `taskkill /T /F` on timeout). Env: `os.environ` minus
`scrubEnv`, plus `SHACKLES_SUBAGENT=1`, `PYTHONUTF8=1`. cwd = harness root of the worktree.

### 15.2 Resolving `{claude}`

`SHACKLES_CLAUDE` env → `runner.local.yaml` `claude:` → `shutil.which("claude")` → newest
version directory matching `claudeSearchPaths` (default `%APPDATA%\Claude\claude-code\*\claude.exe`,
`~/.local/bin/claude`) → error naming all four places. `doctor` prints the resolution and
`--version`; `doctor --probe-cli` runs one `--print` call on the `low` rung with a $0.05 cap asking
for `{"ok": true}` under `--json-schema`, confirming the flags and the envelope shape.

### 15.3 Result envelope

`data = json.loads(stdout)`; result = `data["structured_output"]` when it is an object, else
`data["result"]` with a ```` ``` ```` fence stripped and `json.loads`; `total_cost_usd`, `usage`,
`num_turns`, `session_id`, `is_error` are stored beside the result in `RESULTS/`. Non-zero exit,
`is_error`, timeout, or unparseable output → tree reset, `infra_errors[step] += 1`, HISTORY line,
retry; three failures → exit 1. Infra errors never count as attempts.

### 15.4 The session driver (the primary mode in practice)

`.claude/agents/shackles-gate.md` (frontmatter `tools: Read, Grep, Glob`) and
`shackles-producer.md` (all tools) carry a fixed body: "You execute one harness step. Your task
message names a prompt file; Read it first and follow it exactly; your final message must be
exactly the JSON object it specifies and nothing else." The driver's task message is `Prompt file:
<path>` (the prompt is given verbatim by file, which keeps the driver's context small), the
driver saves the final message to `result_file`, and runs `record`. `docs/PROCESS.md` § Driver
states this verbatim, plus: run the worktree's own `run.py`; never do a gate's job; pass
`--cost` when the Agent tool reports one.

## 16. Spec-drift detection (a hard requirement, and tested itself)

`harness/archives/spec-baseline/MANIFEST.json` = `{accepted_at, commit, note, files: {path:
{sha256, bytes}}}` over `spec.yaml` itself plus every path it lists; `files/<path>` holds a copy of
each. `specdrift.check(repo_root)` returns `{changed: [{path, unified_diff}], added, removed,
missing_baseline: bool}` where "added" means a path newly listed in `spec.yaml`, "removed" a
listed path that vanished or was delisted. `spec check` prints it (exit 3 on drift); `spec diff`
prints only the diffs; `spec accept --note "..."` rewrites the baseline (the note lands in the
manifest and a commit is suggested, not made).

`tests/test_spec_drift.py::test_spec_files_unchanged_since_baseline` fails on drift with the full
diff and the instruction: "review the effects on: process.yaml, the renderer namespace (8.2),
schemas, PROCESS.md, INDEX.md, the flagged-edit list; then `run.py spec accept`". The baseline is
taken **after** the flagged edit of section 21 so the suite is green at delivery.

`tests/test_spec_drift_selftest.py` proves the detector: on a temp copy of the repo it asserts a
clean check; a one-word change in a locked prose file → that path in `changed` with a diff
containing the word; a whitespace-only change is still a change; a file added to `spec.yaml` →
`added`; a listed file deleted → `removed`; `spec.yaml` itself edited → `changed`; a deleted
baseline → `missing_baseline`; `accept` then `check` → clean; the CLI exit codes 0/3; and the
pytest test function itself fails (run via `pytest.main` on the temp copy with `-p no:cacheprovider`)
when drift exists and passes after `accept`.

## 17. Standard features missing from the spec, and what this plan does with them

Included: `doctor` with a CLI probe; config loading with defaults and warnings; artifact, result,
verdict, and state schemas with findings-as-errors; spec-drift detection; spec-structure
consistency tests; `render --all` prose smoke test; audit trail (`PROMPTS/`, `RESULTS/`,
`FINDINGS/`, `HISTORY.md`, diffs for gates, `RESULTS/` envelope metadata); crash-safe idempotent
state; timeouts and hard caps everywhere; a ledger with real CLI costs and roster pricing;
`cost` preview; the stub agent and in-process play; secrets scrub and no-push agents; PROCESS.md,
INDEX.md, README, `--help`; the owner-log hook with `owner --say` fallback; `abandon`, `rounds`,
`clean`, `--prune`; sub-agent definitions for the session driver; CAS ids, worktrees, push fence,
landing loop, `sync_main`, `index.jsonl`, conflict checkpoint, overlap warning; test archiving;
judgment-call files counted and fed to POSTMORTEM; `deferred` resolutions and `ERRATA.md`;
postmortem TODO feed to the next plan (every landed round since the last plan that carried a
`todos` object, so parallel landers are not lost); prompt-size guard; `selftest`; `probe`; the
real-agent test scripts; Windows robustness (UTF-8, `onexc` rmtree, process-group kill,
`PermissionError` retry, list-form commands, `py -3.13`).

Deferred, with the reason: driver-cost measurement from session transcripts (flat
`driverUsdPerStep` is what the owner configured); cache-write tier pricing (subAgents.yaml has
one rate); a web/TUI status view (JSON `status` suffices for an LLM operator); a lease/TTL for
dead claims (`rounds --prune` reports them; expiry reintroduces clock skew); a `projectRoot` for a
target project outside `harness/` (open question 23.3).

## 18. Docs and glue files

### 18.1 `harness/docs/PROCESS.md` (normative, one sentence per line, ≤ 250 lines)

Sections: Principles; Files and paths (the harness-root rule); Steps (the table of section 4 and
the rules under it); Runner commands and exit codes; The driver (session mode, headless mode,
"run the worktree's run.py", "never do a gate's job", saving results); Contracts (result JSON,
verdict JSON, every artifact schema, `deferred`, errata); Mechanical checks (the id table);
Failure, dispute, re-entry (attempts, settled findings, UPSTREAM targets, infra errors, limits);
Checkpoints and owner words (12); Costs (13); Rounds in parallel (14, including the hand-merge
rule and the no-origin rule); The spec files (what is owner's, the drift test, how to flag an
edit); Testing (the four levels of section 20); Windows notes.

### 18.2 `harness/INDEX.md`

`alias -> canonical` lines: process/rules → docs/PROCESS.md; config/budget/prices → project.yaml,
subAgents.yaml, runner.yaml; runner/commands → src/run.py (`--help`); step graph → src/process.yaml;
schemas/contracts → src/schemas.py and PROCESS.md § Contracts; prose/prompts → locked_prose/,
`run.py render`; rounds/archives → archives/rounds/NNNN/, index.jsonl; owner log/hook →
OWNER.log (gitignored), src/owner_log_hook.py, .claude/settings.json; spec baseline/drift →
archives/spec-baseline/, `run.py spec`; tests → tests/ (`py -3.13 -m pytest tests`); real-agent
tests → tests/real/, README § Testing; sub-agent definitions → .claude/agents/.

### 18.3 `README.md` (repo root)

What it is (the `shackles` sentence), quick start (`doctor` → `brief` → plan in chat → `start` →
`next`/`record` loop or `run`), where the rules are, the four test levels with expected cost, and
the note that spec files are the owner's.

### 18.4 `doctor` checks

Python ≥ 3.13 via `py -3.13`; PyYAML, pytest importable; git ≥ 2.30 and `worktree` usable; repo
and harness roots; origin (URL or "none"); `<worktreeDir>/`, `harness/OWNER.log`,
`harness/runner.local.yaml` gitignored; hook configured; `claude` resolution and version; spec
drift; config warnings; process graph ↔ spec consistency; unresolved tokens in `render --all`;
main checkout branch and dirtiness (warning); live worktrees; `runner_commit` versus the invoked
`run.py`. Output: one JSON object with `errors`, `warnings`, `info`; exit 1 only on errors.

## 19. Test strategy

### 19.1 Layers and runtime budget

Unit (no git, milliseconds): renderer and namespace, schemas, config defaults/tolerance, ledger
formulas (living charge with cap and base costs, test counting, budgets, retry cost, time cost),
owner-word parsing including envelopes and `override`, process graph loading/validation, spec
drift, prompt-size guard, envelope parsing, `{claude}` resolution order.
Integration (temp repo, real git, stub agent, **in-process** `run.main(argv)`; seconds each):
every round path. CLI contract (true subprocess; a handful): exit codes, one-JSON-object stdout,
`--help`, `doctor`.
Concurrency (temp bare origin, Python `update` hooks with an absolute `sys.executable` shebang,
verified to run on this git; marked `slow`).
Real-agent (`tests/real/`, marked `real`, skipped unless `SHACKLES_REAL=1`).
Targets on this machine: `-m "not slow and not real"` under 60 s; the whole non-real suite under
4 min. Achieved by in-process invocation (no interpreter start per command) and by sharing one
"played to step X" repo per test class where tests are read-only.

### 19.2 Fixtures (`tests/conftest.py`, `tests/stub_agent.py`)

`Repo(tmp, project=None, runner=None, prose=None, files=None, owner_lines=None)`: copies
`harness/` (spec files, src, runner.yaml, `process.yaml`) into `tmp/repo/harness/`, applies
overrides, writes `.gitignore`, `git init -b main` with a hermetic env (`GIT_CONFIG_GLOBAL=nul`,
`GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed identity), commits, writes the owner log.
`agentCommand` is repointed at `stub_agent.py` via `sys.executable`. Methods: `run(*argv)`
(in-process by default, `subprocess=True` optional) returning `{code, json, stdout, stderr}`,
`start`, `next`, `record`, `act(action, mode)`, `play(until, mode)`, `owner_say`, `state`,
`prompt`, `git`, `head`, `dirty`, `tags`, `add_origin()` (bare repo by absolute path, `main`
pushed), `clone()`, `view(worktree)`. `Origin`: `sha`, `branches`, `install_reject_hook(pattern,
n|all)`, `install_move_and_reject_once_hook()`, `hook_log()`, hooks written in Python with the
absolute interpreter shebang and `newline="\n"`. Cleanup with `shutil.rmtree(onexc=chmod_and_retry)`.
`stub_agent.py`: parses the last `STEP:`/`ARTIFACT:`/`RESULT_FILE:` lines, writes canned valid
artifacts for the toy task (`src/toy/text.py` + `tests/toy/test_text.py`), prints the CLI-style
envelope `{"result": "...", "total_cost_usd": 0.01, "structured_output": {...}}`; modes
`pass|fail|dispute|needs_owner|upstream|blocked|garbage|commit` (`commit` performs a git commit to
exercise `M0`), `STUB_FENCE`, `STUB_ARCHIVE`, `STUB_LOG`, `STUB_OUTSIDE` (writes outside declared
paths for `M1`), `STUB_TOUCH_TESTS` (`M2`), `STUB_BREAK` (verify red, `M3`), `STUB_BIG` (`P1`).

### 19.3 Integration tests (one line each = one or more test functions)

start: folder/STATE/HISTORY/judgment files created, PLAN round set, estimate entry, owner slice
since min(landed_at, presented_at), approval implied when the gate is disabled, `--approval` with
and without a matching log line, invalid plan → nothing created, `--no-branch` ids.
next/record: action shape; attempt/step/idempotency guards (exit 2, state unchanged); prompt
rendered from `prose_commit` (edit prose mid-round, prompt unchanged); every producer status
(DONE, NEEDS-OWNER through an enabled gate withdrawn and upheld, NEEDS-OWNER with the gate
disabled → checkpoint, UPSTREAM to each earlier producer and to CHAT-TO-PLAN, BLOCKED); gate
PASS/FAIL, carried findings rendered downstream, dispute → upheld → settled → disputing again
rejected, `deferred` rendered to POSTMORTEM; gates disabled (whole round with all zeros lands with
no gate prompts), enabled, `override` of a gate and of PLAN-AGENTS (defaults used).
Mechanical: S1, M0, M1, M2, M3 (including timeout), P1, U1, B1, Q1, O1, X1 with the exact ids and
routing; `check` never records.
Checkpoints and words: approve/delegate/delegate-through each checkpoint; abandon from active and
from checkpoint; failure-limit resets on approve; round-limit after `maxRoundAttempts` resumes;
hard stop once; words before the checkpoint's `at` ignored; envelope lines ignored;
`owner --say`; hook script driven with a JSON stdin (main-checkout resolution, `SHACKLES_SUBAGENT`
suppression, envelope suppression).
Costs: precedence of cost sources, spawn floor, driver entry per record, owner charges by
checkpoint kind (word counts), time cost frozen at finish, living charge cases (create, grow past
cap, shrink, delete, new tests), `cost` preview equals the landing entry when main is unmoved,
`spend --project` including a live sibling, index line and `round.history`/`round.todos` rendering
(TODOs from two landed rounds, dropped after a plan triages them).
Out-of-band edits and recovery: PLAN edit → approval checkpoint; SPEC edit → SPEC-TO-TESTS; ERRATA
does not trigger; dirty tree reset counts infra; simulated crash (STATE saved but commit missing,
result saved but not recorded) resumes correctly.
Archive and finish: `archive` tests moved to `tests-archive/`, `keep` untouched; POSTMORTEM PASS →
finished, index line, `sync_main`; `clean` removes the worktree.
Headless: `run --until step` with the stub via subprocess: argv contains the model/effort of the
right roster rung (producer vs gate), tool flags in the right order, `--json-schema` present,
env scrubbed and `SHACKLES_SUBAGENT` set, cwd = harness root; fenced JSON accepted;
`structured_output` preferred; garbage → 3 infra errors → exit 1; timeout kills the process tree.
`probe`/`selftest` run with the stub.

### 19.4 Spec-structure tests

Graph ↔ `gates` keys and order; prose files ↔ graph; every token in every prose file resolves in
`render --all` on a fixture round (the one known exception is asserted explicitly until the edit
lands and removed after); `STATUSES`/`VERDICTS` words appear in the locked prose; roster keys
referenced by `project.yaml` exist; `spec.yaml` lists exactly the files under `harness/`
that are not runner-owned (guards against a new owner file nobody baselined).

### 19.5 Concurrency tests (from the summary's list, adapted)

Claim: stdout shape, worktree on `round/0001` at `origin/main`, origin ref == worktree HEAD, main
checkout untouched. Lost race (narrowed fetch refspec on clone B) for `!` and `=` shapes:
`assertNothingCreated` (no folder in any commit, no worktree, no local branch, clean, still on
main). Bounds: reject-all hook → exactly five pushes `round/0001..0005`, clear error, nothing
created. Explicit branch taken → one push. `worktree add` failure → claim survives, rerun takes
the next id. Id sourcing from folders and branches, ignoring `round/003-x`, `round/abc`, tags.
Preconditions refused (worktreeDir not ignored). Fence: another clone moves the branch → `record`
exits 1. Landing after a sibling moved main: `check` merges only; `run --until done` leaves
`origin/main == round tip` containing both rounds, one living entry equal to this round's diff.
Rejected main push (move-and-reject-once hook) retried inside one `next`; reject-all → exit 1,
state at LANDING, lands on rerun. Conflict → `landing-conflict` checkpoint, worktree clean; hand
merge + approve → lands. `landing-red` after a hand merge. `sync_main` true/idempotent/false.
No-origin landing with main parked and with main checked out and clean. `X1` overlap warning.
`rounds --prune` reports a claimed-but-empty id and removes a landed round's worktree.
`index.jsonl` from two rounds merges cleanly.

## 20. Real-agent testing: cheaper and more comprehensive than one toy round

Level 0, free, seconds: `run.py selftest` (a full stub round; every mechanical path).
Level 1, cents per prompt, minutes: `run.py probe --step STEP --agent low --seed clean|defect`.
It builds a temp repo from `tests/fixtures/toy/`, plays the stub round to just before STEP, then
spawns one **real** agent (default rung `low` = Sonnet 5, cap from `--budget`, default $0.50) on
that step's real prompt, records it, and prints cost, turns, validity, and the verdict or result.
`--seed defect` first applies a canned defect for that gate (`tests/fixtures/toy/defects/<GATE>.py`:
a spec sentence that contradicts the plan; an implementation line outside the spec; a test that
does not cover a spec component; a suite decision that archives the only regression test; a
postmortem with an incomplete trace) so gate effectiveness is measured against ground truth. The
full matrix (8 producer prompts, 6 gates × 2 seeds) costs a few dollars and exercises every
prompt and every contract, including the paths a single round never reaches (dispute, UPSTREAM,
NEEDS-OWNER seeded via the toy's plan). Run this before any whole round; it finds unparseable
results, misread instructions, and gates that cannot pass or cannot fail.
Level 2, dollars, about an hour: `tests/real/test_toy_round.py` = the owner's plan made
reproducible: `run --until done` on `systemTestAgent` in a temp repo from the toy fixture, once
with all gates 0 and `--approval delegated`, once with all gates 1; asserts landed, artifacts
valid, ledger non-zero, no `[unresolved` in any prompt, and writes a cost/turn table to the test
log. Level 3, dollars: two toy rounds from two clones of a local bare origin, both headless, both
land (the concurrency for real). Vary later runs by seeding checkpoints (`approved` instead of
`delegated`, answered with `owner --say`) and `override`. Recommendation: Levels 0–1 on every
prose or contract change; Level 2 gates-off once, gates-on once; Level 3 once.

## 21. Spec edits: exactly one, flagged

Reason: `{{ project.ownerReviewCostPerWord }}` has no key in `project.yaml`, which defines
`planCostPerWord` and `specCostPerWord`; the plan prompt and the spec prompt would render an
`[unresolved]` marker. The minimal fix uses the owner's own, more specific keys.

```diff
--- a/harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
+++ b/harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
@@ -6 +6 @@
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
--- a/harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
+++ b/harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
@@ -11 +11 @@
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```
Procedure: make the edit in its own commit titled `SPEC EDIT: resolve ownerReviewCostPerWord
tokens (2 lines)`; list it under a heading "Spec edits made, awaiting your approval" in the
implementer's final report with this diff; take the drift baseline after it. If the owner rejects
the edit, revert it and the renderer's `[unresolved]` marker keeps the round runnable. No gate
prose is relaxed in this plan: the strict "Fail" lines are tempered by COMMON-GATE's cost rule,
and Level 1 gate probes will show whether relaxation is needed before anyone guesses.

## 22. Implementation order and definition of done

Phase 0 (scaffold): layout, `.gitignore`, `runner.yaml`, `config.py` with defaults, `process.yaml`
+ loader, `doctor` (no CLI probe yet), `specdrift.py` + baseline + both drift tests, the spec edit
commit. Green: `doctor` on this machine, drift tests.
Phase 1 (one round, no origin): `gitops`, `schemas`, `render` + plumbing blocks, `ledger`,
`owner`, `round.py` `start --no-branch`/`next`/`record`, mechanical checks, stub agent, fixtures,
integration tests for the DONE-only path with gates off, then gates on with the stub.
Phase 2 (the rest of a round): statuses, disputes, checkpoints and words, hook, limits, hard stop,
costs incl. living charge, archive, judgment calls, errata, TODO feed, out-of-band edits,
recovery, `render`, `cost`, `status`, `log`, `spend`, `abandon`.
Phase 3 (parallel rounds): claim, worktrees, fence, landing, conflict checkpoint, `sync_main`,
`rounds`, `clean`, overlap warning, concurrency tests with origin hooks.
Phase 4 (agents and docs): `agent.py`, `run`, `{claude}` resolution, `doctor --probe-cli`,
`probe`, `selftest`, agent definitions, `PROCESS.md`, `INDEX.md`, `README.md`, real-agent scripts.
Phase 5 (review): spec-structure tests, `render --all` clean except the documented exception,
`doctor` clean on this machine, the final report with the flagged diff, `spec accept`.

Done means: `py -3.13 -m pytest harness/tests -q -m "not real"` green on this machine; `doctor`
reports no errors; `selftest` lands a stub round with gates on and off; `render --all` shows no
unresolved token after the spec edit; every command in section 10 exists with `--help`;
`PROCESS.md`, `INDEX.md`, `README.md` present and consistent with the code; the final report
carries the section 21 diff. Commit per phase with messages naming the phase; never commit to
`main` (this repo's rule); work on a branch and push it.

## 23. Risks and open questions, each with the recommended resolution

1. **`claude` CLI flags or envelope differ from 2.1.266** (the desktop app updates it). Resolution:
   the template is config, `doctor --probe-cli` verifies it for cents, and the parser accepts both
   `structured_output` and text results. Re-run the probe after CLI updates.
2. **Variadic `--tools`/`--disallowedTools` swallowing later args.** Resolution: fixed argv order
   (flags before `--permission-mode`, task last), asserted by the headless test and the CLI probe.
3. **The harness as its own project versus "general software development".** Paths are
   harness-relative today. Resolution: keep it; add a `projectRoot` config key later, defaulting
   to the harness root, when a target project exists (deferred; the owner should say when).
4. **Approval when CHAT-TO-PLAN-GATE is 0.** Resolution as in 12.2 (implied `approved` with
   checkpoints; `--approval delegated` for hands-off runs). Confirm with the owner.
5. **`maxRoundAttempts` and `maxFailuresBeforeStop` semantics** (comments say "round retries" and
   "gate rejections"). Resolution as in 11.4; documented in PROCESS.md; both are single counters
   the owner can retune.
6. **Owner attention is unmeasured**; `ownerHourlyRate` is only rendered. Resolution: charge
   `costToWaitForOwner` and the per-word review costs; propose to the owner a future
   `estOwnerDecisionTimeHours` key if they want attention time in the ledger.
7. **Gates cannot pass under the strict prose** (a known vision_harness worry). Resolution: measure
   with Level 1 defect/clean probes before touching prose; if relaxation is needed, propose it
   as a flagged diff to COMMON-GATE only, never to the per-gate lists.
8. **Windows file locking** (AV scans, editors) breaking `os.replace` or `git clean`. Resolution:
   retries on `PermissionError`, `onexc` rmtree, and the dirty-tree/infra path already tolerates
   a redo.
9. **Living charge shock**: at $0.25 per token, a 200-line test file is ~$800 in the ledger. It is
   the owner's number and only a ledger figure. Resolution: `cost` preview and the rendered
   prices make it visible to agents; flag in the report that the value dwarfs agent costs, so
   quotes will be dominated by living tokens; the owner may retune.
10. **Runner skew across worktrees** when a sibling lands runner changes mid-round. Resolution:
    each round is driven by its own branch's `run.py`, config reads default, `status`/`doctor`
    report `runner_commit`; landing merges bring the new runner in only at LANDING, after which
    the merged runner drives POSTMORTEM (documented).
11. **The owner-log hook is process-wide**: a sub-agent spawned by the driver via the Agent tool
    does not fire UserPromptSubmit (only user prompts do), and headless runs are suppressed by
    `SHACKLES_SUBAGENT`; but a second interactive session on this repo also logs to the same
    file. Resolution: acceptable and even desired (it is the owner's log); words are read only
    after timestamps, and `HISTORY.md` quotes the line acted on.
12. **`git push HEAD:refs/heads/main` to GitHub needs credentials in the runner's environment**
    while agents get none. Resolution: the runner inherits the session's credentials (`gh` or a
    credential manager); `scrubEnv` strips them only for spawned agents; `doctor` checks `git
    ls-remote origin` works.
13. **Prose determinism vs live config.** Prose comes from `prose_commit`; `project.yaml` and
    `runner.yaml` are read live so an owner can flip a gate mid-round. Resolution: documented;
    a test asserts the split.
14. **Spec files changing under the implementer during the build.** Resolution: the drift test is
    Phase 0; any change after that fails the suite and is reviewed before continuing.
