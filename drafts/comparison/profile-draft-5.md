# Profile: draft 5

## 1. Format and size

- 17 files, 170,164 bytes: `SPEC.md` (21,327 B, entry point), `JUDGMENT-CALLS.md` (22,405 B), 15 component files `components/01-repo-root.md` … `15-schemas.md` (126,432 B; largest `13-tests.md` 26,278 B, then `10-round-engine.md` 17,834 B).
- `SPEC.md` is "the map": §1 one-screen overview (actor table, step table, git, money, judgment calls), §2 vocabulary, §3 repo tree, §4 component map with dependency direction, §5 cross-cutting architecture (5.1 guard, 5.2 git, 5.3 lifecycle per step, 5.4 prompts, 5.5 results, 5.6 money, 5.7 "Where each owner-listed architecture feature lives"), §6 reading order, §7 file list. Every component file uses the fixed layout "Purpose · Owns · Depends on · Depended on by · Files · Signatures · Errors · Invariants · Covered by".
- Judgment calls cited inline as `JC-nn`: 75 citations across SPEC.md and the components; all 54 ids cited at least once outside `JUDGMENT-CALLS.md`; each JC entry carries an *Affects:* back-reference.
- Reading order (SPEC.md §6): 02 → 15 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 03 → 11 → 12 → 13 → 14 → 01.

## 2. Language, runtime, packaging, tooling

- Python ≥ 3.11 (JC-03); git ≥ 2.38 for `merge-tree --write-tree` (01, 07); Claude Code with hooks.
- `harness/pyproject.toml` (02): `shackles-harness` v0, `dependencies = ["pyyaml>=6", "pytest>=8"]`, pytest `testpaths=["tests"], addopts="-q --ignore=tests/probes"`, setuptools `packages=["shackles"], package-dir={"": "src"}`; "No build step is needed to run".
- Dependencies: PyYAML and pytest only. Lint/format/type tools: not specified. Scripts/Makefile: none beyond the `run.py` command set (03).
- CI `.github/workflows/ci.yml` (01): one job, `ubuntu-latest`, Python 3.11, `fetch-depth: 0`, `pip install -e harness`, `run.py doctor --offline --json --strict`, `pytest harness/tests -q --ignore=harness/tests/probes`; probes never in CI.
- Generated: `INDEX.md` (committed, 11), `.claude/agents/shackles-<rung>-{work,gate}.md` (committed, roster-hash stamped, 06), `local.yaml` and `OWNER.log` (gitignored), `archives/spec-baseline/` (04).
- Platform surface: hooks `UserPromptSubmit`/`SessionStart` with `$CLAUDE_PROJECT_DIR` (JC-54); Agent-tool definition front matter (S13, JC-10); probes via `claude -p --output-format json --agent …` (JC-32).

## 3. Repository layout

From SPEC.md §3 and `02-harness-root.md`:

```
shackles_harness/                repo root
├── spec.yaml, SPEC.md           OWNER
├── README.md, .gitignore        ignores harness/OWNER.log, harness/local.yaml, .worktrees/, caches
├── .github/workflows/ci.yml
├── .worktrees/round-NNNN/       gitignored; one git worktree per round
└── harness/                     harness root; every project.yaml path is relative to it
    ├── AGENTS.md, project.yaml, subAgents.yaml, locked_prose/    OWNER
    ├── INDEX.md                 generated, committed
    ├── local.yaml, OWNER.log    generated, gitignored
    ├── pyproject.toml, .claude/settings.json (hooks), .claude/agents/ (generated, committed)
    ├── src/run.py, src/shackles/   LIVING — the runner
    ├── docs/                    LIVING — PROCESS.md, ARCHITECTURE.md, TODO.md, CLARIFICATIONS.md
    ├── tests/                   LIVING — suite, fixtures/, stub/, probes/
    └── archives/                committed: spec-baseline/{MANIFEST.json, files/…}, rounds/NNNN/
```

Round folder `archives/rounds/NNNN/` (names from `roundPaths`): `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SPEC.md`, `SUITE.json`, `POSTMORTEM.md`, `STATE.json`, `HISTORY.md`, `OWNER.log` slice, `PROMPTS/`, `RESULTS/`, `FINDINGS/`, `tests-archive/`, `DEFINED_`/`UNDEFINED_JUDGMENT_CALLS.md` — "the only place agents may write outside their step's declared paths" (02).

