# plan-4: building `shackles_harness` from the owner's spec

Deliverable of one planner, working alone. It is written to be executed by one implementing
agent in one session without further design decisions of consequence. Sections: 1 process,
2 what the spec fixes, 3 features added, 4 design, 5 test strategy, 6 spec edits, 7 build
order, 8 risks and open questions.

## 1. How this plan was developed

1. Read everything in the worktree: `spec.yaml`, its 21 files, and
   `bootstrap/vision-harness-round-concurrency.md`.
2. Consulted the sibling `vision_harness` only for specific points the summary names: its
   config keys, schemas, the process-instruction prose (the `STEP:`/`ARTIFACT:`/`RESULT_FILE:`
   contract), the stub agent, `render`, `invoke_agent`, `read_transcript`, the owner-log hook,
   one real rendered prompt, and the last two postmortems' TODO lists, which are the owner's own
   record of what hurt in parallel rounds. Nothing was imported wholesale.
3. Probed the machine. `py -3.13` is 3.13.2 with PyYAML 6.0.3 and pytest 9.1.1; `python` is
   conda 3.9 and `python3` the Store stub, so every command in this plan says `py -3.13`. git
   is 2.45 (conda MinGW; `sh` present, so update hooks run). No `claude` on PATH: the desktop
   app's bundled CLI is `%APPDATA%\Claude\claude-code\<version>\claude.exe` (2.1.266 today,
   path changes on update) and it accepts `-p --output-format json --system-prompt-file --model
   --effort --max-turns --max-budget-usd --tools --disallowedTools --permission-mode
   --no-session-persistence` (probed by argument parsing; no API call made).
4. Ran a scratch git experiment on this git: an empty-lease push
   (`--force-with-lease=refs/heads/X:`) prints `*` on a win; when the branch exists **at our
   own commit** it prints `=` and exits **0** (a naive exit-code check would call that a win);
   when it exists elsewhere it prints `!` `(stale info)` and exits 1; a `#!/bin/sh` update hook
   in a bare origin runs and can reject; `git rev-parse --git-common-dir` in a linked worktree
   returns the main `.git`. Fixture gotcha found: `git init --bare` leaves HEAD on `master`, so
   clones of it have no checkout until `git symbolic-ref HEAD refs/heads/main` is set.
5. Design method: list every mechanical obligation the spec creates (template keys, step names,
   artifact names, owner words, cost parameters); sort each into *owner wording* (never
   depended on) versus *owner structure* (keys, file names, step names: the contract); take the
   sibling's concurrency protocol and fix each of its nine recorded failures; add the standard
   features a bootstrap of this kind lacks; write the tests into the plan so the implementer
   builds to them.

## 2. What the spec fixes, and what it leaves open

**Fixed by the spec (the contract the runner may depend on).** Names, not sentences.

| Source | Fixed |
| --- | --- |
| `harness/AGENTS.md` | runner at `src/run.py`; routing file `INDEX.md`; rules in `docs/PROCESS.md`; commands named `next` and `record`; prompt files handed verbatim to fresh sub-agents, read-only for gates; result files; living paths `src/ docs/ tests/`; `locked_prose/` frozen mid-round; judgment-call files `DEFINED_JUDGMENT_CALLS.md`, `UNDEFINED_JUDGMENT_CALLS.md`; `{{ plumbing.PROCESS-INSTRUCTIONS }}` is mechanical text the runner supplies |
| `project.yaml` | every key (read by name); `gates` map gives gate names, order and on/off; `roundPaths` gives every round file name and the `NNNN` id width; `defaultShares` keyed by producer name for both pies; `subAgentsFile` |
| `subAgents.yaml` | roster keyed by rung (`max high medium low`) with `model effort` prices and `spawnCost` |
| prose file names | producers = every `<STEP>-OVERVIEW.txt`; gates = every `<STEP>-GATE.txt`; a gate judges the producer with the same prefix |
| template keys used | `project.*` (12 keys), `round.{id,folder,base_commit,plan,budget,spend,remaining}`, `step.retry_cost`, `prose.COMMON-{PROJECT,ROUND,OVERVIEW,GATE}`, `plumbing.{PROCESS-INSTRUCTIONS,GATE-PROSE}` |
| result vocabulary | producer statuses `DONE NEEDS-OWNER UPSTREAM BLOCKED`; gate `PASS/FAIL`, findings `blocking`, each with a `suggestion`; rulings `upheld/withdrawn`, "upheld twice is settled" |
| owner words | `approve/approved`, `delegate/delegated`, `delegate through STEP`, `override` + names |

**Left open, decided here (each also listed in section 8):** step order beyond the gates map
(CLEANUP and LANDING have no gate entry); which steps checkpoint; what `maxRoundAttempts`
counts; how a "suite test" is counted for `testBaseCost`; how owner words are recognised
mechanically; `project.ownerReviewCostPerWord` is referenced by two prose files but
`project.yaml` has `planCostPerWord` and `specCostPerWord` (section 6); `project.remaining`,
`round.*`, `step.retry_cost` are derived values the runner must define.

## 3. Standard features this project lacks, and which are included

Included (the number is used in section 4):

1. **Spec-change alarm**: hashed baseline of every spec file, a test that fails with the diff
   and review instructions, a `baseline` command with an audit trail; the checker is itself
   tested (owner requirement).
2. **Config layering**: code defaults < `harness/src/runner.yaml` (runner-owned) <
   `project.yaml` (owner) < `harness/local.yaml` (gitignored, machine-local, e.g. the path to
   `claude.exe`). Every key read through one accessor with a default: a sibling landing a new
   key never breaks an in-flight round.
3. **Spec pinning**: a round renders prompts and reads config from `spec_commit` via
   `git show`, so nothing the owner edits mid-round changes a live round.
