# Plan 3: building `shackles_harness` from the owner's spec

## 0. How to read this

- §1 the process that produced the plan; §2 facts extracted from the spec that the design rests on; §3 the standard features the project lacks and which are included; §4 the design (normative for the implementer); §5 the test strategy; §6 the real-agent testing loop; §7 spec-file edits; §8 build order; §9 risks and open questions.
- "H" is the harness root, the folder holding `project.yaml` (`<repo>/harness`). Paths below are H-relative unless they start with `<repo>/`. "R" is the git top level, "M" the main checkout (a worktree's parent). `NNNN` is a round id, zero-padded to the width of the `N`-run in `roundPaths.folder`.
- Every "MUST" is something a test in §5 pins.

## 1. Process used

1. Read the whole worktree: `spec.yaml`, its 20 files, `bootstrap/vision-harness-round-concurrency.md`, and the three commits (the owner's recent edits are the judgment-call wording in `AGENTS.md` and `COMMON-OVERVIEW.txt`; that is the kind of change everything must survive).
2. Extracted every `{{ }}` token from the locked prose and every key from `project.yaml`/`subAgents.yaml`, and cross-checked them (§2.2, §2.3).
3. Spot-checked the original `vision_harness` (read-only) only for points the summary names but does not spell out: the `STEP:`/`ARTIFACT:`/`RESULT_FILE:` prompt contract, artifact and result schemas, the owner-log hook and its `settings.json` wiring, budget-share math, the diff bases of the mechanical checks, and the `next`/`record` routing. Kept the shapes that worked in five real rounds; redesigned what §6 of the summary says failed (§4.13).
4. Checked the machine: `py -3.13` is 3.13.2, PyYAML 6.0.3, pytest 9.1.1, git 2.45 (conda MinGW build; no `sh`/bash on PATH, so git hooks are not a reliable test device here); the `claude` CLI is not on PATH in tool shells, so headless agent invocation cannot be the primary path; the machine's agent-coordination rules (worktrees, no screen use).
5. Designed against the constraints in this order: robustness to arbitrary spec edits; "agents make judgment calls only inside a monitored process" (every place an agent could improvise gets a mechanical rail and a record); cost.
6. Wrote the test strategy before freezing the design and re-checked each element for a test that pins it; where the test was hard, changed the design (a test seam instead of git hooks).
7. Self-reviewed against the deliverable checklist and against the nine failures in the summary's §6.

## 2. What the spec already fixes

### 2.1 Steps, gates, checkpoints

From the `gates` map in `project.yaml` (order, enable flags, comments), the locked-prose file names, and `AGENTS.md`:

- Producer steps (an `<STEP>-OVERVIEW.txt` exists): CHAT-TO-PLAN, PLAN-AGENTS, PLAN-TO-SPEC, SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, TESTS-TO-SUITE, CLEANUP, POSTMORTEM.
- Gate prose (an `<STEP>-GATE.txt` exists): PLAN-AGENTS, PLAN-TO-SPEC, SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, TESTS-TO-SUITE, POSTMORTEM. CHAT-TO-PLAN-GATE is mechanical. CLEANUP has no gate.
- Checkpoints the prose asks for: after the plan (approval), after PLAN-TO-SPEC ("Checkpoint after this step"), after CLEANUP ("Checkpoint after this step" = the `gates` comment "checkpoint before landing"). Landing follows CLEANUP; POSTMORTEM and its gate come last; "Round ends here, all agents stop."
- Every gate is currently `0` (disabled). CHAT-TO-PLAN is done in the owner's chat by the top-level agent, which is also the driver.

### 2.2 Template tokens the prose uses

| namespace | keys |
| --- | --- |
| `project` | shackles, budget, remaining, lostValuePerHour, livingFileCostPerToken, livingFileTokenCap, livingFileCostPerTokenOverCap, livingFileBaseCost, testBaseCost, livingSourcePaths, tokenBytes, maxRefactorOverhead, gates, ownerReviewCostPerWord |
| `round` | id, folder, base_commit, plan, budget, spend, remaining |
| `step` | retry_cost |
| `prose` | COMMON-PROJECT, COMMON-ROUND, COMMON-OVERVIEW, COMMON-GATE |
| `plumbing` | GATE-PROSE, PROCESS-INSTRUCTIONS |

### 2.3 The one mismatch

`{{ project.ownerReviewCostPerWord }}` (CHAT-TO-PLAN-OVERVIEW line 6, PLAN-TO-SPEC-OVERVIEW line 11) has no key in `project.yaml`, which has `planCostPerWord` and `specCostPerWord`. The runner tolerates it (§4.5); the recommended two-token fix is in §7.

### 2.4 Config keys and their use

| key | used by |
| --- | --- |
| shackles, currency | rendered only |
| budget | `project.remaining` = budget - all rounds' spend (index + live) |
| hardStopBudgetMultiple | hard-stop checkpoint when round spend > multiple x round budget |
| lostValuePerHour | time cost, computed from `created_at` |
| ownerHourlyRate, costToWaitForOwner | owner cost per checkpoint (§4.12) |
| planCostPerWord, specCostPerWord | owner reading cost, charged once at approval / spec checkpoint |
| livingFileTokenCap, livingFileCostPerToken, livingFileCostPerTokenOverCap, livingFileBaseCost, tokenBytes | living charge at LANDING |
| testBaseCost | per new suite test at LANDING |
| maxRefactorOverhead | cap on `SPEC.json.refactor` budgets (check M4) |
| gates | gate enablement and order consistency (§4.4) |
| defaultShares, gatesFraction, workFraction | step budgets before/without AGENTS-PLAN.json |
| livingSourcePaths, lockedProsePath, archivesPath, roundPaths | every path the runner touches |
| maxSimultaneousSubAgentsPerRound | AGENTS-PLAN validation; rendered |
| maxRoundAttempts | round re-entry limit (§4.10, §9) |
| maxFailuresBeforeStop | per-step failure limit |
| maxTurnsPerRun, maxRunWallClockHours, verifyTimeoutSeconds | action JSON, headless timeouts, verify/suite timeouts |
| estOutputFraction | pricing a run from a token count |
| driverUsdPerStep | flat driver charge per `record` |
| subAgentsFile, maxAgent, gateAgent, systemTestAgent | roster and agent choice |
| roster `spawnCost` | floor for a run's cost when none is reported |

### 2.5 Words the prose defines that the runner must honour

Producer statuses DONE / NEEDS-OWNER / UPSTREAM / BLOCKED (COMMON-OVERVIEW). Gate PASS/FAIL with blocking or non-blocking findings, each with a suggestion; disputes ruled upheld/withdrawn by quotation; upheld twice is settled; a withdrawn finding is not re-raised (COMMON-GATE). Owner words approve/approved, delegate/delegated, delegate through STEP, override + steps or gates; the plan cannot be skipped (CHAT-TO-PLAN-OVERVIEW). DEFINED/UNDEFINED judgment-call files, one line per call (AGENTS.md, COMMON-PROJECT, COMMON-ROUND).

## 3. Standard features the project lacks

Included, each with the section that designs it:

1. Owner contact channel: a chat hook that logs every owner message with a timestamp, and the runner reading owner words only from that log (§4.14, §4.10).
2. Spec-change alarm: a snapshot test that fails, with a diff, when any spec.yaml file changes; a meta-test that proves the alarm works; a `spec-check` command; loud flagging of any spec edit a round makes (§4.16).
3. Owner/runner settings separation: code defaults, runner-owned `plumbing.yaml`, owner-owned `project.yaml` on top; every key read with a default, every key exposed to prose (§4.3).
4. Drift-tolerant prompt rendering with a dry-run `render` command (§4.5).
5. Pipeline discovery from the spec (prose files + gates map), gate enable flags, overrides, delegation, checkpoints (§4.4, §4.10).
6. Machine-checked result and verdict contracts; every invalid agent output becomes a finding, never a crash (§4.7, §4.10).
7. Findings ledger: resolutions, disputes, settled findings, withdrawn findings not re-raised, non-blocking findings carried forward (§4.10).
8. Budget: ledger buckets, per-step budgets from shares, hard stop, quote-versus-actual in a round index, project-wide tally (§4.12).
9. Rails on code steps: path confinement, frozen tests, verify and suite runs, refactor cap, non-goals carried (§4.11).
10. Round concurrency: CAS ids on origin, one worktree per round, push fence, bounded landing loop, post-round sync, a conflict path that converges, sibling path-overlap warning, preconditions checked up front, a prune report (§4.13).
11. Crash recovery: all state committed after every step, dirty-tree recovery, idempotent `record`, infrastructure-error accounting (§4.10).
12. Judgment-call monitoring: the two files exist from round start, gates' calls are appended by the runner, counts are logged per attempt and per round, shown at checkpoints, reviewed by the postmortem (§4.15).
13. Postmortem feedback into the next plan: TODOs, CLARIFICATIONS, quote versus actual (§4.5.3, §4.6).
14. Headless mode with a stub agent, plus `probe` and `sandbox` commands for cheap real-agent tests (§4.9, §6).
15. Test archiving and suite selection applied mechanically (§4.10).
16. Runner pinning per round and a skew warning (§4.13).
17. Observability: `status`, `rounds`, `spend`, `judgment-calls`, HISTORY.md narrative, `doctor` (§4.9).
18. Routing `INDEX.md` and four short docs, as `AGENTS.md` demands (§4.17).

Deliberately excluded: transcript-based driver cost measurement (a flat per-step charge is what the owner's config expresses; revisit if postmortems show driver cost matters); lease/TTL/stale-holder takeover (the summary's non-invariant, kept); automatic merge-conflict resolution (never); any daemon, database, or lock server; a web UI or notifications (the owner is in chat); multi-repository rounds.

## 4. Design

### 4.1 Layout

```
<repo>/
  .gitignore                harness/OWNER.log  harness/DRIVER.json  harness/archives/pending/
                            .worktrees/  .claude/worktrees/  __pycache__/  *.pyc  .pytest_cache/
  .claude/settings.json     UserPromptSubmit hook -> py -3.13 harness/src/owner_log_hook.py   (committed)
  spec.yaml  bootstrap/     unchanged
  harness/
    AGENTS.md project.yaml subAgents.yaml locked_prose/    the owner's (spec.yaml); untouched except §7
    plumbing.yaml           runner-owned settings (§4.3)
    INDEX.md                routing, alias -> path (§4.17)
    docs/PROCESS.md DRIVER.md CONFIG.md TESTING.md
    src/run.py              CLI entry, argparse only; delegates to the package
    src/owner_log_hook.py   the chat hook (§4.14)
    src/shackles/           config.py render.py pipeline.py schemas.py state.py ledger.py gitutil.py
                            ownerlog.py checks.py landing.py round.py specdrift.py probe.py
    src/plumbing/*.txt      runner-owned prompt templates (§4.5)
    tests/                  conftest.py stub_agent.py spec_snapshot.json test_*.py fixtures/
    archives/rounds/NNNN/   round folders; archives/rounds/index.jsonl
```

`src/shackles/` is a package because §5 tests units (render, ledger, checks, landing) in-process; `run.py` stays the only entry point, as `AGENTS.md` says.

### 4.2 Roots, paths, ids

- H defaults to `dirname(dirname(abspath(run.py)))`, so a worktree's own `run.py` drives that worktree ("pinned runner"); `--root DIR` overrides and MUST contain `project.yaml`. R = `git -C H rev-parse --show-toplevel`. M = `main_root(R)` via `--git-common-dir` exactly as in the summary §2.1. `HREL` = H relative to R (`harness`).
- All paths in config, artifacts and prompts are H-relative POSIX. `repo_rel(p) = normpath(HREL/p)`; a path resolving outside R is a usage error (S1 finding when it comes from an artifact). `..` is allowed so a target project whose code lives beside `harness/` declares `../app/`.
- Round id: int; width = length of the `N`-run in `roundPaths.folder` (4 today). Branch `round/NNNN`, worktree `<M>/<worktreeDir>/NNNN`, tags `round/NNNN-landed` and `round/NNNN-abandoned`, folder = `roundPaths.folder` with the `N`-run replaced. Next id = 1 + max(local folder ids, origin `round/*` ids), digits-only tails.
- Every path printed in an action or a prompt is absolute: drivers and sub-agents may have another cwd.
- Files are written UTF-8 with `newline="\n"` through one `write_text()` (tmp + `os.replace`); git commands go through one `git(root, *args)` that passes `-c user.name/-c user.email` from `plumbing.gitIdentity`.

### 4.3 Configuration

`cfg = deep_merge(DEFAULTS, plumbing.yaml, project.yaml)`; `roster = load(H/cfg.subAgentsFile)["agents"]`. Owner keys win. Inside a round all three files and the locked prose are read from `prose_commit` with `git show` (the spec is pinned per round; a new round picks up the owner's latest); before `start` and for `plan`/`render`/`spec-check` they are read from the working tree.

DEFAULTS holds every key the runner reads, valued as `project.yaml` is today, plus the runner keys below. A missing key never crashes; a wrong type is a usage error naming the key. `project.*` in prompts is the merged view plus computed `remaining`.

`plumbing.yaml` (header: "Runner settings. Not the owner's; a key the owner adds to project.yaml overrides the same key here."):

| key | default | use |
| --- | --- | --- |
| mainBranch | target of `origin/HEAD`, else `main` | landing |
| worktreeDir | `.worktrees` | round worktrees under M |
| suiteCommand | `py -3.13 -m pytest -q tests` | run from H at CLEANUP-CHECK and LANDING |
| testPattern | `^\s*def test_` | counts suite tests for `testBaseCost` |
| gitIdentity | `{name: shackles-runner, email: runner@localhost}` | runner commits |
| ownerWords | §4.10 table | owner-word regexes |
| ownerHoursPerCheckpoint | 0.2 | attention estimate priced at `ownerHourlyRate` |
| cleanupExtraPaths | `["docs/", "INDEX.md"]` | CLEANUP may touch these besides implPaths |
| promptMaxChars, diffMaxChars | 240000, 60000 | truncation with a reproduce command |
| agentCommand, gateToolFlags, producerToolFlags, scrubEnv | claude CLI template as in the summary §2.2, with `py`-free paths; `--disallowedTools Edit Write MultiEdit NotebookEdit Bash` for gates; `Bash(git push:*) Bash(git commit:*)` for producers; `GH_TOKEN GITHUB_TOKEN GIT_ASKPASS` | headless mode only |
| pushAttempts, infraRetries | 5, 2 | bounds |
| subagentTypes | `{gate: "Explore", producer: "general-purpose"}` | what the driver is told to spawn |

Load-time validation → `cfg.warnings` (a list of one-line strings): unknown or missing gates (§4.4), `maxAgent`/`gateAgent`/`systemTestAgent` not in the roster (fallback: first roster key), fractions outside [0,1], shares not numeric, `livingSourcePaths` entries escaping R. Warnings are printed by `spec-check` and `doctor`, written to HISTORY.md at `start`, and included as `warnings` in every `next` action.

### 4.4 Pipeline

Built-in order in `pipeline.py` (kind P producer, G gate, M mechanical; `chk` = checkpoint raised after it):

```
CHAT-TO-PLAN P (in chat; `start` records it)   CHAT-TO-PLAN-GATE M chk=approval
PLAN-AGENTS P                                   PLAN-AGENTS-GATE G
PLAN-TO-SPEC P                                  PLAN-TO-SPEC-GATE G chk=review-spec
SPEC-TO-TESTS P                                 SPEC-TO-TESTS-GATE G  (tests freeze after acceptance)
SPEC-TO-IMPLEMENTATION P                        SPEC-TO-IMPLEMENTATION-GATE G
TESTS-TO-SUITE P                                TESTS-TO-SUITE-GATE G  (archive applied after acceptance)
CLEANUP P                                       CLEANUP-CHECK M chk=review-landing
LANDING M
POSTMORTEM P                                    POSTMORTEM-GATE G   -> finished
```

Rules (all generic; none parses prose sentences):

- A producer step is present iff `<STEP>-OVERVIEW.txt` exists at `prose_commit`; absent → skipped with a HISTORY line and a warning. A gate is present iff `project.gates[<GATE>]` is truthy and `<GATE>.txt` exists; truthy without prose → warning, mechanical checks only. Mechanical steps are always present. A `gates` key that names no pipeline step → warning; a pipeline gate absent from `gates` → disabled + warning; enabled gates whose relative order differs from the pipeline's → warning. The spec-change test (§4.16) is what turns these warnings into a review.
- A disabled gate means the producer's acceptance is: DONE + the mechanical checks. The step's `chk` still applies (review-spec after PLAN-TO-SPEC's acceptance).
- Overrides (`override` word or `--override`): the named producer steps and gates are skipped this round (HISTORY "skipped (override)"). CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, CLEANUP-CHECK and LANDING cannot be overridden.
- Delegation skips only `review-spec` and `review-landing`; stop checkpoints (§4.10) are never skipped.
- Acceptance of SPEC-TO-TESTS records `tests_frozen_at = HEAD`; testPaths are frozen from there until LANDING completes (M2).

### 4.5 Templating and prompt assembly

**Engine** (`render.py`): tokens `\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}`; namespaces `prose.` (`locked_prose/<NAME>.txt` at `prose_commit`), `plumbing.` (`src/plumbing/<NAME>.txt` from the worktree; `GATE-PROSE` and `PROCESS-INSTRUCTIONS` are computed, below), `project.`, `round.`, `step.`, `agent.`, `paths.`. Dotted keys walk dicts. Unresolved → literal `[[unresolved: <key>]]` in the output and one entry in a `drift` list returned with the text; never an exception. Include depth ≤ 6 → error. Rendering: str as is; int as is; float with 2 decimals, trailing zeros trimmed; list/dict compact JSON; None → `none`. Tokens inside embedded raw text (AGENTS.md, artifacts, diffs) are never expanded: raw text is inserted after substitution, not before.

**Prompt** = rendered `<STEP>-OVERVIEW.txt` (producer) or `<STEP>-GATE.txt` (gate). Nothing is prepended or appended; the owner's prose decides structure, and reaches the runner's text only through `plumbing.*`. `PROMPTS/<STEP>-<attempt>.txt` gets the result; the rendered drift list goes to HISTORY as `drift: project.x, ...` when non-empty.

**`plumbing.PROCESS-INSTRUCTIONS`** = render of `src/plumbing/<STEP>-PROCESS.txt` if it exists, else `PRODUCER-PROCESS.txt` or `GATE-PROCESS.txt`; every process file ends with `{{ plumbing.COMMON-PROCESS }}` (producers) or `{{ plumbing.COMMON-GATE-PROCESS }}` (gates). Mechanics only, no judgment; they name what the runner checks, so agents are told the rails.

**`plumbing.GATE-PROSE`** in a producer prompt: with a present gate, `<STEP>-GATE.txt` rendered in embed mode: a `prose.X` include the producer's prompt already expanded → `(X, as above)`; `agent.*` → `<the artifact you produce>`; `plumbing.PROCESS-INSTRUCTIONS` → `(gate mechanics: read-only, verdict JSON; docs/PROCESS.md)`. With no gate (disabled, absent, or mechanical) → `plumbing/GATE-ABSENT.txt`: "No judging agent runs after this step this round. The runner checks mechanically: {{ step.mechanical_checks }}." (For CHAT-TO-PLAN: "schema of PLAN.json, then the owner's approval word in the owner log.")

**Contract block** `src/plumbing/COMMON-PROCESS.txt` (the text, minus wrapping):

```
RESULT CONTRACT. The runner parses this; follow it exactly.
STEP: {{ step.name }}. ATTEMPT: {{ step.attempt }}. ARTIFACT: {{ agent.artifact_path }}. RESULT_FILE: {{ agent.result_file }}.
ROOT: {{ paths.harness_root }} (all paths below are relative to it). REPO: {{ paths.repo_root }}. WORKTREE: {{ paths.worktree }}.
Budget for this run: ${{ step.budget }}. Max turns: {{ step.max_turns }}. Sub-agents you may spawn at once: {{ step.subagents }}; their cost is yours.
Read {{ paths.agents_md }} first; its bullets are invariants. This prompt was rendered from commit {{ round.prose_commit }}.
Findings so far, with resolutions (empty on the first attempt): {{ agent.findings }}
Your previous final message: {{ agent.previous }}. ARTIFACT holds your previous attempt; revise it in place.
Every finding id MUST appear in your resolutions as fixed or disputed; the gate rules on disputes; a settled finding cannot be disputed.
You may change files only under: {{ agent.allowed_paths }}. Never commit or push; the runner does. Write DEFINED and UNDEFINED judgment calls to {{ round.judgment_files }}, one line each.
Final message: exactly one JSON object and nothing else, also written verbatim to RESULT_FILE:
{"status": "DONE" | "NEEDS-OWNER" | "UPSTREAM" | "BLOCKED", "notes": "<one paragraph>", "question": "<NEEDS-OWNER: the question and the value at stake>", "assumption": "<NEEDS-OWNER: what you built on meanwhile>", "target": "<UPSTREAM: the earlier step whose artifact is wrong>", "resolutions": {"<id>": {"status": "fixed" | "disputed", "reason": "<why>"}}, "cost_usd": <number, if known>}
Omit fields that do not apply. Then: DONE, the runner checks {{ step.mechanical_checks }}, then {{ step.after_done }}. NEEDS-OWNER: {{ step.after_needs_owner }}. UPSTREAM: the round returns to the target step with your notes as a finding. BLOCKED: the round stops for the owner.
```

`COMMON-GATE-PROCESS.txt` differs in the middle: "You are read-only; a run that changes files is discarded (G1)"; the producer's question and assumption; the producer's final message; and the verdict JSON (§4.7). Both blocks are runner text; wording changes here are free.

Per-step process files (`<STEP>-PROCESS.txt`) state inputs, the artifact, and the mechanical checks; the generic one covers any new step the owner adds. Content, one line each in the file:

| step | inputs (`agent.*`) | produces | checks |
| --- | --- | --- | --- |
| CHAT-TO-PLAN | history, todos, clarifications, PLAN schema, the `start` command | `archives/pending/PLAN.json` | S1 at `start`; approval word (CHAT-TO-PLAN-GATE) |
| PLAN-AGENTS | roster (subAgents.yaml text), step list with kinds and gate flags, default shares | AGENTS-PLAN.json | S1 (shares, keys, counts) |
| PLAN-TO-SPEC | agents plan, plan non-goals verbatim, sibling rounds' declared paths | SPEC.json + SPEC.md | S1, M4, M5, W1 |
| SPEC-TO-TESTS | spec, testPaths, verify, plan validation items | files under testPaths | M1 |
| SPEC-TO-IMPLEMENTATION | spec, impl/test paths, verify, frozen note, merge-pending note | files under implPaths | M1, M2, M3 |
| TESTS-TO-SUITE | spec, test files with counts, testBaseCost, suiteCommand | SUITE.json | S1 |
| CLEANUP | spec, allowed paths, verify, suite | files under implPaths + cleanupExtraPaths | M1, M2, M3, suite |
| POSTMORTEM | state summary, FINDINGS/, HISTORY.md, both judgment files, quote vs actual, owner slice | POSTMORTEM.md with headings `## Issues`, `## Traces`, `## TODO`, `## CLARIFICATIONS`, `## Quote versus actual`, `## Judgment calls` | headings present (S1) |

#### 4.5.3 Context namespaces

- `paths`: harness_root, repo_root, worktree, agents_md, run_py (absolute).
- `round`: id (NNNN), folder, base_commit, prose_commit, plan (plain-English rendering of PLAN.json: summary, then Scope/Validation/Non-goals/Assumptions bullets, TODOs taken), budget, spend, remaining, budgets (per step), history (last five index lines as "round N: quoted X actual Y (outcome)"), todos and clarifications (the `- ` lines under `## TODO` / `## CLARIFICATIONS` of the last landed round's POSTMORTEM.md, else `none`), judgment_files, judgment_counts.
- `step`: name, kind, attempt, budget, max_turns, wall_clock_hours, subagents, retry_cost (the producer's budget), mechanical_checks (ids and one-line meanings), after_done, after_needs_owner, gate_enabled, prompt_chars.
- `agent`: artifact_path, result_file, findings (last findings file text + carried non-blocking findings), previous (previous final message, or "changes are in the worktree"), question, assumption, allowed_paths, spec (SPEC.json + SPEC.md text), agents_plan, roster, impl_paths, test_paths, verify, artifact (gates: inline JSON/MD, or the diff `git diff <base> -- <paths>` truncated at diffMaxChars with the command to reproduce), diff_base, test_files, state, sibling_paths.

### 4.6 Artifacts and schemas

Validation is a hand-written `validate(obj, schema, name, cfg) -> [errors]` (required/optional keys, types string/number/integer/boolean/object/array, plus the rules below); no jsonschema dependency. Unknown keys are allowed.

- PLAN (`PLAN.json`): required `round` int, `presented_at` UTC `%Y-%m-%dT%H:%M:%SZ`, `quote_usd` number, `summary`, `scope[]`, `validation[]`, `non_goals[]`, `assumptions[]`; optional `todos{id: {todo, status: taken|deferred, reason, budget_usd (taken)}}`, `clarifications{id: {question, answer}}`.
- AGENTS_PLAN: required `round`, `agents{step: rosterKey}`, `shares{work{step: frac}, gates{step: frac}}`, `subAgents{step: int}`, `notes`. Rules: keys are present producer/gate steps; roster keys exist; each `shares` part sums to 1 ± 0.01 over present steps (mechanical steps and disabled gates must be 0 or absent); `subAgents` ≤ maxSimultaneousSubAgentsPerRound.
- SPEC (`SPEC.json`): required `round`, `summary`, `verify` (command, run from H), `implPaths[]`, `testPaths[]`, `nonGoals[]`; optional `verifyTimeoutSeconds`, `refactor[{what, budget_usd}]`, `body` (default `SPEC.md`), `testPlan`, `specEdits` bool (§4.16). Rules: paths inside R; implPaths/testPaths prefix-disjoint; `SPEC.md` exists.
- SUITE: required `round`, `keep[]`, `archive[]`, `notes`; optional `raise_to_owner[]`. Rules: every path under testPaths and existing; keep/archive disjoint.
- POSTMORTEM.md: the six headings of §4.5 present.
- RESULT and FINDINGS: §4.7. STATE: §4.8.

### 4.7 Result contracts

Producer final message: `{"status", "notes", "question"?, "assumption"?, "target"?, "resolutions"?, "cost_usd"?, "judgment_calls"?: {"defined": [..], "undefined": [..]}}`. Unknown status → treated as BLOCKED with finding S1 "unknown status".

Gate final message:

```
{"verdict": "PASS" | "FAIL",
 "findings": [{"id": "F<n>", "quote": "<verbatim text judged>", "reason": "<why>", "suggestion": "<what would prevent the FAIL>", "blocking": true | false}],
 "rulings": {"<id>": {"status": "upheld" | "withdrawn", "quote": "<verbatim>"}},
 "needs_owner": {"status": "upheld" | "withdrawn", "reason": "<why; withdrawn: the answer to assume>"},
 "notes": "<one line>", "cost_usd": <number>?, "judgment_calls": {...}?}
```

Ids continue from the highest prior id. The runner normalizes: verdict is FAIL iff any finding is blocking or `needs_owner` is upheld (a mismatch is corrected and noted in HISTORY). A finding missing `suggestion` gets `suggestion: "(none given)"` and a HISTORY note. A new finding whose `quote` equals a withdrawn finding's quote is dropped with a HISTORY note ("re-raised withdrawn finding F3 dropped").

### 4.8 STATE.json (the runner's only state; validated on every save)

```
round int; branch; mode "worktree"|"no-branch"; created_at; status active|checkpoint|finished|abandoned
step; kind_pending producer|gate|null; attempts{step:n}; failures{step:n}; infra_errors{step:n}
step_starts{step:sha}; step_commits{step:sha}; inputs_hash{PLAN, SPEC}; budget_usd
spend{entries[], agent_usd, driver_usd, owner_usd, living_usd, tests_usd}
base_commit; prose_commit; approval{word, quote, at}|null; delegated null|"all"|"through:STEP"; overrides[]
agent_override rosterKey|null; checkpoint{reason, step, question, artifact, at}|null
pending_question{question, assumption}|null; last_findings{producer: relpath}; carried_findings[]
findings_ledger{id: {upheld_count, settled, withdrawn, quote}}; mech_ok{gate: attempt}
tests_frozen_at sha|null; merge_tip sha|null; conflicted_files[]; round_retries int
hard_stop_raised bool; round_limit_raised bool; landed_at; abandoned_at; main_before; owner_since
judgment_counts{defined, undefined}; spec_edits[] (paths a round changed, §4.16)
```

No worktree path, lock, lease, pid or owner field: ownership is "can I still push this branch".

### 4.9 Commands

Invocation: `py -3.13 <H>/src/run.py [--root H] [--round N] <cmd>`. Every command prints exactly one JSON object on stdout (errors: `{"error": msg}` on stderr). Exit codes: 0 ok, 1 error, 2 usage (bad arguments, out-of-order record), 3 check or drift failed, 10 checkpoint.

| command | reads | writes | notes |
| --- | --- | --- | --- |
| `plan` | working tree, index, last postmortem, owner log | `archives/pending/CHAT-TO-PLAN.txt` | renders the CHAT-TO-PLAN prompt for the driver itself; prints its path, the PLAN schema, and the `start` command to run after approval |
| `start --plan F [--budget USD] [--branch NAME] [--no-branch] [--delegated all\|through:STEP] [--agent KEY\|--system-test] [--override STEP,...] [--plan-cost USD]` | plan file, origin refs, owner log | claim, worktree, round folder, start commit + push | validates the plan before any git command (I2); prints `{round, folder, branch, worktree, runner}` |
| `next [--no-push]` | STATE, owner log, git | mechanical effects, prompt file, STATE, commit | prints an action (§4.10) |
| `record --step S --attempt N [--result F] [--cost USD] [--tokens N --agent KEY]... [--no-push]` | result JSON, STATE | RESULTS/, FINDINGS/, STATE, HISTORY, commit + push (the fence) | `--result` defaults to the action's result file |
| `run --until checkpoint\|step\|done [--no-push]` | | | headless: `next` → `agentCommand` → `record`; `infraRetries` per run |
| `status` | STATE | | step, kind, attempts, failures, spend, checkpoint, judgment counts, warnings |
| `spend [--project]` | STATE, index, live rounds | | ledger and totals |
| `check` | STATE, git, verify/suite | nothing shared | the current step's mechanical checks (I9) |
| `abandon --reason R` | STATE | status, tag, index line, commit (+push in worktree mode, rejection ignored) | |
| `rounds` | folders, origin refs, worktrees | | live/finished rounds; claimed ids with no commit past the claim; worktrees with no folder (the prune report; nothing is deleted) |
| `doctor` | machine, repo | | py version, PyYAML, git, origin reachable, `.gitignore` has worktreeDir and `.claude/worktrees/`, hook installed, mainBranch not checked out in any worktree, config warnings |
| `render --step S [--attempt N]` | STATE or a fixture | stdout | dry-run prompt; never touches state |
| `spec-check [--update]` | spec.yaml files, snapshot | snapshot on `--update` | §4.16; exit 3 on drift |
| `judgment-calls` | round folder | | both files, counts |
| `probe`, `sandbox` | | temp dirs | §6 |

Action JSON from `next` (`kind` producer/gate): `{round, step, kind, attempt, agent: {key, name, model, effort, tools: "all"|"read-only", subagent_type}, prompt_file, result_file, artifact, budget_usd, max_turns, wall_clock_hours, subagents, spend, worktree, runner, record_command, warnings, runner_skew}`; `kind` checkpoint: `{round, step, reason, question, artifact, spend, owner_message, judgment_counts}` with exit 10; `kind` done: `{round, status, main_synced, spend}`. `record_command` is the exact `record` line to run next and `owner_message` the exact text to relay at a checkpoint: the driver's freedom is limited to spawning and relaying.

### 4.10 `next`, `record`, routing

**`next`**, in order:

1. `finished`/`abandoned` → `sync_main` (§4.13) → done.
2. Re-hash PLAN.json and SPEC.json+SPEC.md (`inputs_hash`). PLAN changed → approval cleared, step CHAT-TO-PLAN-GATE, downstream counts reset, `round_retries += 1`. SPEC changed after its acceptance → step SPEC-TO-TESTS, downstream reset, `round_retries += 1`. HISTORY line either way.
3. Dirty tree (`git status --porcelain` non-empty): if `merge_tip` is set and `MERGE_HEAD` exists, this is the expected conflicted state, keep it; else `git checkout -- .`, `git clean -fdq`, `infra_errors[step] += 1`, HISTORY line. (`.gitignore` MUST contain worktreeDir; `start` and `doctor` refuse otherwise.)
4. Refresh this round's owner-log slice (§4.14).
5. `checkpoint` status: look for an owner word after `checkpoint.at`; none → commit the slice, print the checkpoint, exit 10. Found → apply (table below), continue.
6. Loop over mechanical work until an agent run is due:
   - CHAT-TO-PLAN-GATE: S1 on PLAN.json; if the gate is enabled, need an approval word after `presented_at` (abandon → abandon; none → checkpoint `approval`); if disabled, `approval = {word: "assumed (gate disabled)"}` and `--delegated` decides delegation. Charge plan words (§4.12). Advance.
   - a present gate for a code step whose mechanical checks have not passed for the current producer attempt (`mech_ok[gate] != attempts[producer]`): run them; findings → route to the producer (below); clean → `mech_ok`.
   - a disabled gate: the same mechanical checks, then acceptance effects (freeze / archive / chk) and advance.
   - CLEANUP-CHECK: M1, M2, M3, suite; findings → CLEANUP; clean → checkpoint `review-landing` unless delegated through it; then advance.
   - LANDING: §4.13.
   - a skipped step (override or absent) → HISTORY line, advance.
   - hard stop or a pending checkpoint → break.
7. Render the prompt for `(step, attempts[step] + 1)`, record `step_starts[step]` (producers, first attempt only), save, commit (no push), print the action.

**`record`**: reject unless `status == active`, `state.step == S`, `N == attempts[S] + 1` (exit 2). Result unreadable or not a JSON object → `infra_errors[S] += 1`, tree reset, exit 1 with "rerun next"; after `infraRetries` at the same attempt → finding I1 "no valid result twice: narrow the step" routed as a FAIL. Otherwise: copy to RESULTS/, `attempts[S] = N`, ledger entries (agent cost, driver), append gate judgment calls to the files, count new judgment lines, validate against RESULT/FINDINGS, route, `check_limits`, save, commit `round NNNN: <S> attempt <N>`, push (worktree mode; rejection → `RunnerError("another runner owns this round (push rejected)")`, exit 1). A gate run that left the tree dirty → G1: discarded as an infrastructure error (reset, attempt not consumed).

**Routing table**:

| event | effect |
| --- | --- |
| producer DONE | JSON artifact → S1; code step → mechanical checks run by `next` before the gate; CLEANUP → commit artifact then CLEANUP-CHECK; POSTMORTEM → gate or finished; else advance |
| producer NEEDS-OWNER | gate present: `pending_question` travels to the gate. Gate absent: not delegated → checkpoint `needs-owner`; delegated → proceed on the assumption, append one line to UNDEFINED_JUDGMENT_CALLS.md ("assumed: ..."), HISTORY line |
| producer UPSTREAM target T | T must be an earlier present producer (else S1 finding to the same step). Findings U1 (notes) to T; reset downstream (`attempts`, `failures`, `step_starts`, `step_commits`, `last_findings`, `mech_ok`, `tests_frozen_at` if T ≤ SPEC-TO-TESTS); `round_retries += 1`; T == CHAT-TO-PLAN → checkpoint `upstream-plan` |
| producer BLOCKED | finding B1; `failures[S] += 1`; checkpoint `blocked` (owner narrows the plan/spec, approves a retry, or abandons) |
| gate PASS | `step_commits[gate] = HEAD`; non-blocking findings → `carried_findings` (shown to later producers); acceptance effects; advance; `chk` if any |
| gate FAIL | `last_findings[producer]`, `failures[producer] += 1`, step = producer; `limit_hit` |
| `needs_owner` upheld | checkpoint `needs-owner` with the question; the owner's answer returns as finding O1 (blocking) to the producer |
| `needs_owner` withdrawn + PASS | advance; the answer to assume is appended to DEFINED_JUDGMENT_CALLS.md by the runner and logged |
| `needs_owner` withdrawn + FAIL | finding Q1 (the answer to assume) + the findings → producer |
| mechanical findings (S1, M1–M5, L1, L2) | as gate FAIL, source `mechanical`, no gate spent |
| resolutions | each `disputed` on a settled id → S2 finding (treated as upheld); rulings update the ledger: `upheld_count`, `settled` at 2, `withdrawn` recorded with the quote |

**Limits** (`limit_hit`): `failures[producer] ≥ maxFailuresBeforeStop` → checkpoint `failure-limit` (approve resets that count); `round_retries > maxRoundAttempts` → checkpoint `round-limit` once (approve continues). Spend > `hardStopBudgetMultiple × budget_usd` → checkpoint `hard-stop` once, evaluated on every ledger entry and before each prompt.

**Owner words** (`plumbing.ownerWords`, regexes, case-insensitive; the latest qualifying owner-log line after the checkpoint's timestamp decides; envelope lines are skipped):

| word | regex | effect |
| --- | --- | --- |
| abandon | `\babandon\b` | abandon |
| delegate through | `\bdelegated?\s+through\s+([A-Za-z-]+)` | approve + `delegated = through:STEP` |
| delegate | `\bdelegated?\b` | approve + `delegated = all` |
| approve | `\bapproved?\b` | approve; `failure-limit` → reset that step; `needs-owner` → the whole message is finding O1 |
| override | `\boverride\b((?:\s+[A-Z][A-Z-]+)+)` | adds each name to `overrides` (checked against the pipeline; unknown names → HISTORY note); may accompany approve |

Checkpoint reasons: approval, review-spec, review-landing, needs-owner, failure-limit, round-limit, hard-stop, blocked, upstream-plan, spec-edit (§4.16). Every checkpoint charges owner cost (§4.12) and writes HISTORY; `owner_message` lists the accepted words.

**Acceptance effects**: SPEC-TO-TESTS → `tests_frozen_at`; TESTS-TO-SUITE → `git mv` each `archive[]` path into `<round>/tests-archive/` (basename; collisions get a numeric suffix); PLAN-TO-SPEC → charge spec words, checkpoint `review-spec`; POSTMORTEM → status `finished`, index line (§4.12), `sync_main`.

### 4.11 Mechanical checks (`checks.py`)

| id | when | rule |
| --- | --- | --- |
| S1 | artifact steps | schema and rules of §4.6; unreadable JSON; unknown status/target |
| S2 | any producer | disputed a settled finding |
| M1 | SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, CLEANUP | `git diff --name-only <base> HEAD` has a file outside allowed paths ∪ round folder (∪ `conflicted_files` after L1; ∪ cleanupExtraPaths for CLEANUP) |
| M2 | SPEC-TO-IMPLEMENTATION, CLEANUP, CLEANUP-CHECK | a testPaths file differs from `tests_frozen_at`, unless HEAD's content equals `merge_tip`'s (inherited from a sibling) or the file is in `conflicted_files` (then non-blocking "merged test, review") |
| M3 | same as M2 + CLEANUP-CHECK | `verify` fails or times out (`verifyTimeoutSeconds`, spec override) |
| M4 | PLAN-TO-SPEC | Σ `refactor[].budget_usd` > maxRefactorOverhead × budget_usd |
| M5 | PLAN-TO-SPEC | a plan `non_goals` string missing verbatim from `nonGoals` |
| W1 | PLAN-TO-SPEC (non-blocking) | implPaths overlap a live sibling round's declared paths (§4.13) |
| G1 | any gate | the gate's run changed tracked files or left untracked ones (besides RESULT_FILE) |
| L1, L2 | LANDING | conflict; verify or suite red after the merge |
| I1 | record | no valid result after `infraRetries` |

Diff base for M1/M2: `merge_tip` when set and later than `step_starts[step]`, else `step_starts[step]` (CLEANUP: its own start). Allowed paths: SPEC-TO-TESTS = testPaths; SPEC-TO-IMPLEMENTATION = implPaths; CLEANUP = implPaths ∪ cleanupExtraPaths; the round folder always. Spec.yaml files are allowed only when `SPEC.json.specEdits` is true, and then flagged (§4.16). `verify` and `suiteCommand` run via `subprocess.run(cmd, shell=True, cwd=H, timeout=...)`, output tail (3000 chars) quoted in the finding.

### 4.12 Spend (`ledger.py`)

Ledger entries `{step, attempt, usd, source, at, extra}`; buckets by source: `agent` (reported `--cost` or result `cost_usd`; else `--tokens` × blend (`estOutputFraction` of output price + rest input price) per `--agent` key; else the roster `spawnCost` floor; the floor also applies as a minimum when a reported cost is below it), `driver` (`driverUsdPerStep` per `record`, plus once at `start` for the planning turns unless `--plan-cost`), `owner` (per checkpoint: `costToWaitForOwner` + `ownerHoursPerCheckpoint × ownerHourlyRate`; plus `planCostPerWord × words(round.plan)` once at approval and `specCostPerWord × words(SPEC.md)` once at spec acceptance), `living` and `tests` (LANDING). `time_usd = hours(now − created_at) × lostValuePerHour` while not finished/abandoned, computed, not stored. `total = Σ buckets + time`.

Living charge at LANDING against the merged tip T (or `base_commit` without a target): for each file under `livingSourcePaths` in HEAD ∪ T, `tokens = ceil(bytes / tokenBytes)`, `price(n) = min(n, cap) × perToken + max(0, n − cap) × perTokenOverCap`; charge `price(tokens_HEAD) − price(tokens_T)`, `+ livingFileBaseCost` for a file absent in T, `− livingFileBaseCost` for a file absent in HEAD. Tests: `testBaseCost × (matches of testPattern in kept testPaths files at HEAD − at T)`, never below 0. Exactly one living and one tests entry per landed round (I8).

Index line (`archives/rounds/index.jsonl`, append-only): `{id, quote_usd, budget_usd, spend: summary, attempts, failures, infra_errors, round_retries, judgment_counts, outcome landed|abandoned, prose_commit, landed_at|abandoned_at}`. `spend --project` = index totals + live round totals; `project.remaining` = budget − that.

### 4.13 Concurrency (`landing.py`, `gitutil.py`, `start`)

Adopt the summary's protocol and invariants I1–I11 unchanged where not listed here; git is the lock manager.

- **Claim** (`start`): validate the plan first; `git fetch origin`; ids from `refs/remotes/origin/round/<digits>` and local folders; loop `pushAttempts` times: `git push --porcelain --force-with-lease=refs/heads/<branch>: origin HEAD:refs/heads/<branch>`; win = exit 0 and a stdout line starting with `*`; `=` and `!` lose; an explicit `--branch` gets exactly one push. On a win: `git worktree add -b <branch> <M>/<worktreeDir>/NNNN HEAD`; everything after that runs with the worktree's H as root: round folder from `roundPaths`, PLAN.json (round set), STATE.json (`base_commit = prose_commit = HEAD`), HISTORY.md, empty DEFINED/UNDEFINED judgment files, the owner slice from `presented_at`, ledger opening entries, config warnings → HISTORY; `git add -A`, commit `round NNNN: start`, `git push -u origin <branch>`. `--no-branch`: id = local max + 1, no fetch/CAS/worktree/push.
- **Preconditions refused up front** by `start` (and reported by `doctor`): `.gitignore` lacks `<worktreeDir>/`; `mainBranch` checked out in any worktree (`git worktree list --porcelain`); origin unreachable (worktree mode); the working tree dirty.
- **Fence**: every `record` commits and pushes the round branch, non-forced; rejection aborts with `another runner owns this round (push rejected)`.
- **Pinned runner**: `start` prints `runner` = the worktree's `src/run.py`; `next` compares sha256 of `src/run.py` + `src/shackles/*.py` between the running copy and `<H>/src` and sets `runner_skew: true` in the action (a warning, not a stop).
- **Sibling overlap** (W1): at PLAN-TO-SPEC acceptance, for each `origin/round/*` branch without a `-landed`/`-abandoned` tag, `git show origin/round/NNNN:<roundfolder>/SPEC.json` (best effort, errors ignored); prefix-overlap of implPaths/testPaths → non-blocking finding carried to the gate and shown in `agent.sibling_paths`.
- **LANDING** = check phase then land phase, as the summary §3.4, with `pushAttempts` bounding the push loop, `main_before` recorded, verify + `suiteCommand` under `verifyTimeoutSeconds`, exactly one living and one tests entry after the push, tag `round/NNNN-landed`, `landed_at`. Check phase is what `check` runs at LANDING (I9).
- **Conflict path that converges** (the summary's §6.1): on `git merge --no-edit <target>` failure the runner does NOT abort. It records `merge_tip = <target sha>`, `conflicted_files` (`git diff --name-only --diff-filter=U`), writes finding L1 listing them with "resolve the markers; run verify", routes to SPEC-TO-IMPLEMENTATION (`failures += 1`, `round_retries += 1`), leaves the tree conflicted, commits nothing. Step 3 of `next` keeps the tree. The producer's PROCESS-INSTRUCTIONS carry a merge-pending note and the allowed set includes `conflicted_files`. `record` for that attempt stages everything and commits (completing the merge, message `round NNNN: merge <target> for landing`), then M1/M2 run against `merge_tip` (§4.11), so the sibling's files are not "outside declared paths" and its test changes are not "changed tests". L2 (red after a clean merge) routes to SPEC-TO-IMPLEMENTATION the same way with `merge_tip` set. A rerun of `next` after a crash mid-conflict finds `MERGE_HEAD` and resumes at the producer attempt.
- **Post-round sync** `sync_main(push)`: fast-forward only, as the summary §3.5; `main_synced` reported; never raises.
- **Prune report**: `rounds` lists claimed ids whose origin branch has exactly one commit past its base and no folder (never-started), worktrees without a folder, and tags; deletion is the owner's.
- **Config skew**: every key has a default (§4.3), so a sibling landing a new key cannot break a live round.
- **Landing order**: none needed; the loop absorbs siblings in any order, and `sync_main` catches the tail. Two rounds editing the same living file discover it at landing only (kept, with W1 as the early warning).

### 4.14 Owner log (`owner_log_hook.py`, `ownerlog.py`)

`.claude/settings.json` registers a `UserPromptSubmit` hook: `py -3.13 harness/src/owner_log_hook.py`. The hook reads the JSON on stdin, resolves M from `CLAUDE_PROJECT_DIR` (or cwd) via `--git-common-dir` so a worktree session still logs to `<M>/harness/OWNER.log` (gitignored), writes `<M>/harness/DRIVER.json` (session id, transcript path), skips empty prompts and envelope-prefixed ones (`<task-notification`, `<system-reminder`, `[SYSTEM NOTIFICATION`, `Stop hook feedback`, `<wake `, `<webhook-payload`, `<event `; list in `plumbing.envelopePrefixes`), and appends `<UTC ISO-8601 Z>\t<message, backslash and newline escaped>`. It never raises (a failing hook would block the owner's chat). The runner copies new lines since `owner_since` (= `presented_at`) into `<round>/OWNER.log` on every `next`; owner words are read from the slice only. Only `next` reads outside the worktree, and only this file.

### 4.15 Judgment-call monitoring

- `start` creates both files (names from `roundPaths.judgmentCalls`) with a one-line header; the header is not counted.
- Every prompt names both files (§4.5) and AGENTS.md is read first, so producers append; gates are read-only and return `judgment_calls` in their verdict, which `record` appends with the suffix ` (via runner, <GATE>-<attempt>)`.
- `record` counts new non-empty lines per file since the previous attempt and writes `judgment calls: +d defined, +u undefined` to HISTORY and `judgment_counts` to STATE; runner-made assumptions (§4.10) are appended and counted too.
- Every checkpoint's `owner_message` ends with the counts and the absolute path of the UNDEFINED file when it grew since the last checkpoint: the owner sees undefined calls before deciding.
- POSTMORTEM receives both files and must review them under `## Judgment calls` (heading check S1); the index line records the counts, so `rounds` shows the trend.

### 4.16 Spec-change protocol (`specdrift.py`)

- `tests/spec_snapshot.json`: `{"taken_at": commit, "spec_yaml": sha256, "files": {path: {"sha256", "lines"}}}` over every file `spec.yaml` lists.
- `compare(root, snapshot) -> [Drift]`, kinds: `changed` (with `git diff <taken_at> -- path` when the commit exists locally, else "content changed, n → m lines"), `removed` (listed, missing on disk), `added` (listed, not in the snapshot), `unlisted` (a file under `lockedProsePath` that spec.yaml does not list), `spec_yaml_changed`, `snapshot_missing`. `update(root)` rewrites the snapshot.
- `tests/test_spec_snapshot.py::test_spec_files_unchanged` fails on any drift with: the drift list and diffs, then "Review the effects on: pipeline (§4.4), template keys (render `spec-check` lists unresolved ones), owner words, checkpoints, statuses, path names; then `py -3.13 harness/src/run.py spec-check --update` in the same commit as the review." `SHACKLES_ROOT` env overrides the root so the meta-test can point it at a temp repo.
- `spec-check` prints the drift list, config warnings, the unresolved-token list from rendering every prose file with a full fixture context, and prose files not reachable from any step; exit 3 on drift.
- A round that edits spec files: only with `SPEC.json.specEdits: true`; at every `record` the runner diffs spec.yaml files against `base_commit`, stores the paths in `spec_edits`, writes the full diff to HISTORY under `## SPEC EDIT`, and raises checkpoint `spec-edit` before LANDING regardless of delegation, with `owner_message` = the diff. The bootstrap edits in §7 are flagged in the implementer's report the same way (full diff).

### 4.17 Docs and INDEX.md

All living, dense, one idea per line (sentence-per-line reduces merge conflicts):

- `INDEX.md`: `alias, alias -> path` lines: process/rules/checkpoints/disputes → docs/PROCESS.md; driver/how to run a round → docs/DRIVER.md; config keys/defaults → docs/CONFIG.md and plumbing.yaml; runner/commands/exit codes → src/run.py --help; schemas/contracts → src/shackles/schemas.py and src/plumbing/COMMON-*.txt; prose → locked_prose/; rounds/archives/index → archives/rounds/; owner log/hook → src/owner_log_hook.py, .claude/settings.json; tests/suite/real-agent loop → docs/TESTING.md; spec change → docs/PROCESS.md §Spec changes and tests/spec_snapshot.json.
- `docs/PROCESS.md`: the normative rules, i.e. §4.4, §4.10–4.16 of this plan condensed: principles, round and folder, steps and gates, runner, agents and contracts, failure/dispute/re-entry, checkpoints and owner words, spec and code rules, landing, judgment calls, spec changes, robustness rules ("the runner never parses a prose sentence; every prose-defined word lives in plumbing.yaml or the contract templates").
- `docs/DRIVER.md`: the driver loop on this machine, step by step: `plan` → chat → `start`; `next` → spawn a fresh sub-agent with the prompt file verbatim (Agent tool: `subagent_type` and `model` from the action; no worktree isolation; effort cannot be set via the tool, note it) → the sub-agent writes RESULT_FILE → `record_command` → repeat; at exit 10 relay `owner_message` and wait; never do a gate's job; never commit or push; `--no-push` only in `--no-branch` mode.
- `docs/CONFIG.md`: every owner key (from §2.4) and every plumbing key with its default and effect.
- `docs/TESTING.md`: the suite (`py -3.13 -m pytest -q harness/tests`), fixtures, the stub, `probe`/`sandbox`, the staged real-agent loop (§6).

## 5. Test strategy

Partial integration, no mocks of git, pytest, `py -3.13 -m pytest -q harness/tests`, target under 150 s. Every test builds a throwaway repo in `tmp_path` holding a copy of the real spec files, `plumbing.yaml` with `agentCommand` repointed at the stub, the real `src/`, and drives it through the CLI (`subprocess.run([sys.executable, run.py, ...])`) or in-process (`round.Round`), asserting exit codes, stdout JSON, files and git state. Hermetic git env: `GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed author. Windows: no symlinks, `\n` newlines, close handles before removing worktrees, `shutil.rmtree` with a read-only `onexc` handler.

**Fixtures** (`conftest.py`): `Repo` (init, `.gitignore`, config copies, commit; `add_origin()` bare repo by absolute path; `clone()` for "another machine"; `view(worktree)`; `run(*args)` → `(code, json, stderr)`; `play(until=STEP, modes=...)` drives the stub in-process to a step in seconds); `Origin` (truth via `git -C origin.git rev-parse`); `overrides(project=..., plumbing=..., prose=...)` to vary config and prose per test without editing spec files. `stub_agent.py`: reads the last `STEP:`/`ARTIFACT:`/`RESULT_FILE:` lines, writes canned artifacts for a tiny sample task (`tests/fixtures/sample_project/`: a two-function module and its tests), prints the final JSON; `STUB_MODE=pass|fail|dispute|needs_owner|upstream|blocked|garbage|dirty_gate|unknown_status|spec_edit`, `STUB_FENCE`, `STUB_ARCHIVE`, `STUB_LOG`, `STUB_JUDGMENT=n` (append n undefined lines), `STUB_COST`; the same `perform()` serves in-process.

**Race seam**: `gitutil.HOOKS = {"before_push": None, "before_fetch": None}`; in-process tests set callables that move `origin/main` (or reject by moving the round branch) between fetch and push; the CLI path is covered by the narrowed-fetch-refspec trick from the summary §5, which needs no hook. Git-hook variants are marked `skipif(no sh)`.

Test files and what each pins (numbers are the case lists the implementer expands one test per line):

- `test_spec_snapshot.py`: current snapshot matches → passes. `test_spec_snapshot_meta.py`: in a temp repo: unchanged → `[]`; one byte changed → one `changed` drift naming the file whose diff contains the new line; file removed → `removed`; new file listed → `added`; unlisted prose file → `unlisted`; spec.yaml edited → `spec_yaml_changed`; snapshot missing → `snapshot_missing`; `--update` then clean; the real pytest test run via subprocess with `SHACKLES_ROOT` fails (exit 1, message names the file and shows the diff) then passes after `--update`.
- `test_render.py`: includes expand; unresolved → placeholder + drift, no exception; depth limit; number/list formatting; embed rules (as-above, artifact placeholder, process line); raw insertion does not expand tokens inside AGENTS.md or artifacts; every locked prose file renders with a full fixture context and the drift set is exactly the known set (today `{project.ownerReviewCostPerWord}`; empty after §7); plumbing templates render with zero drift; `render --step` never changes state.
- `test_config.py`: defaults ← plumbing ← project precedence; missing keys tolerated; wrong type is a usage error naming the key; `NNNN` width from `roundPaths.folder` (also `NNN`); gates unknown/missing/reordered → warnings; roster fallback; `project.remaining`.
- `test_pipeline.py`: present steps from prose files (delete `CLEANUP-OVERVIEW.txt` in the fixture → skipped with HISTORY line); gate present iff enabled and prose exists; overrides skip, protected steps refuse; delegation semantics incl. `through:STEP`; checkpoints raised at the right places, not when delegated; disabled gate = DONE + mechanical checks + acceptance effects.
- `test_round_flow.py` (`--no-branch`): a full round gates-off and gates-on with the stub; each status path (DONE, NEEDS-OWNER with gate present/absent/delegated, UPSTREAM to each earlier step incl. CHAT-TO-PLAN, BLOCKED); verdict normalization; missing suggestion; withdrawn re-raise dropped; disputes, settled at two upholds, S2; carried findings appear in later prompts; limits (failure-limit resets on approve, round-limit, hard-stop once); out-of-band PLAN/SPEC edits re-enter; record idempotency (replay/out-of-order → exit 2); infra errors (garbage result twice → I1); G1 dirty gate; unknown status → BLOCKED; archive applied; frozen tests (M2) with the freeze starting at acceptance; M1/M3/M4/M5; HISTORY narrative order; every `next` action carries `record_command` and absolute paths; STATE validates on every save; crash mid-step resumes (kill after prompt render, rerun `next` returns the same attempt).
- `test_owner_words.py`: each word, case, `delegate through X`, `override A B`, latest-message-wins, timestamps after the checkpoint only, envelope lines ignored, hook escaping round-trips; the hook writes to M from a worktree cwd, never raises on bad stdin.
- `test_spend.py`: agent cost sources and the spawn floor; driver per record; owner per checkpoint and word charges once; living charge with cap crossing, base cost on new/deleted files, refunds, `__pycache__` ignored; tests count via `testPattern`; one living + one tests entry per landed round; time cost; `spend --project` sums index + live; index line fields.
- `test_judgment_calls.py`: files created at start with headers; producer lines counted; gate lines appended via runner with the suffix; runner assumption lines; counts in STATE, HISTORY, checkpoint `owner_message`, index line; POSTMORTEM heading check.
- `test_concurrency.py` (worktree mode, local bare origin): claim (one-line stdout `{round, folder, branch, worktree, runner}`, worktree on `round/0001`, main checkout untouched, no folder in any commit on a lost race); lost race takes the next id; bounds with the seam rejecting all (`round id: push rejected 5 times`); explicit branch taken → one push; `worktree add` failure keeps the claim; id sourcing ignores `round/003-x`, `round/abc`, tags; preconditions refused (gitignore, main checked out, dirty tree); fence (`another runner owns this round`); landing after a sibling moved main (check phase touches nothing; then `run --until done` leaves `origin/main == local main == round tip`, both rounds' files, living entry equals this round's diff only); rejected main push retried within one `next`; reject-all → exit 1, state still at LANDING, lands on rerun; conflict → L1 with `conflicted_files`, tree left conflicted, stub resolves, `record` completes the merge, M1/M2 use `merge_tip`, round lands; L2 path; `sync_main` true/idempotent/false-when-moved; `runner_skew`; `rounds` prune report; W1 overlap warning.
- `test_cli.py`: exit codes; `--root` and default root; `status`, `spend`, `check` (I9), `abandon` from each status, `doctor` findings on a repo missing each precondition, `spec-check` exit 3 and `--update`, `judgment-calls`, `plan` output, `probe`/`sandbox` on the stub.
- `test_headless.py`: `run --until step|checkpoint|done` with the stub as `agentCommand`; tool flags per kind; scrubbed env (`STUB_LOG`); fenced JSON unwrapped; `infraRetries`; wall-clock timeout surfaces as an infra error.
- `test_docs.py`: INDEX.md aliases resolve to existing paths; every CLI command appears in DRIVER.md or PROCESS.md; every key in DEFAULTS is documented in CONFIG.md; no source file contains a sentence copied from locked prose (any 8-word window shared with a prose file) so mechanical behavior cannot silently depend on wording.

## 6. Real-agent testing loop

The owner's loop (tiny task end to end, gates off, then on, then variants) stays as the final stage; three cheaper stages before it find most defects for a fraction of the cost and are repeatable after every prose edit, which is the owner's stated habit.

1. **Dry runs, free**: `render --step S` for all 13 agent steps (fixture context); the reviewer reads the prompts as an agent would; `spec-check` shows drift. Done on every prose change.
2. **Single-step probes, cents each**: `probe --step S [--agent KEY] [--fixture NAME]` builds a temp repo, plays the stub to just before S, renders the real prompt and prints an action; the driver spawns one real sub-agent (default `systemTestAgent`); `probe --check RESULT_FILE` then validates the result contract, the artifact schema, path confinement, verify, and prints a scorecard `{contract, schema, paths, verify, judgment_lines, notes}`. Thirteen probes in parallel exercise every prompt independently; a gate probe on a `defect-*` fixture (a canned implementation with a planted bug, or a spec with a planted ambiguity) measures gate effectiveness directly, which the end-to-end loop measures only by accident. Prose relaxation decisions (§9) are made from probe scorecards, not guesses.
3. **Sandbox rounds, dollars each**: `sandbox --new DIR` clones the repo to a temp dir with a bare origin, copies `tests/fixtures/sample_project/` as the target and adjusts nothing in the spec; real rounds run there with `start --system-test --delegated all` (no checkpoints, cheap model): gates off, then on; then `--delegated` omitted (checkpoints), `--override` (skips), two rounds at once (concurrency), and an L1 conflict provoked by editing the same file in both. Nothing lands on the real main. Real RESULTS/FINDINGS from probes and sandboxes are copied into `tests/fixtures/corpus/` (small JSON) and `test_contracts_corpus.py` replays them through the validators, so contract changes are checked against real agent output.
4. **The real repository**: the owner's tiny task through the harness on the real main, once stages 1–3 are green.

Why cheaper and more comprehensive: a full round is ~16 agent runs and finds one defect per run; probes cost one run per step, isolate prose problems from runner problems, run in parallel, and are the only stage that can measure whether a gate catches a planted defect.

## 7. Spec-file edits

Two edits, one token each, to make the prose reference keys that exist. The runner works without them (placeholder + drift), so they can be deferred; recommended now because the placeholder would otherwise show agents a literal `[[unresolved: ...]]` where a price belongs.

```
--- harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
--- harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```

Alternative with zero prose edits: add `ownerReviewCostPerWord: 0.1` to `project.yaml` (then `planCostPerWord`/`specCostPerWord` are unused). The implementer applies whichever the owner picks, in its own commit, with the diff above in the report, and updates `tests/spec_snapshot.json` in that commit. No other spec file needs an edit: `AGENTS.md`'s paths (`src/run.py`, `docs/PROCESS.md`, `INDEX.md`) are satisfied by the layout, and gate language is left as written until probe scorecards (§6.2) show gates cannot pass; candidate relaxations are listed in §9.4 for that case.

## 8. Build order

Each milestone ends with its tests green and a commit on a `claude/bootstrap-*` branch (never the default branch).

1. Scaffold: `.gitignore`, `.claude/settings.json`, `plumbing.yaml`, `INDEX.md` skeleton, package skeleton, `conftest.py`, sample project fixture. Done when `doctor` runs and reports the missing pieces honestly.
2. `specdrift.py`, `spec_snapshot.json`, `test_spec_snapshot*.py`. Done when the alarm and its meta-test are green; from here every later commit runs under the alarm.
3. `config.py`, `render.py`, plumbing templates, `render` and `spec-check` commands, `test_config.py`, `test_render.py`. Done when all 20 spec files render with exactly the known drift set.
4. `pipeline.py`, `schemas.py`, `state.py`, `ledger.py`, `ownerlog.py` + hook, `round.py` with `plan`/`start --no-branch`/`next`/`record`/`status`/`spend`/`abandon`, the stub; `test_pipeline.py`, `test_round_flow.py`, `test_owner_words.py`, `test_spend.py`, `test_judgment_calls.py`. Done when a gates-off and a gates-on stub round finish in `--no-branch` mode.
5. `checks.py` complete, disputes and limits, out-of-band edits, overrides, archive, freeze. Done when every routing-table row has a passing test.
6. `gitutil.py` + `landing.py`: claim, worktrees, fence, landing, conflict convergence, sync, `rounds`, `doctor` preconditions, `runner_skew`; `test_concurrency.py`. Done when two stub rounds land concurrently on a local origin in either order and the conflict test lands.
7. Headless `run`, `probe`, `sandbox`, corpus replay; `test_headless.py`, `test_cli.py`.
8. Docs (PROCESS, DRIVER, CONFIG, TESTING), INDEX.md complete, `test_docs.py`; the §7 edit with its flagged diff; final `doctor`, `spec-check`, full suite; the implementer's report lists every judgment call it made outside this plan.

## 9. Risks and open questions

1. **`ownerReviewCostPerWord`** (§2.3): choose the two-token prose edit or the config key. Recommendation: the prose edit; the config already names the per-artifact prices.
2. **`maxRoundAttempts: 2` "maximum round retries"**: read as the number of re-entries to an earlier step (UPSTREAM, out-of-band edit, landing failure) before a `round-limit` checkpoint, not total step attempts (which would stop every round at once). Recommendation: keep this reading; the owner confirms or renames the key.
3. **`ownerHourlyRate` has no attention estimate in the config**: priced with `plumbing.ownerHoursPerCheckpoint = 0.2`. Recommendation: keep; the owner may add `ownerHoursPerCheckpoint` to project.yaml to override.
4. **Gate strictness**: every gate file says "Fail" per criterion while COMMON-GATE limits FAIL to defects costing more than a retry; agents may read the per-line "Fail" as absolute and fail everything. Recommendation: measure with gate probes on a clean fixture; if a clean artifact fails twice in three probes, propose to the owner one edit per gate file of the form `Fail` → `Finding` (e.g. PLAN-AGENTS-GATE line 7) with diffs, and apply only what the owner approves.
5. **Effort is not settable through the Agent tool**, so the roster's `effort` is honoured only in headless mode. Recommendation: the action carries `effort` anyway; DRIVER.md notes the gap; revisit when the tool exposes it.
6. **`claude` CLI not on PATH in tool shells**: headless mode is tested with the stub only. Recommendation: `doctor` reports whether `agentCommand[0]` resolves; headless real runs are a later validation item.
7. **No `sh` on PATH**: git-hook tests are skipped here; the seam and the refspec trick cover the same races. Recommendation: accept; mark the hook tests `skipif`.
8. **The harness is its own project**: a round that edits `src/` changes the runner driving it. Recommendation: pinned runner path, `runner_skew` warning, suite at CLEANUP-CHECK; document that a round touching `src/shackles/round.py` should be delegated with checkpoints on.
9. **Sub-agent cwd versus worktree**: an Agent-tool sub-agent runs with the driver's cwd. Recommendation: absolute `ROOT`/`WORKTREE` lines in every prompt; DRIVER.md forbids worktree isolation for round agents; M1 catches strays; gates as `Explore` (read-only) with G1 as the backstop.
10. **Owner-word false positives** from sub-agent text reaching the log: envelope filtering plus "latest message after the checkpoint" mitigate; a residual risk remains for the owner pasting agent output containing "abandon". Recommendation: `owner_message` always states the words that will be acted on; `abandon` additionally requires the message to be under 200 characters or to start with the word (`plumbing.abandonStrict: true`).
11. **Prompt size**: COMMON-ROUND embeds the whole plan and the spec text goes into every code-step prompt. Recommendation: `promptMaxChars` truncation with reproduce commands; `step.prompt_chars` lets PLAN-TO-SPEC-GATE apply its "too large" criterion.
12. **Path base**: config and artifact paths are H-relative with `..` allowed; a target project beside `harness/` declares `../app/`. Recommendation: keep; CONFIG.md states it; revisit if the owner prefers repo-relative.
13. **Concurrent rounds on shared living files**: only W1 warns; landing arbitrates. Recommendation: accept, as the summary did; sentence-per-line docs reduce conflicts.
14. **The pipeline order is built in**, so a prose file for a new step (say `REVIEW-OVERVIEW.txt`) is not run until a round adds it to `pipeline.py`. Recommendation: `spec-check` lists prose files no step uses, so the alarm plus that list route the change to a round; automatic ordering from prose alone is not possible and was not attempted.
15. **BLOCKED goes straight to a checkpoint** rather than a retry. Recommendation: keep (cheapest, and narrowing is the owner's call); if delegated rounds stall on it too often, allow one retry under delegation.