## 4. Actors and roles

- Owner — the human in chat; edits spec files; acts only through verbatim quotes behind the verbs `approve`, `delegate`, `override`, `answer`, `abandon`, `continue`, `raise-hard-stop`.
- Driver — the top-level Claude Code session in `harness/`; runs `run.py`; performs CHAT-TO-PLAN itself (writes `PLAN.json`); spawns one fresh sub-agent per attempt from the prompt file; saves the final message verbatim to `RESULTS/`; calls `record` with observed usage; never commits.
- Runner — `src/run.py` + `shackles/`, "a plain CLI with no LLM inside"; the only thing that commits, pushes, bills and produces owner text; "never parses prose".
- Producers — sub-agents writing in the worktree within declared write roots plus the round folder; end `DONE`/`NEEDS-OWNER`/`BLOCKED`; log judgment calls with `run.py jc`.
- Gates — read-only sub-agents (`-gate` definition tools, JC-44); `PASS`/`FAIL` with findings and rulings in the final message; judgment calls via a result field.
- Conflict resolver — one `conflict` attempt at LANDING or sync on conflicted files only, judged against the auto-merged tree (10).
- Hooks — `UserPromptSubmit` appends the prompt to `OWNER.log`; `SessionStart` writes a marker, regenerates `local.yaml`, warns on stale agent definitions and paused rounds (06).
- Agent definitions — generated per rung in two roles (06). Test-only drivers: `tests/stub/StubDriver`, `tests/probes/LiveAgent` + `live_driver` (13, 14).

## 5. Architecture: the main mechanisms