4. **Runner pinning**: the copy of `run.py` on the round's branch drives the round.
5. **Converging landing conflicts**: conflict detection with `git merge-tree`, then a
   merge-resolution attempt whose confinement checks are measured against the auto-merged
   tree (the sibling's loop could not converge; $11 and 51 minutes lost).
6. **HEAD fence and dirty-tree recovery**: a producer that commits is undone softly; a crash
   leaves a resumable round; bounded infrastructure retries.
7. **Read-only gates by construction**: `.claude/agents/shackles-gate.md` with a tool
   allowlist for driver mode; `--tools Read,Grep,Glob` in headless mode.
8. **Owner interface**: `UserPromptSubmit` + `SessionStart` hooks writing a gitignored
   `OWNER.log` and `DRIVER.json`; a `run.py owner "<text>"` fallback; a strict,
   configurable word rule.
9. **Full cost model** with sources: agent (CLI-reported, usage-priced, or estimated), driver
   (from the session transcript, one cursor per session so two rounds never double-book),
   owner (per checkpoint turn plus plan/spec reading per word), living tokens (cap, base,
   refund, new-test base cost), and elapsed time; quote-versus-actual in the index.
10. **Findings lifecycle**: ids per source (`F M L R U O W`), `fixed/disputed/deferred`
    resolutions, settled after two upholds, non-blocking findings carried to later producers
    and to POSTMORTEM.
11. **Judgment-call files** created at start, fed to gates and POSTMORTEM, counted in the
    index (the project's stated purpose is to monitor these).
12. **Cross-round path overlap warning** when a spec declares paths a live sibling declares.
13. **`doctor`** (environment and spec health, renders every prompt offline), **`render`**
    (prompt preview), **`status --project`** (live rounds, stale claims), **`check`**.
14. **Artifact schema validation** and mechanical checks before any gate spends money.
15. **Overrides**: `override STEP...` skips steps or gates for one round, with documented
    fallbacks for missing artifacts.
16. **Prompt-size guard**: a warning finding when a rendered prompt exceeds a token budget.
17. **Windows-first robustness**: argv commands (no `shell=True`), UTF-8 everywhere, forward
    slashes in JSON, hermetic git in tests, in-process test driving (process spawn is slow
    here).
18. **Real-agent system tests** that spend money where judgment lives (gate replays, step
    replays) and nowhere else, with a per-run budget cap and a cost log.

Considered and excluded: a daemon or lock server (git is the lock); lease expiry (ids are
cheap, a claim is permanent); a web dashboard; jsonschema or any pip dependency (a 40-line
validator suffices); parsing postmortem TODOs by heading (wording-dependent; whole files are
fed instead, capped); automatic conflict resolution (never; a conflict becomes agent work).

## 4. Design

### 4.1 Repository layout

```
CLAUDE.md                     3 lines: read harness/AGENTS.md; runner: py -3.13 harness/src/run.py --help
README.md                     what this is; quick start; how to run tests
.gitignore                    .worktrees/  harness/OWNER.log  harness/DRIVER.json  harness/local.yaml
                              harness/DRAFT-PLAN.json  __pycache__/  *.pyc  .pytest_cache/
pytest.ini                    testpaths=harness/tests; addopts=-q; markers system, slow (harness/tests/system/conftest.py skips its directory unless SHACKLES_SYSTEM=1)
.claude/settings.json         hooks: UserPromptSubmit and SessionStart -> py -3.13 harness/src/owner_hook.py
.claude/agents/shackles-gate.md       tools: Read, Grep, Glob (read-only judge)
.claude/agents/shackles-producer.md   default tools; body: follow the prompt, never commit or push
spec.yaml, bootstrap/         the owner's (unchanged except section 6)
harness/
  AGENTS.md project.yaml subAgents.yaml locked_prose/   the owner's spec files (unchanged except section 6)
  INDEX.md                    routing: "aliases -> path", one line each, grep-able
  docs/PROCESS.md             normative rules (steps, kinds, checkpoints, words, findings, checks, costs, landing, invariants)
  docs/DRIVER.md              operating a round from a chat session, command by command
  docs/TESTING.md             suites, fixtures, stub modes, system tests, baseline procedure
  src/run.py                  CLI entry; argparse; exit codes; re-exec into the round branch's copy (4.10)
  src/runner.yaml             runner-owned settings with comments (4.2)
  src/plumbing/producer.txt   the mechanical block for producers (4.5); gate.txt for gates; <STEP>.txt optional extras
  src/shackles/__init__.py
  src/shackles/config.py      spec loading (spec.yaml list), layering, defaults, pinned reads via git show
  src/shackles/pipeline.py    KNOWN step table; reconciliation with the owner's files; kinds, artifacts, checks
  src/shackles/prose.py       template engine (4.4)
  src/shackles/schemas.py     declarative validator; PLAN, AGENTS_PLAN, SPEC, SUITE, RESULT, FINDINGS, STATE
  src/shackles/gitx.py        git helpers: run, ok, head, main_root, claim, worktree, merge_tree, push loops
  src/shackles/ledger.py      spend entries, buckets, living charge, pricing, transcript reading
  src/shackles/owner.py       OWNER.log slicing, word recognition, checkpoints
  src/shackles/checks.py      mechanical checks M1..M4, schema checks, overlap warning, prompt-size warning
  src/shackles/round.py       Round: start/next/record/abandon/status, HISTORY, STATE persistence
  src/shackles/landing.py     landing_check, land, sync_main, merge-resolution re-entry
  src/shackles/agents.py      headless invocation, claude discovery, env scrub, result extraction
  src/shackles/baseline.py    spec baseline check/update (4.14)
  src/shackles/doctor.py      health report (4.14)
  src/owner_hook.py           the Claude Code hook (stdin JSON -> OWNER.log / DRIVER.json)
  archives/rounds/            NNNN/ per round (owner's roundPaths); index.jsonl; SPEC-CHANGES.md (baseline audit trail)
  tests/                      section 5 (conftest.py, fixtures/, stub_agent.py, test_*.py, system/)
```

Size budget: runner code about 2,200 lines across the modules (none over 450), plumbing 120
lines, docs 350 lines, tests about 2,000 lines. Every file read or written with
`encoding="utf-8"`, LF newlines, JSON `indent=2, ensure_ascii=False`, trailing newline. Paths
inside JSON and prompts are harness-root-relative with forward slashes unless labelled absolute.

Path convention: the **harness root** is the directory holding `AGENTS.md` (`harness/`); the
**repo root** is `git rev-parse --show-toplevel`. Every path in `project.yaml` is relative to
the harness root and may start with `../` (a project that embeds the harness points its living
paths outside it). Internally the runner works in repo-root-relative paths.

### 4.2 Configuration layering and defaults

`config.load(root, pinned_commit=None)` returns one mapping built in this order, later wins:
code defaults (`DEFAULTS` in `config.py`) < `src/runner.yaml` < `project.yaml` < `local.yaml`.
Agents roster from `project.subAgentsFile`. Reads go through `cfg.get(key)`; a missing key
returns the default and `doctor` lists which defaults are in use; unknown keys are kept and
reported. When `pinned_commit` is given, `project.yaml`, `subAgents.yaml` and every locked
prose file are read with `git show <commit>:<path>` (runner.yaml and local.yaml from the
working tree: they are the runner's, not the round's).

`src/runner.yaml` (defaults, all overridable):

```yaml
mainBranch: main
worktreeDir: .worktrees            # repo-root relative; must be gitignored (start refuses otherwise)
pushAttempts: 5                    # pushes, not retries: bounds claim and landing loops
infraRetries: 3
checkpointAfter: [PLAN-TO-SPEC-GATE, CLEANUP]   # approval after CHAT-TO-PLAN-GATE is implicit
ownerWords: {approve: [approve, approved], delegate: [delegate, delegated], abandon: [abandon], override: [override]}
ownerWordMode: start               # a word counts only as the first word of an owner message (4.12)
ownerTurnHours: 0.1                # owner attention per checkpoint turn, x ownerHourlyRate
minRunUsd: 1.0                     # floor for a run's --max-budget-usd
promptTokenWarn: 60000             # W2 above this (bytes / tokenBytes)
postmortemFeedRounds: 3            # postmortems fed to CHAT-TO-PLAN
findingQuoteMaxChars: 600
suiteCommand: [py, -3.13, -m, pytest, -q, harness/tests]     # the project's permanent suite
agentCommand: [claude, -p, --output-format, json, --system-prompt-file, "{prompt_file}", --model, "{model}",
               --effort, "{effort}", --max-turns, "{max_turns}", --max-budget-usd, "{budget_usd}",
               --permission-mode, bypassPermissions, --no-session-persistence, "{tool_flags}",
               "Do the task in your system prompt. Your final message must be exactly the JSON it asks for."]
claudePath: null                   # null: PATH, then newest %APPDATA%\Claude\claude-code\*\claude.exe; local.yaml sets it
gateToolFlags: [--tools, "Read,Grep,Glob"]
producerToolFlags: [--disallowedTools, "Bash(git push:*)", "Bash(git commit:*)"]
scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]
gitIdentity: null                  # null: the repo's own config; tests set GIT_AUTHOR_*/GIT_COMMITTER_* in env
modelAliases: {claude-fable-5-1: fable, claude-opus-5: opus, claude-sonnet-5: sonnet}   # Agent-tool model names
testPatterns: {".py": "^\\s*(async\\s+)?def\\s+test_\\w+", ".js": "\\b(it|test)\\s*\\(", ".ts": "\\b(it|test)\\s*\\("}
cacheWrite1hFactor: 1.6            # 1-hour cache writes priced at this multiple of the roster's 5-minute rate
```

`project.yaml` keys the runner reads, with the meaning fixed here: `budget` (project target),
`hardStopBudgetMultiple`, `lostValuePerHour`, `ownerHourlyRate`, `costToWaitForOwner`,
`planCostPerWord`, `specCostPerWord`, `livingFileTokenCap`, `livingFileCostPerToken`,
`livingFileCostPerTokenOverCap`, `livingFileBaseCost`, `testBaseCost`, `tokenBytes`,
`maxRefactorOverhead`, `gates`, `defaultShares`, `livingSourcePaths`, `lockedProsePath`,
`archivesPath`, `roundPaths`, `maxSimultaneousSubAgentsPerRound`, `maxRoundAttempts`,
`maxFailuresBeforeStop`, `maxTurnsPerRun`, `maxRunWallClockHours`, `verifyTimeoutSeconds`,
`gatesFraction`, `workFraction`, `estOutputFraction`, `driverUsdPerStep`, `subAgentsFile`,
`maxAgent`, `gateAgent`, `systemTestAgent`. Each has a code default equal to today's value.

### 4.3 Pipeline derivation

`pipeline.KNOWN` is the runner's model of the standard process, in order:

| Step | Kind | Artifact (roundPaths key) | Writes | Mechanical checks | After |
| --- | --- | --- | --- | --- | --- |
| CHAT-TO-PLAN | producer (the driver, in chat) | `plan` | round folder | schema PLAN | |
| CHAT-TO-PLAN-GATE | mechanical | | | approval word after `presented_at`; plan reading cost | checkpoint (approval) |
| PLAN-AGENTS | producer | `agentsPlan` | round | schema AGENTS_PLAN; rungs in roster; pies sum 1±0.01; subAgents ≤ max | |
| PLAN-AGENTS-GATE | gate | | | | |
| PLAN-TO-SPEC | producer | `spec` + `specProse` | round | schema SPEC; impl/test paths disjoint by prefix; refactor share ≤ cap; W1 overlap; spec reading cost | |
| PLAN-TO-SPEC-GATE | gate | | | | checkpoint |
| SPEC-TO-TESTS | producer | (diff) | testPaths + round | M1 | |
| SPEC-TO-TESTS-GATE | gate | | | | freeze: `tests_commit` = HEAD at PASS |
| SPEC-TO-IMPLEMENTATION | producer | (diff) | implPaths + round | M1 M2 M3 | |
| SPEC-TO-IMPLEMENTATION-GATE | gate | | | | |
| TESTS-TO-SUITE | producer | `suite` | round | schema SUITE; every test file changed since base in exactly one list; listed paths exist | |
| TESTS-TO-SUITE-GATE | gate | | | | archive move (git mv to `testsArchive`) |
| CLEANUP | producer | (diff) | implPaths + round | M1 M2 M3 M4 | checkpoint |
| LANDING | mechanical | | | 4.10 | |
| POSTMORTEM | producer | `postmortem` | round | file non-empty | |
| POSTMORTEM-GATE | gate | | | | finish: index line, sync main |

Reconciliation with the owner's files at load (and frozen into `STATE.pipeline` at start):

- Producers are the `<STEP>-OVERVIEW.txt` files; gates are the keys of `project.gates`; a gate
  is enabled when its value is truthy. A known gate absent from the map is disabled (doctor
  warns). A `<STEP>-GATE.txt` file without a map entry is disabled (doctor warns).
- **Order**: the owner's `gates` key order orders the gated producers; ungated known steps keep
  their KNOWN anchors (CLEANUP immediately before LANDING, LANDING before POSTMORTEM). If the
  map's order disagrees with KNOWN, the map wins and doctor warns.
- **Unknown steps** (an `X-OVERVIEW.txt` the table lacks): producer with artifact `X.md` in
  the round folder, writes = round folder, no checks; gated if `X-GATE` is in the map and
  `X-GATE.txt` exists; placed where the map puts its gate, else immediately before CLEANUP.
  Doctor reports it. An `X-GATE` map entry with no `X-OVERVIEW.txt` is a load error.
- `checkpointAfter` entries naming absent steps are ignored (doctor warns).

### 4.4 Prose engine

Grammar: `{{ ns.key }}` with `TOKEN = \{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}`. Namespaces:

- `prose.NAME` → the locked prose file `NAME.txt`, rendered recursively. **Each prose file
  renders at most once per document**: a second include of the same name renders empty (this
  is also what makes `plumbing.GATE-PROSE` embed cleanly). Depth limit 8; a cycle is an error.
- `plumbing.PROCESS-INSTRUCTIONS` → `src/plumbing/producer.txt` or `gate.txt` by step kind,
  followed by `src/plumbing/<STEP>.txt` if it exists (step-specific mechanics such as the
  SPEC declarations), rendered with the same context. `plumbing.GATE-PROSE` → the step's gate
  file rendered in **embed mode**: prose already included in the document renders empty,
  `plumbing.PROCESS-INSTRUCTIONS` renders empty, values render normally; if the gate is
  disabled the block is followed by one line saying so. Any other `plumbing.X` →
  `src/plumbing/X.txt` if present.
- `project.key`, `round.key`, `step.key` → values (4.4.1). Value formatting: `str` as is; int
  as is; float with trailing zeros trimmed; bool `true/false`; None `none`; list/dict compact
  JSON with `ensure_ascii=False`.
- **Unresolved key policy**: never raise. Render `[[UNRESOLVED: ns.key]]`, collect it; `next`
  prints the list to stderr and appends `FLAG (runner): unresolved template keys ...` to
  HISTORY.md; `doctor` and the real-spec smoke test (5.4) report them.
- If a producer's or gate's prose contains no `plumbing.PROCESS-INSTRUCTIONS` token, the
  runner appends the block at the end: an agent always receives its contract.
- Prompts are written to `PROMPTS/<STEP>-<attempt>.txt` and committed by `next`.

4.4.1 Value catalogue (all derived values are defined here; add to it, never rename):

- `project.*`: every key of the layered config; plus `remaining` = `budget` − Σ index
  `total_usd` − Σ live sibling rounds' totals (best effort, from their branches' STATE.json,
  cached per `next`); `spent` = the subtrahend; `agents` = the roster as a compact list of
  `{key, name, model, effort, inputUsdPerMTok, outputUsdPerMTok, spawnCost}`.
- `round.*`: `id` (`NNNN` string), `number` (int), `folder` (as in roundPaths, e.g.
  `archives/rounds/0001/`), `worktree` (absolute), `branch`, `base_commit`, `spec_commit`,
  `plan` (PLAN.json rendered as text: summary, then `Scope/Validation/Non-goals/Assumptions`
  bullet lists, quote, todos; extra keys as JSON), `budget`, `spend`, `remaining`, `status`,
  `step`, `history` (HISTORY.md text), `spec` (SPEC.json then SPEC.md text, or `none yet`),
  `agents_plan`, `suite`, `judgment_calls` (both files' text with headers), `findings_all`
  (carried findings as JSON), `owner_log` (this round's slice), `postmortems` (the
  POSTMORTEM.md of the last `postmortemFeedRounds` landed rounds, oldest first, each headed
  `## round NNNN`, or `none`), `history_quotes` (index rows as `id quote actual` lines).
  Before a round exists (`render`/`plan`), every `round.*` renders `n/a`.
- `step.*`: `name`, `kind` (`producer|gate`), `attempt`, `budget`, `max_turns`,
  `wall_clock_seconds`, `retry_cost` (4.9), `agent` (rung key), `model`, `effort`,
  `model_alias`, `producer` (for gates), `gate` (for producers), `gate_enabled`, `artifact`
  (path or `the diff of your declared paths`), `result_file`, `prompt_file`, `write_paths`
  (JSON list), `read_only`, `findings` (prior findings with resolutions and rulings, JSON, or
  `none`), `previous` (the producer's previous final message JSON or `none`), `question`
  (pending NEEDS-OWNER question or `none`), `sub_agents` (allowed count and rung, or `none`),
  `conflicts` (conflicted paths during a merge-resolution attempt, else `none`).

### 4.5 Contracts

**Plumbing, `src/plumbing/producer.txt`** (runner-owned; tests may depend on its
machine-readable lines, which are the last occurrence of each `KEY:` line in a prompt):

```
RESULT CONTRACT. The runner parses this; follow it exactly.
STEP: {{ step.name }}
KIND: producer
ATTEMPT: {{ step.attempt }}
WORKTREE: {{ round.worktree }}
ARTIFACT: {{ step.artifact }}
RESULT_FILE: {{ step.result_file }}
WRITE_PATHS: {{ step.write_paths }}
Every relative path in this prompt is relative to WORKTREE; use absolute paths in tools. Budget for this run ${{ step.budget }}; max turns {{ step.max_turns }}; sub-agents allowed: {{ step.sub_agents }}.
You may create or change files only under WRITE_PATHS. Never run git commit, git push, or git merge; the runner commits. Write nothing to RESULT_FILE: your final message is the result.
Inputs: the round folder {{ round.folder }} (PLAN.json, AGENTS-PLAN.json, SPEC.json, SPEC.md, SUITE.json when they exist, HISTORY.md, FINDINGS/, DEFINED_JUDGMENT_CALLS.md, UNDEFINED_JUDGMENT_CALLS.md).
Findings so far, with resolutions and rulings: {{ step.findings }}
Your previous final message: {{ step.previous }}
Merge conflicts to resolve this attempt (edit, then git add each file; nothing else): {{ step.conflicts }}
Living cost formula: a token is {{ project.tokenBytes }} bytes; a file's first {{ project.livingFileTokenCap }} tokens cost {{ project.livingFileCostPerToken }} each and the rest {{ project.livingFileCostPerTokenOverCap }}; a new living file {{ project.livingFileBaseCost }}; a new suite test {{ project.testBaseCost }}.
Final message: exactly one JSON object and nothing else:
{"status": "DONE" | "NEEDS-OWNER" | "UPSTREAM" | "BLOCKED", "notes": "<one paragraph: what you did and decisions worth recording>", "question": "<NEEDS-OWNER: the question and the value at stake>", "assumption": "<NEEDS-OWNER: what you built on meanwhile>", "target": "<UPSTREAM: the earlier producer step whose artifact is wrong; the contradiction quoted in notes>", "resolutions": {"<finding id>": {"status": "fixed" | "disputed" | "deferred", "reason": "<why>"}}, "subagents": [{"agent": "<rung>", "input": 0, "output": 0, "cache_read": 0, "cache_write": 0}]}
Omit fields that do not apply. Every finding id you were given must appear in resolutions; deferred means it cannot be closed in this round and goes to the postmortem. Disputing a settled finding is rejected. JSON artifacts are validated against their schema and mechanical checks run before any gate; a failure returns to you as a finding.
Then: DONE, the gate runs if enabled ({{ step.gate }}: {{ step.gate_enabled }}). NEEDS-OWNER, the gate rules on the question, or the owner is asked when the gate is disabled; the answer returns as a finding. UPSTREAM, the round returns to the target step with your notes as a finding. BLOCKED, the round pauses for the owner.
```

`src/plumbing/gate.txt` differs in: `KIND: gate`, `READ_ONLY: true`, no WRITE_PATHS, "You
run read-only and see the artifact, its inputs, the intent, prior findings with resolutions,
and the judgment-call files; never the producer's transcript", the producer's question and
final message, and the verdict:

```
{"verdict": "PASS" | "FAIL", "findings": [{"id": "F<n>", "quote": "<verbatim text judged>", "reason": "<why>", "suggestion": "<what would prevent the FAIL>", "blocking": true | false}], "rulings": {"<finding id>": {"status": "upheld" | "withdrawn", "quote": "<verbatim text>"}}, "needs_owner": {"status": "upheld" | "withdrawn", "reason": "<why; if withdrawn, the answer to assume>"}, "notes": "<one line>"}
Omit rulings and needs_owner when there is nothing to rule on. Ids continue from the highest prior id. Verdict is FAIL exactly when a finding is blocking or needs_owner is upheld. Do not repeat the mechanical checks already run.
```

Step-specific plumbing files (`src/plumbing/<STEP>.txt`), each a few lines: **PLAN-TO-SPEC**
(SPEC.json fields: `verify` command run from the repo root, string or argv list, and its
timeout; `implPaths`, `testPaths` disjoint; `refactor` items with their share of the round
budget; `nonGoals` verbatim from the plan; body `SPEC.md`; the checks the runner runs);
**PLAN-AGENTS** (AGENTS-PLAN.json fields, the roster, the pies, the sub-agent cap);
**SPEC-TO-TESTS** (write only under testPaths; tests freeze at the gate's PASS);
**SPEC-TO-IMPLEMENTATION** (write only under implPaths; tests are frozen; verify must pass
within its timeout); **TESTS-TO-SUITE** (SUITE.json `keep`/`archive` partition of every test
file changed this round; archived files move to `tests-archive/`); **CLEANUP** (implPaths only,
verify and the permanent suite green); **POSTMORTEM** (inputs: HISTORY, all findings, spend
summary and quote versus actual, judgment-call files; output POSTMORTEM.md); **CHAT-TO-PLAN**
(you are the driver: write PLAN.json to `harness/DRAFT-PLAN.json` with `presented_at` set when
you present the plan; the owner's words are recognised only as the first word of a message; then
`start --plan`).

**Artifact schemas** (`schemas.py`; required/optional with types `str int number bool list
dict`; extra keys allowed; messages `"<SCHEMA>: <key> <problem>"`):

- PLAN: required `presented_at str, summary str, scope list, validation list, non_goals list,
  quote_usd number`; optional `assumptions list, todos dict, overrides list, round int`.
- AGENTS_PLAN: required `round int, agents dict (STEP → rung), shares dict {work: {STEP:
  number}, gates: {STEP: number}}`; optional `gateAgents dict, subAgents dict (STEP → {count
  int, agent str}), notes str`.
- SPEC: required `round int, summary str, verify str|list, implPaths list, testPaths list,
  nonGoals list`; optional `verifyTimeoutSeconds number, refactor list [{what str, share
  number}], body str` (default `SPEC.md`).
- SUITE: required `round int, keep list, archive list, notes str`.
- RESULT and FINDINGS as in the plumbing above. STATE in 4.6.

**Result extraction** (`agents.extract_json(text)`): try the whole message; then a
```` ```json ```` fence; then the last balanced top-level `{...}`. Failure → the attempt counts
with synthesized finding `R1` ("final message was not the contract JSON") and the same step
runs again.

### 4.6 Round data model

Round folder from `roundPaths` (`NNNN` → zero-padded to the count of `N`s). Files: the
artifacts, `STATE.json`, `HISTORY.md`, `OWNER.log` (slice), `PROMPTS/`, `RESULTS/`,
`FINDINGS/` (gate verdicts as `<GATE>-<n>.json`; mechanical and landing findings as
`<STEP>-<n>.mechanical.json`), `tests-archive/`, the two judgment-call files (created empty at
start). `RESULTS/` and `FINDINGS/` and `PROMPTS/` are created at start with a `.keep`.

`STATE.json` (validated on every save):
required `round int, branch str, created_at str, presented_at str, status str
(active|checkpoint|finished|abandoned), step str, kind_pending str|null, attempts dict,
failures dict, infra_errors dict, reentries int, step_commits dict, step_starts dict,
inputs_hash dict, budget_usd number, spend dict, base_commit str, spec_commit str, pipeline
list, gates_enabled dict, checkpoints_after list, overrides list`;
optional `pre_head, delegated (null|"all"|"through:STEP"), approval {word, quote, at},
checkpoint {reason, step, question, artifact, at}, pending_question, carried_findings list,
findings_ledger dict, last_findings dict, merge_pending {target, target_sha, automerge_tree,
conflicted} | null, tests_commit, hard_stop_raised bool, landed_at, abandoned_at, main_before,
driver {session, cursor}`. No worktree key (derivable), no lock, lease, pid or owner field.

`spend`: `entries` list of `{step, attempt, usd, source, at, usage?, note?}` with sources
`cli usage estimate` (bucket `agent_usd`), `driver`, `owner`, `living`; buckets recomputed on
every append; `time_usd` = hours since `created_at` × `lostValuePerHour`, computed, not stored;
`total_usd` = buckets + time.

`HISTORY.md`: `# Round NNNN history`, then `## <STEP> attempt <n> (<status or verdict>)
<ts>` followed by the notes; `## MECHANICAL <step> <PASS|FAIL> <ts>` with finding ids; `##
CHECKPOINT <reason> at <step> <ts>` with the question; `## LANDING ...`; `FLAG (runner|driver):
...` single lines for anomalies. Append-only.

`archives/rounds/index.jsonl`: one line per finished or abandoned round, appended on the round
branch: `{id, quote_usd, spend {agent_usd, driver_usd, owner_usd, living_usd, time_usd,
total_usd}, attempts, failures, reentries, judgment_calls {defined, undefined}, outcome
(landed|abandoned), spec_commit, landed_at|abandoned_at}`. `judgment_calls` are line counts
of the two files (non-empty lines).

### 4.7 The state machine

**`start --plan FILE [--budget USD] [--branch NAME] [--no-branch]`**
1. Validate the plan file (schema, `presented_at` parses, `quote_usd > 0`) before any git
   command. Preconditions (each a clear error, nothing created): git ≥ 2.38; `.gitignore`
   contains `<worktreeDir>/`; an `origin` exists unless `--no-branch`.
2. Claim the id (4.10) and create the worktree; with `--no-branch`: id = 1 + highest local
   folder, no fetch, no push, no worktree, work in the current checkout.
3. In the round folder: PLAN.json (copy; `round` set), STATE.json (`base_commit = spec_commit =
   HEAD`, pipeline frozen, `gates_enabled` from config, `budget_usd` = `--budget` or the
   quote, `overrides` from PLAN.json), HISTORY.md, empty judgment-call files, OWNER.log slice
   since `presented_at`; driver charge from the transcript (4.9). `git add -A` (round folder
   only), commit `round NNNN: start`, push `-u` (unless `--no-branch`). Print exactly one line:
   `{"round", "folder", "branch", "worktree"}`.

**`next [--no-push]`** (the only place mechanical steps run):
1. Load STATE; `finished|abandoned` → `sync_main` → print `{"kind": "done", "main_synced":
   bool}` → exit 0.
2. Re-hash `PLAN.json`, `SPEC.json`, `SPEC.md`; a changed hash re-enters at the first step
   that consumes it (PLAN → `CHAT-TO-PLAN-GATE`, so approval is required again; SPEC →
   `SPEC-TO-TESTS`), resets downstream attempts and failures, appends a FLAG.
3. Dirty-tree recovery: `git status --porcelain` non-empty and no `merge_pending` with a live
   `MERGE_HEAD` → `git checkout -- . && git clean -fdq` (worktreeDir is ignored, hence the
   precondition), `infra_errors[step] += 1`, FLAG. With `merge_pending` and no `MERGE_HEAD`
   (crash before the merge started): redo the merge in step 6.
4. Refresh the owner slice from `<main_root>/harness/OWNER.log` (lines with timestamp ≥
   `presented_at`, envelopes filtered).
5. `status == checkpoint`: look for an owner message after `checkpoint.at` (4.12); none →
   print the checkpoint JSON `{"kind": "checkpoint", "reason", "step", "question", "artifact",
   "spend"}` → exit 10; found → apply (approve/delegate/abandon/answer) and continue.
6. Loop until an agent run is due: overridden step → `## <STEP> skipped (override)`, advance;
   mechanical step → run it (CHAT-TO-PLAN-GATE: approval; LANDING: 4.10), advance or
   checkpoint or re-enter; disabled gate → auto-PASS with `FINDINGS/<GATE>-<n>.json`
   `{"verdict":"PASS","findings":[],"source":"disabled"}`, advance (honouring
   `checkpointAfter`); producer or enabled gate → the hard-stop check (4.9), attempt =
   `attempts[step] + 1`, render the prompt, set `kind_pending`, `pre_head = HEAD`,
   `step_starts[step]` if absent, save, commit (no push), print the action → exit 0.

Action JSON: `{"kind": "producer"|"gate", "round", "step", "attempt", "prompt_file",
"result_file", "artifact", "agent", "model", "model_alias", "effort", "budget_usd",
"max_turns", "wall_clock_seconds", "tools": "read-only"|"producer", "agent_type":
"shackles-gate"|"shackles-producer", "worktree", "spend", "warnings": [...]}`.

**`record --step S --attempt N --result FILE [--cost USD | --usage IN,OUT,CR,CW --agent RUNG]
[--no-push]`**
1. Guard: `status == active`, `STATE.step == S`, `N == attempts[S] + 1`, `kind_pending` set;
   otherwise exit 2 with the reason (replays and out-of-order records are refused, never
   double-applied).
2. HEAD fence: `HEAD != pre_head` → `git reset --soft <pre_head>` and FLAG "producer
   committed; undone softly".
3. Read the result file, extract JSON (4.5), validate against RESULT or FINDINGS. Copy the raw
   file to `RESULTS/<S>-<N>.json` if it is not already there.
4. `attempts[S] = N`. Ledger: agent entry (`cli` from `--cost`, `usage` priced from `--usage`
   or the result's `subagents`, else `estimate` = `budget_for(S)` + spawn cost, with FLAG);
   driver entry (4.9).
5. Producer outcomes:
   - `DONE`: `git add -A` (the round folder and the step's write paths only; anything else
     is left for M1 to report) and commit `round NNNN: <S> attempt <N>`; run the step's
     mechanical checks (4.8). Findings → `FINDINGS/<S>-<N>.mechanical.json`,
     `failures[S] += 1`, re-enter `S` at `N+1` with the findings; limit check. Clean →
     `step_commits[S] = HEAD`; advance to the gate (enabled) or past it (disabled).
   - `NEEDS-OWNER`: gate enabled → advance to the gate with `pending_question`; disabled →
     checkpoint `question` (owner cost); the owner's next message becomes finding `O<n>` for
     `S` at `N+1` ("approve" means proceed on the assumption; recorded as a decision).
   - `UPSTREAM`: `target` must be an earlier producer in the pipeline; finding `U<n>` (quote =
     notes) attached to the target; downstream attempts and failures reset; `reentries += 1`;
     `maxRoundAttempts` exceeded → checkpoint `round-limit`.
   - `BLOCKED`: checkpoint `blocked` with the notes; "approve" reruns the step.
6. Gate outcomes: apply `rulings` to `findings_ledger` (upheld → `upheld_count += 1`,
   `settled` at 2; withdrawn → closed); a ruling on an unknown or settled id is ignored with a
   FLAG. `PASS` → non-blocking findings appended to `carried_findings`; `needs_owner.upheld`
   → checkpoint `question`; `step_commits[gate] = HEAD`; post-gate mechanics (freeze
   `tests_commit`; archive move); advance, honouring `checkpointAfter`. `FAIL` →
   `failures[producer] += 1`, `last_findings[producer]` = the file, re-enter the producer at
   the next attempt; `failures ≥ maxFailuresBeforeStop` → checkpoint `failure-limit`
   ("approve" resets that step's count).
7. Save STATE, append HISTORY, `git add -A`, commit, `git push -u origin <branch>` (unless
   `--no-branch` or `--no-push`). A rejected push → `RunnerError("another runner owns this
   round (push rejected)")`, exit 1, nothing else changes (the fence).
8. Print `{"kind": "recorded", "round", "step": <next step>, "spend"}` → exit 0.

**`abandon --reason R`** from any status: status `abandoned`, tag `round/NNNN-abandoned`,
index line, commit, push best-effort. **Checkpoint kinds**: `approval`, `review` (after a
`checkpointAfter` step), `question`, `blocked`, `failure-limit`, `round-limit`, `hard-stop`.

Advance rule: the next step in `STATE.pipeline`; after leaving a step in `checkpoints_after`
that is not delegated through, raise `review` with the artifact path. Delegation:
`delegated == "all"` skips every `approval|review` checkpoint; `through:STEP` skips those at
or before STEP in pipeline order. `question|blocked|failure-limit|round-limit|hard-stop`
are never skipped.

### 4.8 Mechanical checks (`checks.py`)

Each returns findings `{id, quote, reason, suggestion, blocking: true}` in the FINDINGS shape;
ids are stable so tests and prompts can name them.

| Id | When | Check |
| --- | --- | --- |
| S1 | after any JSON artifact | schema validation; one finding per message |
| S2 | PLAN-AGENTS | rung keys exist; `subAgents[*].count ≤ maxSimultaneousSubAgentsPerRound`; each pie sums to 1±0.01 over the steps it names; unknown step keys |
| S3 | PLAN-TO-SPEC | `implPaths`/`testPaths` non-empty and disjoint by prefix; Σ `refactor[*].share ≤ maxRefactorOverhead`; `verify` non-empty |
| W1 | PLAN-TO-SPEC | non-blocking: a live sibling round (origin `round/*` branch without a landed/abandoned tag, STATE.json read via `git show`) declares an overlapping path |
| M1 | SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, CLEANUP | `git diff --name-only <base> HEAD` contains a path outside write paths ∪ round folder; base = `step_starts[step]` (4.10 changes the base and the allowed set during a merge-resolution attempt) |
| M2 | SPEC-TO-IMPLEMENTATION, CLEANUP | `git diff --name-only <tests_commit> HEAD -- <testPaths>` non-empty (tests changed after SPEC-TO-TESTS-GATE PASS) |
| M3 | SPEC-TO-IMPLEMENTATION, CLEANUP | `verify` (argv; a string is split with `shlex.split(posix=os.name != "nt")`) run from the repo root with cwd = worktree, timeout `verifyTimeoutSeconds` (spec value wins); non-zero exit or timeout; quote = last 3000 chars |
| M4 | CLEANUP, LANDING | `suiteCommand` green within `verifyTimeoutSeconds` |
| T1 | TESTS-TO-SUITE | every file changed under testPaths since `base_commit` is in exactly one of `keep`/`archive`; listed paths exist |
| W2 | any prompt | non-blocking warning in the action: rendered prompt > `promptTokenWarn` tokens |
| L1, L2, L3 | LANDING and its re-entry | 4.10 |
| R1 | any record | result JSON invalid |

Mechanical findings count as failures for the producer. W-findings never block; they are
recorded in HISTORY and shown to the next producer.

### 4.9 Costs

- `budget_for(step)`: `budget_usd × workFraction × shares.work[step]` for producers,
  `budget_usd × gatesFraction × shares.gates[producer]` for gates; shares from AGENTS-PLAN.json
  when it exists, else `defaultShares`; floor `minRunUsd`. `step.retry_cost` =
  `budget_for(producer) + spawnCost(producer's rung) + driverUsdPerStep`.
- Agent cost per run: `--cost` (CLI `total_cost_usd`, source `cli`); else `--usage` or the
  result's `subagents` priced at the rung's rates (`input × in + output × out + cache_read × cr
  + cache_write × cw`, per MTok; source `usage`); else `estimate` = `budget_for(step)` +
  spawnCost. `estOutputFraction` prices a bare token count when only a total is known:
  `tokens × (f × out + (1−f) × in)`.
- Driver cost: `DRIVER.json` `{session_id, transcript_path, cursor}` in the main checkout
  (gitignored); on `start` and every `record`, assistant messages in the transcript from
  `cursor` onward (de-duplicated by `message.id`; usage fields `input_tokens`,
  `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and when present
  `cache_creation.ephemeral_1h_input_tokens` priced at `cacheWrite1hFactor` × the 5-minute
  rate) are priced by `message.model` against the roster (fallback `maxAgent`) and booked to
  this round; the **cursor is advanced in DRIVER.json** (session-global), so two rounds driven
  by one session never book the same turn twice. No transcript → `driverUsdPerStep` flat, never
  a $0 entry. Headless mode books no driver cost.
- Owner cost: each checkpoint turn `costToWaitForOwner + ownerHourlyRate × ownerTurnHours`;
  at the approval checkpoint `planCostPerWord × words(round.plan text)`; at the spec checkpoint
  `specCostPerWord × words(SPEC.md)` (words = whitespace-separated tokens). Charged once per
  checkpoint raised.
- Living charge at LANDING against the tip actually merged (`target`, else `base_commit`):
  for each path under `livingSourcePaths` in `git diff --name-status`, `before/after` = blob
  sizes (0 when absent), `tok(b) = ceil(b / tokenBytes)`, `price(t) = min(t, cap) × rate +
  max(t − cap, 0) × rateOver`, delta = `price(after) − price(before)`, plus `livingFileBaseCost`
  for an added file and minus it for a deleted one; plus `testBaseCost` × (matches of the
  extension's `testPatterns` regex in `after` minus `before`) for files under `testPaths`
  that are kept in the suite. One `living` entry per landed round.
- Hard stop: after every ledger append and once before each prompt render, if `total_usd >
  hardStopBudgetMultiple × budget_usd` and not `hard_stop_raised`: set it and checkpoint
  `hard-stop`; never while a checkpoint is being raised.
- `spend` prints buckets, entries, quote versus actual; `spend --project` sums the index and
  live rounds (the only command that reads across rounds, besides `status --project`).

### 4.10 Concurrency (adopted from the sibling, with fixes)

Invariants, restated for this project: I1 one round per id; I2 nothing created until the
claim wins; I3 each round in its own worktree, reading nothing of siblings except best-effort
`git show`; I4 nothing touches `main` before LANDING; I5 one runner per round, fenced by
non-forced pushes; I6 `main` on origin only fast-forwards and holds each landed round on top of
everything landed meanwhile; I7 no force-push, no automatic conflict resolution; I8 exactly one
living entry per landed round, priced against the merged tip; I9 `check` never pushes, tags,
moves a branch or writes the ledger; I10 agents get no push credential and the HEAD fence
undoes commits; I11 all state is committed after every step and `next` is re-entrant. No
leases, heartbeats, TTLs or takeovers.

**Claim** (`gitx.claim`): `git fetch origin`; ids from `refs/remotes/origin/round/<tail>`
with `tail.isascii() and tail.isdigit()`; `rid = 1 + max(local folder ints, origin ints)`;
loop `pushAttempts` times: `git push --porcelain --force-with-lease=refs/heads/<branch>:
origin HEAD:refs/heads/<branch>`; **won ⇔ exit 0 and a stdout line starting with `*`**
(`=` is a loss even at exit 0, as measured on this machine; `!` is a loss); explicit
`--branch` pushes exactly once and errors on a loss; otherwise `rid += 1` without re-fetch.
Then `git worktree add -b <branch> <main_root>/<worktreeDir>/NNNN HEAD`; a failure there
leaves the claim claimed and errors (a rerun takes the next id).

**Fence**: every `record` pushes; a rejected push is a hard stop with the fixed message.

**Runner pinning**: `run.py` given `--round N` (or `--root DIR` pointing at a worktree)
compares its own path with `<worktree>/harness/src/run.py`; when they differ and the latter
exists, it re-executes that file with the same arguments (`subprocess.run`, same stdio,
propagated exit code). Written down in PROCESS.md: the round's own runner drives the round.

**LANDING, check phase** (also `check` at LANDING): target = `origin/<mainBranch>` after a
fetch when it exists, else local `<mainBranch>`, else none. `git merge-tree --write-tree
--name-only <target> HEAD`: conflicts → finding `L1` (quote = the conflicted paths) and the
worktree untouched; clean → `git merge --no-edit <target>` (a merge commit on the round
branch; a no-op when already contained), then `verify` and `suiteCommand` under the timeout →
`L2` on failure. The check phase never pushes, tags, charges or moves a branch.

**LANDING, land phase**: loop `pushAttempts`: living charge computed against the merged tip;
`git push origin HEAD:refs/heads/<mainBranch>` (never `git branch -f` on a possibly
checked-out main); rejected → re-run the check phase (re-fetch, re-merge, re-verify) and retry;
findings on a retry return them; exhausted → error, state unsaved, rerun lands again. After a
successful push: the living entry (once), tag `round/NNNN-landed`, `landed_at`, `main_before`
= the target's sha before the merge, and local `<mainBranch>` updated by `git fetch origin
<main>:<main>` when it is not checked out anywhere (else a FLAG; the checkout catches up on
its own). Without an origin: `git branch -f` when main is not checked out; when the main
checkout has it checked out and clean, `git -C <main_root> merge --ff-only HEAD`; otherwise
error.

**Conflict re-entry (the fix)**: on `L1`, `merge_pending = {target, target_sha,
automerge_tree (the tree oid merge-tree printed, conflict markers included), conflicted}`;
the runner runs `git merge <target>` (stops with conflicts in the tree and index) and re-enters
SPEC-TO-IMPLEMENTATION at the next attempt with `L1` and `step.conflicts` set; the plumbing
tells the agent to resolve and `git add` those files only. On `record`: unmerged index entries
remain → finding `L3`, attempt fails; else the runner commits (a merge commit, since
`MERGE_HEAD` exists), and M1/M2 are measured as `git diff --name-only <automerge_tree> HEAD`
(the hand edits) against write paths ∪ round folder ∪ `conflicted`; M3 runs; `merge_pending`
cleared. The next LANDING check finds the merge already contained and proceeds. Byte-identical
retries are impossible by construction because the merge base moved.

**After the last commit**: `sync_main` exactly as the sibling (fast-forward-only, timid,
returns `main_synced`), using `git push origin HEAD:refs/heads/<main>` and the same local
update rule as landing.

**Preconditions enforced by `start`**: `.gitignore` has `<worktreeDir>/`; origin exists
(unless `--no-branch`); git ≥ 2.38 (for `merge-tree --write-tree`). **`status --project`**
lists local folders, origin `round/*` branches, tags, and flags claimed ids with no commit
beyond the claim ("stale claim").

### 4.11 Agents

**Driver mode (primary).** The driver is the Claude Code session in the main checkout. It
runs `next`, reads `prompt_file`, and calls the Agent tool with `subagent_type` =
`action.agent_type` (`shackles-gate` is defined with `tools: Read, Grep, Glob`;
`shackles-producer` with default tools), `model` = `action.model_alias`, `prompt` = the file's
content verbatim (the Agent tool takes no file; "verbatim" means the whole text), no isolation
(the worktree is named in the prompt and lies inside the repo, so file tools reach it). It
saves the sub-agent's final message to `result_file` exactly as returned and runs `record`,
passing `--usage` when the tool result reports token usage, else nothing (estimate). Effort
cannot be set per Agent-tool call today; the definition files carry `model: inherit` and the
limitation is documented (headless mode sets `--effort`).

**Headless mode** (`run --until checkpoint|step|done [--no-push]`): `next` → `agentCommand`
with `{prompt_file} {model} {effort} {max_turns} {budget_usd} {tool_flags}` substituted
(`{tool_flags}` expands to `gateToolFlags` or `producerToolFlags`), `cwd` = worktree, env
minus `scrubEnv`, timeout `wall_clock_seconds`; stdout JSON's `result` is the message and
`total_cost_usd` the cost → `record --cost`. Up to `infraRetries` retries per run on timeout,
non-JSON stdout, or non-zero exit; each retry resets the tree, counts an infra error and is
committed. `claude` resolution: `claudePath`, else PATH, else the newest
`%APPDATA%\Claude\claude-code\*\claude.exe` (version-sorted), reported by `doctor`.
`doctor --agent` performs one $0.01-class real call (`--max-budget-usd 0.05`, prompt "reply
OK") only when asked.

### 4.12 Owner interface

- `src/owner_hook.py`: stdin JSON; `SessionStart` (argument `--session-start`) and
  `UserPromptSubmit` both write `harness/DRIVER.json` `{session_id, transcript_path,
  updated_at, cursor?}` (cursor preserved); `UserPromptSubmit` appends `<UTC ISO Z>\t<message
  with \ and newline escaped>` to `harness/OWNER.log` unless the prompt is empty or starts with
  an envelope marker (`<task-notification`, `<system-reminder`, `[SYSTEM NOTIFICATION`,
  `<wake `, `<webhook-payload`, `<event `). Root = `CLAUDE_PROJECT_DIR` or cwd; never raises.
- `run.py owner "<text>"` appends the same line shape (for tests and hookless drivers).
- Word recognition (`owner.words`): the message, unescaped, lower-cased, stripped of leading
  punctuation; with `ownerWordMode: start` a word counts only when the message's first word is
  one of `ownerWords[kind]` (so "I don't approve" and a pasted gate prompt never count).
  `delegate through STEP` → `through:STEP` (upper-cased, must be a pipeline step else ignored
  with FLAG); `override A B` → the named steps or gates added to `overrides` (never
  CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, LANDING; `PLAN-TO-SPEC` refused with a usage error since
  nothing can run without a spec); `abandon` anywhere. Only lines with timestamp ≥
  `presented_at` (approval) or > `checkpoint.at` (resume) are considered; the last qualifying
  message wins. At a `question` checkpoint the first non-word message after `checkpoint.at`
  is the answer.
- Checkpoints print JSON and exit 10; DRIVER.md tells the driver to relay `question` to the
  owner in chat and to wait; the hook records the reply; rerun `next`.

### 4.13 CLI reference

Global: `--root DIR` (a checkout or worktree; default cwd's repo) or `--round N` (derives the
worktree from `main_root` + `worktreeDir`), `--verbose`. Exit codes: 0 ok/finished, 1 error,
2 usage or guard refusal, 3 check failed, 10 checkpoint.

| Command | Reads | Writes / prints |
| --- | --- | --- |
| `doctor [--agent] [--json]` | everything | health report (4.14); exit 3 on hard problems |
| `plan` | spec | prints the rendered CHAT-TO-PLAN prompt (no round) and the PLAN schema |
| `render STEP [--attempt N] [--fixture]` | spec, round if any | prints a prompt; `--fixture` uses a synthetic round; no state change |
| `start ...` | plan, origin, owner log | claim, worktree, round folder, commit, push; one JSON line |
| `next [--no-push]` | STATE, owner log, git | mechanical effects, prompt, STATE, commit; action or checkpoint JSON |
| `record ...` | result, STATE | RESULTS/, FINDINGS/, STATE, HISTORY, commit + push |
| `run --until ... [--no-push]` | | headless loop |
| `status [--project] [--json]` | STATE (+ index, origin refs) | summary |
| `spend [--project] [--json]` | STATE, index | ledger summary |
| `check` | STATE, git, verify/suite | current step's mechanical findings; exit 3 if any |
| `abandon --reason R` | STATE | abandoned status, tag, index line, commit |
| `owner "<text>"` | | appends to `<main_root>/harness/OWNER.log` |
| `baseline [--check] [--note TEXT]` | spec files | `tests/spec_baseline.json`; `archives/SPEC-CHANGES.md` |

All commands are also callable in-process: `run.main(argv) -> int` with stdout/stderr going
through `sys.stdout`/`sys.stderr` (tests capture with `capsys`).

### 4.14 Doctor and spec baseline

`doctor` reports, each line `OK|WARN|FAIL <topic>: <detail>`: python version; PyYAML,
pytest importable; git version and identity; `claude` path and version; spec.yaml files all
exist; pipeline derivation (unknown steps, disabled gates, order deviations, ignored
checkpoints); every prose file's includes resolve; every producer and gate prompt renders with
a synthetic round and lists unresolved keys; config keys using defaults; unknown config keys;
`ownerWords` each appearing somewhere in the spec text (a heuristic WARN when a configured word
is absent); worktreeDir ignored; origin reachable (`git ls-remote`, WARN on failure); stale
claims. `--json` for tests.

Baseline (`baseline.py`): `harness/tests/spec_baseline.json` = `{"spec_yaml": sha256,
"commit": sha, "files": {path: sha256}}` over `spec.yaml` and every listed file (LF-normalised
bytes so autocrlf cannot trip it). `check(root) -> {changed, added, removed, missing, ok}`;
the test (5.4) fails with a message naming each file, `git diff <commit> -- <paths>` truncated
to 200 lines when the commit is known, and the instruction: review effects with
`py -3.13 harness/src/run.py doctor`, then `baseline --note "<what was reviewed>"`. `baseline`
rewrites the JSON and appends `<ts> <commit> <files> <note>` to `archives/SPEC-CHANGES.md`.

### 4.15 Documentation

`INDEX.md` lines: `process, rules, steps, checkpoints, words, findings, checks, costs, landing
-> harness/docs/PROCESS.md`; `driving a round, spawning, record, recovery -> harness/docs/DRIVER.md`;
`tests, fixtures, stub, system tests, baseline -> harness/docs/TESTING.md`; `config, defaults ->
harness/src/runner.yaml, harness/project.yaml (owner), harness/local.yaml (machine)`; `spec
files -> spec.yaml`; `runner, commands, exit codes -> harness/src/run.py --help`; `contracts,
result JSON, verdict JSON -> harness/src/plumbing/`; `schemas -> harness/src/shackles/schemas.py`;
`rounds, archives, index -> harness/archives/rounds/`; `owner log, driver pointer, hooks ->
harness/src/owner_hook.py, .claude/settings.json`; `agent definitions -> .claude/agents/`;
`spec changes -> harness/archives/SPEC-CHANGES.md, harness/tests/spec_baseline.json`.

`PROCESS.md` is normative and dense (≤ 150 lines): principles; the pipeline table; kinds;
checkpoints and words; delegation and overrides; result and verdict contracts (by reference to
plumbing); findings lifecycle; mechanical checks table; costs; landing and conflict re-entry;
concurrency invariants; recovery; what is frozen when. One sentence per line where practical
(keeps merges clean). `DRIVER.md` (≤ 80 lines) is the exact operating sequence: `doctor`,
`plan`, draft to `harness/DRAFT-PLAN.json`, wait for the word, `start`, the
`next`/spawn/save/`record` loop with the Agent-tool parameters, checkpoint etiquette, cost
flags, what to do on `push rejected`, crash, or `L1`. `TESTING.md` (≤ 80 lines): commands,
fixtures, stub modes, system tests and their budget cap, baseline procedure.

### 4.16 Robustness rules the implementer follows

No `shell=True`; every subprocess is an argv list with `cwd`, `capture_output=True`,
`text=True`, `encoding="utf-8"`, `errors="replace"`, and a timeout where the command is not
git. git calls set `GIT_TERMINAL_PROMPT=0`. Paths compared after `os.path.normcase` and
forward-slash normalisation; prefix checks use `PurePosixPath` parts, not string prefixes
(`src/` must not match `src2/`). JSON files written atomically (temp file + `os.replace`).
Timestamps UTC `%Y-%m-%dT%H:%M:%SZ`. `PYTHONUTF8=1` set for child Pythons. Quotes in findings
truncated to `findingQuoteMaxChars`. No module-level side effects; `run.main` builds
everything from `--root`.

## 5. Test strategy

Suite: `py -3.13 -m pytest` from the repo root (pytest.ini). Target: the permanent suite under
90 s on this machine; system tests excluded by default.

### 5.1 Fixtures (`harness/tests/conftest.py`, `fixtures/`)

- **`hermetic_git`** (session): env with `GIT_CONFIG_GLOBAL` = an empty temp file,
  `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, `GIT_AUTHOR_NAME/EMAIL`,
  `GIT_COMMITTER_NAME/EMAIL`, `PYTHONUTF8=1`; fixtures set `core.autocrlf=false`,
  `core.longpaths=true`.
- **`Repo(tmp, spec="fixture"|"real", gates=None, config=None)`**: a temp repo containing a
  copy of `harness/src` and `harness/src/plumbing`, a `harness/` spec built from
  `fixtures/spec/` (minimal `AGENTS.md`, a `project.yaml` generated from a template with
  living paths `../src/ ../tests/ docs/`, a copy of the real `subAgents.yaml` shape, and
  generated prose files: each `<STEP>-OVERVIEW.txt` is one line naming the step plus the
  includes and plumbing tokens the real files use; gate files likewise), `spec.yaml`, a
  `.gitignore` with `.worktrees/`, and the **miniproject** (`src/`, `tests/`, a `verify` of
  `py -3.13 -m pytest -q tests`); `spec="real"` copies the repo's actual spec files instead
  (for the smoke tests only). `runner.yaml` overrides: `agentCommand` → the stub,
  `suiteCommand` → the miniproject's pytest, `driverUsdPerStep 1.0`. Methods: `run(*argv)` →
  `Result(code, stdout, stderr, action)` in-process by default, `subprocess=True` for the CLI
  contract tests; `git(...)`; `read/write/json(path)`; `owner(text, at=None)` appends an
  owner line with a controllable timestamp; `add_origin()` (bare, `symbolic-ref HEAD
  refs/heads/main`, absolute path); `clone()` ("another machine"); `view(worktree)`; `play(
  until=STEP, mode="pass")` drives a round in-process with `stub_agent.perform`.
- **`Origin`**: `sha(branch)`, `branches()`, `install_reject_hook(pattern, n|"all")`,
  `install_move_and_reject_once_hook()`, `hook_log()` (sh scripts; verified to run on this
  git).
- **`stub_agent.py`**: invoked as `py -3.13 stub_agent.py <prompt_file> <model> <effort>
  <max_turns> <budget_usd> [tool flags...]`; parses the last `STEP: KIND: ARTIFACT:
  RESULT_FILE: WRITE_PATHS: WORKTREE:` lines; writes canned artifacts from
  `fixtures/canned/<STEP>.*` (SPEC-TO-TESTS writes `tests/test_greet.py` + a scratch test;
  SPEC-TO-IMPLEMENTATION writes `src/greet.py`; TESTS-TO-SUITE archives the scratch test when
  `STUB_ARCHIVE=1`); prints `{"result": "<json>", "total_cost_usd": 0.01}`. Env switches:
  `STUB_MODE=pass|fail|dispute|needs_owner|upstream|blocked|garbage|deferred|commit`
  (`commit` makes a producer commit, to test the HEAD fence), `STUB_FENCE=1`, `STUB_STRAY=1`
  (writes outside its paths, for M1), `STUB_TOUCH_TESTS=1` (for M2), `STUB_BREAK=1` (impl that
  fails verify, for M3), `STUB_LOG=<file>` (argv, cwd, env keys per call), `STUB_CONFLICT=1`
  (writes a resolving version of a conflicted file, for L1 re-entry). `perform()` is the
  in-process entry.

### 5.2 Unit tests (fast, no git)

`test_prose.py`: token grammar and whitespace; namespaces; value formatting per type; include
once per document; depth and cycle errors; embed mode drops already-included prose and the
process token; unresolved keys render the placeholder and are collected; a prose file without
the process token gets it appended. `test_config.py`: layering order, defaults reported, `..`
paths, `NNNN` width from `roundPaths.folder`, roster loading. `test_pipeline.py`: KNOWN
reconciliation cases: all gates off; a gate missing; gates reordered (map wins, warning);
unknown step with and without a gate; gate without prose is an error; checkpoints ignored
when absent. `test_schemas.py`: each schema's required/optional/type messages; extra keys
allowed; RESULT/FINDINGS shapes; STATE round-trip. `test_ledger.py`: buckets; blended and
usage pricing including 1-hour cache; living charge cases (added under cap, grown across the
cap, shrunk, deleted with base refund, new test functions counted per extension, files outside
living paths free, round folder free); time cost; hard-stop threshold. `test_owner.py`: hook
line escaping; envelopes filtered; word rules (`start` mode: "approve", "Approved, delegated."
→ approve, "I don't approve" → none, "delegate through plan-to-spec" → `through:PLAN-TO-SPEC`,
"override SPEC-TO-TESTS-GATE POSTMORTEM"; unknown through-step ignored with FLAG; timestamp
filters). `test_extract.py`: JSON extraction from bare, fenced, and prose-wrapped messages.
`test_hook.py`: `owner_hook.py` run as a subprocess with stdin JSON for both events.

### 5.3 Round tests (git, single checkout `--no-branch`, stub agent, in-process)

`test_round.py`: start validates the plan before any git write (a bad plan creates nothing);
start creates folder, files, `.keep`s, judgment-call files, STATE, HISTORY, commit; approval
checkpoint raised without a word (exit 10, owner cost charged once); "approve" resumes with
checkpoints, "delegate" without; `delegate through PLAN-TO-SPEC-GATE` skips the spec review
only; each step's action JSON fields; prompt archived and committed; record guard cases (wrong
step, wrong attempt, status not active, replay) exit 2 and change nothing; a full pass round
to `done` with gates enabled (stub), asserting `step_commits`, `attempts`, FINDINGS/RESULTS/
PROMPTS per step, the archive move, the index line, `judgment_calls` counts, `main_synced`;
the same with all gates disabled (auto-PASS files with `source: disabled`; checkpoints still
raised); overrides (`override PLAN-AGENTS` → defaultShares used; `override TESTS-TO-SUITE` →
keep all; refused overrides). `test_outcomes.py`: gate FAIL → producer re-entry with findings
and `failures`; dispute → rulings applied, settled at two upholds, disputing a settled id
flagged; deferred resolutions carried to POSTMORTEM's prompt; NEEDS-OWNER with gate enabled →
gate rules; with gate disabled → `question` checkpoint, the owner's reply becomes `O1` in the
next prompt; UPSTREAM → target re-entry, downstream resets, `reentries`, round-limit
checkpoint; BLOCKED → checkpoint; failure limit → checkpoint, "approve" resets; hard stop
raised once; R1 on garbage; HEAD fence on `STUB_MODE=commit`; dirty-tree recovery counts an
infra error; out-of-band PLAN/SPEC edits re-enter correctly. `test_checks.py`: M1 (stray),
M2 (touched tests), M3 (red verify, timeout), M4, S2 pies and caps, S3 disjointness by path
parts (`src/` vs `src2/`), T1 partition, W2 on a huge prompt, W1 overlap against a sibling
branch's SPEC.json. `test_costs.py`: agent cost sources (`--cost`, `--usage`, `subagents`,
estimate + FLAG); driver cost from a fixture transcript with the session-global cursor (two
rounds, one session: each turn booked once); owner costs at approval/spec/question
checkpoints; `spend --project`. `test_cli.py` (subprocess): `--help`, exit codes, one-line
`start` output, `doctor --json` on the fixture repo, `render --fixture`, `owner`, the re-exec
pinning (a worktree copy of `run.py` that prints a marker is what actually runs).

### 5.4 Real-spec tests (the only tests that read the owner's files)

`test_spec_baseline.py`: `test_spec_files_unchanged` (the alarm, 4.14) and its own tests on a
temp copy: modified file detected with name and diff; a file added to `spec.yaml` detected as
`added`; a listed file deleted → `missing`; a file removed from the list → `removed`; clean →
ok; `baseline` rebaselines and appends the audit line; and `test_alarm_fails_on_change`, which
calls the alarm test function against a mutated temp root and asserts it raises
`pytest.fail.Exception` with the file name in the message. `test_real_spec.py`: real
`spec.yaml` files all exist and load; pipeline derives with today's map; every producer and
gate prompt renders via `render --fixture` without exception or leftover `{{`; unresolved keys
must be listed in `harness/tests/spec_waivers.json` (`{key: reason}`), otherwise the test
fails naming them (with the section 6 edit applied, the waiver file is empty). No test asserts
on any sentence of the owner's prose.

### 5.5 Concurrency tests (bare origin, hooks, clones; subprocess for the CLI-level ones)

Claim: win shape, files only in the worktree, main checkout untouched, `OWNER.log` absent in
the worktree; lost race via narrowed fetch refspec for both `=` (same commit) and `!` shapes,
`assertNothingCreated` (no folder anywhere including `git log --all`, no worktree, one local
round branch, clean, still on the starting branch); reject-all hook → exactly `pushAttempts`
pushes logged, the fixed error, nothing created; explicit `--branch` taken → one push, error;
`worktree add` failure keeps the claim and a rerun takes the next id; id sourcing from folders
and branches, ignoring `round/003-x`, `round/abc` and tags; worktreeDir not ignored → refused.
Worktree operation: owner log read from the main checkout for a checkpoint raised in a
worktree; `status/spend/check` under `--root` and `--round`; `record` pushes from the worktree.
Fence: another clone moves the round branch → the next `record` exits 1 with the message.
Landing: sibling moved main → `check` merges only (no tag, ledger, push); `run --until done`
leaves origin main == round tip containing both rounds' files with one living entry equal to
this round's diff (I8); move-and-reject-once hook → one LANDING attempt, hook log shows
rejection then acceptance; reject-all → exit 1, nothing landed, state still at LANDING, clean,
lands after the hook is removed; **conflict**: sibling edits the same line → `L1` names the
file, worktree left in a merge with markers, `merge_pending` set; the stub resolves
(`STUB_CONFLICT=1`) → `record` commits a merge commit, M1/M2 measured against the automerge
tree pass, `L3` when a file is left unmerged, then LANDING lands; a hand edit outside the
allowed set during resolution → M1. Post-round `sync_main` true/idempotent/false cases.
Pinning: a worktree whose `run.py` differs is the one that runs. Version skew: a project.yaml
on main with a new key does not break a round pinned at an older `spec_commit`.

### 5.6 Real-agent system tests (`harness/tests/system/`, opt-in)

Enabled by `SHACKLES_SYSTEM=1`; `SHACKLES_SYSTEM_BUDGET_USD` (default 2.0) caps each run via
`--max-budget-usd`; every run appends `{test, step, agent, cost, verdict, at}` to
`harness/tests/system/RUNS.jsonl` (committed: it calibrates shares and quotes). Agent =
`project.systemTestAgent` unless `SHACKLES_SYSTEM_AGENT` names a rung.

1. **Gate replays** (`test_gate_replays.py`, parametrised over every enabled-able gate): for
   each gate, `fixtures/system/<GATE>/good/` and `bad/` hold a complete round folder state
   (plan, spec, artifact under judgment, findings); the test builds a temp round at that
   state, renders the real gate prompt from the real prose, runs the real agent headless with
   `gateToolFlags`, and asserts PASS on good, FAIL on bad (with at least one blocking finding
   whose `quote` appears in the artifact). This is the direct measure of the two things the
   owner worries about: can gates be passed, and do they catch defects. About $0.5-2 per gate.
2. **Step replays** (`test_step_replays.py`): each producer from canned upstream state (the
   PLAN-AGENTS run from a canned plan, PLAN-TO-SPEC from plan + agents plan, and so on),
   asserting the artifact passes the mechanical checks and `record` accepts the result
   contract. About $1-5 per step.
3. **End-to-end mini round** (`test_e2e_mini.py`): the owner's throwaway task — the
   miniproject's `greet()` — as a headless `run --until done` with real agents, gates on,
   delegated; asserts landed, suite green, index line written. Run once per significant
   change; gates-off variant is one env flag.
4. Every other variant the owner listed (checkpoints, approval skips, upstream, blocked,
   conflicts, fences, hard stops) is exercised by the stub for free (5.3, 5.5).

Why this is cheaper and more comprehensive than end-to-end runs alone: judgment is the only
thing a real model adds, and judgment lives in gates and single steps; replays isolate each
prompt so a failure names the prose responsible, cost a dollar or two instead of a full
round, can be rerun after every prose change, and the replay fixtures double as the
"defective artifact" corpus that measures gate effectiveness — which an end-to-end run of a
tiny task never measures (nothing in it is defective on purpose).

## 6. Spec edits

Exactly two lines, both the same defect: two prose files reference `project.ownerReviewCostPerWord`,
which `project.yaml` does not define (it defines `planCostPerWord` and `specCostPerWord`).
Without the edit the runner renders `[[UNRESOLVED: project.ownerReviewCostPerWord]]` in those
prompts (it never crashes) and the smoke test requires a waiver. Recommended minimal edits:

```diff
--- harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
--- harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```

The implementer applies them in a separate commit titled `SPEC EDIT: resolve
ownerReviewCostPerWord`, records both diffs in `harness/archives/SPEC-CHANGES.md` via
`baseline --note`, and repeats the diffs in the final report. If the owner prefers no edit,
add `{"project.ownerReviewCostPerWord": "owner declined the edit; see plan-4 §6"}` to
`spec_waivers.json` instead. No gate language is relaxed: COMMON-GATE's cost rule ("FAIL only
when the defect ... costs more than [a retry]") already tempers the per-line "Fail" lists, and
the gate replays (5.6) will show whether relaxation is needed before anyone edits wording.

Observed but deliberately not edited: `subAgents.yaml`'s `high` rung is named "Fable 5.1 Low"
(the runner uses keys only); `AGENTS.md` says "grep `INDEX.md`" and this plan puts it at
`harness/INDEX.md`, next to it.

## 7. Build order and acceptance

One session, in this order; each milestone ends with its tests green and a commit.

- **M0 scaffold**: layout, `.gitignore`, pytest.ini, config layering, spec loader with pinned
  reads, pipeline derivation, prose engine, plumbing files, schemas, `render`, `plan`,
  `doctor`, baseline + `SPEC-CHANGES.md`, hooks, agent definitions. Accept: `doctor` on this
  repo shows no FAIL; 5.2 and 5.4 green; the baseline JSON committed; the section 6 edit
  applied and audited.
- **M1 rounds, single checkout**: `start --no-branch`, `next`, `record`, `abandon`,
  `status`, `spend`, `owner`, ledger, checkpoints and words, stub agent, `Repo`. Accept: 5.3
  green; a stub round runs to `done` in under 20 s.
- **M2 checks and local landing**: M1-M4, S/T/W checks, `check`, archive move, living charge,
  merge-tree conflict path and re-entry, index line, sync without origin. Accept:
  `test_checks.py`, `test_costs.py`, local landing and conflict tests green.
- **M3 concurrency**: claim, worktrees, fence, push loops, `status --project`, pinning,
  `Origin` fixtures. Accept: 5.5 green, whole suite under 90 s.
- **M4 agents and docs**: headless `run`, claude discovery, `doctor --agent`, DRIVER.md,
  PROCESS.md, TESTING.md, INDEX.md, README, CLAUDE.md. Accept: `doctor` finds `claude.exe`
  on this machine; a stub headless `run --until done` passes; docs match the code (a
  reviewer reads PROCESS.md against `next`/`record`).
- **M5 system tests**: fixtures for gate and step replays, `RUNS.jsonl`, e2e mini. Accept:
  runnable and skipped by default; run for real only on the owner's go, starting with two gate
  replays (PLAN-TO-SPEC-GATE good/bad) to price the loop.

Definition of done: every invariant in `harness/AGENTS.md` holds by construction (listed
against the mechanism in PROCESS.md); every command in DRIVER.md was executed once on the
fixture; no test depends on a sentence of the owner's prose; the final report lists the two
spec diffs, the defaults the runner supplies for missing keys, and every WARN `doctor` prints.

## 8. Risks and open questions, with recommendations

1. **`ownerReviewCostPerWord`** (section 6): recommend the two-line edit.
2. **Step order and checkpoints are runner-owned** (4.3, `checkpointAfter`): recommend
   keeping them in `runner.yaml`, readable as an optional `project.yaml` key of the same name
   should the owner want to own them; doctor reports the effective order.
3. **`maxRoundAttempts`** is read as the number of re-entries (UPSTREAM or landing conflict)
   before a `round-limit` checkpoint. Alternative: total gate rejections; rejected because
   `maxFailuresBeforeStop` already covers that per step.
4. **`testBaseCost` counting** by regex per extension is an approximation; recommend it,
   with a documented `testPatterns` override; an exact pytest collection count is a later
   TODO.
5. **Owner word rule** (first word of a message) trades a little owner convenience for zero
   false positives from pasted prompts; DRIVER.md tells the driver to ask for a reply that
   starts with the word. Alternative `anywhere` mode is one config line.
6. **Driver mode cannot set effort or read sub-agent cost reliably**; recommend accepting
   estimates in driver mode and using headless mode for delegated rounds and all system
   tests, where cost and effort are exact.
7. **`claude.exe` path churn on app updates**: discovery picks the newest version directory;
   `local.yaml` pins it when needed; `doctor` says which was chosen. `bypassPermissions` in
   `-p` may need `--allow-dangerously-skip-permissions` or the desktop trust prompt on this
   machine; `doctor --agent` is the check, and `agentCommand` is config, not code.
8. **`merge-tree --write-tree` semantics** (conflict markers in the written tree, exit 1 on
   conflict): git 2.45 documents them; the implementer confirms with one fixture test before
   relying on the automerge tree; fallback if a git build misbehaves: use the pre-merge HEAD as
   the M1/M2 base and allow only the conflicted files.
9. **Hooks fire in every session in the repo**, including ones not driving a round; the
   OWNER.log then carries unrelated messages. Harmless under the first-word rule and the
   `presented_at`/`checkpoint.at` windows; documented.
10. **Prompt size**: whole artifacts are inlined (plan, spec, findings, history for
    POSTMORTEM); W2 warns, PLAN-TO-SPEC-GATE may fail a spec as too large, and the round
    then splits the work; no truncation is done silently.
11. **Gates may fail everything** under the current "Fail" lists; the gate replays measure
    it before any wording is touched; if relaxation is needed, propose the smallest edit with
    replay evidence, flagged as in section 6.
12. **Windows**: the suite spawns many git processes; in-process driving keeps it tractable;
    `core.longpaths` and the Windows Store `python3` stub are avoided by construction; the
    sibling's `#!/bin/sh` hooks work here because the conda git ships `sh`, which `doctor`
    verifies for the test environment (WARN, not FAIL, since production never needs hooks).
13. **Living-path semantics for an embedded harness** (`../src/`): tested through the
    miniproject fixture, which is the general-project case the vision names; the harness's
    own `src/ docs/ tests/` case is exercised by the real-spec smoke test.
14. **Living tokens charge the runner's own growth** once rounds run on this repo; section
    4.1's size budget and "one sentence per line" docs keep the first rounds' landing charges
    and merge conflicts small.
