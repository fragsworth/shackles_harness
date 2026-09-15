# Profile: draft 4

## 1. Format and size

- 13 Markdown files, 199,448 bytes: `SPEC.md` 21,351 B; `JUDGMENT-CALLS.md` 30,687 B; `components/00-contracts.md` … `10-tests.md` (11 files, 147,410 B; largest `10-tests.md` 35,722 B, smallest `01-root-and-tooling.md` 4,124 B).
- Entry point `SPEC.md`, "the top-level map … written top-down": §1 What the harness is (§1.1 requirements table, §1.2 robustness "five ways"), §2 Architecture in one page, §3 Folder structure, §4 Component index (§4.1 dependency direction), §5 Cross-cutting rules, §6 Glossary, §7 Reading order.
- Components: 00 contracts · 01 root and tooling · 02 runner CLI · 03 spec files and config · 04 steps, prose, plumbing, prompts, agent definitions · 05 round state and records · 06 git, checks, suite, landing · 07 money and limits · 08 doctor, invoke, hook · 09 docs · 10 tests. Per source file each states "what it **owns**, what it **depends on**, what **depends on it**, its classes and functions (name, parameters with types, return type, one-line purpose, errors raised)" (SPEC.md §4).
- Judgment calls cited inline as `(JC-nn)`: 42 of 80 ids appear in component files (00:1, 01:5, 02:2, 03:2, 04:7, 05:8, 06:7, 07:5, 08:4, 09:0, 10:1); the other 38 appear only in `JUDGMENT-CALLS.md`, where every entry names its spec section (e.g. "05 §5.7"). `SPEC.md` cites no numeric id.
- Reading order (SPEC.md §7): [00 contracts] → [03 config] → [04 steps & prose] → [05 state] → [06 git] → [07 money] → [02 commands] → [08 doctor] → [01 tooling] → [09 docs] → [10 tests].

## 2. Language, runtime, packaging, tooling