a. Step table — `steps.py` (05): `STEP_TABLE` of frozen `Step` records (kind DRIVER/PRODUCER/CHECKPOINT/RUNNER/PRODUCER_NO_GATE, gate flag, prose stems, artifact keys, input and write-root symbols, `skip_effect`); 11 steps; `lint()` checks it against `project.yaml: steps` and `locked_prose/` names (order mismatch is an error, JC-39).
b. Lifecycle — `round_start/next/record/owner.py`, `advance.py`, `landing.py` (10); state = `STATE.json` (S1) in the round folder inside the worktree, committed on `round/NNNN`, "the only file the engine reads to decide anything"; statuses claimed/planning/running/paused/landing/ended; pause kinds approval/checkpoint/needs-owner/blocked/limit/fence/landing; every change ends in `fence()` = commit + lease push (JC-41).
c. Prompts — `prose.py` + `plumbing.py` (05): `{{ ns.NAME }}` over `prose` (recursive, cycle-checked), `project`, `round`, `agents` (AGENTS.md `##` sections), `plumbing` (`PROCESS-INSTRUCTIONS`, `GATE-PROSE`); `assemble_prompt` = overview or gate prose + `COMMON-STEP-END` appended (JC-06); strict rendering raises `UnresolvedTokenError` naming all; the conflict prompt falls back to owner `COMMON-*` files (JC-05).
d. Owner channel — `ownerlog.py`, `hooks.py` (06), `round_owner.py` (10): JSONL log (S9); `verify_quote` = NFC/whitespace-normalized substring of a `prompt` entry with index > `pause.log_index_at_pause` (JC-07); verbs in `STATE.owner_words`, answers in `STATE.answers` (JC-26); byte-exact round slice per verb and at end (JC-50); `start` refuses without a log.
e. Git — `gitops.py` (07): claim = first commit pushed `--force-with-lease=refs/heads/round/NNNN:` expecting absence, 3 id retries (JC-13); fence = lease push, rejection → pause `fence` + `FenceLost`; worktree `<repo>/.worktrees/round-NNNN`; landing = `merge-tree --write-tree`, verify in a temporary worktree, `push_ref` with lease on `main_before`, retried up to `maxRoundAttempts` (JC-15); conflict → one attempt, strays restored from the auto-merged tree; round branch rebased onto the landed commit; bounded post-landing `sync`; `sync_archives_only` for abandoned rounds (JC-22); driver checkout only fast-forwarded when clean (JC-24).
f. Results/findings — `results.py`, `findings.py` (08): S7 shapes; fenced JSON tolerated (JC-52); `normalize_gate` — "the verdict wins" (FAIL without findings is malformed, JC-30); statuses open/fixed/disputed/upheld/settled/withdrawn/closed; upheld twice = settled; withdrawn repeats dropped by normalized quote (JC-31); a `DONE` lacking a resolution for a handed finding is rejected; per-gate `FINDINGS/STEP-n.json`; flags shown once at the next pause.
g. Money — `tokens.py`, `pricing.py`, `ledger.py` (09): token = `ceil(bytes / tokenBytes)`; attempt cost = `max(spawnCost, priced usage)`, usage measured via `record --tokens-*` else estimated with `estOutputFraction` (JC-17); `driverUsdPerStep` per accepted step (JC-48); living charge at CLEANUP on the net diff `main_before → cleanup commit` (cap, base cost, renames free JC-45, `testBaseCost` per test function); carry-forward docs at `postMortemFileCostPerToken` (JC-18); archive charges (JC-19); ledger inside STATE (S10); round hard stop on `spent + projected living` before landing, individual stop after each attempt (JC-33); shares never billed; time cost context only (JC-29).
h. Checks — `mechanical.py`, `verify.py`, `suite.py` (10): at `record` on the uncommitted diff: strays and spec-file edits reverted, never a failure (JC-23); then per kind: PLAN/AGENTS-PLAN/SPEC shapes, SPEC-TO-TESTS collects and the pre-existing suite passes (JC-46), SPEC-TO-IMPLEMENTATION whole suite within `verifyTimeoutSeconds`, SUITE paths, POSTMORTEM Summary, CLEANUP verify, conflict (no markers, other files equal the merged tree, verify), gate (any diff reverted); `verify.run` = `cfg.verifyCommand`; TESTS-TO-SUITE moves or splits files into `tests-archive/` then re-verifies (JC-47, JC-53); one `rejections` counter per step for gate FAIL, mechanical and malformed, bounded by `maxTurnsPerGate` (JC-14).
i. Doctor/index — `doctor.py`, `index.py` (11): S17 report by area (spec-files, config, roster, steps, prose, agent-defs, owner-log, git, hooks); renders every producer/gate/checkpoint/conflict prompt via `placeholder_attempt`; `INDEX.md` one line per file from headers, regenerated at CLEANUP, test-checked (JC-25).
j. Robustness — SPEC.md §5.1: hashed baseline plus byte snapshots in `archives/spec-baseline/` (JC-02); `test_spec_guard.py` is the only test reading real spec files and prints unified diffs; `start` refuses on drift, `accept-spec` re-baselines; mechanics tests use a generated one-line-per-file spec tree (13); config schema with five defaulted keys named by doctor (JC-09), unknown keys refuse `start` (JC-08); unknown steps or prose names refuse (05 lint).

## 6. Module inventory

34 source modules: `src/run.py` plus 33 under `src/shackles/` (no `__init__.py` is mentioned).

