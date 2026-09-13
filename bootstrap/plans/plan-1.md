# shackles_harness — implementation plan (plan-1)

Target: everything in the repository except the owner's spec files (`spec.yaml` and the files it lists) and `bootstrap/`.
Stack: Python 3.13 (`py -3.13`), PyYAML, pytest, git; Windows 11 / PowerShell; no other dependencies.
Executed by one implementing agent in one session, then reviewed, then tested. The bootstrap is ordinary engineering; the harness's runtime invariants (harness/AGENTS.md) bind agents *inside* rounds, not this build.

Vocabulary used below: **spec files** = the files spec.yaml lists (owner-owned, change often, never parsed for wording); **runner** = `harness/src/run.py` plus its modules (deterministic, no LLM); **driver** = the LLM session that runs `next`/`record` and spawns fresh sub-agents; **producer/gate** = the step agents; **round** = one branch `round/NNNN`, one worktree, one folder `harness/archives/rounds/NNNN/`.

---

## 1. How this plan was made

1. Read every file in the worktree: `spec.yaml`, the four config/prose spec files, all 18 locked prose files, `bootstrap/vision-harness-round-concurrency.md`.
2. Extracted every `{{ … }}` key the prose uses (the renderer's required namespace, §5.5) and every structural fact the prose states about the pipeline (gate list and order in `project.yaml`, "checkpoint after this step" in PLAN-TO-SPEC and CLEANUP, POSTMORTEM has a gate, CLEANUP has none, CHAT-TO-PLAN-GATE is mechanical). Found one unresolvable key: `project.ownerReviewCostPerWord` (project.yaml has `planCostPerWord`/`specCostPerWord`) — §7.
3. Checked specific points in the sibling (`C:\Users\twolf\Claude\vision_harness`, read-only): `run.py` (claim, next/record routing, landing loop, sync, living charge, result unwrapping), `schemas.json`, `stub_agent.py`, the `Repo`/`Origin` test fixtures and hook scripts, `docs/PROCESS.md`, the `COMMON-PROCESS`/`COMMON-GATE-PROCESS` plumbing, one rendered prompt, one `STATE.json`, `HISTORY.md`, and the round 004/005 postmortems (the real parallel-round failures). Used to verify and to harvest failure modes, not copied.
4. Probed this machine (scratchpad only, nothing touched the screen): `py -3.13` = 3.13.2, PyYAML 6.0.3, pytest 9.1.1, git 2.45 (conda MinGW build, `sh.exe` present, no `core.hooksPath`). Built a bare origin with an `update` hook and pushed: **hooks run**, rejection shows as `!` exit 1; a CAS push `--force-with-lease=refs/heads/round/0001:` of a ref that already exists at our HEAD returns **`=` and exit 0**, so a win must be "exit 0 and a `*` line"; `git clean -fd` spared a nested linked worktree (nested repo), but the ignore precondition is kept; `core.autocrlf=true` comes from conda's system gitconfig, so byte hashes of spec files must normalize line endings. `claude` is the desktop-bundled binary, not on PATH in PowerShell: driver mode is primary, headless mode is probed by `doctor`.
5. Listed what an LLM-operated harness of this kind needs and what the sibling's postmortems show missing (§3), chose what to include, designed, wrote, then re-read against the hard constraints.

---

## 2. Facts the spec files fix, and how the runner stays independent of their wording

- Paths in `project.yaml` are relative to the **harness root** `harness/` (the directory containing `project.yaml`): living paths are `harness/src/`, `harness/docs/`, `harness/tests/`; locked prose `harness/locked_prose/`; rounds `harness/archives/rounds/NNNN/`. The id width (4) is derived from the run of `N` in `roundPaths.folder`, never hard-coded; every round file name comes from `roundPaths`.
- Pipeline (derived from `project.gates` order + which `*-OVERVIEW.txt`/`*-GATE.txt` files exist + the runner's own step table, §5.4): CHAT-TO-PLAN → CHAT-TO-PLAN-GATE (mechanical approval, checkpoint) → PLAN-AGENTS → gate → PLAN-TO-SPEC → gate (checkpoint after) → SPEC-TO-TESTS → gate → SPEC-TO-IMPLEMENTATION → gate → TESTS-TO-SUITE → gate → CLEANUP (mechanical checks after; checkpoint before landing) → LANDING (mechanical) → POSTMORTEM → gate → finished.
- The runner **renders** spec prose and **reads** spec YAML keys; it never parses prose text for behaviour. Every structural coupling is explicit and linted (§5.2): unknown/missing keys degrade to defaults with a warning, unresolvable template keys render as visible `[unset: key]` placeholders, extra or missing prose files are reported, gate enable flags are read by name from `project.gates`.
- Owner-word vocabulary (approve/delegate/delegate through/override/abandon) lives in `runner.yaml`; the lint warns if a word is absent from all locked prose (soft cross-check only).

---

## 3. Standard features missing from a brand-new harness — what this plan includes

| # | Feature | Why | In plan |
| --- | --- | --- | --- |
| 1 | **Spec-change fingerprint test**, itself tested | Owner's hard requirement; the sibling had nothing; prose changes silently changed agent behaviour | §5.10, §6.3 |
| 2 | **`doctor` preflight + spec/pipeline lint** | Sibling failed late on unenforced preconditions (worktree dir not ignored, main checked out, config key skew) | §5.2, §5.11 |
| 3 | **Graceful template resolution** (`[unset: key]`, never crash) | Spec files change arbitrarily | §5.5 |
| 4 | **Converging landing-conflict path** | Sibling's L1 loop could not converge ($11.22, hand merge) | §5.9 |
| 5 | **Pinned prose + config + runner per round** (`prose_commit`) | Sibling broke in-flight rounds when a sibling landed new config | §5.3, §5.5 |
| 6 | **Don't reset a producer's unrecorded work** (`pending_action`) | Sibling deleted an uncommitted artifact after a failed `record` | §5.4 |
| 7 | **Cross-round path overlap warning** at spec time | Sibling only discovered clashes at landing | §5.9 |
| 8 | **`deferred` resolution status** | Producers had to mark unfixable findings "fixed" every step | §5.4 |
| 9 | **Judgment-call monitoring** (files created at start, counts in status/history/index, surfaced at checkpoints) | It is the project's stated purpose | §5.3, §5.6 |
| 10 | **Token-priced ledger from `subAgents.yaml`** with `spawnCost` floor, plus per-checkpoint owner cost and plan/spec word costs | Sibling's ledger was hand-typed guesses for five rounds | §5.8 |
| 11 | **`rounds`, `prune`, `note`, `owner-say`** operator commands | Claimed ids and worktrees accumulate; drivers need to flag things | §5.11 |
| 12 | **`render`/`chat` offline prompt rendering + golden fixture render test** | Owner edits prose often; see the effect without spending an agent | §5.5, §6.2 |
| 13 | **`sandbox` + `probe`/`probe-check`: single-step real-agent probes and gate-defect fixtures** | Cheaper, attributable real-agent testing (§6.5) | §5.11, §6.5 |
| 14 | INDEX.md, docs/PROCESS.md, docs/TESTING.md, README, `.gitignore`, owner-log hook | AGENTS.md points at them; nothing exists | §5.13 |

Deferred (named non-goals for the bootstrap): transcript-based driver pricing (sibling's double-counting mess; flat `driverUsdPerStep` instead), lease expiry/stale-holder takeover (by design), mechanising the plan's validation items, external-repo targets (paths go through one resolver so this stays cheap later), a TUI/daemon.

---

## 4. Repository layout to build

```
.gitignore                    harness/OWNER.log, harness/DRIVER.json, .worktrees/, __pycache__/, *.pyc, .pytest_cache/
.claude/settings.json         UserPromptSubmit hook -> py -3.13 harness/src/owner_log_hook.py
README.md                     5 lines: what this is, entry points, how to run the suite
harness/
  INDEX.md                    routing index (alias -> canonical), not a living path
  SPEC-FINGERPRINT.json       accepted spec hashes (runner-owned metadata; always an allowed path)
  docs/PROCESS.md             normative rules; one sentence per line (merge-friendliness)
  docs/TESTING.md             suite layout, fixtures, real-agent loop
  src/run.py                  CLI entry; argparse; dispatch only
  src/shackles/               package: config.py gitops.py render.py rounds.py (state, next/record) checks.py
                              ledger.py landing.py fingerprint.py owner.py probe.py  (merge small ones freely)
  src/runner.yaml             runner-owned config: step table, owner words, defaults, agent command
  src/schemas.json            PLAN, AGENTS_PLAN, SPEC, SUITE, RESULT, FINDINGS, STATE
  src/plumbing/*.txt          HEADER, producer, code, gate, chat, GATE-DISABLED (rendered into {{ plumbing.* }})
  src/owner_log_hook.py
  tests/conftest.py, stub_agent.py, test_*.py, fixtures/golden-round/, fixtures/throwaway-plan.json
  archives/rounds/            created by the first start; index.jsonl appended per finished round
```

Sizes to expect: runner ≈ 2,000 lines total across modules, tests ≈ 2,500, docs ≈ 250. Everything under `harness/src`, `harness/docs`, `harness/tests` is living (charged per token from the first real round on), so write densely.

---

## 5. Design

### 5.1 Conventions

- All paths in JSON/STATE/artifacts are repo-relative with forward slashes; absolute paths only in printed actions (`worktree`, `prompt_file`, `result_file`).
- All timestamps UTC `YYYY-MM-DDTHH:MM:SSZ`. All files UTF-8, `\n`, written atomically (`tmp` + `os.replace`).
- Commands print exactly one JSON object on stdout; humans read stderr (`shackles: …`; `--verbose` echoes git). Exit codes: 0 ok/finished, 1 error, 2 usage/contract, 3 check failed, 10 checkpoint.
- git is called with `-c user.name=shackles -c user.email=shackles@localhost`, a per-call timeout (`gitTimeoutSeconds`, default 120; network ops 300), never `shell=True`. Verify/suite commands are argv lists run from the repo root with `verifyTimeoutSeconds`.
- Config keys are read through one accessor with defaults (`cfg.get("maxTurnsPerRun", default)`); a missing key logs one warning per command.

### 5.2 Configuration

**`harness/project.yaml`** (spec): read verbatim at `prose_commit` (`git show <sha>:harness/project.yaml`) for a round; from the working tree when no round exists. Every key the prose references is exposed as `project.<key>`; runtime additions: `project.remaining` (project budget minus `spend --project`).

**`harness/subAgents.yaml`** (spec): `agents.<rung>` with `name, model, effort, inputUsdPerMTok, outputUsdPerMTok, cacheReadUsdPerMTok, cacheWriteUsdPerMTok, spawnCost`. `project.maxAgent/gateAgent/systemTestAgent` are rungs. An unknown rung anywhere falls back to `maxAgent` with a warning.

**`harness/src/runner.yaml`** (runner-owned, living):

```yaml
mainBranch: main
worktreeDir: .worktrees                 # repo-relative; must be gitignored (start refuses otherwise)
pushAttempts: 5                          # bounds the claim loop and the landing push loop
gitTimeoutSeconds: 120
suiteCommand: [py, -3.13, -m, pytest, -q, harness/tests]
ownerDecisionMinutes: 12                 # owner attention charged per checkpoint at project.ownerHourlyRate
testFunctionPattern: '^\s*(async\s+)?def\s+test_\w+'   # counts suite tests for project.testBaseCost
checkpoints: [CHAT-TO-PLAN-GATE, PLAN-TO-SPEC-GATE, CLEANUP]   # a checkpoint follows each of these
ownerWords:                              # case-insensitive regexes, tried in this order, last matching log line wins
  abandon: '\babandon(ed)?\b'
  delegate-through: '\bdelegated?\s+through\s+([A-Za-z][A-Za-z0-9-]*)'
  delegated: '\bdelegated?\b'
  approved: '\bapproved?\b'
  override: '\boverride\s+((?:[A-Za-z][A-Za-z0-9-]*[\s,]*)+)'
steps:                                   # producers/code/mechanical in order; gates are derived (5.4)
  - {name: CHAT-TO-PLAN, kind: chat, artifact: plan}
  - {name: PLAN-AGENTS, kind: producer, artifact: agentsPlan, schema: AGENTS_PLAN}
  - {name: PLAN-TO-SPEC, kind: producer, artifact: spec, schema: SPEC, prose: specProse}
  - {name: SPEC-TO-TESTS, kind: code, paths: testPaths}
  - {name: SPEC-TO-IMPLEMENTATION, kind: code, paths: implPaths, verify: true, freezeTests: true}
  - {name: TESTS-TO-SUITE, kind: producer, artifact: suite, schema: SUITE}
  - {name: CLEANUP, kind: code, paths: implPaths, extraPaths: [INDEX.md], verify: true, freezeTests: true}
  - {name: LANDING, kind: mechanical}
  - {name: POSTMORTEM, kind: producer, artifact: postmortem}
headless:
  agentCommand: [claude, -p, --output-format, json, --system-prompt-file, "{prompt_file}", --model, "{model}",
                 --effort, "{effort}", --max-turns, "{max_turns}", --max-budget-usd, "{budget_usd}",
                 --permission-mode, bypassPermissions, "{tool_flags}",
                 "Do the task in your system prompt. Your final message must be the result JSON it asks for."]
  gateToolFlags: [--disallowedTools, Edit, Write, MultiEdit, NotebookEdit, Bash]
  producerToolFlags: [--disallowedTools, "Bash(git push:*)", "Bash(git commit:*)"]
  scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]
```

`artifact` values are keys of `project.roundPaths.artifacts`; `extraPaths` are harness-root-relative. The step table is data so the owner can reorder or add a step without touching code; each `kind` must have a handler in code (loader error otherwise).

**Lint** (run by `doctor`, strictly by `start`, as warnings by every other command): every `producer`/`code`/`chat` step has `locked_prose/<NAME>-OVERVIEW.txt` (start: error); every `*-OVERVIEW.txt` names a step (warning: "prose for unknown step"); every `*-GATE.txt` names a step (warning); every `project.gates` key is a derived gate or `CHAT-TO-PLAN-GATE` (warning) and their order agrees with the step order (warning); every `{{ key }}` in every prose file resolves against the golden fixture context (warning listing keys); include depth ≤ 5 and no cycles (error); each `ownerWords` entry has a literal match somewhere in locked prose (warning); `worktreeDir` is ignored (`git check-ignore -q <dir>`); `mainBranch` is not checked out in any worktree (`git worktree list --porcelain`); origin reachable (`git ls-remote --exit-code origin HEAD`, warning when absent); `py -3.13`, PyYAML, pytest, git ≥ 2.30; spec fingerprint status; headless `agentCommand[0]` resolvable on PATH (info only).

### 5.3 Round model

- Id `rid` (int) rendered with the width from `roundPaths.folder`; branch `round/<id>`; worktree `<main_root>/<worktreeDir>/<id>`; tags `round/<id>-landed`, `round/<id>-abandoned`; next id = `1 + max(local folder ids, origin round-branch ids)`. `main_root` = `dirname(abspath(join(root, git rev-parse --git-common-dir)))`, falling back to `root`.
- Round folder (names from `roundPaths`): `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SPEC.md`, `SUITE.json`, `POSTMORTEM.md`, `STATE.json`, `HISTORY.md`, `OWNER.log` (slice), `PROMPTS/`, `RESULTS/`, `FINDINGS/` (`<STEP>-<attempt>.{txt,json}`), `tests-archive/`, `DEFINED_JUDGMENT_CALLS.md`, `UNDEFINED_JUDGMENT_CALLS.md`. `start` creates the two judgment files with a one-line header (so they are committed and appendable); `next` recreates `PROMPTS/ RESULTS/ FINDINGS/` before printing an action.
- `harness/archives/rounds/index.jsonl`: one line per finished or abandoned round, `{id, quote_usd, spend, attempts, failures, reentries, outcome, prose_commit, landed_at|abandoned_at, judgment_calls: {defined, undefined}}`; appended on the round branch, merged by landing.
- `<main_root>/harness/OWNER.log` (gitignored): `<UTC Z>\t<message, \ and newlines escaped>`, appended by the hook. Each round copies new lines into its slice from `owner_since = min(previous round's landed/abandoned_at, PLAN.presented_at)`.

**`STATE.json`** (validated on every save; unknown keys rejected):

```
round, branch, created_at, status: active|checkpoint|finished|abandoned, step, kind_pending,
attempts{step:int}, failures{step:int}, infra_errors{step:int}, reentries:int,
step_starts{step:sha}, step_commits{step:sha}, inputs_hash{PLAN,SPEC}, budget_usd,
spend{agent_usd, driver_usd, owner_usd, living_usd, entries[]},
base_commit, prose_commit, delegated: null|"all"|"through:STEP", overrides[], approval, checkpoint,
pending_action: null|{step, attempt}, pending_question, last_findings{producer:path},
carried_findings[], deferred_findings[], findings_ledger{id:{upheld_count, settled}}, mech_ok{gate:attempt},
merge_in_progress: null|{target, target_sha, conflicted[], snapshot{path:blobsha}},
hard_stop_raised, round_limit_raised, owner_since, main_before, landed_at, abandoned_at,
spec_fingerprint_accepted_at_start: bool, judgment_calls{defined, undefined}
```

No lock/lease/pid/worktree key: ownership is "can I still push this branch"; the worktree path is derivable.

**Status lifecycle**: `active` ⇄ `checkpoint` (owner word resumes; `abandon` from anywhere → `abandoned`); POSTMORTEM-GATE PASS → `finished`.

### 5.4 Pipeline and state machine

**Derived gates.** After step X (`producer` or `code`), gate `X-GATE` exists iff `locked_prose/X-GATE.txt` exists at `prose_commit`; it is enabled iff `project.gates[X-GATE]` is truthy (missing key → disabled + warning). `CHAT-TO-PLAN-GATE` is the mechanical approval gate; disabled → no approval wait (approval recorded as `{"word": "gate-disabled"}`). A disabled or overridden gate is skipped with a HISTORY line and counts as PASS (`step_commits` set), and the producer's prompt shows its gate prose annotated `(this gate is disabled this round; judge yourself by it)` via `plumbing/GATE-DISABLED.txt`.

**Checkpoints** follow the steps in `runner.yaml.checkpoints` (after CHAT-TO-PLAN-GATE it *is* the approval wait; after PLAN-TO-SPEC-GATE PASS; after CLEANUP's mechanical checks pass = before landing). A checkpoint is skipped when `delegated == "all"` or `delegated == "through:S"` with S at or after the step. `start --delegated all|through:STEP` sets it without an owner word.

**`next`** (the only place mechanical work runs), in order:
1. `finished`/`abandoned` → `sync_main`, return `{kind: done, main_synced}`.
2. Re-hash `PLAN.json` and `SPEC.json` (normative machine-read files only; SPEC.md edits are logged, not re-entered). PLAN changed → re-enter CHAT-TO-PLAN-GATE, approval cleared, downstream counts reset, `reentries += 1`. SPEC changed after PLAN-TO-SPEC-GATE → re-enter SPEC-TO-TESTS, reset downstream, `reentries += 1`.
3. Dirty tree (`git status --porcelain`, ignoring `merge_in_progress` states): if `pending_action` is set and every dirty path is inside that step's allowed paths + round folder → exit 2 `uncommitted work for STEP attempt N: record it, or run next --discard`; otherwise `git checkout -- . && git clean -fdq`, `infra_errors[step] += 1`, HISTORY line. `--discard` forces the reset.
4. Refresh the OWNER.log slice. If `status == checkpoint`: look for a word after `checkpoint.at`; none → commit the slice, return the checkpoint (exit 10); `abandon` → abandon; approve/delegate → resume (failure-limit checkpoint resets that step's failure count; needs-owner checkpoint writes finding `O1` = the owner's words and re-enters the producer).
5. Loop mechanical work until an agent run is due: CHAT-TO-PLAN-GATE (approval words after `PLAN.presented_at`, or `approval` already set; `override` words parsed here and at every resume → `overrides`); LANDING (§5.9); a gate for a `code` step runs `checks(producer)` first (§5.7) unless `mech_ok[gate] == attempts[producer]`; a checkpoint step that is not delegated raises `checkpoint(review)`; hard stop (§5.8) is evaluated before rendering; a skipped (overridden) producer step advances with a HISTORY line.
6. Render the prompt to `PROMPTS/<STEP>-<attempt>.txt`, set `pending_action`, `step_starts[step]` if unset (HEAD), save, commit (`round NNNN: STEP attempt N prompt`, no push), print the action:
   `{round, step, kind: producer|code|gate, attempt, prompt_file, result_file, artifact, worktree, tools: all|read-only, budget_usd, max_turns, agent, model, effort, sub_agents_allowed, spend}`.

**`record --step S --attempt N --result FILE [--cost USD | --usage JSON] [--agent RUNG] [--sub-usage JSON --sub-agent RUNG]… [--no-push]`**:
- Refuse (exit 2) unless `status == active`, `step == S`, `N == attempts[S] + 1`, and `pending_action == {S, N}`.
- Read the file; strip a surrounding ``` fence; if still not a JSON object, take the last balanced `{…}`; else exit 2 (nothing consumed; the driver fixes the file). Copy to `RESULTS/S-N.json`. Validate against RESULT or FINDINGS; a schema failure is exit 2 for gates (driver re-asks the gate) and finding `S1` (mechanical FAIL) for producers.
- Ledger entries (§5.8); `attempts[S] = N`; `pending_action = null`; `git add -A` and commit `round NNNN: S attempt N` (before checks, so checks see HEAD); route:
  - Producer `DONE`: JSON artifact validated against its schema (fail → `S1`); PLAN-TO-SPEC also runs the overlap check (§5.9) and charges `specCostPerWord`; TESTS-TO-SUITE's `archive` list is applied by the runner (`git mv` into `tests-archive/`) at its gate's PASS; CLEANUP runs `checks` immediately; POSTMORTEM advances to its gate. Then advance.
  - `NEEDS-OWNER`: store `pending_question`, advance to the gate (which rules on it); no gate (disabled) → checkpoint `needs-owner` directly.
  - `UPSTREAM {target}`: target must be an earlier producer; write finding `U1` (the notes) for it, reset downstream counts, `reentries += 1`; target CHAT-TO-PLAN → checkpoint `upstream` (re-plan in chat).
  - `BLOCKED`: finding `B1`, `failures += 1`, retry.
  - Resolutions: each carried/last finding id must appear as `fixed|disputed|deferred`; disputing a settled id → exit 2; `deferred` moves it to `deferred_findings` (carried to POSTMORTEM's prompt only); missing ids → non-blocking finding `R1` listing them on the next gate's input (never a FAIL by itself).
  - Gate: `rulings` update `findings_ledger` (upheld twice → settled; withdrawn → dropped from carried); `needs_owner` upheld → checkpoint `needs-owner` with the question; withdrawn → finding `Q1` (the answer to assume) returns to the producer without a FAIL unless the verdict is FAIL. Verdict is authoritative: PASS with blocking findings → flags normalized to non-blocking and HISTORY notes the inconsistency; FAIL → `failures[producer] += 1`, `last_findings`, back to the producer. PASS → `step_commits[gate] = HEAD`, non-blocking findings appended to `carried_findings`, advance (checkpoint if due).
- Push the round branch; a rejected push raises `another runner owns this round (push rejected)` (exit 1). On `finished`/`abandoned`, `sync_main`.

**Limits.** `maxFailuresBeforeStop` per producer → checkpoint `failure-limit` (approve resets). `maxRoundAttempts` = maximum `reentries` (out-of-band edits, UPSTREAM, landing L1/L2) → checkpoint `round-limit` once. Infrastructure errors do not count. `maxTurnsPerRun` and `maxRunWallClockHours` are passed to the agent (prompt text; headless flags/timeout).

**Overrides.** `override X Y…` (names of gates or steps; `gates` = every gate) recorded in `overrides`; CHAT-TO-PLAN and LANDING cannot be overridden (warning, ignored).

### 5.5 Prompt rendering

Token syntax `{{ ns.key }}`; namespaces:

| ns | keys |
| --- | --- |
| `prose` | any `locked_prose/<NAME>.txt` at `prose_commit`, rendered recursively (depth ≤ 5) |
| `project` | every `project.yaml` key; `remaining` |
| `round` | `id folder worktree base_commit plan budget spend remaining history todos clarifications judgment_calls` |
| `step` | `name attempt kind budget max_turns retry_cost agent model effort sub_agents_allowed artifact artifact_schema result_file inputs allowed_paths verify test_paths impl_paths findings previous question` |
| `plumbing` | `PROCESS-INSTRUCTIONS` (kind-specific file from `src/plumbing/`), `GATE-PROSE`, `AGENTS-MD`, `HEADER` |

Values: strings verbatim; numbers compact (`12.5`, `50000`); lists/dicts as one-line JSON. Unresolved → `[unset: ns.key]`, a stderr warning, and a HISTORY line `render: unresolved keys …` (once per prompt). `round.plan` is PLAN.json as plain text (summary; Scope/Validation/Non-goals/Assumptions bullets; Quote; TODO triage). `round.history` = last 5 index lines as `round N: quoted X actual Y (outcome)`; `round.todos`/`round.clarifications` = `- ` bullets under headings starting `## TODO` / `## CLARIFICATIONS` in every landed round's POSTMORTEM.md, minus lines a later PLAN.json `todos` object already names (exact text).

`plumbing.GATE-PROSE` = the step's `<STEP>-GATE.txt` with every line consisting solely of `{{ prose.* }}`/`{{ plumbing.* }}` tokens removed, then rendered (so producers see the judgment criteria without the gate's includes; structural, wording-free). For CHAT-TO-PLAN: `none: the owner is the gate`. For a disabled gate: the same text under the GATE-DISABLED note.

A prompt = `HEADER` (step/attempt/round/worktree line + `harness/AGENTS.md` verbatim, unrendered) + the rendered OVERVIEW (producers) or GATE (gates) prose. `PROCESS-INSTRUCTIONS` is rendered from the kind's plumbing file and contains only mechanics: inputs **by path** (spec, plan, agents plan, judgment-call files, previous artifact), allowed paths, verify command and timeout, sub-agent allowance and rung prices (`spawnCost`), `step.artifact_schema` (generated from `schemas.json`), findings so far with resolutions (inline JSON), previous final message, the machine lines, and the final-message contract:

```
STEP: <name>. ATTEMPT: <n>. ARTIFACT: <path>. RESULT_FILE: <abs path>. WORKTREE: <abs path>.
Producer final message, exactly one JSON object: {"status": "DONE"|"NEEDS-OWNER"|"UPSTREAM"|"BLOCKED", "notes": "...",
 "question"?: "...", "target"?: "STEP", "resolutions"?: {"F1": {"status": "fixed"|"disputed"|"deferred", "reason": "..."}},
 "sub_agents"?: [{"agent": "<rung>", "usage": {"input":0,"output":0,"cache_read":0,"cache_write":0}} | {"agent": "...", "cost_usd": 0}]}
Gate final message: {"verdict": "PASS"|"FAIL", "findings": [{"id": "F<n>", "quote": "...", "reason": "...", "suggestion": "...", "blocking": true|false}],
 "rulings"?: {"F1": {"status": "upheld"|"withdrawn", "quote": "..."}}, "needs_owner"?: {"status": "upheld"|"withdrawn", "reason": "..."}, "notes": "..."}
```
Gates are told they write no files: the driver (or headless runner) saves the final message. Producers are told: never commit or push; append judgment calls to the two files; large inputs are files to read, not text to reproduce. Prompts stay small (paths, not bodies).

`render --step X [--round N | --fixture golden] [--attempt N]` prints a prompt without a round side effect; `chat` renders CHAT-TO-PLAN (no round: `round.*` from history/todos, budget from `defaultShares`).

### 5.6 Owner interaction

- Hook `.claude/settings.json` → `py -3.13 harness/src/owner_log_hook.py` (UserPromptSubmit; stdin JSON; finds `main_root` via `git rev-parse --git-common-dir` from `CLAUDE_PROJECT_DIR`/cwd; skips envelopes such as `<system-reminder`, `<task-notification`; appends the line). `owner-say "<text>"` appends the same line format tagged `[relayed]`; HISTORY records relayed approvals as such.
- Words are read only from the round's slice, only after the relevant timestamp (`PLAN.presented_at` for approval; `checkpoint.at` for resumes), latest matching line wins; `delegate through STEP` captures the step; `override …` captures names.
- Checkpoint action: `{kind: checkpoint, reason: approval|review|needs-owner|failure-limit|round-limit|hard-stop|upstream|spec-changed, step, question, artifact, spend, undefined_judgment_calls: [last 5 lines]}`; exit 10. The driver relays it in chat and stops. Owner cost per checkpoint: `costToWaitForOwner + ownerHourlyRate × ownerDecisionMinutes/60`; approval also charges `planCostPerWord × words(PLAN text)`; PLAN-TO-SPEC-GATE PASS charges `specCostPerWord × words(SPEC.md)`.

### 5.7 Mechanical checks (`checks(producer)`; findings are blocking unless noted)

- **M1 confinement**: `git diff --name-only <step_starts[producer]> HEAD` must lie within declared paths (`SPEC.<paths>` for the step) + round folder + `extraPaths` + `harness/SPEC-FINGERPRINT.json`; prefix match on `/`-terminated dirs, exact on files.
- **M2 frozen tests** (`freezeTests`): `git diff --name-only <step_commits[SPEC-TO-TESTS-GATE]> HEAD -- <testPaths>` empty (for CLEANUP: against `step_starts[CLEANUP]`, after the suite archive moves).
- **M3 verify** (`verify`): `SPEC.verify` (argv list or string; string → `shell=True`) green within `SPEC.verifyTimeoutSeconds` or the project default.
- **S1 schema**, **R1 missing resolutions** (non-blocking), **P1 overlap** (non-blocking, §5.9), **T1 hand-resolved test files** (non-blocking, §5.9), **L1/L2** landing (§5.9).
- SPEC validation: `implPaths`/`testPaths` non-empty lists, disjoint by prefix; `verify` present.
- `check` runs the current step's checks without recording (exit 3 on findings); at LANDING it runs the check phase only.

### 5.8 Ledger

Entry `{step, attempt, usd, source, at, extra}`; buckets: `agent_usd` ← `cli|usage|estimate`, `driver_usd` ← `driver`, `owner_usd` ← `owner`, `living_usd` ← `living`; `time_usd` computed live = hours from `created_at` to now (or to `landed_at`/`abandoned_at`) × `lostValuePerHour`; `total = Σ`.
- `--usage` is priced from the run's rung (`--agent`, default the action's agent): `input×in + output×out + cache_read×cr + cache_write×cw` per MTok; `--cost` is taken as reported; neither → `max(spawnCost, 0)` as `estimate` with a HISTORY note; every entry is at least `spawnCost`. `sub_agents` in the result (or `--sub-usage/--sub-agent`) add entries the same way.
- `driverUsdPerStep` per `record` (source `driver`).
- Per-run budgets: shares from `AGENTS-PLAN.json` (`shares.work`, `shares.gates`, each summing to 1 ± 0.001) else `project.defaultShares`; `budget = budget_usd × workFraction|gatesFraction × share`. `step.retry_cost` = the producer's per-run budget.
- **Living charge** at landing, against the tip actually merged (`target` or `base_commit`): for each file under `livingSourcePaths` present at HEAD or base, `tokens = ceil(bytes/tokenBytes)` from `git cat-file -s`; `f(t) = min(t,cap)×cost + max(t−cap,0)×costOverCap`; charge `f(head) − f(base)`; `+livingFileBaseCost` per file new at HEAD, `−livingFileBaseCost` per file removed; `+testBaseCost × Δ(count of testFunctionPattern matches)` over files under `testPaths` that remain in the suite (not archived); `__pycache__`/`*.pyc` excluded. One entry per landed round, after the push succeeds.
- **Hard stop**: `total > hardStopBudgetMultiple × budget_usd` → checkpoint `hard-stop` once per round, evaluated on every entry and before rendering, never while a checkpoint is being raised.
- `spend` prints the summary + entries; `spend --project` sums `index.jsonl` plus every live round folder.

### 5.9 Concurrency and landing (from the bootstrap summary, adapted)

Invariants kept: I1–I9 and I11 verbatim in spirit; I10 (no push credential) is enforced in headless mode (env scrub + tool flags) and stated as a prompt rule in driver mode (the fence and M1 catch the consequences). Non-invariants kept: no lease expiry, no takeover, no cross-round path arbitration beyond a warning.

**`start --plan FILE [--budget USD] [--branch NAME] [--no-branch] [--delegated all|through:STEP] [--accept-spec]`**:
1. Validate the plan (schema) first; then lint strictly; then fingerprint status — stale and no `--accept-spec` → error listing the changed files and the two commands to run (§5.10).
2. Preconditions (unless `--no-branch`): `worktreeDir` ignored; `mainBranch` not checked out in any worktree; origin present.
3. `git fetch origin`; ids from `refs/remotes/origin/round/<digits>`; `rid = 1 + max(ids ∪ local folders)`; up to `pushAttempts` pushes of `git push --porcelain --force-with-lease=refs/heads/<branch>: origin HEAD:refs/heads/<branch>`; **win = exit 0 and a stdout line starting `*`** (`=` and `!` lose — verified on this git); explicit `--branch` → exactly one push then error; exhausted → error naming the last branch. Nothing is created before the win (I2).
4. `git worktree add -b <branch> <wt> HEAD`; from here every path is under `wt`. Create the folder and files (§5.3), `STATE` (`base_commit = prose_commit = HEAD`, `status active`, `step CHAT-TO-PLAN-GATE`, `attempts {CHAT-TO-PLAN: 1}`), the OWNER slice, the `CHAT-TO-PLAN` estimate entry (from `defaultShares`), with `--accept-spec` the rewritten `harness/SPEC-FINGERPRINT.json` plus a HISTORY block quoting the file-level diff summary; `git add -A; commit "round NNNN: start"; push -u origin <branch>`. Print `{round, folder, branch, worktree}`.
5. `--no-branch`: id from local folders, no fetch/CAS/worktree/push (tests, offline).

**Fence**: every state-changing command commits and pushes the round branch; a rejected non-forced push aborts with `another runner owns this round (push rejected)` (I5). Runner pinning: `next`/`record` warn when the running `run.py` is not the one inside `--root` (`os.path.realpath(__file__)`), because config, prose and runner are pinned at `prose_commit`.

**Overlap warning**: at PLAN-TO-SPEC `record`, for every `origin/round/<id>` branch not tagged landed/abandoned (after a fetch), read its `SPEC.json` with `git show`; any prefix overlap of `implPaths`/`testPaths` → non-blocking finding `P1` naming the round and paths, carried to SPEC-TO-IMPLEMENTATION.

**LANDING** (mechanical, inside `next`): `attempts[LANDING] += 1`; check phase: target = `origin/<main>` after fetch if it exists, else local `<main>`, else none; `git merge --no-edit <target>`; `main_before` recorded after target resolution; on a clean merge run verify then `suiteCommand` (`L2` on red); then `spec-status` (stale → checkpoint `spec-changed`, not `L2`). Land phase = the summary's bounded loop: compute the living charge against the merged tip, `git branch -f <main> HEAD`, push `<main>:<main>`; rejected → re-fetch, re-merge, re-check, retry up to `pushAttempts`; then one living entry, tag `round/NNNN-landed`, `landed_at`. `sync_main` after the last commit (fast-forward only, never raises).

**Converging conflict path** (replaces the sibling's non-convergent L1):
- *Conflict* (`git merge` fails): do **not** abort. Record `merge_in_progress = {target, target_sha, conflicted: git diff --name-only --diff-filter=U, snapshot: {path: blob sha of every tracked/untracked non-ignored file}}`, write finding `L1` (target, conflicted files, "resolve the markers in exactly these files, then make verify green"), `failures[SPEC-TO-IMPLEMENTATION] += 1`, `reentries += 1`, re-enter SPEC-TO-IMPLEMENTATION. `next`'s dirty-tree logic treats this state as expected. On `record` of that attempt: `git diff --check` must report no markers (else `L1` again); M1 = files whose blob differs from the snapshot, minus `conflicted`, minus the round folder; M2 = frozen tests as usual except conflicted test files, which produce non-blocking `T1` for the gate to judge; M3 verify; then the runner commits the merge (`git add -A; git commit` with `MERGE_HEAD` present) and clears `merge_in_progress`. A crash leaves `MERGE_HEAD` + state agreeing; `MERGE_HEAD` without state → `git merge --abort`, infra error.
- *Red on the merged tip* (`L2`): the merge commit stands; `step_starts[SPEC-TO-IMPLEMENTATION]` and the M2 baseline are reset to that merge commit, so the diffs measure only the fix.
- After the re-entered SPEC-TO-IMPLEMENTATION passes its gate: if nothing under `testPaths` changed relative to the pre-landing CLEANUP tip, jump straight to LANDING (HISTORY: `skipped TESTS-TO-SUITE/CLEANUP: tests unchanged after landing fix`); otherwise continue normally.

**`rounds`** lists local folders and origin branches with status/step/spend/landed tags; **`prune [--apply]`** reports (and with `--apply` removes) worktrees of finished/abandoned rounds and origin branches claimed with no start commit beyond the base (claimed-never-started), never touching live rounds.

### 5.10 Spec fingerprint

`harness/SPEC-FINGERPRINT.json`:
```json
{"accepted_at": "…Z", "accepted_commit": "<sha>", "spec_list_sha256": "<sha256 of normalized spec.yaml>",
 "files": {"harness/AGENTS.md": "<sha256>", "...": "..."}, "note": "<optional>"}
```
Normalization: bytes → strip UTF-8 BOM → `\r\n`/`\r` → `\n`; hash the normalized UTF-8 bytes (so autocrlf checkouts agree). `fingerprint.status(root) → {ok, changed[], added[], removed[], missing[], list_changed, manifest_missing}` where `added/removed` compare spec.yaml's list to the manifest keys and `missing` are listed files absent on disk. Commands: `spec-status` (JSON; exit 0/3), `spec-diff` (`git diff <accepted_commit> -- <files>` plus list changes), `spec-accept [--note]` (rewrite with HEAD; no commit). The pytest test `harness/tests/test_spec_fingerprint.py::test_spec_files_unchanged_since_acceptance` fails with the categorized list and the instruction "review the effects (run `doctor` and `render` for affected steps), then `spec-accept` and commit". The meta-tests (§6.3) prove the test itself. `start` refuses stale specs (above); the suite run at landing cannot be red for this reason because `start` already gated it and the manifest lands with the round.

### 5.11 CLI reference

Global: `--root DIR` (repo root or round worktree; default: nearest ancestor of cwd with `harness/project.yaml`), `--round N`, `--verbose`, `--no-push` (where relevant).

| command | reads | writes |
| --- | --- | --- |
| `doctor` | toolchain, git state, spec files, fingerprint | nothing; exit 3 on errors |
| `lint` | spec files, runner.yaml | nothing |
| `spec-status` / `spec-diff` / `spec-accept [--note]` | spec files, manifest, git | manifest (accept only) |
| `render --step S [--round N \| --fixture golden] [--attempt N]`, `chat` | round or fixture | stdout only |
| `start …` | plan, origin refs, owner log | origin claim, worktree, round folder, start commit + push |
| `next [--discard]` | STATE, owner log, git | mechanical effects, prompt, STATE, commit; action or checkpoint (10) |
| `record …` | result file | RESULTS/FINDINGS, STATE, HISTORY, commit + push (fence) |
| `run --until checkpoint\|step\|done` | — | headless loop: next → agent command → record; 3 retries per run, each an infra error |
| `status`, `spend [--project]`, `rounds` | STATE, index, siblings | nothing |
| `check` | STATE, git, verify/suite | nothing shared |
| `abandon --reason R` | STATE | abandoned status, tag, index line, commit (no push) |
| `note "text"`, `owner-say "text"` | — | HISTORY FLAG line / OWNER.log line |
| `prune [--apply]` | worktrees, origin | with `--apply`: worktree removal, branch deletion of never-started claims |
| `sandbox --new DIR` | this repo | `DIR/origin.git` (bare, `main` pushed) + `DIR/repo` clone with the hook installed; prints both |
| `probe --step S [--defect NAME] [--agent RUNG]`, `probe-check --step S --result FILE` | golden fixture | a detached temp worktree with the fixture round positioned at S; the contract verdict |

### 5.12 Driver protocol and headless mode

Driver (documented in PROCESS.md; this is what the owner's real-agent runs follow):
1. `py -3.13 harness/src/run.py chat` → read; converse with the owner; write `PLAN.json` (schema in `schemas.json`, `presented_at` = when the plan was posted) to a scratch path; wait for the word.
2. `start --plan … [--accept-spec]`; note the printed `worktree`; from now on every command takes `--root <worktree>` and is the worktree's own `run.py`.
3. Loop: `next` → on an action, spawn one **fresh** sub-agent with the prompt file's content verbatim (producers: a general agent; gates: a read-only agent type; never `isolation: worktree` — the round worktree is the isolation; the prompt's `WORKTREE:` line tells the agent where to work), save its final message to `result_file`, `record … --usage <the run's usage JSON>` (or `--cost`), repeat. Never do a gate's job, never edit artifacts, never commit or push by hand.
4. Exit 10 → relay `question` (and any undefined judgment calls listed) to the owner in chat and stop; after the owner speaks, `next` again.
5. Exit 1 with `another runner owns this round` → stop and report.

Headless: `run` substitutes `{prompt_file} {model} {effort} {max_turns} {budget_usd} {tool_flags}` into `headless.agentCommand`, scrubs `scrubEnv`, runs with `maxRunWallClockHours` as the timeout, parses stdout JSON (`result` unwrapped; `total_cost_usd` → `--cost`; `usage` if present → `--usage`), writes the result file, records. `doctor` reports whether `agentCommand[0]` resolves; the suite exercises `run` only with the stub.

### 5.13 Documents

- `harness/INDEX.md`: alias → canonical lines for process, config, runner commands, schemas, prose, plumbing, rounds, index, owner log, hook, suite, fixtures, fingerprint.
- `harness/docs/PROCESS.md` (one sentence per line): principles (mechanical before judgment; budgets are targets; only the runner commits/pushes/contacts the owner); round and files; steps and gates (derived, enable flags, overrides); checkpoints and words; failure/dispute/re-entry (incl. `deferred`, settled, limits); spec and code rules (declared paths, freeze, verify); landing and conflict convergence; concurrency invariants; driver protocol; runner pinning; what is generic to spec changes and what the lint checks.
- `harness/docs/TESTING.md`: suite map, fixtures, how races are made deterministic, the fingerprint meta-test, the real-agent loop (§6.5), how to run: `py -3.13 -m pytest -q harness/tests`.
- `README.md` at the root: three sentences and the two commands.

---

## 6. Test strategy

### 6.1 Principles
Partial integration, no mocks of git: every test builds a throwaway repo in a temp dir (copy of the real spec files + `harness/src` + a generated `.gitignore`, hermetic git env `GIT_CONFIG_GLOBAL=NUL`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed author) and drives the runner. Most tests call `run.main(argv)` in-process with captured stdout (fast on Windows); `test_cli.py` runs a handful through `subprocess` with `sys.executable` to pin exit codes and single-line JSON. Target: full suite < 3 minutes; concurrency tests marked `slow` but included by default.

### 6.2 Fixtures (`conftest.py`)
- `Repo(tmp, project_overrides, prose_overrides, files, owner_lines, branch)`; `Repo.add_origin()` (bare, absolute path, `main` pushed); `Repo.clone()`; `Repo.view(worktree)` (`--root`); `Origin` with `install_reject_hook(pattern, n|all)` and `install_move_and_reject_once_hook()` (sh `update` hooks with **absolute** log paths; verified to run here); `Repo.start/next/record/act/play(until=…)`; `owner_say`; fetch-refspec narrowing to force a lost claim.
- `stub_agent.py`: parses the last `STEP:/ARTIFACT:/RESULT_FILE:/WORKTREE:` lines; modes `pass fail dispute needs_owner upstream blocked garbage fence deferred outside_paths break_tests red no_resolutions sub_agents`; writes canned valid artifacts (plan/agents plan/spec+SPEC.md/tests/impl/suite/postmortem with `## TODO`/`## CLARIFICATIONS`); appends judgment-call lines; `STUB_LOG` records argv/cwd/env keys; usable as the headless command and in-process (`perform`).
- `fixtures/golden-round/`: a complete tiny round over a toy project inside the temp repo (`src/greeting.py` + `tests/test_greeting.py`), plus `defects/<GATE>/<name>/` variants with `expect.json` (`{"verdict": "FAIL", "quote_contains": "<planted text>"}`) for the probe loop.

### 6.3 Suites and what they assert
- `test_spec_fingerprint.py`: the required test (§5.10). `test_spec_fingerprint_meta.py`: on temp copies — unchanged → ok; one prose file edited → `changed == [that path]` and the real test function raises `AssertionError` naming it; CRLF rewrite → still ok; a file added to / removed from spec.yaml → `added`/`removed`; a listed file deleted → `missing`; manifest absent → `manifest_missing`; `spec-accept` → ok; `start` refuses stale without `--accept-spec`, accepts with it and the start commit contains the manifest + HISTORY summary.
- `test_config.py` / `test_lint.py`: defaults for missing keys, id width derivation, derived gates from files + flags, step-table validation, every lint rule fires on a crafted violation and the real repo passes `doctor` (minus origin/headless items).
- `test_render.py`: every step of the golden round renders with zero `[unset:` (after §7 edits; a test also proves the placeholder appears when a key is removed), GATE-PROSE strips include-only lines, disabled-gate note, machine lines present and last, AGENTS.md verbatim and unrendered, prompts read prose from `prose_commit` not the working tree, `chat` without a round.
- `test_state_machine.py`: full happy path with checkpoints and delegated; each stub mode's routing (FAIL/dispute/settled after two upholds/withdrawn dropped/needs-owner upheld and withdrawn/UPSTREAM to each earlier producer incl. CHAT-TO-PLAN/BLOCKED/deferred/R1); limits (`maxFailuresBeforeStop`, `reentries`), hard stop once, overrides (gate skipped, step skipped, CHAT-TO-PLAN refused), out-of-band PLAN/SPEC edits, `pending_action` protection and `--discard`, idempotent `next`, `record` guards (exit 2 cases), fence-unwrapping and last-object recovery, owner words after timestamps only, envelopes ignored, `owner-say` marked relayed.
- `test_checks.py` / `test_ledger.py`: M1/M2/M3 each via stub modes; SPEC path validation; living charge arithmetic incl. cap, new/removed file base cost, test-count delta and archived tests excluded; usage pricing per rung and `spawnCost` floor; owner charges; shares/budgets; `spend --project` across a live sibling.
- `test_concurrency.py` (`slow`): claim (stdout shape, worktree on `round/0001`, main checkout untouched, no `OWNER.log` in the worktree); lost race via narrowed refspec, both `!` and `=` shapes, `assertNothingCreated`; reject-all hook → exactly `pushAttempts` pushes and the error text; explicit `--branch` taken → one push; `worktree add` failure keeps the claim; id sourcing ignores `round/003-x`, `round/abc`, tags; fence (another clone moves the branch → `record` exit 1); landing after a sibling moved `main` (both rounds' files present, one living entry equal to this round's diff); move-and-reject-once hook → retry inside one `next`, `attempts[LANDING] == 1`; reject-all on `main` → exit 1, nothing tagged, rerun lands; **conflict**: L1 leaves `MERGE_HEAD`, finding lists the file, the stub resolves it, M1 ignores non-conflicted merge changes, T1 for a conflicted test, the merge commit has two parents, TESTS-TO-SUITE/CLEANUP skipped when tests unchanged, and the round lands; L2 red on the merged tip → fix diff measured from the merge commit; `sync_main` true/idempotent/false; `prune` reports and removes only dead rounds; overlap warning `P1`.
- `test_headless.py`: `run --until done` with the stub command; garbage output → 3 infra retries then error; tool flags per kind; scrubbed env keys absent in `STUB_LOG`.
- `test_hook.py`: `owner_log_hook.py` with sample stdin (envelopes skipped, escaping, main-root resolution from a worktree).
- `test_probe.py`: `probe` positions the fixture at a step and prints an action; `probe-check` passes on the stub's output and fails on `outside_paths`; defect fixtures load and their `expect.json` is validated.

### 6.4 Windows specifics
Paths compared by `realpath`; temp cleanup with `ignore_errors` + `onexc` chmod; CRLF cases in fingerprint and result parsing; commands as argv lists; `sys.executable` in stub commands.

### 6.5 Real-agent testing loop (proposed instead of repeating end-to-end throwaway rounds)

The end-to-end round is the most expensive (~15 agent runs, $30–90, hours) and least attributable test: when something goes wrong you cannot tell which prompt, which gate, or which mechanism failed, and it has no ground truth for gate effectiveness. Proposed ladder, each rung cheaper than the next and each answering a question the stub suite cannot:

1. **Stub suite** (free, minutes): every mechanism.
2. **`probe --step S`** (one real run, $1–5, ~5 min each; all steps in parallel ≈ $25): renders the real prompt from the golden round in a detached temp worktree, the driver spawns the real agent (rung `systemTestAgent` by default), `probe-check` verifies only the contract — valid final JSON, schema-valid artifact, no edits outside declared paths, judgment-call files appended, no push. A failure names one prompt. Rerun after any prose or plumbing change.
3. **`probe --step X-GATE --defect NAME`** ($1–5): the gate reads a planted-defect artifact; `probe-check` asserts FAIL with a finding quoting the planted text; the clean variant must PASS. This measures gate discrimination directly — the thing "gate effectiveness" means — and is the evidence for any gate-language relaxation (§7).
4. **`sandbox --new DIR` + one throwaway round** (the owner's plan, unchanged in substance): real driver, real agents, gates off then on, checkpoints on then delegated — but landing into a local bare origin, so nothing pollutes the real origin or the id sequence, and the run is repeatable. Do this once per change to the runner's flow, not per prose tweak.

Cheaper because rungs 2–3 replace most rung-4 repetitions; more comprehensive because they test each prompt and each gate in isolation with ground truth. The throwaway plan lives at `harness/tests/fixtures/throwaway-plan.json` (add `harness/src/hello.py` printing a greeting plus its test; explicit non-goals).

---

## 7. Spec file edits (minimal; flag each to the owner with this diff)

Both fix a stale key; without them the two prompts show `[unset: project.ownerReviewCostPerWord]` (harmless, but wrong).

```
--- harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
--- harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```
Alternative with zero prose edits: add `ownerReviewCostPerWord: 0.1` to `project.yaml` (also owner-approved). Recommend the prose edits.

No other spec edit is needed to build or run. Gate-language relaxation is **not** proposed now: `COMMON-GATE` already bounds FAIL by retry cost; decide after rung 3 of §6.5 produces data. The implementing agent must not touch any other spec file; the fingerprint test enforces that every spec change is deliberate.

---

## 8. Implementation order

1. **M0 scaffolding**: `.gitignore`, README, INDEX.md, `runner.yaml`, `schemas.json`, config loader + defaults, fingerprint module + both tests, `doctor`/`lint`, hook + `.claude/settings.json`. Commit; suite green.
2. **M1 rendering**: renderer, plumbing texts, golden fixture, `render`/`chat`, render tests.
3. **M2 single-checkout state machine** (`--no-branch`): start/next/record, findings/dispute/deferred, checkpoints and words, limits, overrides, pending-action guard, stub agent, state-machine tests.
4. **M3 mechanical + ledger**: M1–M3, suite archive, living charge, landing to local `main`, sync, index, POSTMORTEM gate, `status/spend/check/abandon/note`.
5. **M4 concurrency**: claim/worktrees/fence, landing with origin and retry loop, conflict convergence, overlap warning, `rounds/prune`, hook fixtures, concurrency tests.
6. **M5 operations**: headless `run`, `sandbox`, `probe`/`probe-check` + defect fixtures, PROCESS.md/TESTING.md final pass, `doctor` complete.
7. Apply the §7 edits (flagged), `spec-accept`, run `doctor`, then the §6.5 ladder from rung 2.

Commit per milestone on a branch off `origin/HEAD` (never on `main`; repo-local git identity per the machine notes); attribution trailer as configured.

---

## 9. Risks and open questions, each with the recommended resolution

1. **Headless `claude -p` flags/availability on this machine** (binary is the desktop-bundled CLI, not on PATH). → Driver mode is primary; `agentCommand` is config; `doctor` reports; verify flags with `claude --help` from a session where it resolves before relying on `run`.
2. **Claude Code hook execution on Windows** (shell used for hook commands is unverified). → Smoke-test the hook once in the bootstrap; `owner-say` is the documented fallback and is marked relayed in HISTORY.
3. **`maxRoundAttempts` semantics** ("round retries"). → Count re-entries (out-of-band edits, UPSTREAM, L1/L2); checkpoint once when exceeded. Owner may redefine.
4. **Owner-cost model** (`ownerHourlyRate`, `costToWaitForOwner`, per-word costs have no stated formula). → §5.6/§5.8 formula with `ownerDecisionMinutes` in runner.yaml; flag to the owner.
5. **Gate verdict vs. `blocking` inconsistency.** → Verdict is authoritative; flags normalized; logged.
6. **Gate strictness** (prose says "Ambiguous? Fail" often). → Measure with defect probes before relaxing; no edit now.
7. **`.worktrees/` vs the machine convention `.claude/worktrees/`.** → Default `.worktrees/` (self-contained, gitignored by this repo); `worktreeDir` is config.
8. **Living paths are harness-root-relative** and the harness is its own project. → One path resolver; external targets are a later round.
9. **Driver mode cannot scrub credentials from sub-agents** (I10). → Prompt rule + fence + M1; headless mode enforces fully.
10. **Conflict-path snapshot cost** on large repos (hashing every file). → Use `git ls-files -s` for tracked blobs and hash only untracked non-ignored files; fine at this scale.
11. **Fingerprint friction** (every owner prose tweak requires `--accept-spec` at the next `start`). → Intended alert; one flag, diff shown, recorded in HISTORY; the manifest lands with the round so `main` is never red for this reason.
12. **Suite duration on Windows** (git process spawns). → In-process runner calls; `slow` marker; keep hook-based tests focused.
13. **Prose that names paths** (`src/run.py`, `docs/PROCESS.md`, `INDEX.md`) must match the layout. → Layout §4 matches AGENTS.md; the lint does not check prose paths (wording); a `test_index_targets_exist` checks INDEX.md's canonical targets exist.
14. **CHAT-TO-PLAN-GATE disabled means no approval.** → As specified; `--delegated` still controls checkpoints; documented.
15. **Two parallel rounds both editing `PROCESS.md`.** → One sentence per line and the converging conflict path; no ordering primitive (documented).