- Python `requires-python >= 3.11` (CI installs 3.12); package `shackles` 0.1.0, src layout, manifest `harness/pyproject.toml` (01 §1.1; JC-09: "`run.py` is named by the owner, so Python is given"). Dependencies `PyYAML >= 6` only; optional group `test`: `pytest >= 8`. setuptools packages `shackles`, `shackles.commands`, `shackles.plumbing`; package data `plumbing/templates/*.txt`. pytest: `testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = "-q -m 'not live' -p no:cacheprovider"`, marker `live`. No build step: `run.py._bootstrap_sys_path()` (02 §2.1).
- Lint / format / type tools: not specified.
- CI: `.github/workflows/harness.yml` at the repository root (01 §1.6, JC-12): push + pull request, `ubuntu-latest`, `fetch-depth: 0`, Python 3.12, `pip install -e "harness[test]"`, runs `harness/scripts/check.sh`; "Live probes never run in CI."
- Scripts: `harness/scripts/check.sh` = `python src/run.py doctor --check --offline` then `python -m pytest`; "No other scripts exist" (01 §1.5).
- Generated: `.claude/agents/shackles-<rung>.md` and `shackles-<rung>-gate.md` (by `agentdefs.py`, committed, freshness-tested; JC-75); `harness/local.yaml` (gitignored, "no user input"); `harness/spec.baseline.json` (written by `accept-spec`, committed); `harness/OWNER.log` (hook-written, gitignored).
- `.gitignore` (01 §1.2): `/OWNER.log`, `/local.yaml`, `/.worktrees/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `/.claude/settings.local.json`. Environment variables: `SHACKLES_LIVE=1`, `SHACKLES_INVOKER=stub`, `SHACKLES_STUB_SCRIPT` (08 §8.2), `$CLAUDE_PROJECT_DIR` (01 §1.3).

## 3. Repository layout

From SPEC.md §3 (paths relative to the git repository root):

```
<repo root>/
  spec.yaml, SPEC.md                                             (owner)
  .github/workflows/harness.yml                                  CI                          → [01]
  harness/                                                       harness root; driver cwd (JC-70)
    AGENTS.md  project.yaml  subAgents.yaml  locked_prose/*.txt  (owner)
    INDEX.md  README.md                                          uncharged; CLEANUP-only edits → [09]
    pyproject.toml  .gitignore  spec.baseline.json                                           → [01],[03]
    local.yaml (gen, ignored)  OWNER.log (ignored)  .worktrees/round-NNNN/ (ignored)         → [03],[08],[06]
    .claude/settings.json (hook);  .claude/agents/shackles-<rung>[-gate].md (gen, committed) → [01],[04]
    scripts/check.sh                                                                         → [01]
    src/run.py  src/hooks/owner_log.py  src/shackles/{commands/, plumbing/templates/, *.py}  → [02]..[08]
    docs/PROCESS.md ARCHITECTURE.md FORMATS.md TODO.md CLARIFICATIONS.md      (living)       → [09]
    tests/conftest.py support/ fixtures/ test_*.py probes/                    (living)       → [10]
    archives/rounds/.gitkeep;  archives/rounds/NNNN/ appears after landing/abandon
```

- Harness code: `harness/src/shackles/` plus `src/run.py` and `src/hooks/owner_log.py` (imports nothing from the package). Rounds: the round folder `archives/rounds/NNNN/` (names from `project.yaml` `roundPaths`) lives on branch `shackles/round-NNNN`, checked out as worktree `harness/.worktrees/round-NNNN/` (JC-10), and reaches `main` at landing or abandon as "the permanent record". Living paths `src/`, `docs/`, `tests/` (`livingSourcePaths`); everything else under `harness/` is uncharged and not agent-editable except `INDEX.md`/`README.md` at CLEANUP (JC-13). Owner files: `spec.yaml`, `SPEC.md` at the repo root; `AGENTS.md`, `project.yaml`, `subAgents.yaml`, `locked_prose/*` under `harness/` — "not part of this recreation".

## 4. Actors and roles

(SPEC.md §1–§2 "Roles"; 08; 10)
- **Owner** — a human; "only the driver speaks to them"; words reach the runner only as `--quote` text verified against `OWNER.log`.
- **Driver** — top-level Claude Code agent, cwd `harness/`; interprets owner words, runs `run.py`, spawns sub-agents via the Agent tool, passes prompts/messages verbatim; edits living files only as the CHAT-TO-PLAN producer of `PLAN.json`.
- **Runner** — `harness/src/run.py`: "the only thing that commits, pushes, moves files between suite and archive, and computes money".
- **Producer** — fresh read-write sub-agent `shackles-<rung>` doing one step in the round worktree within declared paths plus the round folder.
- **Gate** — read-only sub-agent `shackles-<rung>-gate` (tools `Read, Grep, Glob`) judging one artifact; reads `FINDINGS/`, never `RESULTS/` (JC-80).
- **Conflict attempt** — producer-kind attempt `LANDING-n` editing only the conflicted files of a landing/sync merge (06 §6.4).
- **Helper** — agent a producer spawns via `run.py spawn`, run headless by `invoke.CliInvoker`, capped by `maxSimultaneousSubAgentsPerRound` lock-file slots, billed measured (08 §8.2; JC-62, JC-64).
- **Prompt hook** — `src/hooks/owner_log.py`, `UserPromptSubmit`, one JSON line per owner prompt; never exits non-zero (JC-63).
- **Probe agent** — real agent at rung `systemTestAgent`, run by `tests/probes/` on real prose with planted defects (10 §10.6).
- **CI** — runs `doctor --check --offline` and the non-live suite (01 §1.6).

## 5. Architecture: the main mechanisms

a. **Step table** — `steps.py`: `STEPS`, eleven frozen `Step` dataclasses (name, kind `driver|producer|checkpoint|landing|cleanup`, has_gate, prose stems, artifacts, `writes`/`inputs`/`checks` symbols, share_source, overridable). `lint()` compares it with `project.yaml` `steps` at doctor and start; `consumers()` lists what to revisit on change. The table is code; the owner's map is only linted against it.

b. **Round lifecycle / state** — `state.py` `RoundState` over `STATE.json` ("the runner's only state") in the round folder inside the worktree; statuses `planning → awaiting-owner → running → paused → done|abandoned`; cursor `{step, phase}`; eight pause kinds (`checkpoint, needs-owner, blocked, limit, mechanical, hard-stop, drift, sync`). Ledger, questions, findings, flags and decisions all live inside it (JC-03); atomic write, fence push after every change, unknown keys preserved; active round found by scanning `.worktrees/` (JC-35). Transitions run in `commands/next_.py::advance` and the fixed 13-item `record` sequence (JC-16).

c. **Prompt assembly** — `prose.py`: generic `{{ ns.KEY }}` engine (namespaces `prose, project, round, plumbing, agents`), recursive `prose.*` includes with cycle/depth errors, unknown tokens left verbatim and listed, `AGENTS.md` split on `## ` headings. `plumbing/builder.py` + nine `string.Template` files generate `PROCESS-INSTRUCTIONS`, `GATE-PROSE` and driver-facing texts. `prompts.py`: prose → render → append `COMMON-STEP-END` (JC-31) → `PROMPTS/<attempt>.txt`; tokens `ceil(bytes/tokenBytes)`, warn above `promptSizeWarnTokens`; `render_offline` for doctor. "Nothing in code decides behaviour from the wording of locked prose."

d. **Owner channel** — hook → `harness/OWNER.log`. `ownerlog.py`: `require_log` at start, `verify_quote` = whitespace-normalised substring over prompts since the round's `slice_from` (JC-40, JC-79), `write_slice` into the round folder. `decisions.py`: nine kinds `approve, delegate, delegate-through, override, answer, abandon, revise, resume, raise-limit` (JC-42) via `owner --decision KIND --quote TEXT`; "the runner classifies nothing". Global question ids (JC-06); flags delivered at the next pause; driver summaries `PROMPTS/PAUSE-k.txt`, `CHECKPOINT-i-n.txt` (JC-01).

e. **Git model** — `gitops.py` `Git` is the only module running git. Claim: `push --force-with-lease=refs/heads/<branch>:` (empty lease), retried with the next id up to 3×; remote required (JC-43). Fence: lease push after every state change; rejection → `FenceError`, exit 3. One worktree per round; sequential attempts; every attempt's uncommitted diff is committed at record, accepted or not (JC-72). `landing.land`: fetch, hard-stop projection (JC-45), `merge --no-ff --no-edit` main into the branch; conflict → automerge snapshot ref `refs/shackles/automerge/<branch>` (JC-44) + conflict attempt on the conflicted files; then `fast_forward_main` (lease push `branch:main`, retried up to `SYNC_BOUND = 3`, JC-49) and `update_driver_checkout` (`pull --ff-only`). Post-landing commits reach main via bounded `landing.sync` (conflicts reuse `LANDING-n`, JC-47); `abandon` = record-only landing (JC-48); semantic conflict after a clean merge → pause `mechanical` (JC-46).

f. **Results / verdicts / findings** — `messages.py`: one JSON object (one fenced block tolerated, JC-36); producer `DONE|NEEDS-OWNER|BLOCKED`, gate `PASS|FAIL` (JC-04); invalid → `INVALID`, a mechanical rejection retried without a gate turn (JC-77). `findings.py::accept_gate_message`: rulings on `disputed` findings (upheld → count+1, `settled` at 2; missing ruling = upheld, JC-39); repeats of withdrawn findings dropped by normalised quote/identical text; "verdict wins" (PASS → open findings become `note`; FAIL → open/settled blocking). `FINDINGS/<STEP>-<n>.json` keyed by the judged producer attempt (JC-02); `check_resolutions` requires `fixed`/`disputed` per open finding after a FAIL, settled cannot be disputed. States `open, fixed, disputed, withdrawn, settled, note`. `judgment.py` appends `- [<attempt>] <text>` lines.

g. **Money** — `charges.py` (pure): `estimate_tokens = ceil(bytes/tokenBytes)`, `file_price` with cap, `living_charge` per file (new = base + price; removed = refund; changed/renamed = delta; carry files at `postMortemFileCostPerToken`, no base/cap, JC-53; tests ± `testBaseCost` by bare name), `archive_charges` (frozen), `usage_usd`, `estimate_usage` (`total = input/(1−f)`, JC-54), spawn floor. `ledger.py`: attempts by precedence `--usage-json` → `--tokens` → estimate (JC-59), `driverUsdPerStep` once per step (JC-58), helpers measured, `book_round_end` at CLEANUP or abandon (`living` only if landed, `archive`, `carry`), `project_spent` from `archives/rounds/*/STATE.json` (JC-78), `lostValuePerHour` shown never booked (JC-55). `budget.py`: shares from `defaultShares` or `AGENTS-PLAN.json`, `share × quote` per attempt incl. retries, `rung_for` within `maxAgent`. `limits.py`: `maxTurnsPerRun`, `maxRunWallClockHours` (active time, JC-56), individual cap, `hardStopBudgetMultiple × quote`, `maxTurnsPerGate` incl. mechanical rejections (JC-57), `maxRoundAttempts` restarts (JC-34), `raise-limit` overrides; post-landing steps never stop for money.

h. **Checks** — `checks.py::run_for_attempt` on `status_porcelain`: `declared_paths` expands `writes` symbols (`<round> <living> <testPaths> <living minus testPaths> <carry-files> <root-docs> <conflicts>`) ∩ living paths; `path_policy` reverts strays — "reverted and reported, never a reason to reject". `CHECKS`: `artifact-*` (5), `non-goals-carried` (advisory), `tests-collect`, `new-tests-exist`, `verify-suite` (`pytest <testPaths> -m "not live"`, `verifyTimeoutSeconds`), `suite-consistent`, `conflict-only`, `no-markers`; `run_pytest` is the single spawn point. `suite.py`: a test = `test*` function at module level or in a `Test*` class, found by `ast` (JC-52); archived tests moved to `tests-archive/` by `git mv` with the attempt.

i. **Doctor / lint / index** — `doctor.py::run_all`: 16 named checks with severities (`spec-files, config, roster, step-table, prose-files, render, agents-md, plumbing-templates, agent-defs, hook, owner-log, baseline, git, python-and-deps, archives, worktrees`); renders every step × kind offline; reports unresolved tokens, unknown steps, defaulted keys (notes), unused keys (errors), unused prose, stale agent defs; regenerates `local.yaml` and agent defs only when error-free and not `--check`. `INDEX.md` is not generated: hand-maintained by CLEANUP, checked by `test_docs_consistency.py`.

j. **Robustness to spec-file edits** (SPEC.md §1.2): (1) one reader per file — `config.py` with registries `PROJECT_KEYS`/`SUBAGENTS_KEYS` (unregistered key = "unused setting" error, JC-21), `prose.py`, `specfiles.py`; (2) explicit defaults, only `testPaths` and `promptSizeWarnTokens` (JC-18, JC-19), listed by doctor; (3) drift first-class — sha256 baseline, `test_spec_drift.py` shows a `git show` diff, `start` refuses, `next`/`record` pause `drift`, `accept-spec`; (4) step table code-linted; (5) mechanics tests use a generated spec, never real prose (JC-65). Also `roundPaths` resolved only via `paths.RoundPaths`; `STATE.json` keeps unknown keys; the judgment tool and `spawn` run through the driver checkout's `run.py` (JC-27).

## 6. Module inventory

42 Python modules named (1 entry, 1 hook, 2 `__init__`, 10 commands, 28 package modules) plus 9 template text files.
- `src/run.py` — CLI: `main`, `build_parser`, `dispatch`, `emit`/`render_human`, `_bootstrap_sys_path`.
- `src/hooks/owner_log.py` — hook: `main`, `harness_root`, `append_line`; stdlib only.
- `shackles/__init__.py` — listed; content not specified.
- `shackles/errors.py` — `HarnessError` + `UsageError`(4), `RefusedError`(2) with children `ConfigError, StepTableError, ProseError, DriftError, OwnerLogError, QuoteNotFoundError, StateError, MessageError, ArtifactError, DecisionError, LimitError, GitError, SpawnError`, `FenceError`(3).
- `shackles/commands/__init__.py` — `Session` (roots, config, roster, lazy round/git, clock; `open`, `require_round`, `require_no_round`, `fence`), `COMMANDS`.
- `commands/doctor.py, start.py, next_.py, record.py, owner.py, status.py, judgment.py, spawn.py, spec_drift.py, accept_spec.py` — one thin module per command (`add_arguments`, `run`).
- `paths.py` — `Roots`, `RoundPaths`, `pad_round_id`, `is_under`.
- `specfiles.py` — spec-file list, hashing, `Baseline`, `Drift`, `drift`, `drift_diff`, `accept`, `is_spec_file`.
- `config.py` — `Key`, `PROJECT_KEYS`, `SUBAGENTS_KEYS`, `Config`, `Rung`, `AgentRoster`.
- `localcfg.py` — `EnvProbes`, `LocalConfig`, `generate`, `ensure`.
- `steps.py` — `Step`, `STEPS`, lookups, `lint`, `consumers`.
- `prose.py` — `ProseSet`, `Context`, `Rendered`, `render`, `find_tokens`, `references`, `gates_text`.
- `plumbing/builder.py` — `AttemptView`, `process_instructions`, `gate_prose`, `checkpoint_summary`, `pause_summary`, `template`; templates `producer, gate, driver, conflict, checkpoint, pause, cleanup, gate-absent, gate-off`.
- `prompts.py` — `round_values`, `project_values`, `build_context`, `open_attempt`, `resolve_inputs`, `render_offline`, `synthetic_round`.
- `agentdefs.py` — `FRONTMATTER_KEYS`, `producer_definition`, `gate_definition`, `write_all`, `check`, `agent_name`.
- `state.py` — `RoundState` (load/save, attempts, cursor, pauses, questions, flags, end_round), `find_active_round`; records `AttemptRecord, QuestionRecord, DecisionRecord, LedgerEntry, FindingRecord`.
- `history.py` — `Entry`, `append`, constructors, `read_entries`.
- `messages.py` — `ProducerMessage`, `GateMessage`, `parse_text`, `parse_file`.
- `artifacts.py` — `validate_plan/agents_plan/spec/suite/postmortem`, `read_json`.
- `findings.py` — `accept_gate_message` → `GateOutcome`, `check_resolutions` → `ResolutionOutcome`, `open_findings`, findings-file I/O.
- `judgment.py` — `init_files`, `append_line`, `append_from_message`, `read`, `counts`.
- `ownerlog.py` — `Entry`, `read`, `require_log`, `verify_quote`, `slice`, `write_slice`, `previous_round_end`.
- `decisions.py` — `KINDS`, `apply` → `Applied`, `checkpoint_skipped`, `is_overridden`.
- `gitops.py` — `Git`: claim/unclaim, fence, worktrees, status/diff/revert/commit, tree reads, merge/automerge/conclude/abort, `fast_forward_main`, `update_driver_checkout`, `restore_paths_from`, `probes`; types `Claim`, `Change`, `MergeResult`.
- `checks.py` — `CheckReport`, `declared_paths`, `path_policy`, `run_for_attempt`, `CHECKS`, `run_pytest`.
- `suite.py` — `TestRef`, enumeration by `ast`, `new_tests`, `plan_moves`, `apply_moves`, `stats`.
- `landing.py` — `land`, `finish_landing`, `sync`, `abandon`, `remove_round_worktree`, `SYNC_BOUND`.
- `charges.py` — `Prices`, `estimate_tokens`, `file_price`, `FileDelta`, `ChargeBreakdown`, `living_charge`, `archive_charges`, `usage_usd`, `estimate_usage`, `apply_spawn_floor`.
- `ledger.py` — `book_attempt`, `book_driver_step`, `book_helper`, `book_round_end`, totals, `project_spent`, `project_remaining`, `elapsed_context_usd`.
- `budget.py` — `share_for`, `attempt_budget_usd`, `rung_for`, `helpers_for`, `individual_cap_usd`.
- `limits.py` — `effective`, `before_attempt`, `after_record`, `rejections_exhausted`, `restarts_exhausted`, `Pause`.
- `doctor.py` — `Report`, `Finding`, `run_all`, `regenerate`.
- `invoke.py` — `Invoker` (Protocol), `InvokeResult`, `CliInvoker` (`CLI_ARGS`), `StubInvoker`, `acquire_slot`, `invoke_for_spawn`, `invoker_from_env`.

Classes: 38 distinct `class` declarations across source and test support (test-side `FakeHarness, Sayer, Runner, Behavior, StubAgent, OwnerScript, Trace`), 28 of them `@dataclass`. `plumbing/__init__.py` is implied by `pyproject.toml` but never named. Dependency direction (SPEC.md §4.1, acyclic): `run.py → commands/* → {landing, checks, suite, ledger, limits, findings, decisions, prompts, doctor, invoke} → {gitops, state, history, messages, artifacts, judgment, ownerlog, charges, budget, plumbing, prose, steps, agentdefs} → {config, specfiles, localcfg, paths, errors}`.

## 7. Data contracts

All in `components/00-contracts.md`, each with one owning module; `docs/FORMATS.md` is "the agent-facing copy".
- CLI convention (§0.1) — one JSON object on stdout (`{"ok": true, …}` / `{"ok": false, "error": {code, message, detail}}`), `--human`, exit codes 0 ok / 1 unexpected / 2 refused / 3 fence broken / 4 usage.
- Error taxonomy (§0.2) — `HarnessError(code, message, detail, exit_code)`, kebab-case codes.
- Identifiers (§0.3) — round id padded to the `N` run in `roundPaths.folder`; branch `shackles/round-<id>`; attempts `<STEP>-<n>` / `<STEP>-GATE-<n>`; findings `F-<STEP>-<k>`; global integer question ids; ledger `L-<k>`.
- Round folder (§0.4, `paths.RoundPaths`) — `archives/rounds/NNNN/`: `PLAN.json, AGENTS-PLAN.json, SPEC.json, SPEC.md, SUITE.json, POSTMORTEM.md, STATE.json, HISTORY.md, OWNER.log, PROMPTS/, RESULTS/, FINDINGS/, tests-archive/, DEFINED_/UNDEFINED_JUDGMENT_CALLS.md` plus runner-only `PROMPTS/PAUSE-<k>.txt`, `PROMPTS/CHECKPOINT-<i>-<n>.txt` (JC-01). On the round branch; on main after landing/abandon.
- `STATE.json` (§0.5, `state.py`) — full shape: `schema, round{id, folder, branch, base_commit, created_at, approved_at, ended_at, worktree}, status, pause, mode, overrides, limit_overrides, cursor, open_attempt, attempts[], counters, plan, questions[], agents_plan, findings[], flags, decisions[], ledger{entries[], total_usd}, landing, suite_moves[], fence, owner_log{slice_from}`; atomic write; unknown keys preserved.
- Final messages (§0.6, `messages.py`) — producer `{status, summary, questions[], narrow, flags[], resolutions[], judgment_calls[]}`; gate `{status, summary, rulings[], findings[], flags[], judgment_calls[]}`; saved unchanged to `RESULTS/<attempt>.json`.
- Artifacts (§0.7, `artifacts.py`; fields invented, JC-05) — `PLAN.json` (`text, scope, validation_steps, non_goals, assumptions, quote_usd, refactor_fraction, todos_accepted, questions`), `AGENTS-PLAN.json` (`steps{agent, share, helpers, expected_retries}, gates{}, notes`), `SPEC.json` (`summary, components, implementation_steps, test_plan, non_goals, refactors, validation_steps`), `SUITE.json` (`tests[{file, name, decision, reason}], middle_ground_flags`), `POSTMORTEM.md` (first heading `Summary`), judgment-call files (`- [<attempt id>] <text>` under a runner-written header).
- `FINDINGS/<STEP>-<n>.json` (§0.8, `findings.py`) — `step, judges, gate_attempt, verdict, summary, findings[], dropped[], rulings[], resolutions_seen[], mechanical[], inputs`; what the next gate and producer read.
- `HISTORY.md` (§0.9, `history.py`) — append-only `## <ts> ATTEMPT|OWNER|RUNNER|ROUND …` entries; final messages embedded as fenced `json`.
- `OWNER.log` (§0.10) — JSON lines `{ts, session, cwd, prompt}` at `harness/OWNER.log`; the round's slice in the round folder.
- `spec.baseline.json` (§0.11, `specfiles.py`) — `{schema, files{path: "sha256:…"}, accepted_commit, accepted_at, accepted_by: owner-quote|by-owner-flag|bootstrap, note}` at `harness/`.
- `next` outputs (§0.12) — kinds `none, driver, producer, gate, checkpoint, owner, done`, per-kind keys, absolute paths.
- `local.yaml` (§0.13, `localcfg.py`) — `generatedAt, harnessRoot, repoRoot, specYaml, git{}, python{}, claude{}, agentDefinitions, specBaseline{}, effectiveConfig, defaultedKeys, ownerLog{}`; readers may use only `git.*` and `claude.command` (JC-08).
- Rendered prompts (§0.14) — `PROMPTS/<attempt>.txt`, plumbing tokens replaced, `COMMON-STEP-END` last, handed verbatim. Agent definitions (04 §4.5): frontmatter `name, description, model, effort` (+ `tools: Read, Grep, Glob` for gates). Plumbing templates (04 §4.3): `${name}` placeholders, specified by required sections, "not its wording".

## 8. Testing

- Three layers (10 intro). (1) Mechanics tests against a *generated* harness in a temp dir: `tests/support/fakespec.py::generate` writes, from `steps.STEPS` and the key registry, `spec.yaml`, `SPEC.md`, `AGENTS.md` (three headings), `project.yaml` with every registered key at small values (`tokenBytes 4`, `maxTurnsPerGate 3`, `maxRoundAttempts 2`…), `subAgents.yaml` (rungs `max, high, medium, low`), one-line `locked_prose/<STEP>-OVERVIEW.txt`/`<STEP>-GATE.txt` carrying every token the real files use (no `CHAT-TO-PLAN-GATE.txt`, "like the real tree"), plus a skeleton: a *copy* of the real `src/` (JC-66), one-line docs, `tests/test_smoke.py`, `pyproject.toml`, generated agent defs, an accepted baseline. `fakegit.py`: real repo with a bare `origin.git`; `commit_on_main_elsewhere`, `move_remote_branch` simulate another contributor/runner. `ownerlog_writer.py::Sayer.say` seeds hook-format lines and returns the `--quote` text; `run_hook` runs the real hook. `cli.py::Runner` calls `run.main` in-process. `stub_agent.py::StubAgent` scripts a `Behavior` per attempt id → step → kind (message, artifact, edits, strays, judgment calls, raw result, tokens/usage) with per-step defaults. `artifacts_samples.py` builders. `stub_driver.py::drive` runs the full `next`/`record`/`owner` loop under an `OwnerScript`, returning a `Trace`. (2) Guard tests on the real tree: `test_spec_drift.py`, `test_agentdefs.py::test_committed_definitions_are_fresh`, `test_config_surface.py`, `test_docs_consistency.py` — "the only tests that open files of the real harness other than the code itself" (JC-65). (3) Live probes.
- Fixtures: `clock, fake, runner, stub, owner, started, approved, real_roots` (§10.1); files under `tests/fixtures/` (`messages/` incl. `fenced_json.txt`, `two_objects.txt`; `findings/prior_findings.json`; `owner_log/sample.jsonl` with one malformed line; `hook/payload.json`; `automerge/conflicted.py`) (§10.3).
- Counts: 39 `test_*.py` files with 488 distinct named cases; 8 probe files plus `probes/conftest.py`; 7 support modules; `tests/conftest.py`.
- Split (by file; the only marker is `live`): 23 unit-level module files (`test_paths` … `test_invoke`); 4 real-git files (`test_gitops`, `test_checks`, `test_landing`, `test_suite_moves`); 8 command files (`test_cli`, `test_cmd_doctor/start/spawn/status/accept_spec/spec_drift/judgment`) plus the stub-driven end-to-end `test_round_flow.py` (30 scenarios); 4 real-tree guards; 8 probes.
- Live probes (§10.6): skipped unless `SHACKLES_LIVE=1` and the `claude` command exists; `live_harness` = "a *copy of the real harness* (real prose, real config)" with git, bare remote, owner log; `probe_invoker` = `CliInvoker` at `systemTestAgent`; `run_gate`/`run_producer` render the real prompt with a synthetic round, invoke, parse. Planted defects: an ambiguous spec sentence, a function outside the spec, an uncovered component, an imbalanced/absurd agents plan, a disputed prior finding then a re-raised withdrawn one, a postmortem missing its trace, a contradicting doc → `UNDEFINED` call, a producer message that parses. Cost printed at session end; never in CI.
- Assertions: mostly encoded in case names (`test_fence_push_rejected_when_remote_moved`); explicit detail for a minority (`test_spec_files_match_baseline` "the failing test *shows the diff*"; `test_happy_path_gates_off_checkpoints_on` lists the exact kinds sequence, ledger kinds, worktree removal, remote branch retention). Probes assert "on structure and on quoted text, never on wording" (JC-68). `test_step_names_unique_and_order_fixed` writes the eleven names a second time on purpose (JC-69); the sync-exhaustion test prefers a monkeypatched `fast_forward_main` (JC-67); timeouts use tiny values (`verifyTimeoutSeconds: 1`).

## 9. Docs

(`components/09-docs.md`: "when they disagree, the code is right and the document is fixed")
- `harness/INDEX.md` — routing: one grep-friendly line per file/dir/module/command/doc/support file (`path — purpose (owner component)`), three routing hints, no prose; CLEANUP-only edits.
- `harness/README.md` — what it is, prerequisites, setup (`pip install -e ".[test]"`, `doctor`, open Claude Code in `harness/`, type one message so `OWNER.log` exists), a round in brief, commands, testing, accepting spec changes, where the record is.
- `docs/PROCESS.md` — the rules in 14 required sections: roles, step table, driver loop, owner decisions, final messages, judgment calls, findings, mechanical checks and strays, pauses and limits, landing/sync/abandon, money, spec drift, self-hosting hazard, changing the step table.
- `docs/ARCHITECTURE.md` — the one-page diagram, module map (owns/depends/depended-on), dependency rule, data flow of one attempt, git model, testing strategy, invariants.
- `docs/FORMATS.md` — the [00] contracts under fixed headings (`## PLAN.json` … `## spec.baseline.json`) that prompts name and `test_docs_consistency.py` asserts.
- `docs/TODO.md` — carry-forward file edited by POSTMORTEM; seeded with upstream mechanics, owner attention pricing placeholders, measured Agent-tool usage.
- `docs/CLARIFICATIONS.md` — carry-forward file for owner-only questions; seeded with the entry template only.

## 10. Notable or unusual decisions

- Self-hosting: living paths are the harness's own `src/`, `docs/`, `tests/`, so "producers edit the runner's code in rounds" (JC-71); mitigated by invoking the judgment tool and `spawn` through the driver checkout's `run.py --root <worktree>` (JC-27) and a PROCESS.md "self-hosting hazard" section.
- The driver is a chat-session agent with cwd `harness/`; the runner is a Python CLI; step sub-agents come from the Agent tool via generated per-rung definitions, while helpers and probes use a headless `claude` CLI (`CliInvoker`; JC-61, JC-64).
- `STATE.json` is the only runner state and also holds the ledger, questions, findings, flags and decisions (JC-03).
- The round is claimed by CAS push at `start`, before planning; plan, questions and approval happen inside the round (JC-74); the driver itself is the CHAT-TO-PLAN producer.
- LANDING runs inside `next` (JC-17); POSTMORTEM/CLEANUP commit after landing and merge back through a bounded sync, `SYNC_BOUND = 3` (JC-49); `abandon` still lands the record (JC-48).
- Every command prints exactly one JSON object, `--human` opt-in, exit code 3 reserved for a broken fence (JC-07).
- Only two defaulted keys (`testPaths`, `promptSizeWarnTokens`); any unregistered key is an error, so uncommenting an owner placeholder refuses starts (JC-18, JC-19, JC-21).
- `accept-spec` is a runner command needing an owner quote or `--by-owner` and commits directly on main (JC-15); CI exists though the owner never asked (JC-12).
- Agent definitions are committed with a freshness test rather than gitignored (JC-75); `INDEX.md`/`README.md` sit outside living paths, CLEANUP-only (JC-13).
- Gates have only `PASS|FAIL` (JC-04); a missing ruling on a disputed finding counts as upheld (JC-39); mechanical rejections skip the gate (JC-77) yet count toward `maxTurnsPerGate` (JC-57).
- Worktrees nest inside the repo at `harness/.worktrees/` (JC-10); one worktree per round with rejected attempts' edits kept as the retry base (JC-72).
- `maxRunWallClockHours` counts active time only (JC-56); `lostValuePerHour` is shown, never booked (JC-55); carry-forward files are code constants priced at the postmortem rate whenever they change (JC-25, JC-53).

## 11. Judgment calls

**Total: 80** (`JC-01` … `JC-80`; grouped by component, then "Whole-system calls").

**Classification scheme, verbatim:**

> Definition (the owner's): **a judgment call is any choice that lands in the finished work that the author is not confident in making correctly, for any reason.** This log tracks and classifies them; it does not stop them.
>
> Every call carries one **cause** and one **reach**.
>
> Cause (why I was not confident):
> - `GAP` — the inputs are silent on the point; I had to invent.
> - `AMBIG` — the inputs say something, but two readings are reasonable.
> - `TENSION` — two input statements pull in different directions and I picked a reconciliation.
> - `TOOL` — depends on facts about external tooling (git, Claude Code, pytest, YAML) I could not verify here.
> - `TASTE` — a design preference among workable options.
>
> Reach (how much of the design changes if the call is reversed):
> - `local` — one function or file changes.
> - `component` — one component changes, its neighbours keep their contracts.
> - `system` — a contract between components changes.
>
> Each entry: **ID · cause/reach · spec section** — the choice; what I chose; alternatives; why not confident.

**By cause:** GAP 39, AMBIG 24, TASTE 8, TOOL 7, TENSION 2. **By reach:** local 48, component 26, system 6 (JC-02, 03, 05, 70, 71, 72).

**By theme** (analyst grouping, each id once):
- Platform/tooling facts (git, Claude Code hooks/agents/CLI, sub-agent limits): 10 — JC-10, 11, 27, 30, 31, 32, 43, 44, 61, 64.
- Gaps in the owner files (invented names, JSON shapes, missing keys/prose, vocabulary): 12 — JC-01, 02, 03, 05, 08, 18, 19, 25, 28, 33, 42, 76.
- Money rules: 9 — JC-22, 37, 45, 53, 54, 55, 58, 59, 78.
- Git semantics (drift diff, semantic conflicts, sync ids, abandon, bounds, worktree model, claim timing): 7 — JC-23, 46, 47, 48, 49, 72, 74.
- Limits and pauses: 5 — JC-14, 34, 41, 56, 57.
- Findings, gates, messages: 5 — JC-04, 36, 39, 77, 80.
- Steps, prose, prompt rendering: 5 — JC-24, 26, 29, 51, 73.
- Owner channel (quotes, numbering, acceptance, log slice): 4 — JC-06, 15, 40, 79.
- Config/robustness policy: 7 — JC-20, 21, 38, 50, 52, 60, 62.
- Layout, roles, tooling taste, whole-system: 11 — JC-07, 09, 12, 13, 16, 17, 35, 63, 70, 71, 75.
- Tests: 5 — JC-65, 66, 67, 68, 69.

**Ten most consequential** (the six `system` calls plus four `component` calls other components cite):
1. JC-03 — ledger, questions, findings, flags, decisions all inside `STATE.json`; no `LEDGER.json`.
2. JC-05 — the JSON shapes of `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SUITE.json` are invented; prompts, checks and stubs depend on them.
3. JC-02 — attempt ids `STEP-n` / `STEP-GATE-n`; `FINDINGS/` keyed by the judged producer attempt.
4. JC-72 — one worktree per round, sequential attempts, every attempt's diff committed at record.
5. JC-70 — `harness/` is the harness root, its parent the repo root, the driver's cwd `harness/`.
6. JC-71 — the harness develops itself.
7. JC-43 — CAS claim by `push --force-with-lease=refs/heads/<branch>:` with an empty lease; a remote is required.
8. JC-48 — `abandon` is a record-only landing so the record and ledger reach main.
9. JC-64 — helpers exist, spawned through the runner so their usage is billed.
10. JC-74 — the round is claimed at `start` before planning.

## 12. Traceability

- Requirements → components: yes, a table. SPEC.md §1.1 "The properties the requirements demand (and where each lives)" has 14 rows mapping paraphrased owner requirements to component files and section anchors (e.g. "Git is the only lock … → [06] §gitops"). §1.2 maps the robustness demand to five mechanisms "each owned by exactly one component". Every component section carries owns / depends on / depended on by; every JC entry names its spec section; 42 calls are cited inline. No per-requirement ids; not a matrix over owner sentences.
- Inconsistencies flagged in the owner's files (in `JUDGMENT-CALLS.md` unless noted):
  - `project.yaml`'s living-charge comment refers to "the spec's testPaths" but no such key exists (JC-18; 03 §3.3); it mentions "the prompt-size warning" but no threshold key exists (JC-19).
  - The owner's TODO says `allowUpstream` mechanics are unimplemented; `allowUpstream: 1` refuses to start (JC-14).
  - No `CHAT-TO-PLAN-GATE.txt` exists though CHAT-TO-PLAN is gate-capable (JC-28); no `LANDING-*.txt` prose exists (JC-33).
  - `roundPaths` names no driver-facing summary files (JC-01) nor a ledger file (JC-03).
  - Commented-out `ownerHourlyRate`, `costToWaitForOwner` would be "unused" if uncommented (03 §3.3; JC-21).
  - `AGENTS.md` says "Your system prompt names your step, your inputs, …" but agent definitions are static per rung (JC-32).
  - "Enforced distribution of budget (sum to 1)" admits two readings (JC-22, JC-37); COMMON-OVERVIEW's three statuses vs gates (JC-04); `PLAN.json` is `.json` while the plan "needs to read as plain English" (JC-76).
  - `INDEX.md` at the harness root is outside living paths yet AGENTS.md routes to it (JC-13).
  - Nothing states that `harness/` is the harness root or the driver's cwd (JC-70); the vision says "general software development" while `livingSourcePaths` point at the harness itself (JC-71).
  - `subAgents.yaml`'s ladder order is unstated (JC-20); `maxSimultaneousSubAgentsPerRound`'s scope is unstated (JC-62); PLAN-AGENTS "sub-agents" vs Claude Code sub-agents' inability to use the Agent tool (JC-64).
  - `maxRoundAttempts` ("restarting a round after minor issues") is undefined (JC-34); the decision vocabulary lacks `revise`, `resume`, `raise-limit` (JC-42); "one numbered list per turn" vs global numbering (JC-06); drift acceptance "reviewed and accepted" names no actor or mechanism (JC-15).
  - `docs/TODO.md` is seeded with "measured usage from the Agent tool when it becomes available" and "owner attention pricing placeholders in project.yaml" (09 §9.6; JC-59).

## 13. Gaps against the brief

- Function signatures: present for most modules with parameter types, return types, purpose and errors. Shortfalls: helper/return dataclasses named without fields — `CheckpointView`, `PauseView` ("small dataclasses of the fields listed above", 04 §4.3); `AgentsPlanInfo`, `SpecInfo`, `SuiteInfo`, `PostmortemInfo` (05 §5.4); `GateOutcome`, `ResolutionOutcome` (05 §5.5, partial); `Applied` (05 §5.8, partial); `Claim`, `Change`, `MergeResult` (06 §6.1, partial); `CheckContext`, `VerifyResult` (06 §6.2); `LandOutcome`, `SyncOutcome` (06 §6.4); `Slot`, `InvokeRequest` (08 §8.2); `Finding` (08 §8.1). Command modules list "private helpers only" unnamed (02 §2.4); `status.py`'s result is prose, not keys. No errors stated for `history.py`, `budget.py`, `limits.py`, `agentdefs.py`, most of `charges.py`.
- Files named but not specified: `shackles/__init__.py` (SPEC.md §3); `plumbing/__init__.py` implied by `pyproject.toml` (01 §1.1) but never listed.
- Templates and docs: the nine plumbing templates are given as required sections, "what it must contain, not its wording" (04 §4.3); all seven docs are section outlines with no draft text.
- Config, CI and scripts are itemised in prose, not given as file content (`pyproject.toml`, `.claude/settings.json`, the workflow; 01 §1.1, §1.3, §1.6).
- Tests: 488 cases are listed by name in `10-tests.md`; explicit assertion statements accompany a minority (e.g. `test_spec_files_match_baseline`, `test_happy_path_gates_off_checkpoints_on`, `test_prose_values_renders_lists_and_numbers`); probes state the expected verdict. "Cases and assertions" is met at the level of descriptive names.
- Internal naming inconsistencies: the agent-definition guard is `tests/test_agent_defs.py` in 01 §1.4, 04 §4.5 and the 10 intro but `test_agentdefs.py` in 10 §10.4; 08 §8.1 names `tests/test_doctor.py` while 10 §10.5 defines `test_cmd_doctor.py`.
- Drift toward line-by-line implementation: the fixed 13-item `record` sequence (02 §2.4, JC-16); exact git invocations and ref names in `gitops.py` (`--force-with-lease=refs/heads/<branch>:`, `commit-tree`, `refs/shackles/automerge/`, `pull --ff-only`; 06 §6.1); the `AGENTS.md` heading-normalisation rule and token regex (04 §4.2); `messages.py` error-reason strings (05 §5.3); the finding-repeat normalisation rule (05 §5.5); `run_pytest` "captures the last 40 lines" (06 §6.2); the arithmetic in `charges.py` (07 §7.1); concrete numeric values of the fake `project.yaml` (10 §10.2); the 90-day price-date constant (08 §8.1, JC-60). By contrast JC-44 leaves the automerge plumbing "to the implementer".
- Not specified anywhere: lint/format/type tooling; the content of `shackles/__init__.py`; the exact `CLI_ARGS` of `CliInvoker` (deliberately isolated, JC-61); the hook's stdin payload keys beyond fallbacks (JC-11).