- `run.py` — entry; `sys.path` insert; `sys.exit(cli.main(argv))`.
- 03 `cli.py` — argparse sub-commands (`setup doctor accept-spec start next record owner jc status ledger verify index hook render`), `Ctx` build, exception → exit code 0/1/2/3. `output.py` — every driver/owner string (`next_action_text`, `owner_text`, `bill_text`, `error`, `json_dump` …).
- 04 `paths.py` — `Paths`; repo/harness discovery, `round_folder`, `round_file`, `is_under`. `specfiles.py` — spec list, hashing, baseline, `drift -> DriftReport(FileDrift)`, `format_drift`. `config.py` — `Key` schema, `Config`, `Rung`, `Roster`, `RoundPaths`; `load_config`, `load_roster`, `project_values`. `agentsmd.py` — AGENTS.md `##` sections. `localyaml.py` — derive/write/read `local.yaml`.
- 05 `steps.py` — `StepKind(Enum)`, `Step`, `STEP_TABLE`, lookups, `lint -> LintReport`. `prose.py` — `Namespaces`, `Rendered`, `render`, `find_tokens`, `round_values`. `plumbing.py` — `AttemptSpec`, `Prompt`, `process_instructions`, `gate_prose_for`, `assemble_prompt`, `placeholder_attempt`.
- 06 `ownerlog.py` — `Entry`, `Match`; locked append, `normalize`, `verify_quote`, `slice`. `hooks.py` — `hook_prompt`, `hook_session_start`. `agentdefs.py` — `definition_text`, `write_all`, `is_stale`, `definition_name`.
- 07 `gitops.py` — the only module running git: `PushOutcome(Enum)`, `MergeResult`, `FileChange`; facts, `claim_round`, `fence_push`, worktrees, diffs/reverts, `merge_tree`, `commit_tree`, `push_ref`, `fast_forward_checkout`.
- 08 `state.py` — `State` with nested `Attempt`, `Pause`, `Flag`, `Limits`, `Landing`, `StepRecord`; load/save/transitions. `results.py` — `ProducerResult`, `GateResult`, `read_result`, `normalize_gate`. `findings.py` — `Finding` lifecycle. `judgmentcalls.py` — JC lines, `jc_command`. `history.py` — append-only HISTORY.md.
- 09 `tokens.py` — token estimate, test-function counting, Summary bytes. `pricing.py` — pure price formulas. `ledger.py` — `bill_attempt`, `bill_driver_step`, `book_round`, `LivingChange`, hard stops, `project_remaining`, `format_bill`.
- 10 `round_start.py` — `Ctx`, `RoundCtx`, `preflight`, `start`, `open_round`, `fence`. `round_next.py` — `next_action -> NextAction`, `issue`, `pause_text`. `round_record.py` — `record -> RecordOutcome`. `round_owner.py` — `owner_verb`. `advance.py` — `accept`, `skip`, `validate_agents_plan`, `end`. `mechanical.py` — `check_attempt -> CheckResult`, `allowed_roots`. `verify.py` — `run -> VerifyResult`, `collect_only`. `suite.py` — `apply -> SuiteReport`, `split_file`. `landing.py` — `land`, `verify_tree`, `sync`, `sync_archives_only`.
- 11 `doctor.py` — `run_doctor -> Report`, `checks_for_start`. `index.py` — `generate`, `regenerate`, `is_current`.

Error classes: `PathsError`, `SpecListError`, `ConfigError`, `AgentsMdError`, `ProseError`, `UnresolvedTokenError`, `UnknownStepError`, `OwnerLogError`, `GitError`, `StateError`, `MalformedResult`, `StartRefused`, `NoActiveRound`, `FenceLost`, `QuoteNotFound`, `PlanQuestionsOpen`, `OverrideRefused`, `VerbNotAllowed`, `VerifyError`, `ProbeError`. Test-side classes: `SpecTree`, `Repo`, `FakeClock`, `CliResult`, `StubDriver`, `StubContext`, `Behavior`, `LiveAgent`.

## 7. Data contracts

Seventeen shapes in `15-schemas.md`, each naming writer and readers:

- S1 `STATE.json` — status, mode, overrides, owner_words, answers, quote_usd, agents_plan, per-step attempts/rejections, current, pause (`log_index_at_pause`), flags, findings, limits, landing, ledger; round folder in the worktree, committed on the round branch.
- S2 `PLAN.json` — text, scope, non_goals, assumptions, validation_steps, quote_usd, numbered questions with lettered options, accepted_todos; round folder, driver-written; answers not here (JC-26).
- S3 `AGENTS-PLAN.json` — per-step/gate rung and share (plus sub_agents), rationale; round folder; validated (JC-35).
- S4 `SPEC.json` + `SPEC.md` — summary, non_goals, components[{name, description, files}], test_plan, …; only summary and files read mechanically; round folder.
- S5 `SUITE.json` — decisions[{path, function|null, suite|archive, why}], flags; round folder.
- S6 `POSTMORTEM.md` — first heading `# Summary`/`## Summary`; that section is charged; round folder.
- S7 `RESULTS/STEP-n.json` — producer/driver/conflict: status, summary, artifacts, resolutions, flags, questions, narrow, judgment_calls; gate: verdict, summary, rulings, findings, flags, judgment_calls; unknown keys kept; round folder, driver-written verbatim.
- S8 `FINDINGS/STEP-n.json` — verdict plus finding records (id, status, upheld_count, history), dropped_repeats; round folder.
- S9 `OWNER.log` line — `{i, ts, session, kind: prompt|marker, text}`; `harness/OWNER.log` (gitignored) and the round slice.
- S10 ledger — attempts, driver_steps, living{files, tests, carry_forward}, archive, time_context_usd, total_usd; inside STATE.
- S11 `MANIFEST.json` — schema, accepted_at, files{path: {sha256, bytes}}; `archives/spec-baseline/` beside `files/` snapshots.
- S12 `local.yaml` — derived paths, remote, main branch, hashes; harness root, gitignored.
- S13 agent definition — name/description/model/effort front matter, gate `tools:` list, roster-sha stamp; `.claude/agents/`.
- S14 `HISTORY.md` entry — per-attempt heading, cost, notes, verbatim final message; round folder, append-only, never read.
- S15 judgment-call line — `- STEP-n (<rung>|driver|gate) <iso>: <text>`; the two `*_JUDGMENT_CALLS.md` files.
- S16 `next` output — action spawn|driver-step|pause|ended|refused, step, attempt, kind, rung, read_only, agent_definition, prompt_file, result_file, owner_text, reason; stdout labelled lines or `--json`.
- S17 doctor report — errors/warnings[{area, item, detail}], rendered{name: {tokens, unresolved}}; stdout.

Elsewhere: `PROMPTS/STEP-n.txt` (05); probe `PLANT.json` (14); literal `pyproject.toml`, `.claude/settings.json`, `.gitignore` (01, 02); TODO/CLARIFICATIONS line formats (12).

## 8. Testing

- Infrastructure (13): `tests/conftest.py` fixtures — `spec_tree` (a complete minimal repo from `fixtures/spec_tree.py::make(tmp_path, prose_overrides, config_overrides, roster_overrides)`: one-line owner files, `project.yaml` from `fixtures/config_values.py::MINIMAL`, four-rung roster, one-line prose files for every required/optional name each carrying one token per namespace, the real `src/` copied in, a seed test); `repo` (git init, bare remote `origin.git`, `setup`, OWNER.log marker); `ctx` with `FakeClock`; `cli` (in-process `cli.main` → `CliResult`); `owner_says`; `stub`; `started`.
- Fixtures: `fixtures/artifacts.py` builders (`PLAN`, `AGENTS_PLAN`, `SPEC`, `SUITE`, `POSTMORTEM_MD`, `done`, `needs_owner`, `blocked`, `gate_pass`, `gate_fail`); `fixtures/sample_tests/` (3 files).
- Stub agent: `tests/stub/behaviors.py` — 46 scripted behaviors (`done_ok` … `conflict_touch_other_file`, `jc_defined:<n>`), parsing paths from the labelled `next` output and the `ARTIFACT:` line, "never from prose"; `stub_agent.py::StubDriver(cli, script)` keyed `STEP`/`STEP-gate`/`LANDING-conflict`; `test_stub_agent.py` parametrized over the catalog plus `test_every_behavior_used_in_flow`.
- Fake remote: every git test uses a temporary bare remote; race tests use a second clone.
- Files: 35 `test_*.py` under `tests/` (one per module plus guard, flow, stub, docs, scaffold), `conftest.py`, 3 fixture modules, 3 sample tests, 2 stub modules; probes: `conftest.py`, `live_agent.py`, `live_driver.py`, `test_probe_gates.py`, 5 fixture directories. About 380 named cases.
- Split: guard (`test_spec_guard.py`, 4 cases, the only test reading real spec files, fails with `format_drift` diffs); unit/mechanics (30 per-module files on the generated tree); integration (`test_round_flow.py`, about 40 stub-driven paths through the real CLI covering checkpoints/delegation, every pause kind, gate retries, verdict-wins, malformed JSON, suite archiving, overrides, abandon, landing conflict, sync, hard stops, limits, fence lost and ledger totals); scaffold (`test_repo_scaffold.py`, `test_docs.py`, `test_index.py` reading real `INDEX.md` headers); live probes (6 tests).
- Live probes (14): skipped unless `SHACKLES_PROBES=1` and `claude` on PATH; never in CI or `verifyCommand`. `LiveAgent.run(prompt_file, cwd, timeout_s)` runs `claude -p --output-format json --agent <definition> …` and returns `(final_message_json, usage)`; `live_driver.run_round` does `start`, the plan step, `owner delegate`, then next/spawn/`record --tokens-…`, capped at `max_attempts` (default 6); `plant()` copies planted-defect files before the step named in `PLANT.json`. Five defect fixtures (`ambiguous_spec`, `out_of_spec_impl`, `uncovered_component`, `bad_suite_choice`, `postmortem_trace_gap`) each expect FAIL with a finding quoting the planted item (normalized substring); `test_clean_fixture_passes` expects no FAIL and every attempt `measured=True`. "Pass criteria are on S7 fields only (verdict, quotes), never on wording."
- Notable assertions: `test_no_force_push_anywhere` (source scan of `gitops.py`); `test_defaulted_keys_are_exactly_the_documented_ones`; `test_committed_defs_current` / `test_committed_index_current` (regenerate in memory, compare bytes); `test_ledger_bills_actual_attempts_not_shares`. No network; no real sleep except `impl_hangs` (1-second timeout).

