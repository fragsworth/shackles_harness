# plan-2 — bootstrap plan for `shackles_harness`

Planner 2. Written from the worktree at `.claude/worktrees/agent-ac9753cf3c467ed84`, 2026-09-12.
"The spec" means the file set listed in `spec.yaml`. Paths are repo-relative unless they start with a
drive letter. The implementing agent is "you".

---

## 0. How to read this

Sections 1–3 are the reasoning (process, requirements, gaps). Section 4 is the design and is normative:
build what it says. Section 5 is the test strategy, 6 the real-agent loop, 7 the spec edits, 8 the
build order with acceptance criteria, 9 risks and open questions. Appendices hold verbatim templates
and schemas. When a decision here conflicts with an owner spec file, the spec wins and you flag it
(§7 procedure).

---

## 1. Process used to develop this plan

1. Read every file in the repository: `spec.yaml`, `harness/AGENTS.md`, `harness/project.yaml`,
   `harness/subAgents.yaml`, all 18 `locked_prose/*.txt`, and
   `bootstrap/vision-harness-round-concurrency.md`.
2. Built a requirements ledger: every sentence of the spec that implies mechanism was classified as
   **judgment** (prose for agents; the runner must not interpret it), **mechanical** (the runner must
   implement it), or **ambiguous** (needs a defined resolution; flagged in §9). Every mechanical item was
   then checked for wording-dependence: does the runner need to know a *word* from the prose to work?
   Where yes, the design was changed until the answer was no, or the dependence was reduced to a
   structural convention (`{{ ns.key }}` placeholders, file naming, YAML keys) and listed in the
   wording-adjacent rules table (§4.16) that the spec-change guard points reviewers at.
3. Compared the vision_harness summary against this spec item by item: adopt / adapt / reject (§4.12).
   Checked one specific point in the read-only original — the exact `claude -p` invocation and tool
   flags that ran real rounds on this machine — so the default `agentCommand` is verified, not guessed.
4. Enumerated what an LLM-operated harness of this kind standardly needs and the spec does not mention
   (§3), and decided which to include now.
5. Designed the state machine, cost model, checks and concurrency; wrote the schemas and the
   PROCESS-INSTRUCTIONS template verbatim so no consequential decision is left to you.
6. Designed the test strategy around a scripted stub agent and throwaway git repos, then a cheaper
   real-agent loop than the owner's (§6).
7. Listed the minimal spec edits (§7) and the risks with resolutions (§9).

Nothing was executed, spawned, or modified. The only file written is this plan.

---

## 2. What the spec fixes, and what it leaves to us

### 2.1 Facts the spec fixes (mechanical; honored exactly)

| Source | Fact |
| --- | --- |
| AGENTS.md | Runner is `harness/src/run.py`; it alone commits, pushes, contacts the owner. Producers edit only inside their worktree, only within declared paths plus the round folder. |
| AGENTS.md | Every agent's prompt names its step, inputs, artifact path, and the exact JSON its final message must be; the runner parses that JSON. |
| AGENTS.md | `locked_prose/` does not change mid-round. `src/`, `docs/`, `tests/` are living (tokens charged/refunded). |
| AGENTS.md | Driver loop: `next` → prompt file → fresh sub-agent (read-only for gates) → save final message → `record`. The driver never judges. |
| AGENTS.md | `{{ plumbing.PROCESS-INSTRUCTIONS }}` = mechanical steps, never judgment. Routing lives in `INDEX.md`, rules in `docs/PROCESS.md` (both must exist). |
| AGENTS.md | Two judgment-call files per round, appended by agents, one line per call. |
| project.yaml | All numeric settings (§4.11 uses each). `gates:` map in run order with 0/1. `roundPaths` layout with `NNNN` ids. Agent tiers by key. |
| project.yaml | Checkpoints (comments): after plan, after spec, before landing. Landing after TESTS-TO-SUITE. Round ends after POSTMORTEM. |
| subAgents.yaml | Tier keys `max/high/medium/low` with model, effort, prices, spawnCost. |
| Prose | Placeholder grammar `{{ namespace.key }}` with namespaces `project`, `round`, `step`, `prose`, `plumbing`. |
| Prose | Producer outcomes DONE / NEEDS-OWNER / UPSTREAM / BLOCKED. Gate PASS/FAIL; blocking vs non-blocking findings; disputes upheld/withdrawn by quotation; "upheld twice is settled"; every finding carries a suggestion. |
| Prose | Owner words: approve(d), delegate(d), delegate through STEP, override + steps/gates. CHAT-TO-PLAN is the chat agent itself. |
| Prose | PLAN-TO-SPEC and CLEANUP: "Checkpoint after this step". POSTMORTEM writes TODOs and CLARIFICATIONS. TESTS-TO-SUITE decides suite vs archive per test. |

### 2.2 What the spec leaves undefined (resolved here; each also in §9)

Step order for CLEANUP (only in comments and prose); meaning of `maxRoundAttempts`,
`maxFailuresBeforeStop`, `systemTestAgent`, `maxRunWallClockHours`, `costToWaitForOwner`,
`ownerHourlyRate`; where TODOs/CLARIFICATIONS live; what happens to NEEDS-OWNER/UPSTREAM/BLOCKED when
a gate is disabled; how owner words reach the runner; what a step's "sub-agents" are; how a gate's
read-only-ness is enforced; how costs are learned from a sub-agent; the
`{{ project.ownerReviewCostPerWord }}` placeholder that has no key in `project.yaml`.

---

## 3. Standard features missing from the spec

Included now (each has a design section):

| Feature | Why standard for an LLM-run harness | § |
| --- | --- | --- |
| Schema validation of every artifact and agent result, with agent-actionable errors | LLM output is this system's untrusted input | 4.6 |
| Spec-change guard with acknowledgement, and a self-test of the guard | Required by the owner; the only alert channel for "the rules changed" | 4.14 |
| `lint` (static: config, placeholders, pipeline consistency) and `doctor` (environment: git, `py -3.13`, `claude` flags, origin, ignores) | Failures must surface before money is spent | 4.7 |
| Pinned prompts: prose rendered from the round's `prose_commit`; spec files hash-pinned per round | Makes "prose does not change mid-round" true mechanically | 4.5, 4.9 |
| Mechanical pre-gate checks: path confinement, locked files, frozen tests, suite green, artifact schema, refactor cap, conflict markers | Cheap deterministic rejections before paying a gate | 4.10 |
| Crash-safe, idempotent commands; `status`; `push` retry; `resume` | Rounds run for hours and are interrupted constantly | 4.7, 4.9 |
| Cost ledger: agent, driver, time, owner, living tokens; quote vs spend; hard stop; project totals across rounds | The spec is built around money; agents are told budgets | 4.11 |
| Owner-word trail: every owner-driven command carries `--quote`, appended to the round's OWNER.log | POSTMORTEM must trace issues to "exact owner words" | 4.9 |
| Findings ledger: ids, dispositions, uphold counts, settlement, withdrawn-never-re-raised | COMMON-GATE's dispute protocol needs memory across attempts | 4.9 |
| Landing-conflict convergence (conflict attempt) | The sibling system's worst recorded failure | 4.12 |
| Carry-forward docs `docs/TODO.md`, `docs/CLARIFICATIONS.md`, read by CHAT-TO-PLAN, written by POSTMORTEM | The prose names them but gives them no home | 4.15 |
| Sandbox and stub agent shared by tests and real-agent smoke runs | Cheap, repeatable real-agent testing | 5, 6 |
| Secrets hygiene: scrubbed env, no push credential for agents, gate tool flags | AGENTS.md invariant 1 | 4.13 |
| Round-id width, step list, gate enablement, paths, tiers all read from the spec generically, with defaults for absent keys | Robustness to arbitrary spec changes | 4.2, 4.3 |

Deferred (seeded into `docs/TODO.md`, not built): lease/heartbeat for stale rounds (the sibling's
reasoning against it holds); cross-round path arbitration beyond a warning; a status UI; multi-repo
projects; automatic gate-language relaxation; exact tokenizers (bytes/`tokenBytes` stays).

---

## 4. Design

### 4.1 Repository layout after bootstrap