## 9. Docs

- `README.md` (01) — what it is, requirements, install, first run, command table, where things are, spec-file changes and `accept-spec`, tests and probes.
- `docs/PROCESS.md` (12, ≤ 2,500 tokens) — roles, driver loop, final messages (S7 verbatim), findings, judgment calls, mechanical checks at record, owner words, money in one paragraph, paths.
- `docs/ARCHITECTURE.md` (≤ 2,000 tokens) — component list, dependency rule and "no load-bearing file" rule, git model in ten lines, spec guard rationale, step table (test-checked), "where to add things".
- `docs/TODO.md` — header plus `- [ ] (round NNNN) <resolution> — <trace>`; read by CHAT-TO-PLAN, ticked by CLEANUP.
- `docs/CLARIFICATIONS.md` — header plus `## C-<round>-<n>` sections (`Plan:`, `Owner words:`, `Judgment calls:`, `Options:`).
- `harness/INDEX.md` (11) — generated `path — purpose` lines with a three-line preamble.
- Invariant: no `project.yaml` number is repeated in the docs (`test_docs.py`).

## 10. Notable or unusual decisions

- The runner is self-hosted in living `src/` and edited by rounds, but always executes from the driver's checkout, so runner changes apply only from the next round (JC-49).
- CHAT-TO-PLAN is a `driver` attempt kind: the driver writes `PLAN.json` and a result file itself; no gate (JC-04).
- `STATE.json` is the runner's only state, lives in the round folder inside the worktree, and is committed and lease-pushed after every `next`, `record` and owner verb (JC-41); answers go to `STATE.answers`, never into `PLAN.json` (JC-26).
- Unknown config keys refuse `start`; exactly five keys (`testPaths`, `verifyCommand`, `promptTokenWarning`, `gitRemote`, `mainBranch`) have code defaults that doctor names (JC-08, JC-09).
- A git remote is required; the claim is a lease push expecting an absent ref (JC-12, JC-13); dirty living paths in the driver's checkout refuse `start` (JC-37).
- Two committed agent-definition files per rung, roster-hash stamped; stale definitions refuse `start` (JC-10); gate read-only via the tools list plus reverting any gate diff (JC-44).
- Abandoned rounds still merge their archive folder to `main` (JC-22); after landing the round branch is rebased onto the landed commit so POSTMORTEM/CLEANUP start from the landed tree, then merged back by a bounded sync.
- One `rejections` counter per step covers gate FAILs, mechanical failures and malformed results, bounded by `maxTurnsPerGate` (JC-14); `maxRoundAttempts` bounds landing/sync push races (JC-15).
- A single `continue` verb clears `needs-owner`/`blocked`/`limit`/`fence`/`landing` pauses and resets whichever limit fired (JC-27); `raise-hard-stop` is per round only.
- Carry-forward docs are excluded from the living charge and priced at `postMortemFileCostPerToken` for any edit (JC-18); time cost is context, not billed (JC-29); attempt cost floors at `spawnCost`.

## 11. Judgment calls

Total: 54 (JC-01 … JC-54), in `JUDGMENT-CALLS.md`.

Classification scheme, verbatim (section "Classification scheme"):

> Each entry carries three labels.
> - **Kind** (the owner's own scheme from AGENTS.md): `DEFINED` — decidable from the spec files alone; `UNDEFINED` — needed knowledge outside them (platform behaviour, git, Claude Code, taste).
> - **Cause**: `A` spec silent · `B` spec ambiguous or two passages pull apart · `C` platform/tooling uncertainty · `D` structure/taste with several workable options · `E` conservative safety choice.
> - **Impact** if wrong: `high` (changes what the owner sees or what lands on main), `medium` (changes agent behaviour or billing), `low` (local, easy to change).

Preceded by: "Definition used (the owner's): a judgment call is any choice that lands in the finished work that I am not confident in making correctly, for any reason."

Tallies: Kind — DEFINED 43, UNDEFINED 11. Cause — A 20, B 13, C 11, D 4, E 6. Impact — high 8, medium 27, low 19.

By theme (analyst's grouping):
- Platform/tooling facts (11): JC-03, 06, 10, 13, 17, 20, 32, 44, 45, 52, 54.
- Git semantics (7): JC-12, 15, 22, 23, 24, 37, 41.
- Owner channel and verbs (7): JC-07, 26, 27, 38, 42, 50, 51.
- Money rules (7): JC-18, 19, 29, 33, 35, 36, 48.
- Layout, structure, docs, taste (6): JC-01, 02, 11, 25, 40, 49.
- Steps, prose, prompt assembly (4): JC-04, 05, 28, 43.
- Config surface and lint (3): JC-08, 09, 39.
- Mechanical checks and suite handling (3): JC-46, 47, 53.
- Limits and turn counting (2): JC-14, 16.
- Findings/result semantics (2): JC-30, 31.
- Skips, overrides and defaults (2): JC-21, 34.

Ten most consequential (the eight rated `high`, then two `medium`):
1. JC-54 — hook wiring (`UserPromptSubmit`/`SessionStart`, `$CLAUDE_PROJECT_DIR`, stdin fields).
2. JC-07 — OWNER.log is JSONL; a quote verifies as a normalized substring of an entry logged after the current pause began.
3. JC-13 — claim = `--force-with-lease=refs/heads/round/NNNN:` expecting absence, 3 id retries.
4. JC-10 — two committed agent definitions per rung, roster-hash stamped; stale refuses `start`.
5. JC-12 — a git remote is required; tests use a bare local remote.
6. JC-21 — one fixed mechanical skip effect per overridden step.
7. JC-27 — a single `continue` verb resumes five pause kinds and resets the limit that fired.
8. JC-01 — repo layout: `spec.yaml`/`SPEC.md` above `harness/`.
9. JC-08 — unknown config keys refuse `start` rather than warn.
10. JC-35 — work and gate shares each sum to 1 over their own pool (±0.001).

## 12. Traceability

- Mapping: SPEC.md §5.7 "Where each owner-listed architecture feature lives" — a 17-row table from the owner's SPEC.md features to component numbers and modules. Each component file adds "Covered by" and "Depends on / Depended on by"; each JC carries *Affects:*. No per-requirement table quoting owner sentences by id.
- Inconsistencies flagged in the owner's files (all in `JUDGMENT-CALLS.md`):
  - JC-09: `project.yaml` mentions "the spec's testPaths" and a "prompt-size warning" without defining keys — hence the five defaults.
  - JC-04: the step table lists `CHAT-TO-PLAN: 0` like gated steps and its prose mentions "the gate that judges you", yet no gate prose exists. JC-05: SPEC.md requires a conflict attempt but no prose exists for it. JC-06: COMMON-STEP-END "is produced at the end of every step", reading like a separate message.
  - JC-08: "robust to arbitrary changes" pulls against "each [setting] is used for something".
  - JC-14, JC-16: "turns (rejections) per gate" and "turns" undefined; JC-15: the `maxRoundAttempts` comment fits three readings.
  - JC-18: the `postMortemFileCostPerToken` comment fits two readings; JC-29: `lostValuePerHour` "for context" vs "Costs, dollars, estimated, not real"; JC-35: "sum to 1" vs "a gate that is off does not incur a charge"; JC-36: `remaining` "can become stale".
  - JC-26: "STATE.json — the runner's only state" vs the plan being "what the owner approved" including answers.
  - JC-27: verbs listed only for plan approval; nothing says how the owner resumes after NEEDS-OWNER or a limit. JC-21: "override … the runner skips them" gives no consequences.
  - JC-43: AGENTS.md's rule makes anything read from a pointed-to file an UNDEFINED judgment call, arguing for inlining every artifact against prompt size.
  - JC-01: `spec.yaml` above `harness/` "may only be how the notes were laid out". JC-30: "every finding carries a suggestion" implies a FAIL always has findings.
  - Doctor (11) also reports rungs ranked above `maxAgent` as "unreachable ceiling" and `steps` values of 1 for gateless steps as "no effect".

## 13. Gaps against the brief

Shortfalls:
- Function signatures: many parameters untyped (`cfg`, `roster`, `kind`, `now`, `args`), e.g. `advance.validate_agents_plan(plan: dict, cfg, roster, overrides)`, `state.set_pause(state, kind, step, detail, log_index, now)`, `index.generate(paths: Paths, cfg)`; `output.py` lists `status_text(...)` with an ellipsis and `record_text`, `doctor_text`, `drift_text` untyped; `cli.py` has a command table but no per-command handler signatures. Errors are listed per component, not per function.
- Classes: `State`'s nested dataclasses are defined only as "mirroring S1 exactly"; `RoundPaths` "mirroring the YAML"; `doctor.Report`, `ledger.LivingChange`, `NextAction`, `RecordOutcome`, `Behavior` have no field list beyond S16/S17 or an inline tuple.
- Source files: `src/shackles/__init__.py` (implied by `packages=["shackles"]`) and any `tests/__init__.py` are never mentioned; the five probe fixture directories name no files beyond `PLANT.json`.
- Tests: about 380 cases are named, but explicit assertions appear only for a minority (the guard, `test_config`, `test_no_force_push_anywhere`, `test_committed_*_current`, `test_docs`, the flow paths); most unit files leave the assertion implied by the name.
- Other files: no lint/format/type tooling, Makefile or scripts; `ARCHITECTURE.md` §2 cites a "no load-bearing file" rule defined nowhere else in the draft.
- Internal inconsistencies: SPEC.md §4 says `{04, 05, 06, 07, 08, 09} → 04 (config/paths) only` and "No module imports `cli.py`, `round_*.py` or `doctor.py`", but `08-state-results-findings.md` depends on 05, `09-money.md` on 07 and 08, and `11-doctor-index.md` says 10 (`advance.end`, `round_start.preflight`) calls `index.regenerate` and `doctor.checks_for_start` while 10's "Depends on" omits 11. `mechanical.check_attempt` is declared with three arguments (`rctx, attempt, spec`) but called with two in `round_record.record` step 2.

Drift into line-by-line implementation:
- Literal file contents for `.gitignore`, `pyproject.toml`, `.claude/settings.json` (01, 02) and the exact S13 `tools:` list.
- Exact git invocations: `--force-with-lease=refs/heads/round/<id>:`, `merge-tree --write-tree --merge-base=<base>`, `read-tree -u --reset`, `-M --find-renames=50%` (07).
- Regexes for `tokens.count_test_functions` (`^\s*(async\s+)?def\s+test_\w*\s*\(`, `^\s*(it|test)\s*\(`) and the exact `jc_command` string (08, 09).
- Procedural algorithms: `round_record.record` as six ordered steps, `landing.land` and `sync` as numbered loops, `next_action` as a five-rule list (10); `state.save` atomicity; `ownerlog.append` via `fcntl.flock`.
- Magic numbers fixed in prose: `verify.run` "last 200 lines", `render` depth 20, 3 claim retries, `max_steps=60`, probe `max_attempts` 6, 4-decimal rounding, ±0.001 share tolerance.