```
spec.yaml                       owner (unchanged)
.gitignore                      new: .worktrees/  harness/OWNER.log  harness/DRIVER.json  harness/local.yaml  __pycache__/  .pytest_cache/
bootstrap/                      existing; plans/ added by planners
harness/
  AGENTS.md project.yaml subAgents.yaml locked_prose/      owner (two one-word prose edits, §7)
  INDEX.md                      routing, one grep-able line per entry
  docs/PROCESS.md               the rules (normative for agents at runtime)
  docs/TODO.md                  carry-forward, append-only per round
  docs/CLARIFICATIONS.md        carry-forward, append-only per round
  src/run.py                    CLI entry; the file AGENTS.md names
  src/config.py                 spec loading, defaults, typed access, path helpers
  src/pipeline.py               step table + consistency checks
  src/prompts.py                template rendering, PROCESS-INSTRUCTIONS, GATE-PROSE
  src/schemas.py                schema dicts + minimal validator
  src/gitutil.py                subprocess/git wrapper, hermetic env, main_root
  src/rounds.py                 Round: state, next, record, routing, checkpoints
  src/checks.py                 mechanical checks M0–M7, L1–L2
  src/ledger.py                 cost math, living charge, shares
  src/landing.py                claim, worktrees, landing loop, sync, abandon, prune
  src/specguard.py              spec snapshot compare/ack (used by tests and CLI)
  src/sandbox.py                throwaway repo/origin builder (used by tests and smoke)
  src/smoke.py                  real-agent step-isolation matrix
  src/owner_log_hook.py         optional Claude Code UserPromptSubmit hook
  tests/conftest.py fixtures.py stub_agent.py spec_snapshot.json test_*.py fixtures/tiny/ fixtures/tiny_bad/
  archives/rounds/              created by the first round; index.jsonl appended per finished round
```

Target sizes: `src/` ≤ 2600 lines of Python, `tests/` ≤ 2600, `docs/` ≤ 450. Density is charged
(project.yaml): no docstrings restating code, no defensive code for impossible states.

### 4.2 Robustness rules (apply everywhere)

- R1. The runner reads the spec **only** through `config.py`; every key has a typed default and a
  documented meaning; unknown keys are ignored; missing keys warn in `lint`, never crash.
- R2. No string from prose is ever matched by the runner. The only structural conventions used:
  placeholder grammar `{{ ns.key }}`; prose file naming `<STEP>-OVERVIEW.txt`, `<STEP>-GATE.txt`,
  `COMMON-*.txt`; YAML keys; `roundPaths` values; the `N` run in `roundPaths.folder`.
- R3. Vocabulary the runner must parse (outcomes, verdicts, dispositions) is defined by the runner's
  schemas and repeated verbatim in PROCESS-INSTRUCTIONS, which AGENTS.md makes authoritative ("Follow
  it exactly; the runner parses it"). If the owner renames a word in prose, the prompt shows both, the
  agent follows the JSON contract, and `lint` warns that a schema word is absent from the prose.
- R4. Every command is idempotent or refuses (exit 2) — never double-applies.
- R5. Every write of runner state is atomic (`os.replace`), LF, UTF-8. Every read of spec text
  normalizes CRLF/CR→LF and strips a BOM before hashing or rendering.
- R6. Nothing mechanical depends on step *names* except through `pipeline.py`, which is validated
  against the spec by tests that fail loudly with instructions.

### 4.3 Config model (`config.py`)

- `find_root(start)`: nearest ancestor containing `spec.yaml`. `HARNESS = dirname(dirname(run.py))`
  when run from the repo; under `--root`, `ROOT/<relative harness dir of the invoking runner>`.
- `load(root)` → `Config` with `project` (project.yaml), `agents` (file named by
  `project.subAgentsFile`, default `subAgents.yaml`), `runner` (operational defaults below, overridden
  by any same-named key in project.yaml, then by `harness/local.yaml` if present — gitignored,
  machine-local), `spec_files` (from spec.yaml, resolved, POSIX-normalized).
- Typed accessors with defaults: `cfg.num("hardStopBudgetMultiple", 6)`, `cfg.gates()` → ordered
  dict name→bool (absent name ⇒ disabled; non-0/1 coerced by truthiness, lint warns),
  `cfg.paths.round_folder(id)`, `cfg.paths.artifact("spec")`, `cfg.paths.living()`,
  `cfg.id_width` = length of the longest `N` run in the last component of `roundPaths.folder`
  (default 4), `cfg.tier(key)` → agent dict (unknown key → RunnerError naming valid keys).
- Runner defaults (all overridable): `mainBranch: main`, `worktreeDir: .worktrees`,
  `pythonCommand: ["py","-3.13"]`,
  `suiteCommand: ["py","-3.13","-m","pytest","harness/tests","-q","-p","no:cacheprovider"]`,
  `agentCommand` (§4.13), `gateToolFlags`, `producerToolFlags`,
  `scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]`, `agentTimeoutSeconds: 3600`, `agentRetries: 3`,
  `pushAttempts: 5`, `settleAfterUpholds: 2`, `inlineFindingsMaxBytes: 8192`, `historyTailLines: 60`,
  `tierOverride: null` (forces every step's tier; for cheap real-agent runs).
- Default `roundPaths` (used if the owner deletes the block) equal the current file's values.

### 4.4 Pipeline (`pipeline.py`)

The step table is code, validated against the spec by `tests/test_pipeline.py`. Kinds: `plan` (done by
the driver before `start`), `producer`, `gate` (LLM), `mech-gate`, `mechanical`.

| # | Step | Kind | Prose file | Artifact / writes | After PASS (mechanical) | Checkpoint after | Default when overridden |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | CHAT-TO-PLAN | plan | CHAT-TO-PLAN-OVERVIEW | `plan` | — | (approval is `start` itself) | cannot be overridden |
| 2 | CHAT-TO-PLAN-GATE | mech-gate | — | — | — | — | schema check still runs |
| 3 | PLAN-AGENTS | producer | PLAN-AGENTS-OVERVIEW | `agentsPlan` | — | — | defaults (§4.11) |
| 4 | PLAN-AGENTS-GATE | gate | PLAN-AGENTS-GATE | — | — | — | auto-pass |
| 5 | PLAN-TO-SPEC | producer | PLAN-TO-SPEC-OVERVIEW | `spec`, `specProse` | charge spec words | — | must be provided |
| 6 | PLAN-TO-SPEC-GATE | gate | PLAN-TO-SPEC-GATE | — | — | **review** | auto-pass |
| 7 | SPEC-TO-TESTS | producer | SPEC-TO-TESTS-OVERVIEW | writes `test_paths` | — | — | no tests; frozen set empty |
| 8 | SPEC-TO-TESTS-GATE | gate | SPEC-TO-TESTS-GATE | — | freeze tests (M2 set) | — | auto-pass |
| 9 | SPEC-TO-IMPLEMENTATION | producer | SPEC-TO-IMPLEMENTATION-OVERVIEW | writes `impl_paths` ∪ `refactor_paths` | — | — | must be provided (rare) |
| 10 | SPEC-TO-IMPLEMENTATION-GATE | gate | SPEC-TO-IMPLEMENTATION-GATE | — | — | — | auto-pass |
| 11 | TESTS-TO-SUITE | producer | TESTS-TO-SUITE-OVERVIEW | `suite`; writes `test_paths` | archive tests; suite green (M3) | — | all round tests join the suite |
| 12 | TESTS-TO-SUITE-GATE | gate | TESTS-TO-SUITE-GATE | — | — | — | auto-pass |
| 13 | CLEANUP | producer | CLEANUP-OVERVIEW | writes all living paths | — | **review** (before landing) | skipped |
| 14 | LANDING | mechanical | — | — | living charge, tag, index line | — | cannot be overridden |
| 15 | POSTMORTEM | producer | POSTMORTEM-OVERVIEW | `postmortem`; writes `docs/TODO.md`, `docs/CLARIFICATIONS.md` | finish | — | round finishes after LANDING |
| 16 | POSTMORTEM-GATE | gate | POSTMORTEM-GATE | — | finish | — | auto-pass |

Rules:
- Gate enablement: `cfg.gates()[name]`; a disabled or overridden gate is an **auto-pass** with an empty
  findings file and a HISTORY line.
- Pre-gate mechanical checks run at `record` of every producer (§4.10); they can FAIL a producer
  without spending the gate.
- `PIPELINE` is a list of `Step` dataclasses; `producer_of(gate)`, `gate_of(producer)`, `index(name)`,
  `producers_before(name)` are the only lookups other modules use.
- Missing prose file (owner deleted it): producer → RunnerError at `start` ("step X has no prose;
  override it or restore the file"); gate → treated as disabled, lint warns.

### 4.5 Templates and prompt assembly (`prompts.py`)

**Grammar.** `\{\{\s*([A-Za-z][\w-]*)\.([\w.-]+)\s*\}\}`. Recursive for `prose.*` (depth ≤ 6, cycle →
marker). Unresolved → `«unresolved: ns.key»` in place, collected into `warnings`, appended to
PROCESS-INSTRUCTIONS as `WARNINGS:` and written to HISTORY. Never an exception.

**Sources.** `prose.X` reads `<lockedProsePath>/X.txt` via `git show <prose_commit>:<path>` when a
round exists, else the working tree (the CHAT-TO-PLAN prompt and the `prompt` command). Round rendering
never reads the working tree's prose.

**Namespaces.**
- `project.<key[.sub]>`: any project.yaml value; computed `remaining` = `budget − project spend`
  (the `spend --project` figure) and `spent`.
- `round.*`: `id` (zero-padded), `folder` (POSIX, repo-relative), `base_commit`, `plan` (PLAN.json,
  pretty JSON, 2-space), `budget` (quote), `spend`, `remaining`, `mode`, `step`, `attempt`.
- `step.*`: `name`, `kind`, `attempt`, `budget`, `retry_cost` (= producer share + `driverUsdPerStep`),
  `agent` (display name), `gate`, `gate_enabled`.
- `prose.<NAME>`.
- `plumbing.GATE-PROSE`: for producer S, the rendered `<S>-GATE.txt` if it exists; if S's gate is
  mechanical, a generated list of the checks; if none, `(no gate)`. If the gate is disabled or
  overridden this round, the block is prefixed with one line: `(Gate disabled this round: a DONE result
  passes without review. The standard below still applies.)`
- `plumbing.PROCESS-INSTRUCTIONS`: Appendix A, generated per step and attempt.

**Formatting.** ints as-is; floats via `repr` with a trailing `.0` stripped (`0.1`, `12.5`, `10`);
bools `yes`/`no`; None `none`; lists `a, b, c`; dicts `k: v, k: v` in insertion order.

**Assembly.** Producer prompt = rendered `<S>-OVERVIEW.txt`; gate prompt = rendered `<S>-GATE.txt`.
If the file has no `plumbing.PROCESS-INSTRUCTIONS` placeholder, the block is appended after a blank
line (lint warns). The prompt is written to `PROMPTS/<STEP>-<attempt>.txt`; for code gates the diff is
written beside it as `PROMPTS/<STEP>-<attempt>.diff` and named in `DIFF_FILE:`.

### 4.6 Schemas (`schemas.py`)

A ~90-line validator supporting `type` (object/array/string/number/integer/boolean/null and unions),
`required`, `properties`, `additionalProperties` (default true), `items`, `enum`, `minimum`,
`minItems`, `pattern`. Errors are path + message (`findings[2].suggestion: required`). Schemas are
Python dicts; `run.py schema NAME` prints one. Listings in Appendix B: `PLAN`, `AGENTS_PLAN`, `SPEC`,
`SUITE`, `PRODUCER_RESULT`, `GATE_RESULT`, `STATE`, `ACTION`. Artifact keys map to schemas by their
`roundPaths.artifacts` key (`plan`, `agentsPlan`, `spec`, `suite`); `specProse` and `postmortem` are
prose (non-empty check only).

Result normalization (mechanical; a HISTORY line when applied): the JSON may be fenced or surrounded
by prose — the runner extracts the last top-level `{…}` that parses. Gate: **blocking findings decide** —
FAIL with zero blocking findings is recorded as PASS, PASS with a blocking finding as FAIL. Missing or
duplicate finding ids become `<GATE>-<attempt>.F<n>`. A disputed finding with no ruling stays open
(`unruled`, re-asked next time).

### 4.7 CLI (`run.py`) and exit codes

Invocation: `py -3.13 harness/src/run.py [--root DIR] [--round ID] [--json] <command> …`. `--round`
is inferred from the current branch `round/<id>`, else the single non-finished round folder, else
required. Exit codes: `0` ok, `1` error, `2` usage / invalid input / refused by a guard, `3` check
failed, `10` checkpoint. `start`, `next`, `record` and the resume commands always print exactly one
JSON object on stdout; other commands print tables unless `--json`.

| Command | Does | Writes |
| --- | --- | --- |
| `prompt STEP [--attempt N]` | Renders a prompt (CHAT-TO-PLAN needs no round) | stdout |
| `start --plan F [--branch NAME] [--no-branch] [--allow-stale-spec] [--allow-unacknowledged-spec] [--no-push]` | Validates the plan (mech-gate), claims an id, creates worktree and round folder, first commit + push | claim ref, worktree, round folder |
| `next [--no-push]` | Mechanical work until an LLM run is due; renders the prompt; prints action / checkpoint / done | round folder, local commit |
| `record --step S --attempt N --result F [--cost USD \| --tokens-in N --tokens-out M] [--no-push]` | Validates the result, runs checks, routes, ledger, commit **+ push (the fence)** | RESULTS/, FINDINGS/, STATE, HISTORY |
| `record --step S --attempt N --infra-error TEXT` | Counts an infra error, re-renders the same attempt | STATE, HISTORY |
| `approve --quote T` · `delegate [--through STEP] --quote T` · `answer --text T --quote T` · `resume --quote T` · `override --steps A,B --quote T` · `abandon --reason R --quote T` (all accept `--owner-minutes M`) | Owner-driven transitions (§4.9) | STATE, OWNER.log, HISTORY, commit + push |
| `push` | Retries the last push after a network failure | origin |
| `run --until checkpoint\|step\|done [--no-push]` | Headless loop: next → agent → record | as above |
| `status`, `spend [--project]`, `check` | Read-only (`check` merges into the round worktree only at LANDING) | nothing shared |
| `lint`, `doctor` | Static / environment checks | stdout |
| `spec status\|diff\|ack [--note T]`, `spec adopt --quote T` | Spec guard (§4.14); `adopt` merges origin main mid-round and re-pins | snapshot / round |
| `prune` | Removes worktrees of finished/abandoned rounds; reports claimed-but-empty ids | worktrees |
| `sandbox --dir D [--task tiny] [--origin]` | Builds a throwaway project repo (+ local bare origin) with the harness copied in | D |
| `smoke …` | §6 | report dir |
| `schema NAME` | Prints a schema | stdout |

### 4.8 Round folder and STATE.json

Round folder = `HARNESS/<roundPaths.folder with the N-run → id>`; every sub-path from `roundPaths`.
Runner-owned files (agents may not write them; M0): `STATE.json`, `HISTORY.md`, `OWNER.log`,
`PROMPTS/`, `RESULTS/`, `FINDINGS/`, `tests-archive/`. Agents write artifacts and the two judgment-call
files (created empty at start; the runner reports their line counts per attempt in HISTORY).

STATE.json (schema in Appendix B): `state_version: 1`, `round` (int), `id`, `branch`, `no_branch`,
`created_at`, `status` ∈ active|checkpoint|finished|abandoned, `mode` ∈ approved|delegated,
`delegate_through`, `overrides[]`, `step`, `attempts{}`, `failures` (int), `infra_errors{}`,
`re_entries` (int), `step_starts{}`, `step_commits{}`, `base_commit`, `prose_commit`, `spec_hashes{}`,
`inputs_hash{}`, `quote_usd`, `ledger[]`, `spend`, `checkpoint|null`, `pending_questions[]`,
`owner_answers[]`, `findings_ledger{}`, `carried_findings[]`, `frozen_tests{}|null`,
`conflict_files[]|null`, `last_time_accrual`, `landed_at`, `abandoned_at`, `hard_stop_raised`,
`failure_cap_raised`, `reentry_cap_raised`, `runner_version`, `runner_path`. No worktree key, no
lock/lease/pid. Saved only through `Round.save()`, which validates.

`HISTORY.md` is append-only: `## <UTC> <STEP> attempt <n> — <event>` then bullets (verdict, cost and
source, findings count, summary, judgment-call counts, living estimate for code steps).
`index.jsonl` (`HARNESS/archives/rounds/index.jsonl`): one line per finished/abandoned round
`{id, quote_usd, spend, attempts, failures, re_entries, outcome, prose_commit, landed_at|abandoned_at}`.

### 4.9 Lifecycle

**Planning (driver, in chat).** The driver renders `prompt CHAT-TO-PLAN`, converses, writes PLAN.json
(Appendix B) including `approval` — its judgment call, under the prose, of the owner's words — and
`owner_words` verbatim. Then `start --plan F`:
1. `lint` fatal errors → refuse. Spec snapshot unacknowledged → refuse unless `--allow-unacknowledged-spec`.
2. Validate PLAN (schema + mech-gate checks: `approval.overrides` are known names excluding
   CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, LANDING; `through` is a known step; every overridden producer with a
   required artifact has a `provided_artifacts` entry that validates; `quote_usd > 0`; quote above the
   project's remaining budget ⇒ warning only). If CHAT-TO-PLAN-GATE is disabled, only the schema runs.
3. Git mode. `--no-branch` or no origin: run in the current checkout on the current branch, id =
   1 + max local folder id. Otherwise: `git fetch origin`; refuse if the working-tree spec files differ
   from `origin/<mainBranch>` (unless `--allow-stale-spec`); warn if local HEAD ≠ origin main; claim an
   id (§4.12); `git worktree add -b round/<id> <main_root>/<worktreeDir>/<id> origin/<mainBranch>`.
4. In the round root: create the folder; copy PLAN.json (set `round`); copy provided artifacts; create
   empty judgment-call files; write STATE (`base_commit = prose_commit = HEAD`, `spec_hashes`), HISTORY,
   the OWNER.log slice (`owner_words` + `approval.words`); ledger `owner` = words(plan prose fields) ×
   `planCostPerWord`. Commit `round <id>: start`, push `-u`. Print `{round, id, folder, branch, worktree, runner}`.

**`next`.** (1) finished/abandoned → `sync_main`, print done, exit 0. (2) Spec pin: working-tree spec
hashes ≠ `spec_hashes` → exit 1 with the file list and the `spec adopt` hint. (3) Dirty-tree recovery:
`git status --porcelain` non-empty → `git checkout -- .` and `git clean -fdq -- <harness dir> <living
paths>` (never the whole tree; refused if `worktreeDir/` is not ignored), `infra_errors[step]++`,
HISTORY line. (4) Refresh the OWNER.log slice from `<main_root>/harness/OWNER.log` if present.
(5) Accrue time cost. (6) Hard stop: `spend ≥ hardStopBudgetMultiple × quote` and not `hard_stop_raised`
→ checkpoint(stop). (7) status checkpoint → print it, exit 10. (8) Input hashes: PLAN/AGENTS-PLAN/SPEC
changed since last hashed (ignoring `errata`) → re-enter at the first consumer step, HISTORY line
"out-of-band edit". (9) Loop: the current step is mechanical (auto-pass gate, mech-gate, LANDING,
post-PASS mechanics, TESTS-TO-SUITE reuse rule) → execute and advance; else render the prompt, save,
commit (no push), print the action (Appendix B), exit 0.

**`record`.** Guard: `status == active`, `state.step == S`, `N == attempts[S] + 1`; else exit 2. Parse
and validate the result; copy to `RESULTS/S-N.json`; ledger `agent` entry (source `cli`, `tokens`, or
`estimate` = step share) plus `driver` entry `driverUsdPerStep`; run §4.10 checks for producers; route:

| Producer outcome | Gate enabled | Gate disabled / overridden |
| --- | --- | --- |
| DONE | → gate | auto-pass → next step |
| NEEDS-OWNER (`question`, `assumption`) | → gate with the question. Gate `owner_question` upheld → checkpoint(question); withdrawn → `answer_to_assume` recorded in `owner_answers[]` as `{by: gate}`, verdict applies | mode approved → checkpoint(question); mode delegated → continue on `assumption`, add to `pending_questions` |
| UPSTREAM (`upstream.step`, an earlier producer) | routed mechanically, no gate: `failures++`, `re_entries++`, finding `<S>-<N>.U1` (source downstream) attached to the upstream step's next attempt | same |
| BLOCKED (`narrow`) | checkpoint(blocked) | same |

Gate result: PASS → post-PASS mechanics; non-blocking findings → `carried_findings` (advisory for the
next producer); review checkpoint if due. FAIL → `failures++`; the producer gets attempt+1 with all
open findings inlined. Findings ledger: each finding `{id, step, attempt, quote, reason, suggestion,
blocking, status ∈ open|withdrawn|settled|resolved, upholds}`; producer `disputes` mark findings
disputed; gate `rulings` set upheld (`upholds++`; settled at `settleAfterUpholds`, after which disputes
on it are dropped with a HISTORY note) or withdrawn; a new finding whose whitespace-normalized `quote`
equals a withdrawn one is dropped as non-blocking with a HISTORY note. Then `git add -A`, commit
`round <id>: <S> attempt <N>`, push. A push rejected as non-fast-forward ⇒
`RunnerError("another runner owns this round (push rejected)")`; any other push failure ⇒ error
naming `run.py push`.

**Checkpoints.** `checkpoint = {kind ∈ review|question|blocked|stop, step, raised_at, artifact?,
question?, reason?}`. Raising one charges `costToWaitForOwner`. Review checkpoints are raised after
PLAN-TO-SPEC-GATE PASS and after CLEANUP's record, skipped when `mode == delegated` or
`delegate_through` is at/after the step. Question, blocked and stop are never skipped by delegation.
Resumes (each requires `--quote`, appended to OWNER.log and HISTORY; `--owner-minutes M` charges
`ownerHourlyRate × M/60`):
- review: `approve` (re-hash inputs; continue), `delegate [--through]` (set mode; continue), `abandon`.
- question / blocked: `answer --text` → the current producer gets a new attempt with the text inlined
  under `OWNER ANSWERS:`; `abandon`.
- stop (hard stop; `failures ≥ maxFailuresBeforeStop`; `re_entries ≥ maxRoundAttempts`): `resume` sets
  the matching `*_raised` flag and continues; `abandon`.
`override --steps` may be issued at any time for steps not yet passed.

**Finish.** POSTMORTEM(-GATE) PASS → `status = finished`, index line, commit, push, `sync_main`.
**Abandon.** Any status before `landed_at`: tag `round/<id>-abandoned`, index line, commit, push. After
landing it is refused with the hint `override --steps POSTMORTEM`.

### 4.10 Mechanical checks (`checks.py`)

Run at `record` for producers, before the gate; a blocking finding ⇒ the producer FAILs (attempt+1)
without spending a gate; findings go to `FINDINGS/<S>-<N>.json` with `"source": "mechanical"`.
Out-of-scope changes are **reverted** (`git checkout --` / delete untracked) so the tree stays
reproducible; in-scope work is kept and committed.

| Id | Check | Scope |
| --- | --- | --- |
| M0 | Any change to a spec.yaml file or a runner-owned round file; any change by a gate. The diff is saved to FINDINGS for the owner and the HISTORY line starts `LOCKED FILE EDIT ATTEMPTED` | all steps |
| M1 | Changed paths ⊄ allowed(step) = round folder minus runner files ∪ step writes (§4.4) ∪ `conflict_files` (conflict attempt only) | all producers |
| M2 | A frozen test file changed (blob sha ≠ `frozen_tests`); exempt: `conflict_files` on a conflict attempt | SPEC-TO-IMPLEMENTATION, CLEANUP |
| M3 | `SPEC.verify` then `suiteCommand`, each under `verifyTimeoutSeconds`, must exit 0; the finding carries the last `historyTailLines` lines | SPEC-TO-IMPLEMENTATION, TESTS-TO-SUITE (after the archive move), CLEANUP |
| M4 | Living charge of the diff within `refactor_paths` > `maxRefactorOverhead × quote` | SPEC-TO-IMPLEMENTATION, CLEANUP |
| M5 | Conflict markers (`^<{7} `, `^={7}$`, `^>{7} `) in any `conflict_files` file | conflict attempt |
| M6 | Artifact missing or failing its schema/consistency: AGENTS-PLAN budgets sum ≤ quote − spend and tiers exist; SPEC `impl_paths`/`test_paths` disjoint by prefix, `impl_paths` non-empty; SUITE covers every changed test file | producers with artifacts |
| M7 | Result JSON invalid → `record` exits 2, nothing applied (the driver fixes or re-asks; `--infra-error` if the agent is at fault) | all |
| L1 | Landing merge conflict (§4.12) | LANDING |
| L2 | Verify/suite red on the merged tip | LANDING |

Freeze: at SPEC-TO-TESTS-GATE PASS, `frozen_tests = {path: blob}` for every file under `test_paths`
that differs from `base_commit`; re-frozen on a later PASS after re-entry. Archive: after
TESTS-TO-SUITE's record, `git mv` each `archive` test to `tests-archive/<basename>` (collision →
`<dir>__<basename>`), then M3. Reuse rule: if SUITE.json exists and its `path` set equals the current
changed-test set, TESTS-TO-SUITE auto-passes on re-entry (HISTORY line).

### 4.11 Cost model (`ledger.py`)

Ledger entries `{ts, step, attempt, kind ∈ agent|driver|time|owner|living|estimate, usd, source, note,
detail?}`; `spend = Σ usd`. Use of every project.yaml number:

| Key | Use |
| --- | --- |
| `budget` | project target; `project.remaining` in prompts; warning when a quote exceeds it |
| `hardStopBudgetMultiple` | round hard stop at `multiple × quote`; per-run agent cap `max_budget_usd = share × multiple` |
| `lostValuePerHour` | `time` entry at each `next` for hours elapsed since `last_time_accrual` |
| `ownerHourlyRate` | shown to agents; `owner` entry `rate × --owner-minutes/60` on resume |
| `costToWaitForOwner` | `owner` entry per checkpoint raised |
| `planCostPerWord`, `specCostPerWord` | `owner` entries: words(PLAN.json prose fields) at start; words(SPEC.md) when the spec checkpoint is raised (at PLAN-TO-SPEC-GATE PASS if delegated) |
| `livingFileTokenCap`, `livingFileCostPerToken`, `livingFileCostPerTokenOverCap`, `livingFileBaseCost`, `testBaseCost`, `tokenBytes` | living charge: per file `f(t) = min(t,cap)×rate + max(t−cap,0)×rateOver`, `t = ceil(bytes/tokenBytes)`; charge `f(after) − f(before)` (refunds fall out); ± `livingFileBaseCost` per file created/deleted; `testBaseCost × Δcount(^\s*def test_)` over suite test files. Computed once at LANDING against the merged target (or `base_commit` in no-branch mode); shown as an estimate in HISTORY after each code step |
| `maxRefactorOverhead` | M4 |
| `gates`, `defaultShares`, `gatesFraction`, `workFraction` | share(S): AGENTS-PLAN value; else `defaultShares.work[S] × quote` (gates: `defaultShares.gates[producer_of(S)]`); else an equal split of `workFraction × quote − Σ explicit producer shares` over unassigned producers, and of `gatesFraction × quote` over unassigned **enabled** gates |
| `maxSimultaneousSubAgentsPerRound` | AGENTS-PLAN validation and a MUST-NOT line; enforcement by instruction |
| `maxRoundAttempts` | cap on `re_entries` (UPSTREAM and L1) → stop checkpoint |
| `maxFailuresBeforeStop` | cap on total gate + mechanical FAILs → stop checkpoint |
| `maxTurnsPerRun` | `max_turns` in the action / `--max-turns` |
| `maxRunWallClockHours` | headless `run` pauses (`{"kind":"paused"}`, exit 0) when one invocation exceeds it |
| `verifyTimeoutSeconds` | M3 / L2 |
| `estOutputFraction` | token estimate when only a total token count is known: out = total × fraction |
| `driverUsdPerStep` | `driver` entry per `record` |
| `subAgentsFile`, `maxAgent`, `gateAgent`, `systemTestAgent` | roster file; default producer tier; default gate tier; default `smoke` tier |
| `currency` | printed in tables |

Agent cost: `--cost` (source `cli`; headless reads `total_cost_usd`) > `--tokens-in/out` priced with
the tier's rates + `spawnCost` > `estimate` = share(S), flagged in HISTORY and prompts.

### 4.12 Concurrency and landing (`landing.py`)

Adopted from the sibling verbatim: git as the lock manager; CAS claim with `--force-with-lease=<ref>:`
and the `*` porcelain test; one push when `--branch` is explicit; ids monotonic and never released; a
worktree per round; push-fenced `record`; bounded landing loop with re-check; side-effect-free check
phase; timid `sync_main`; append-only `index.jsonl`; no lease/heartbeat; crash recovery by re-entry;
hermetic test fixtures. Ids: `1 + max(local folders (any digit width), origin round branches)`.

Adapted, each deliberately:
1. **Rounds start from `origin/<mainBranch>`**, not local HEAD, and **landing pushes
   `HEAD:refs/heads/<mainBranch>` from the worktree without moving the local `main` ref.** This removes
   the "main must not be checked out anywhere" precondition; the owner's checkout just
   `git pull --ff-only`s (the `done` action says so). No-branch mode: the round's commits are already on
   the current branch; landing = verify + suite + living charge.
2. **Conflict convergence.** On L1: `git merge` conflicts → capture `git diff --name-only --diff-filter=U`
   → `git add -A` → commit `round <id>: landing conflict with <target>, markers left in <n> files` → set
   `conflict_files`, `failures++`, `re_entries++`, route to SPEC-TO-IMPLEMENTATION attempt+1 with finding
   `L1` listing the files and the instruction to resolve the markers keeping both intents;
   `step_starts[SPEC-TO-IMPLEMENTATION] = that commit`. On that attempt M1 allows the conflicted files,
   M2 exempts them, M5 requires the markers gone. Its gate judges; TESTS-TO-SUITE reuses SUITE.json if
   the test set is unchanged; CLEANUP re-runs (with its review checkpoint unless delegated); LANDING
   merges again, now trivially. Tested with the stub's `resolve` mode.
3. **`sync_main` after POSTMORTEM** uses the same bounded loop but runs verify/suite only if the
   re-merge touched paths outside `archives/` and `docs/`.
4. **Runner pinned to the worktree copy.** `start` prints `runner = <worktree>/harness/src/run.py`; the
   action repeats it; `next` refuses to drive a round whose `runner_path` root differs from the invoking
   runner's root unless `--root` is explicit (prevents version skew; escape hatch documented).
5. **Preconditions at `start`**: `<worktreeDir>/` ignored; `git --version ≥ 2.20`; origin reachable
   (`git ls-remote --exit-code origin HEAD`). Failures refuse before any claim.
6. **Cross-round overlap warning**: at `start`, read `SPEC.json` from every live origin round branch
   (`git show origin/round/<id>:<spec path>`) and print the siblings' `impl_paths` so the driver can
   weigh overlap before PLAN-TO-SPEC.
7. `prune` command; `abandon` pushes.

Landing algorithm (LANDING executes inside `next`):
```
check():  fetch; target = origin/<main> if it exists else None
          if target: merge --no-edit target → conflict ⇒ (abort; return [L1 + files])
          verify, suite (timeouts) ⇒ red ⇒ [L2 + tail]
          return []
land():   findings = check()
          if findings: route (L1 → conflict attempt; L2 → SPEC-TO-IMPLEMENTATION attempt+1 with the tail); return
          for attempt in 1..pushAttempts:
              living = living_charge(target or base_commit)
              if target is None or no_branch: break
              if push origin HEAD:refs/heads/<main> ok: break
              if attempt == pushAttempts: raise RunnerError   # state not saved; rerun next lands again
              findings = check(); if findings: route; return
          ledger living (once); tag round/<id>-landed; landed_at; step_commits[LANDING]; advance
```
The `check` command runs `check()` at LANDING and otherwise validates state and runs lint; it never
pushes, tags or charges.

### 4.13 Agent invocation

**Driver mode (normal).** The driver is a Claude Code session in the main checkout. Per action: read
`prompt_file`; spawn a fresh sub-agent with that text verbatim as its task (gates: a read-only agent
type such as `Explore`, or an explicit READ-ONLY instruction — M0 reverts and records any change a gate
makes); save the sub-agent's final message to `result_file` **exactly as returned** (the runner
unwraps); then `record` with `--cost` if the tool reported cost, `--tokens-in/out` if it reported
tokens, else nothing (estimate). The driver never edits results beyond saving them (Appendix C).

**Headless mode (`run`).** `agentCommand` default, verified against the sibling's working config:
```
["claude","-p","--output-format","json","--system-prompt-file","{prompt_file}","--model","{model}",
 "--effort","{effort}","--max-turns","{max_turns}","--max-budget-usd","{max_budget_usd}",
 "--permission-mode","bypassPermissions","{tool_flags}",
 "Do the task in your system prompt. Your final message must be the result JSON it asks for."]
```
`gateToolFlags = ["--disallowedTools","Edit","Write","MultiEdit","NotebookEdit","Bash"]`;
`producerToolFlags = ["--disallowedTools","Bash(git push:*)","Bash(git commit:*)","Bash(git reset:*)","Bash(git checkout:*)","Bash(git clean:*)"]`.
Resolve `claude` with `shutil.which` (Windows `.cmd`/`.exe`), `shell=False`, `cwd = round root`, env
minus `scrubEnv` plus `PYTHONUTF8=1`, `timeout = agentTimeoutSeconds`, `encoding=utf-8`,
`errors=replace`. Parse stdout JSON → `result` (unwrap) → `result_file`; cost from `total_cost_usd`.
`agentRetries` attempts; each failure = dirty recovery + infra error. `doctor` checks that
`claude --help` mentions each flag used and warns per missing flag (the owner adjusts `local.yaml`).
`tierOverride` in `local.yaml` forces one tier for every step (cheap real-agent runs).

### 4.14 Spec-change guard (`specguard.py`, `tests/test_spec_guard.py`)

- Snapshot `harness/tests/spec_snapshot.json`: `{"spec_yaml": sha, "files": {relpath: {sha256, lines}},
  "known_unresolved": [placeholders], "ack": {at, commit|null, note}}`. Hash = sha256 of bytes after BOM
  strip and CRLF/CR→LF.
- `compare(root)` → `{changed, added, removed, list_changed, unresolved_new}`.
- `test_spec_unchanged` fails on any non-empty set with: the lists; per changed file a unified diff from
  `git show <ack.commit>:<path>` when available (else line counts); and the **review checklist**
  verbatim: (1) `run.py lint`; (2) reconcile the wording-adjacent rules table in PROCESS.md; (3) a step
  or gate added/renamed/removed → update `pipeline.py`; (4) project.yaml key changes → `config.py`
  defaults; (5) run the suite; (6) `run.py spec ack --note "<what you reviewed>"`.
- `start` refuses while the guard would fail (§4.9); `lint` reports it.
- Self-test `test_spec_guard_self` (the test of the test): copy `spec.yaml`, the spec files, the
  snapshot and `specguard.py` to a temp dir; assert clean; mutate one prose byte → reported changed; add
  an entry to spec.yaml → added; delete an entry → removed; rewrite a file with CRLF and BOM → clean;
  `ack` → clean. Meta step: run `py -3.13 -m pytest tests/test_spec_guard.py::test_spec_unchanged -q` as
  a subprocess inside a temp copy of the harness after a mutation and assert non-zero exit with the
  mutated filename and the checklist in the output — proving the test itself fires.

### 4.15 Docs

`INDEX.md` (≤ 60 lines): one line per file/dir/command: `path — what — read when`. Includes the
driver quick-start: `py -3.13 harness/src/run.py prompt CHAT-TO-PLAN` first; after `start`, use the
worktree's runner.

`docs/PROCESS.md` (≤ 320 lines), sections in order: Roles (owner, driver, producers, gates, runner);
Round lifecycle and statuses; Steps table (§4.4); Owner words → commands (the driver maps words to
`start`'s `approval` / `approve` / `delegate` / `override` / `abandon`, always with `--quote`);
Outcomes and routing (§4.9); Findings, disputes, settlement; Checkpoints; Stops and caps; Mechanical
checks (§4.10); Costs (§4.11); Freeze and archive rules; Landing, conflicts, sync; Concurrency
invariants (I1–I11 adapted); Spec guard and acknowledgement; Driving a round (Appendix C);
Wording-adjacent rules (§4.16); Escape hatches (`--root`, `push`, `spec adopt`, `--infra-error`).

`docs/TODO.md`, `docs/CLARIFICATIONS.md`: a one-line header each, then `## round <id>` sections
appended by POSTMORTEM; bootstrap seeds TODO.md with the deferred list from §3 and §9.

### 4.16 Wording-adjacent rules table (goes in PROCESS.md)

Places where a runner rule mirrors prose and needs review if the prose changes: `settleAfterUpholds=2`
↔ COMMON-GATE "upheld twice"; outcome/verdict/disposition vocabulary ↔ COMMON-OVERVIEW and
COMMON-GATE; review checkpoints ↔ PLAN-TO-SPEC / CLEANUP "Checkpoint after this step" and project.yaml
comments; step order ↔ `gates` order and comments; carry-forward doc names ↔ POSTMORTEM "TODOs" /
"CLARIFICATIONS"; CHAT-TO-PLAN done by the driver ↔ "top-level agent in the owner's chat session";
gate read-only ↔ AGENTS.md "read-only for gates"; owner words ↔ the CHAT-TO-PLAN word list.

---

## 5. Test strategy

**Principles.** Partial integration, no mocking of git or the filesystem; every scenario runs the real
runner in a throwaway repo built by `sandbox.py`; the LLM is replaced by `stub_agent.py`. Fast paths use
in-process `play()`; CLI paths use `subprocess`. Targets: whole suite < 4 minutes on this machine, each
test < 15 s, no network, no user git config touched.

**Fixtures (`tests/fixtures.py`, on `src/sandbox.py`).**
- `Repo(tmp)`: `git init`; `.gitignore` (with `<worktreeDir>/`); hermetic env (`GIT_CONFIG_GLOBAL` = an
  empty temp file, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed author/committer,
  `PYTHONUTF8=1`); copies `spec.yaml` and `harness/{AGENTS.md, project.yaml, subAgents.yaml,
  locked_prose, src, docs, INDEX.md}` plus a fresh acked `spec_snapshot.json`; **not** `harness/tests`
  (the sandbox suite is only the round's tests). Writes `harness/local.yaml`: `agentCommand` →
  `py -3.13 <absolute stub path>`, `suiteCommand` scoped to the sandbox. Initial commit on `main`.
- `Repo.add_origin()`: local bare origin by absolute path; `Repo.clone()`; `Repo.view(worktree)`.
- `Origin`: truth via `git -C origin.git`; hook installers `reject(refglob, n|all)` and
  `move_and_reject_once(refname, to_ref)`, written as `#!/bin/sh` wrappers calling `py -3.13 <hook>.py`
  (Git for Windows runs sh hooks). Milestone 0 has a probe test asserting hooks fire; if they do not on
  this machine, switch to the seam `SHACKLES_BEFORE_PUSH_CMD` (the runner executes it before each push
  when set) — decide once, in milestone 0, and record the choice in PROCESS.md.
- `play(repo, until=STEP, script=…)`: drives `next` / stub / `record` in-process to a step in seconds.
- `stub_agent.py`: parses `STEP:`, `KIND:`, `ROUND:`, `ATTEMPT:`, `ROOT:`, `ARTIFACT:`, `RESULT_FILE:`,
  `DIFF_FILE:`. Canned tiny task from `tests/fixtures/tiny/` (a hello module + its test). Modes via
  `STUB_MODE` or `STUB_SCRIPT` (JSON `{"STEP:attempt"|"STEP"|"*": mode}`): `pass`, `pass_nb`, `fail`,
  `dispute`, `uphold`, `withdraw`, `needs_owner`, `q_uphold`, `q_withdraw`, `upstream`, `blocked`,
  `garbage`, `fence`, `prose_wrapped`, `stray`, `locked`, `frozen`, `red`, `markers`, `resolve`, `slow`,
  `replay` (`STUB_REPLAY=<round folder>`), `archive` (`STUB_ARCHIVE=1`), plus `STUB_LOG` for
  invocation assertions. Prints `{"result": "<json>", "total_cost_usd": 0.01}` like `claude -p`.

**Test files and what they assert.**
- `test_spec_guard.py`: §4.14, including the subprocess meta-test.
- `test_config.py`: defaults for every key when deleted; id width from `NNNN`/`NNN`/none; gates map
  order and absent ⇒ disabled; local.yaml precedence; CRLF/BOM normalization; `..` living paths.
- `test_pipeline.py`: gate keys ⊆ pipeline with equal relative order; every OVERVIEW/GATE file ↔ a step;
  synthetic spec variants (gate removed, `CLEANUP-GATE` added, step renamed) fail with the expected
  instruction text.
- `test_prompts.py`: every placeholder in every prose file resolves for a synthetic round except the
  snapshot's `known_unresolved`; recursion, cycle, marker; value formatting; prose read from
  `prose_commit` not the tree (modify prose after start → prompt unchanged); GATE-PROSE selection (LLM
  gate, mech gate, disabled); PROCESS-INSTRUCTIONS present exactly once even when the placeholder is
  removed; machine lines present.
- `test_schemas.py`: validator behaviors; each schema with a good and a bad example; unwrapping (fence,
  prose-wrapped, last object); gate normalization; id assignment.
- `test_runner_cli.py` (no-branch mode, fast): start refusals (bad plan, unacked spec, stale spec);
  action shape; record guards (wrong step/attempt, replay ⇒ exit 2); infra-error path; scoped dirty
  recovery (an untracked dir outside living paths survives); every cell of the §4.9 outcomes table with
  gates on and off, approved and delegated; disputes → rulings → settlement → dropped dispute;
  withdrawn-not-re-raised; review checkpoints raised/skipped by `delegate --through`; `answer` inlined;
  runtime `override`; each cap → stop → `resume`; hard stop; abandon before/after landing;
  `status`/`spend` output; `push` retry; runner-path guard.
- `test_checks.py`: M0–M7 each triggered by a stub mode, revert verified and in-scope work kept;
  freeze/re-freeze; archive move and collision; reuse rule; living charge arithmetic (cap crossing,
  refund, base costs, test count) against hand-computed numbers; time accrual; share defaults with and
  without AGENTS-PLAN and with disabled gates; `retry_cost`.
- `test_concurrency.py`: claim (I1/I2 assertions from the summary incl. `git log --all` emptiness);
  lost race via a narrowed fetch refspec (`!` and `=` shapes); reject-all bound (5 pushes, exact error);
  explicit branch taken (one push); worktree-add failure keeps the claim; id sourcing ignores
  `round/003-x` and tags; fence (another clone moves the branch → `record` exits 1 with the message);
  landing after a sibling moved main (`check` side-effect free; then lands on top; living entry equals
  this round's diff only); rejected main push with move-and-reject-once (`attempts[LANDING] == 1`,
  sibling file present); reject-all landing (exit 1, no tag, no living entry, state at LANDING, lands on
  rerun); conflict → conflict attempt → `resolve` → lands (markers gone, both sides present);
  `sync_main` true / idempotent / false; index.jsonl merges from two rounds; `prune`; overlap warning;
  start from origin main not local HEAD; stale-spec refusal.
- `test_full_round.py`: `run --until done` with gates off, then all gates on with a script holding one
  FAIL per gate and one dispute; asserts the whole archive shape (every roundPaths file), one HISTORY
  entry per attempt, `finished`, tag, index line, `sync_main`; a delegated run raises no review
  checkpoint; an approved run raises exactly two and completes after two `approve`s.
- `test_stub_agent.py`: each mode yields schema-valid output; `replay`.
- `test_smoke.py`: `smoke --emit` builds one sandbox per step, prompts carry the machine lines, the
  manifest lists expectations; `smoke --collect` on canned stub results yields the expected matrix.
- Windows cases inline: paths with spaces; CRLF spec files; UTF-8 BOM; `.cmd` resolution (skipped if no
  `claude`); rmtree retry on locked files; `git worktree prune` in teardown.

**Bootstrap acceptance.** `py -3.13 -m pytest harness/tests -q` green; `run.py lint` clean (only the
acknowledged unresolved list, empty if the §7 edits stand); `run.py doctor` green except flags the
installed `claude` lacks; `run.py sandbox --dir <tmp> --origin` then `run --until done` with the stub in
that sandbox, gates on, finishes.

---

## 6. Real-agent testing loop (proposal)

The owner's plan (tiny task end to end, gates off, then on, then variations) pays for the whole
sequential pipeline each time and stops learning at the first gate that refuses a reasonable artifact.
Cheaper and more comprehensive:

1. **Stub suite** (free, minutes): every mechanical variation — checkpoints, approval skips, overrides,
   caps, conflicts, races — is already a deterministic test (§5). Do not spend agents on them.
2. **Step-isolation smoke matrix** (`run.py smoke`, roughly $3–8 with `low`, 15 minutes, parallel): for
   each producer and gate step, build a sandbox played to just before that step from the tiny fixture,
   render the real prompt, and run one real agent on it. Two variants per gate: `good` (the fixture
   artifact; expect PASS) and `bad` (`fixtures/tiny_bad/`: a spec missing a component; tests not
   covering it; an implementation with a feature beyond spec; an unjustified suite decision; a
   postmortem with a broken trace; expect FAIL). Producers: expect a schema-valid result and, for
   artifacts, M6-valid output. `--mode emit` writes prompts and a manifest so the driver dispatches them
   with its Agent tool in parallel; `--mode exec` runs `agentCommand`; `--collect` validates results and
   prints `step × variant → valid | verdict as expected | cost | turns`, writing `smoke-report.json`.
   This measures gate effectiveness and prompt comprehension directly, covers steps a sequential run
   never reaches, and gives the owner evidence for relaxing gate language, if any.
3. **One sequential end-to-end** in a sandbox (`run.py sandbox --dir … --origin`), gates on,
   `tierOverride: low`, the tiny task (roughly $5–15). Then copy its `PROMPTS/` + `RESULTS/` into
   `tests/fixtures/replay/`: the stub's `replay` mode turns one paid run into a permanent regression test
   of prompt→result parsing.
4. **First real round on the real repo** (dogfooding): a small real task with the configured tiers; its
   POSTMORTEM seeds `docs/TODO.md`. Rerun the matrix after any prose change.

Default `smoke` tier: `systemTestAgent` (currently `medium`); `--agent low` for the cheap pass.

---

## 7. Spec file edits (exact, minimal)

Two one-token edits, both fixing a placeholder with no key in project.yaml. Apply them in a
**separate commit** whose subject starts with `SPEC EDIT (owner review required)` and whose body holds
this diff; repeat the diff in the final report; record it in `spec ack --note`. If the owner declines,
revert that commit — the runner still works (unresolved marker + `known_unresolved` in the snapshot).

```
--- harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
+++ harness/locked_prose/CHAT-TO-PLAN-OVERVIEW.txt
@@ -6 +6 @@
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the plan, and the plan needs to read as plain English.
+Assume a cost of ${{ project.planCostPerWord }} per word in the plan, and the plan needs to read as plain English.
--- harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
+++ harness/locked_prose/PLAN-TO-SPEC-OVERVIEW.txt
@@ -11 +11 @@
-Assume a cost of ${{ project.ownerReviewCostPerWord }} per word in the spec, and the spec needs to read as plain English.
+Assume a cost of ${{ project.specCostPerWord }} per word in the spec, and the spec needs to read as plain English.
```

No edit to `project.yaml`, `subAgents.yaml`, `AGENTS.md`, or any gate prose. Gate language is not
relaxed in bootstrap: COMMON-GATE's cost threshold already tempers the per-line "Fail" lines; measure
with the smoke matrix first and hand the owner numbers (§6). Operational keys (`agentCommand`,
`mainBranch`, …) live in runner defaults and `local.yaml`, so the owner may adopt them into
project.yaml later without any bootstrap edit.

---

## 8. Build order and acceptance criteria

Work in this order; each milestone ends green.

| M | Build | Accept when |
| --- | --- | --- |
| 0 | `.gitignore`; `gitutil.py`; `sandbox.py` + `fixtures.py` (Repo/Origin/hooks); hook probe test | the probe proves hooks fire, or the seam is chosen and recorded |
| 1 | `config.py`, `specguard.py`, `spec_snapshot.json`, `test_config.py`, `test_spec_guard.py` (incl. meta) | the guard fails on a byte change and its self-test passes |
| 2 | `pipeline.py`, `schemas.py`, `prompts.py`; `prompt`/`lint`/`schema` commands; their tests | every prose placeholder resolves except the known list; `lint` clean |
| 3 | `rounds.py`, `ledger.py` (shares, ledger, time, owner); `run.py` no-branch `start/next/record/status`; stub agent; `test_runner_cli.py` outcomes table | a stub round runs to finished in no-branch mode with gates off |
| 4 | `checks.py` (M0–M7), freeze/archive/reuse, living charge; `test_checks.py` | each check triggers and reverts; arithmetic tests pass |
| 5 | `landing.py` (claim, worktree, fence, landing loop, conflict attempt, sync, abandon, prune, overlap warning); `test_concurrency.py` | all §5 concurrency assertions |
| 6 | Owner-driven commands, checkpoints, caps, headless `run`, `doctor`, `push`, `spec adopt`; `test_full_round.py` | the gates-on scripted round with fails and disputes finishes; the approved run needs exactly two approvals |
| 7 | `smoke.py`, `fixtures/tiny_bad/`, `test_smoke.py`; `owner_log_hook.py` | `smoke --emit` / `--collect` round-trip on stub results |
| 8 | `INDEX.md`, `docs/PROCESS.md`, `docs/TODO.md`, `docs/CLARIFICATIONS.md`; the §7 commit; final report with the diff, `lint`/`doctor` output, suite time | §5 acceptance list |

Engineering rules: tests first for every mechanical check and guard; commit per milestone (you are not
subject to the runtime invariants); no new dependencies (PyYAML, pytest, git only); every subprocess
call goes through `gitutil.run()` with explicit encoding; no `print` outside `run.py`.

---

## 9. Risks and open questions, with recommended resolutions

| # | Question / risk | Resolution in this plan |
| --- | --- | --- |
| 1 | `{{ project.ownerReviewCostPerWord }}` has no key | Two one-token prose edits (§7); the marker fallback keeps rounds running if declined |
| 2 | CLEANUP's position and the checkpoints exist only in comments and prose | `pipeline.py` fixes them; `test_pipeline.py` fails loudly on drift; listed in the wording-adjacent table |
| 3 | Owner words (approve/delegate/override) must not be parsed by the runner | The driver interprets them (its judgment call under the prose) and issues commands with `--quote`; the runner stores the quote |
| 4 | Gate prose may be too strict to pass | Not relaxed now; the smoke matrix measures pass/fail per gate and gives the owner evidence; `spec adopt` lets a running round pick up relaxed prose |
| 5 | Landing conflicts never converged in the sibling | Conflict attempt (§4.12) with M1/M2/M5 adjustments, tested with `resolve` |
| 6 | `claude` CLI flags drift (`--effort`, `--max-budget-usd`, `--system-prompt-file`) | `doctor` checks `--help`; `agentCommand` overridable in `local.yaml`; default verified from the sibling |
| 7 | Cost unknown in driver mode | `--cost` > `--tokens-*` > estimate = step share, flagged; the hard stop still bounds spend |
| 8 | sh hooks may not run on this machine's git | Milestone 0 probe; the seam fallback decided once |
| 9 | `maxRoundAttempts` / `maxFailuresBeforeStop` semantics | Re-entry cap / total-FAIL cap → stop checkpoint; owner `resume` raises the cap once per round |
| 10 | NEEDS-OWNER with the gate disabled in delegated mode | Continue on the stated assumption, list in `pending_questions` at the next checkpoint or done; approved mode asks |
| 11 | Upheld question in delegated mode | Still a question checkpoint: delegation removes review checkpoints, not questions a gate judged worth the owner's cost |
| 12 | A gate absent from `project.gates` | Disabled; lint warns (matches the all-zero current file) |
| 13 | `systemTestAgent`, `maxRunWallClockHours`, `costToWaitForOwner`, `ownerHourlyRate` | smoke default tier; headless pause; flat per checkpoint; `--owner-minutes` on resume |
| 14 | The harness modifies its own runner in a round | Runner pinned to the worktree; M3 runs the harness suite before the gate; `--root` escape hatch |
| 15 | `git clean` near `.claude/worktrees/` | Clean scoped to the harness dir + living paths; `worktreeDir/` must be ignored; doctor warns about an unignored `.claude/worktrees/` |
| 16 | Round-id width changes mid-history | Ids are ints; folders parsed with `\d+`; rendering uses the current width |
| 17 | AGENTS-PLAN budgets exceeding the quote | M6 blocking finding; defaults fill omitted steps |
| 18 | The owner edits SPEC at a checkpoint | `approve` re-hashes; downstream re-entry only if a consumer already ran |
| 19 | `errata` excluded from hashing could hide changes | Errata are shown to every later step (`ERRATA:` line) |
| 20 | Two driver sessions, one OWNER.log | The per-round slice comes from `--quote`; the hook is optional, never required |
| 21 | M4 measures refactoring by declared paths only | Accepted; the gate judges the rest |
| 22 | Token counting by bytes/`tokenBytes` | The owner's number is the contract; exact tokenizers deferred |

---

## Appendix A — PROCESS-INSTRUCTIONS template (generated; machine lines are the `KEY:` lines)

```
PROCESS-INSTRUCTIONS (mechanical; generated by the runner; follow exactly)
STEP: {step}
KIND: {producer|gate}
ROUND: {id}
ATTEMPT: {n}
ROOT: {absolute round root}
HARNESS: {harness dir, repo-relative}
READ: {repo-relative inputs: upstream artifacts, FINDINGS/…, RESULTS/… of prior attempts, harness/INDEX.md, harness/docs/PROCESS.md; gates also the artifact and DIFF_FILE}
ARTIFACT: {repo-relative artifact path(s), or "none" for gates}
DIFF_FILE: {PROMPTS/<STEP>-<n>.diff or "none"}
MAY-WRITE: {allowed paths; "nothing (read-only)" for gates}
MUST-NOT: run git commit, push, reset, checkout or clean; edit {spec files}; write outside MAY-WRITE; run more than {maxSimultaneousSubAgentsPerRound} sub-agents at once; contact the owner
BUDGET_USD: {share}   MAX_TURNS: {maxTurnsPerRun}   AGENT: {key} ({display name})
GATE_ENABLED: {yes|no}   MODE: {approved|delegated}
OPEN FINDINGS: {inline JSON if ≤ inlineFindingsMaxBytes else path}   (producers on retry; gates always)
OWNER ANSWERS: {inline list or "none"}
ERRATA: {inline SPEC.errata or "none"}
CARRIED (advisory): {inline or "none"}
RESULT_FILE: {repo-relative path the driver will write; do not write it yourself}
RESULT: your final message is exactly one JSON object and nothing else, matching this schema:
{PRODUCER_RESULT or GATE_RESULT schema, pretty JSON}
ARTIFACT SCHEMA: {artifact schema, pretty JSON, or "prose, non-empty"}
WARNINGS: {unresolved placeholders etc., or "none"}
```
For CHAT-TO-PLAN (no round): `READ` = docs/TODO.md, docs/CLARIFICATIONS.md, the latest POSTMORTEM.md,
`spend --project`; `ARTIFACT` = "PLAN.json at a path of your choice"; `RESULT` = "when the owner
approves, run `run.py start --plan <path>`; the approval block is your reading of their words".

## Appendix B — Schemas (required fields marked *)

PLAN: `title*` str; `owner_words*` [{at, text}] ≥1; `scope*` [str] ≥1; `validation*` [str] ≥1;
`non_goals` [str]; `assumptions` [str]; `todos` {suggested [str], accepted [str]}; `quote_usd*` number > 0;
`approval*` {mode* ∈ approved|delegated, through str|null, overrides [str], words* str};
`provided_artifacts` {artifactKey: path}; `round` (set by start).

AGENTS_PLAN: `steps*` {STEP: {agent* tierKey, budget_usd* ≥ 0, sub_agents {max_simultaneous int, agent tierKey|null}, note str}};
`gates*` {GATE: {agent* tierKey, budget_usd* ≥ 0}}; `total_usd` number.

SPEC: `summary*` str; `impl_paths*` [str] ≥1; `test_paths*` [str]; `refactor_paths` [str]; `verify` str|null;
`steps*` [{id*, description*, paths [str]}] ≥1; `test_plan*` [str] ≥1; `non_goals` [str]; `assumptions` [str]; `errata` [str].

SUITE: `tests*` [{path*, decision* ∈ suite|archive, reason*}]; `flag_for_owner` [str].

PRODUCER_RESULT: `status*` ∈ DONE|NEEDS-OWNER|UPSTREAM|BLOCKED; `summary*` str; `question` str|null;
`assumption` str|null; `upstream` {step*, quote*, contradiction*}|null; `narrow` str|null;
`disputes` [{finding*, argument*, quote*}]; `judgment_calls` {defined int, undefined int}.
Consistency: NEEDS-OWNER ⇒ question and assumption; UPSTREAM ⇒ `upstream.step` is an earlier producer;
BLOCKED ⇒ narrow.

GATE_RESULT: `verdict*` ∈ PASS|FAIL; `findings*` [{id, quote*, reason*, suggestion*, blocking* bool}];
`rulings` [{finding*, disposition* ∈ upheld|withdrawn, quote*}];
`owner_question` {disposition* ∈ upheld|withdrawn, answer_to_assume str|null}|null; `summary*` str.

STATE: as §4.8; all listed keys required except those marked `|null`.

ACTION (stdout of `next`): `kind*` ∈ agent|checkpoint|done|paused. agent: `round, id, step, attempt,
role ∈ producer|gate, prompt_file, result_file, artifact [], read_only bool, agent {key, name, model,
effort}, budget_usd, max_budget_usd, max_turns, spend, remaining, runner {version, path}, worktree,
notes []`. checkpoint: `checkpoint {kind, step, artifact?, question?, reason?}, how_to_resume []`.
done: `status, main_synced, landed_at, pending_questions [], spend, hint`.

## Appendix C — Driver procedure (PROCESS.md, "Driving a round")

1. `py -3.13 harness/src/run.py prompt CHAT-TO-PLAN` → follow it in chat; write PLAN.json.
2. On the owner's approval word: `start --plan PATH` → note `worktree` and `runner`.
3. Loop: `py -3.13 <runner> next`. If `agent`: spawn a fresh sub-agent with the prompt file verbatim
   (read-only type for gates); save its final message to `result_file`; `record --step --attempt
   --result [--cost | --tokens-in/--tokens-out]`. If `checkpoint`: relay to the owner in chat; on their
   words run `approve | delegate | answer | resume | override | abandon --quote "<their words>"`.
   If `done`: relay `pending_questions`; tell the owner to `git pull --ff-only`.
4. Never write artifacts, judge, commit or push yourself. If a sub-agent returns garbage twice, use
   `record --infra-error`.
