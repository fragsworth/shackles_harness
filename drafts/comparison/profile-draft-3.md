# Profile: draft 3

## 1. Format and size

- 23 Markdown files, 212,397 bytes, all flat under `drafts/draft-3/`. Entry point `SPEC.md` (11,845 B). Judgment-call log split in two: `JUDGMENT-CALLS.md` (13,678 B, JC-01…JC-35, holds the scheme) and `JUDGMENT-CALLS-2.md` (11,947 B, JC-36…JC-71). Twenty numbered component files `01`…`20` (largest `18-tests-unit.md` 14,333 B and `02-lifecycle.md` 13,915 B; smallest `20-tooling-ci.md` 3,155 B).
- Organisation: `SPEC.md` §1 "Map of this spec" is a table of every file and what it specifies; §2 restates the owner's requirements as twelve design principles; §3 "Architecture in one page" (ASCII diagram plus round folder and step list); §4 component isolation rules; §5 conventions (signature notation, paths, times, money, exit codes, identifiers); §6 glossary. Files 03–15 each hold one section per `src` module with an explicit **owns / depends on / depended on by** header, then types, then functions.
- Component files: `01-repo-layout` (tree, ownership labels), `02-lifecycle` (behaviour, no code), `03-cli`, `04-config`, `05-steps-prose`, `06-templates-prompts`, `07-schemas`, `08-state-history-rounds`, `09-gitops`, `10-engine`, `11-findings-checks-verify`, `12-landing-suite`, `13-ledger`, `14-ownerlog-jc-agentdefs`, `15-install-doctor-index`, `16-docs`, `17-tests-infra`, `18-tests-unit`, `19-tests-flows`, `20-tooling-ci`.
- Judgment calls cited inline: yes, as `[JC-nn]` tags: 89 tag occurrences citing 66 distinct calls. Five calls (JC-47, JC-49, JC-57, JC-63, JC-68) have no inline tag; `JUDGMENT-CALLS-2.md` says "Calls JC-46 onward were made without an inline tag in the spec at first; the `Affects` field is the cross-reference". Every call carries an `Affects` field naming file and section.
- Reading order (`SPEC.md` §1): "this file, `01`, `02`, `07`, `08`, then the rest in numeric order; tests last."

## 2. Language, runtime, packaging, tooling

- Language: Python 3.11+, standard library plus `pyyaml`; tests with `pytest` (`SPEC.md` §5, JC-58). Hand-rolled JSON validation, no `jsonschema`/`pydantic`. No build step; `python src/run.py ...` runs from the harness root.
- Manifest: `harness/pyproject.toml` (`20-tooling-ci.md`, given verbatim): `name = "shackles-harness"`, `version = "0"` ("never bumped; the harness is not packaged"), `requires-python = ">=3.11"`, `dependencies = ["pyyaml>=6"]`, optional `test = ["pytest>=8"]`; `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = "-q -m 'not probe'"`, marker `probe`. No build backend.
- Lint/format/type tools: not specified.
- CI: `.github/workflows/ci.yml`, optional (JC-02), given verbatim: checkout v4, setup-python 3.12, `pip install pyyaml pytest`, a git identity, `cd harness && python -m pytest`. The drift test runs in CI; probes never do.
- Scripts: "None beyond `src/run.py` and the hook" (`20` §Scripts). Every owner/agent action is a `run.py` subcommand.
- Generated files (by `run.py install`): `.claude/agents/<rung>.md` and `<rung>-gate.md`, `.claude/settings.json` (merged, other keys kept), `CLAUDE.md` (exactly `@AGENTS.md`, written once, never overwritten), `INDEX.md`, `local.yaml`; required lines appended to `<repo>/.gitignore`; first spec baseline taken when `local.yaml` has none. `spec accept` writes `local.yaml` hashes and copies under `archives/spec-baseline/`. `INDEX.md` is also regenerated at CLEANUP.
- Environment variables (`20`): `SHACKLES_VERIFY=1` (set by `verify.run`), `SHACKLES_PROBES=1` (probes), `CLAUDE_PROJECT_DIR` (hook command only), `GIT_TERMINAL_PROMPT=0` (set by `gitops`).

## 3. Repository layout

From `01-repo-layout.md` (each path labelled owner / living / generated / local / record / derived):

```
<repo root>/                       git repository; remote `origin` required
  spec.yaml, SPEC.md               owner
  README.md                        derived, one paragraph [JC-01]
  .gitignore                       derived
  .github/workflows/ci.yml         derived, optional [JC-02]
  .worktrees/round-NNNN/           local (gitignored); one worktree per active round
  harness/                         THE HARNESS ROOT (contains project.yaml)
    AGENTS.md, project.yaml, subAgents.yaml, locked_prose/*.txt   owner
    CLAUDE.md                      generated (`@AGENTS.md`) [JC-03]
    INDEX.md                       generated, one line per file
    local.yaml                     generated, committed: spec baseline hashes + generated-file hashes [JC-51]
    OWNER.log                      local (gitignored), JSONL written by the hook
    pyproject.toml                 derived
    .claude/settings.json          generated (UserPromptSubmit hook)
    .claude/agents/<rung>.md, <rung>-gate.md   generated
    src/                           living: the runner (34 files, see §6)
    docs/                          living: 9 files (see §9)
    tests/                         living: fixtures, test_*.py, probes/
    archives/                      record (free)
      spec-baseline/               accepted copies of the spec files, for diffs [JC-04]
      rounds/NNNN/                 PLAN.json AGENTS-PLAN.json SPEC.json SPEC.md SUITE.json POSTMORTEM.md
                                   STATE.json HISTORY.md OWNER.log
                                   PROMPTS/ RESULTS/ FINDINGS/ tests-archive/
                                   DEFINED_JUDGMENT_CALLS.md UNDEFINED_JUDGMENT_CALLS.md
```

- Harness code lives in `harness/src/`; the runner finds its root as the parent of `src/` (`paths.harness_root`), "never by walking from the current directory". Round folder names come from `project.yaml` `roundPaths` at run time; code refers to them by key.
- Rounds/archives: `harness/archives/rounds/NNNN/` on branch `round/NNNN`, later on `main`. Agents work in `<repo>/.worktrees/round-NNNN/harness/`; the main checkout stays on `main`.
- Gitignored (`20`): `.worktrees/`, `harness/OWNER.log`, `__pycache__/`, `.pytest_cache/`. Committed: `local.yaml`, `.claude/`, `CLAUDE.md`, `INDEX.md`, `archives/`.
- Owner files: `spec.yaml` and `SPEC.md` at the repo root; `AGENTS.md`, `project.yaml`, `subAgents.yaml`, `locked_prose/` under `harness/`. Default living paths `src/ docs/ tests/`; `INDEX.md`, `local.yaml`, `CLAUDE.md`, `.claude/`, `pyproject.toml`, `README.md`, `archives/` are free.
- Hand-written files that must exist before the first round: `README.md`, `.gitignore`, `pyproject.toml`, all of `docs/`, `INDEX.md`, an empty `archives/rounds/`.

## 4. Actors and roles

(`SPEC.md` §6 glossary, §3 diagram, `02-lifecycle.md`)

- **owner**: the human whose words start and steer a round; edits only the spec files; answers via chat; runs `install`/`doctor`/`spec accept` per `docs/OWNER-GUIDE.md`.
- **driver**: the top-level agent in the owner's chat; runs `python src/run.py next|record|...` from the MAIN checkout, spawns one fresh sub-agent per attempt with the prompt file verbatim, relays runner messages, turns owner words into structured `--decision`/`--quote` flags, and is itself the CHAT-TO-PLAN producer.
- **runner**: `src/`; owns STATE.json, HISTORY.md, git, ledger, prompts; the only thing that commits, pushes or contacts the owner; verifies quotes, never parses prose.
- **producer**: one agent attempt writing an artifact or code in the worktree, only inside declared paths plus its round-folder artifacts and JC trails.
- **gate**: a read-only agent attempt (definition `<rung>-gate`, `tools: Read, Grep, Glob`) that judges a producer and returns findings/rulings/verdict.
- **LANDING contingent agent**: one attempt spawned only on a textual merge conflict, judged against git's auto-merged tree (`12-landing-suite.md`).
- **producer sub-agents**: allowed per `AGENTS-PLAN.json`, bounded by `maxSimultaneousSubAgentsPerRound` in the plan and stated in LIMITS; the runner "cannot count an agent's own sub-agents" (JC-48).
- **hook**: `src/hooks/owner_log_hook.py`, run by Claude Code's `UserPromptSubmit` hook; appends every owner prompt to `OWNER.log`; always exits 0, prints nothing to stdout.
- **agent definitions / Agent tool**: generated `.claude/agents/*.md` per rung carrying `model` and `effort`; loaded at session start; stale set makes `start`/`next` refuse.
- **git `origin`**: the only lock (CAS branch push, lease pushes).
- **test doubles**: `StubAgent` (scripted behaviours), `FakeDriver` (drives next/record), `ClaudeCliAgent` (`claude -p` for opt-in probes).

## 5. Architecture: the main mechanisms

a. **Step table / process definition**: `src/steps.py` `TABLE: tuple[Step, ...]` of eleven frozen `Step` dataclasses (`kind`, `gate_capable`, prose stems, `artifact_keys`, `scopes`, `verify`, freeze flags, `contingent_agent`, `books_charges`, `skippable`) with enums `Kind`, `Scope`, `Verify`. `lint(cfg, bundle)` checks `project.yaml` `steps:` order, gate-on-without-prose, required/unknown prose files, `roundPaths.artifacts` keys, `defaultShares.gates`, prose tokens. Key choice: the table is code; config only toggles gates; unknown inputs refuse to start (`SPEC.md` §2 principle 3).

b. **Round lifecycle / state**: `src/state.py` `RoundState` is "the runner's only state", persisted as `archives/rounds/NNNN/STATE.json` on the round branch; statuses `PLANNING | RUNNING | PAUSED | DONE | ABANDONED`; `position = {step, phase, attempt}` with phase `produce | gate | checkpoint | runner`. Walked by `next_action.advance_through`; transitions applied by `recording` and `pauses`. Every change: mutate state → write STATE.json/HISTORY.md → `add_and_commit` → `push_lease`. HISTORY.md is append-only and never read back; the worktree path is never stored.

c. **Prompt assembly**: `src/templates.py` is a namespace-agnostic `{{ ns.KEY }}` recursive engine (`Resolver` protocol, cycle/depth guards, collects all unresolved tokens, `render_lenient` for doctor, `mask_namespace`); `src/context.py` supplies `project.*`, `round.*`, `agents.<SECTION>` (level-2 headings of AGENTS.md, normalised keys, JC-60), `prose.<STEM>`, `plumbing.*`; `src/prompts.py` renders a fixed layout (header line, AGENTS.md verbatim, the step's overview or gate prose, COMMON-STEP-END tail, JC-23) and a mechanical PROCESS-INSTRUCTIONS block with fixed headings, appended when the prose omits its token. Owner text is read only by `prose.py`, `config.py`, `specfiles.py`; `prose.py` "never interprets wording".

d. **Owner channel**: `src/ownerlog.py` JSONL `OWNER.log` (`ts`, `session`, `cwd`, `text`), per machine, written by `hooks/owner_log_hook.py` via the generated `.claude/settings.json` hook; `verify(quote, sources)` = whitespace-normalised substring of any entry in the local log or the round's committed slice, no keyword check (JC-13); the round's slice is copied into the round folder. Decisions are structured CLI flags: `start --quote`, `record STEP --decision approve|delegate|abandon [--through STEP] [--override A,B-GATE] --quote`, `resume --quote [--hard-stop-multiple] [--extend]`, `abandon --quote`; plan answers live inside `PLAN.json` (`answer`, `quote`) and are verified at record (JC-62). Owner-facing messages (`pauses.checkpoint_message`, `pause_message`, `final_message`) are fixed-section, verbatim-quote only.

e. **Git model**: `src/gitops.py` `Repo` class wraps every git call. Claim = plain push of a new `round/NNNN` branch (rejection → `FenceError("CLAIM_LOST")`, retry next id); fence = `--force-with-lease=<branch>:<sha read>` after every state change, rejection = exit 4, loser's commit saved to `round/NNNN-orphan-<ts>` and local branch reset (JC-31); one worktree per round; `start` refuses while any `round/*` is non-terminal (JC-05). Landing (`src/landing.py`): fetch, record `pre_landing_main` once, projected living charge → hard stop, merge `origin/main` into the round branch in the worktree, verify, `push_lease`, `push_to(branch, main, lease)`; a moved main loops at most `maxRoundAttempts`; a conflict becomes one LANDING attempt with declared paths = conflicted files, judged against the auto-merged tree; second conflict/verify failure → `LANDING_FAILED`. After landing `next` fast-forwards the main checkout (JC-10). Bounded post-landing sync after CLEANUP (and after abandon-after-landing) re-merges POSTMORTEM/CLEANUP commits into main; exhaustion → round stays `DONE` with `sync.status = failed` (JC-33). Remote round branches kept; `prune` removes worktrees only.

f. **Results, verdicts, findings**: `src/schemas.py` validates producer messages (`status DONE | NEEDS-OWNER | BLOCKED`, `questions`, `narrow`, `resolutions fixed|disputed`, `flags`, `judgment_calls`) and gate messages (`verdict PASS|FAIL`, `rulings upheld|withdrawn` with quote, `findings` with severity/quote/text/suggestion). `src/findings.py` statuses `open, fixed, disputed, withdrawn, settled, dropped, flagged, closed`; verdict wins (FAIL upgrades non-blocking to blocking, PASS downgrades blocking to flags, JC-34); a new finding whose normalised quote equals a withdrawn one is dropped with a HISTORY note (JC-17); upheld twice = settled; missing resolution = invalid (exit 5); verify failures raise runner findings `R<n>`; flags queued and delivered at checkpoints, pauses and the final message. Ids are round-wide `F<n>` (JC-46).

g. **Money**: `src/ledger.py`; `tokens.estimate = ceil(bytes / tokenBytes)` is the single estimate. Attempt cost = rung `spawnCost` + measured tokens (four `--*-tokens` flags) at per-MTok prices, else estimated (input = prompt file tokens, output = `estOutputFraction` × input, JC-39) + `driverUsdPerStep` once per step (JC-55). Living charge booked once at CLEANUP on the net change from `pre_landing_main` to the tree CLEANUP leaves: per-file token delta at `livingFileCostPerToken` up to `livingFileTokenCap` then `livingFileCostPerTokenOverCap`, ± `livingFileBaseCost` per new/removed file, carry-forward files at `postMortemFileCostPerToken` (JC-11); may be negative. Archive charges: `planCostPerToken` × PLAN.json, `specCostPerToken` × (SPEC.json + SPEC.md), `postMortemCostPerSummaryToken` × the `Summary` section (JC-29, JC-66); test base cost by test-function count delta. `lostValuePerHour` informational (JC-38). Hard stops: `HARD_STOP` when spend (+ projected living charge at landing) > `hardStopBudgetMultiple` × quote; `HARD_STOP_INDIVIDUAL` when an attempt costs > multiple × its share × quote (JC-71); overrides are round-scoped via `resume`. `project.remaining` = budget − sum of every archived round's ledger total (JC-63).

h. **Checks**: `src/checks.py` classifies the worktree's uncommitted `git status` into accepted vs strays by `steps.resolve_scopes`; spec files, runner-owned round files (STATE.json, HISTORY.md, OWNER.log, PROMPTS/, FINDINGS/, other RESULTS) and frozen tests are always strays; strays are reverted (`gitops.revert_paths`), never fail the attempt; artifact presence/validity failures do (`InvalidError`). `src/verify.py` runs `verifyCommand` in the worktree with `verifyTimeoutSeconds`: `collect` mode (`--collect-only`) for SPEC-TO-TESTS (JC-70), `suite` mode for SPEC-TO-IMPLEMENTATION, TESTS-TO-SUITE (after `suite.apply`), LANDING, POSTMORTEM, CLEANUP; tail becomes a runner finding. `src/suite.py` enumerates round tests by `ast` (added/changed vs `base_commit`) and cuts archived functions into `tests-archive/` (JC-36, JC-37). Mechanical (verify) rejections consume gate turns (JC-32).

i. **Doctor / lint / index**: `src/doctor.py` reports seven isolated areas (`config` incl. defaulted keys, `lint`, `render` of every prompt with a sample round, `spec` drift, `generated` staleness, `hook`/OWNER.log, `git`), exit 3 on any error; `doctor --show STEP [--gate]` renders one prompt. `steps.lint` as in (a). `src/index.py` generates `INDEX.md` mechanically from docstrings/headings/first lines (JC-43), `--check` compares, regenerated at CLEANUP and by `install`.

j. **Robustness to spec-file edits**: code depends "only on file names, config keys and a fixed step list" (`SPEC.md` §2 principle 2); unknown config keys refuse and missing optional keys default (`config.py`); unknown/missing prose files are lint errors, prose is addressed by stem only; AGENTS.md sections by normalised heading; `spec.yaml` files hashed into `local.yaml` with copies in `archives/spec-baseline/`; `test_spec_drift.py` fails with a diff after any edit and `start` refuses on drift until `spec accept`; `doctor` renders every prompt offline and names unresolved tokens; mechanics tests run on a generated one-line-per-file spec (`tests/fixture_spec.py`) so a prose rewrite "fails only `test_spec_drift.py`".

## 6. Module inventory

34 source files under `harness/src/` (33 modules plus `hooks/owner_log_hook.py`), from `01-repo-layout.md` and files 03–15:

- `run.py`: argparse tree, `--root`/`--json`/`--debug`, exception→exit-code mapping, printing (`build_parser`, `main`, `print_result`).
- `commands.py`: one `cmd_<name>(root, args) -> CommandResult` per command, `register`, `load_world`, `parse_token_flags`. Classes `CommandResult`, `World`.
- `errors.py`: `HarnessError` (code, message, exit_code, details) and subclasses `UsageError`(2), `RefusedError`(3), `FenceError`(4), `InvalidError`(5), `ConfigError`, `LintError`, `DriftError`, `RenderError`, `GitError`(1); `exit_code_for`.
- `paths.py`: `harness_root`, `repo_root`, worktree paths, `round_folder_name`; class `RoundPaths` (every round-folder path by key).
- `config.py`: `project.yaml`/`subAgents.yaml` schema and validation; classes `KeySpec`, `RoundPathsConfig`, `ProjectConfig`, `AgentSpec`, `AgentsConfig`; `PROJECT_KEYS`, `load_project`, `load_agents`, `validate_project`, `validate_cross`, `example_*_dict`, `render_value`.
- `specfiles.py`: `spec.yaml` listing, pattern expansion, sha256 hashing, `DriftReport`, `check_drift`, `assert_no_drift`, `diff_text`, `accept`.
- `localstate.py`: `LocalState` model of `local.yaml`, `load`/`save`, `HARNESS_VERSION`.
- `tokens.py`: `estimate`, `text_tokens`, `file_tokens`, `blob_tokens`.
- `steps.py`: `TABLE`, enums `Kind`/`Scope`/`Verify`, classes `Step`, `LintReport`, `Overrides`; `lint`, `parse_overrides`, `gate_is_on`, `resolve_scopes`, `checkpoint_covered`, lookup helpers.
- `prose.py`: `ProseBundle` (texts by stem, AGENTS.md sections), `load`, `section_key`, `split_sections`, `referenced_stems`.
- `templates.py`: `Token`, `Resolver` protocol, `find_tokens`, `find_malformed`, `render`, `render_lenient`, `mask_namespace`.
- `context.py`: `RoundValues`, `Context` resolver, `sample_round`, `round_values`, `gates_text`, `project_value`, `all_rounds_spend` (`SpendSummary`).
- `prompts.py`: `Role` enum, `AttemptSpec`, `RenderedPrompt`, `Limits`; `assemble`, `process_instructions`, `gate_prose_preview`, `landing_prompt_body`, `chat_prompt_note`, `size_warning`, `write_prompt`, `render_all`.
- `schemas.py`: JSON extraction and validators; dataclasses `Question`, `Plan`, `StepAssignment`, `GateAssignment`, `AgentsPlan`, `SpecDoc`, `SuiteDecision`, `SuiteDoc`, `Result`, `Resolution`, `JudgmentCallLine`, `RawFinding`, `Ruling`, `FindingsDoc`; `validate_plan/agents_plan/spec/suite/result/findings`, `postmortem_summary`, `rung_for`, `budget_for`, `describe`.
- `state.py`: `RoundState` and 18 sub-dataclasses (`Position`, `Approval`, `Overrides`, `StepRecord`, `AttemptRecord`, `FindingRecord`, `Resolution`, `RulingRecord`, `Flag`, `OwnerDecision`, `Landing`, `Sync`, `LedgerState`, `LedgerEntry`, `Run`, `Pause`, `HardStopOverride`, `Abandoned`), `load`/`save`, transition helpers.
- `history.py`: `HistoryEntry`, `append`, entry builders (`spawned`, `recorded`, `gate`, `owner`, `paused`, `resumed`, `landing`, `sync`, `charges`, `note`).
- `rounds.py`: `RoundRef`, `LoadedRound`; `discover`, `active`, `next_id`, `preconditions`, `start`, `scaffold`, `ensure_worktree`, `load_active`, `abandon`, `status_text`, `prune`.
- `gitops.py`: class `Repo` (fetch, CAS push, lease pushes, worktrees, status, revert, merge, conflict inspection, ls-tree, diff, backup branch, identity); `Change`, `MergeResult`, `TreeEntry`.
- `next_action.py`: `Action`; `next`, `advance_through`, `prepare_producer`, `prepare_gate`, `prepare_checkpoint`, `prepare_landing_attempt`.
- `recording.py`: `DecisionArgs`, `RecordOutcome`; `record`, `record_plan`, `record_checkpoint`, `record_producer`, `record_gate`, `fail_producer`, `accept_step`, `handle_invalid`, `finish_round`, `commit_and_push`.
- `pauses.py`: limits (`check_run_limits`, `check_hard_stop`, `check_individual`), `pause`, `resume`, owner messages (`checkpoint_message`, `pause_message`, `final_message`), `judgment_calls_since`, `deliver_flags`.
- `findings.py`: `FindingView`, `GateOutcome`; `apply_gate`, `apply_resolutions`, `raise_runner`, `close_on_accept`, `views_for_prompt`, `open_non_blocking`, `normalise_quote`.
- `checks.py`: `Classification`, `CheckReport`; `classify_changes`, `run_for_attempt`, `validate_artifacts`, `runner_owned_round_files`, `spec_file_rels`, `conflict_marker_check`.
- `verify.py`: `VerifyResult`; `run` (collect|suite with timeout, log file), `finding_text`.
- `landing.py`: `LandOutcome`, `SyncOutcome`; `land`, `after_conflict_resolved`, `sync`, `remove_worktree`, `projected_charge_text`.
- `suite.py`: `TestRef`, `ApplyReport`; `tests_in_source`, `tests_at_ref`, `enumerate_round_tests`, `count_tests`, `apply`, `frozen_file_list`.
- `ledger.py`: `Usage`, `AttemptCost`, `FilePrice`, `LivingCharge`, `ArchiveCharge`, `RoundBooking`; `attempt_cost`, `book_attempt`, `file_price`, `living_charge`, `archive_charge`, `test_charge`, `elapsed`, `book_round`, `charges_text`, `ledger_text`, `project_remaining`.
- `ownerlog.py`: `Entry`, `Log`; `append`, `append_from_hook`, `read`, `verify`, `slice_since`, `write_slice`, `hook_command`.
- `hooks/owner_log_hook.py`: `main()` — stdin hook payload → `OWNER.log` line; always exit 0.
- `judgment_calls.py`: `Kind` enum; `append_line`, `ingest`, `read_since`, `cli_command`, `trail_path`.
- `agentdefs.py`: `agent_markdown`, `settings_json`, `generate`, `expected_hashes`, `staleness`, `hook_installed`, `definition_names`.
- `install.py`: `InstallReport`; `install`, `check`.
- `doctor.py`: `Finding`, `DoctorReport`; `run` (seven areas), `render_prompt`.
- `index.py`: `IndexLine`; `collect`, `purpose_of`, `render`, `write`, `check`.

Test-side classes (`17-tests-infra.md`): `FixtureSpec`, `FakeClock`, `FixtureRepo`, `StubAgent`, `Trace`, `FakeDriver`, `ClaudeCliAgent`. No `__init__.py` files are mentioned.

## 7. Data contracts

- `STATE.json` (`08`, full JSON example): `harness_version`, `round`, `status`, `branch`, `base_commit`, `origin_quote`, `quote`, `position`, `approval` (mode/through/overrides/quote), `step_records`, `attempts`, `findings`, `flags`, `owner_decisions`, `frozen_tests`, `landing`, `sync`, `ledger`, `run`, `restarts`, `pause`, `hard_stop_override`, `abandoned`. Persisted at `archives/rounds/NNNN/STATE.json` on the round branch.
- `HISTORY.md` (`08`): `# HISTORY` heading, then `## <at> <title>` entries with `- ` bullets; append-only, never read by code; round folder.
- `OWNER.log` (`14`): JSON Lines `{"ts","session","cwd","text"}`; local at `<harness>/<ownerLogPath>`, gitignored; a round slice in the same format is rewritten into the round folder.
- `PLAN.json` (`07`): `text`, `quote` (number), `questions[{n,text,options,answer,quote}]`, `todos`, `non_goals`, `validation_steps`, `assumptions`; round folder, written by the driver.
- `AGENTS-PLAN.json`: `steps{STEP:{rung,share,subagents[{rung,count}],rationale}}`, `gates{STEP:{rung,share,rationale}}`, `refactor_share`, `notes`.
- `SPEC.json`: `components[{id,title,description,files}]`, `steps[{id,...,components}]`, `test_plan[{id,description,components,kind}]`, `non_goals`, `refactors`; `SPEC.md` free prose, non-empty.
- `SUITE.json`: `decisions[{test,where suite|archive,reason}]`, `flags`.
- `POSTMORTEM.md`: Markdown; the first `Summary` heading's body is the priced/relayed summary.
- Producer/chat/landing final message (`RESULTS/<STEP>-<n>.json`): `status`, `summary`, `questions`, `narrow`, `resolutions[{finding,resolution,note}]`, `flags`, `judgment_calls[{kind,line}]`; extracted from the last ```json fence or last balanced object.
- Gate final message (`FINDINGS/<STEP>-<n>.json`): `verdict`, `summary`, `rulings[{finding,ruling,quote}]`, `findings[{severity,quote,text,suggestion}]`, `judgment_calls`.
- Prompt files `PROMPTS/<STEP>-<n>.txt` / `<STEP>-GATE-<n>.txt`, companion `<STEP>-<n>.diff`; verify logs `RESULTS/<STEP>-<n>.verify.txt`.
- Judgment-call trails `DEFINED_JUDGMENT_CALLS.md` / `UNDEFINED_JUDGMENT_CALLS.md`: one line `<UTC ISO> <STEP> attempt <n>: <line>`.
- `local.yaml` (`04`): `spec_baseline{path:hash}`, `spec_accepted_at`, `generated{subAgentsHash,agentDefsHash,settingsHash,hookHash}`, `installed_at`, `harness_version`; committed at the harness root, header comment "do not edit".
- `spec.yaml`: `files:` list of relative paths, `dir/*` patterns allowed (non-recursive).
- `INDEX.md` (`15`): heading line then `<path> — <purpose>` sorted by path.
- `.claude/settings.json` and `.claude/agents/<rung>[-gate].md` (`14`, `20`): hook JSON and agent frontmatter (`name`, `description`, `model`, `effort`, gate `tools`) given verbatim.
- `docs/TODO.md`, `docs/CLARIFICATIONS.md` (`16`): level-1 heading, format note, `- [round NNNN] <text>` bullets.
- `pyproject.toml`, `.gitignore`, `ci.yml`: verbatim in `20`.

## 8. Testing

- Infrastructure (`17-tests-infra.md`): `tests/fixture_spec.py` generates a complete one-line-per-file spec repository from `steps.names()` and `config.example_*_dict` (prose files are markers like `PLAN-AGENTS-OVERVIEW {{ prose.COMMON-PROJECT }} ... {{ plumbing.PROCESS-INSTRUCTIONS }}`, plus a living skeleton `src/app.py`, `tests/test_app.py`, docs, pyproject); `tests/gitfixtures.py` (bare origin, clones, `advance_main_elsewhere`); `tests/conftest.py` fixtures `clock` (`FakeClock`), `fixture_repo`, `world`, `say` (appends to OWNER.log as the hook would), `stub`, `driver`, `started`, `approved`, `real_repo_root`, `probe` marker; `tests/stub_agent.py` `StubAgent` with 28 scripted producer behaviours and 14 gate behaviours consumed per attempt from a script; `tests/fake_driver.py` `FakeDriver` loops `next` → stub → `record`, consuming an `owner_script` at checkpoints/pauses, `run`, `run_until`, `Trace`.
- Test files: 25 unit files (`18`: `test_paths, test_config, test_specfiles, test_tokens, test_steps, test_prose, test_templates, test_context, test_prompts, test_schemas, test_state, test_history, test_gitops, test_ownerlog, test_judgment_calls, test_agentdefs, test_install, test_ledger, test_suite, test_findings, test_checks, test_verify, test_doctor, test_index, test_docs`) and 11 in `19` (`test_flow_start, test_flow_plan, test_flow_round, test_flow_gates, test_flow_pauses, test_flow_landing, test_flow_suite, test_flow_ledger, test_cli, test_spec_drift, test_spec_lint`): 36 named `test_*.py`, plus 5 support modules, `tests/probes/conftest.py`, `tests/probes/live_agent.py` and four probe test functions whose file names are not specified.
- Split: unit (25 files, module-level, mostly on the fixture repo with a temp origin); flow/integration (8 `test_flow_*` files driving whole or partial rounds through the real `next`/`record` functions, asserting on STATE.json, HISTORY.md, git and the ledger); `test_cli.py` via subprocess; two real-file tests (`test_spec_drift.py`, `test_spec_lint.py`); live probes opt-in.
- Live probes: skipped unless `SHACKLES_PROBES=1`, `-m probe` and the `claude` CLI on PATH; `ClaudeCliAgent` runs `claude -p --model <model> --output-format json` with the prompt on stdin in the worktree, `--allowedTools` reduced for gates, saves the final text and returns reported usage (JC-44); use the `systemTestAgent` rung and the fixture spec; each plants a defect and asserts "the harness reaction, never the agent's wording" (parses, at least one finding with quote and suggestion, strays reverted, a JC line landed; verdict not asserted).
- Notable assertions: flow tests recompute ledger values from fixture prices; `full_round_lands_and_books` asserts origin/main contains the round folder and regenerated INDEX.md; `fence_recovery_keeps_orphan_branch` uses two clones of one origin; `landing_retries_when_main_moves` monkeypatches `gitops.Repo.push_to`; the drift test's failure message embeds `diff_text` per file and the `spec accept` command; `test_docs.py` asserts every registered command is mentioned in OWNER-GUIDE/PROCESS and `SCHEMAS.md` names every `describe()` field; `test_spec_lint.py` asserts only the config/lint/render doctor areas (JC-45); every runner call takes `clock.now()`.

## 9. Docs

(`16-docs.md`; all of `docs/` is living and priced; each file has an `Audience:` line.)

- `docs/PROCESS.md`: rules for agents inside the harness — worktree, prompt layout, declared paths and strays, final-message JSON, findings/resolutions, `jc` command, limits, the driver's loop.
- `docs/OWNER-GUIDE.md`: install, starting a round, pointer to the owner words, checkpoints/pauses, editing spec files and the drift guard, where things are, several machines, recovering.
- `docs/ARCHITECTURE.md`: one section per owner feature sentence naming the modules/functions that realise it, the module dependency table, invariants tests enforce.
- `docs/PROMPTS.md`: prompt layout, the five namespaces and keys, recursion/cycle rules, unknown tokens, plumbing append, size warning.
- `docs/SCHEMAS.md`: the six JSON shapes with field tables plus STATE.json top-level fields (hand-written; checked against `schemas.describe` by test).
- `docs/LEDGER.md`: attempt cost, living charge with a worked example, archive charges, carry-forward pricing, hard stops, informational items.
- `docs/TESTING.md`: running tests, the generated fixture spec, stub behaviours table, fake driver, git fixtures, drift/lint tests, probes.
- `docs/TODO.md`, `docs/CLARIFICATIONS.md`: carry-forward files edited by POSTMORTEM, `- [round NNNN] <text>` bullets.
- `harness/INDEX.md`: generated one-line-per-file routing index (free).
- `README.md` (repo root): one fixed paragraph pointing to `harness/docs/OWNER-GUIDE.md` and `doctor`.
- `harness/CLAUDE.md`: generated, exactly `@AGENTS.md`.

## 10. Notable or unusual decisions

- Self-hosting is embraced: `src/` is a living path and, after a successful landing, `next` fast-forwards the main checkout "so the runner code in use is the landed one" (JC-10, `02` §4 LANDING).
- The driver runs the runner from the MAIN checkout; agents work in `.worktrees/round-NNNN/harness/`; the runner locates its root as the parent of `src/`, never from cwd (`01`).
- The runner's only state is `STATE.json` on the round branch; `HISTORY.md` is never read back; the worktree path is never stored; any machine can `next` after a fetch (`02` §10).
- Landing and end-of-round booking happen inside `next` and `record CLEANUP`; no `land`/`book` commands exist (JC-47).
- Five config keys the code needs but `project.yaml` lacks are defaulted (`testPaths`, `carryForwardFiles`, `promptWarnTokens`, `ownerLogPath`, `verifyCommand`) and reported by `doctor` (JC-18); `allowUpstream` must be `0` or `start` refuses (JC-06).
- `local.yaml` is committed, and accepted spec copies live under `archives/spec-baseline/` so the drift test can print a diff (JC-04, JC-51).
- One active round at a time (JC-05); `start` requires an owner `--quote` (JC-53); remote `round/NNNN` branches are kept forever (JC-52).
- Effort reaches the Agent tool through an `effort:` frontmatter field in generated per-rung definitions with a read-only `-gate` twin each; `.claude/` sits at `harness/` and the session starts there; no SessionStart hook (JC-41, JC-42, JC-57).
- Quote verification is a whitespace-normalised substring with no keyword check (JC-13); owner answers live inside `PLAN.json` (JC-62).
- Producers' round-folder scope is their own artifacts plus the two JC trails, not the folder (JC-67); strays are reverted, never fail; NEEDS-OWNER/BLOCKED work is committed before pausing (JC-50).
- Archived tests are cut out at function granularity with `ast`, decorators included, class tests becoming prefixed top-level functions (JC-37); SPEC-TO-TESTS verify is collect-only (JC-70).
- A fence loser's commit goes to `round/NNNN-orphan-<ts>` and the branch is reset (JC-31); a failed post-landing sync leaves the round `DONE` with `sync.status = failed` (JC-33); COMMON-STEP-END is the tail of the single prompt (JC-23); `jc` is a `run.py` subcommand (JC-54).

## 11. Judgment calls

Total: 71 (JC-01…JC-35 in `JUDGMENT-CALLS.md`, JC-36…JC-71 in `JUDGMENT-CALLS-2.md`). Definition used: "a judgment call is any choice that lands in the finished work that I am not confident in making correctly, for any reason."

Classification scheme, verbatim:

> Each call carries three labels:
>
> - **Kind** — why the choice was not forced:
>   `GAP` the owner's files are silent · `AMBIGUITY` they admit more than one reading ·
>   `CONFLICT` two owner statements pull apart · `TOOLING` behaviour of an external tool
>   (Claude Code, git, pytest, GitHub) that the files cannot settle.
> - **Weight** — how much moves if the owner overrules it:
>   `light` local to one section · `structural` ripples across components ·
>   `owner-facing` changes what the owner sees or must do.
> - **D/U** — per the owner's AGENTS.md: `D` (defined) decided from the spec files alone;
>   `U` (undefined) needed knowledge from outside them.
>
> Format: **JC-nn** (Kind · Weight · D/U) · *Choice* · *Chose* · *Alternatives* · *Why unsure* · *Affects*.

Label tallies: Kind GAP 36, AMBIGUITY 24, TOOLING 8, CONFLICT 3. Weight light 51, structural 13, owner-facing 7. D 58, U 13.

By theme (analyst's grouping, 71 total):
- Platform/tooling facts (Claude Code, git, pytest, CI, language): 11 — JC-02, 03, 23, 36, 37, 40, 41, 42, 44, 57, 58.
- Config keys and the settings surface: 6 — JC-06, 18, 19, 26, 51, 68.
- Step table, overrides, prose files: 5 — JC-07, 09, 12, 25, 60.
- Prompt rendering semantics: 8 — JC-20, 21, 22, 24, 27, 48, 49, 69.
- Money rules: 9 — JC-08, 11, 29, 38, 39, 55, 63, 66, 71.
- Git semantics, landing, sync, branches: 7 — JC-10, 16, 31, 33, 35, 52, 64.
- Findings, verdicts, result validation: 9 — JC-17, 28, 30, 32, 34, 46, 56, 61, 65.
- Runs, limits, pauses: 3 — JC-14, 15, 50.
- Owner channel and quotes: 3 — JC-13, 53, 62.
- Spec guard/drift: 2 — JC-04, 45. Concurrency: 1 — JC-05. Write scopes: 1 — JC-67. Test/verify handling: 2 — JC-59, 70. Taste/command surface: 4 — JC-01, 43, 47, 54.

Ten most consequential:
1. JC-58 — Python 3.11+, pyyaml, pytest, hand-rolled validation, no build step.
2. JC-18 — defaulted config keys the owner's `project.yaml` lacks, reported by `doctor`.
3. JC-10 — main checkout fast-forwarded after landing so later steps run the landed runner.
4. JC-13 — quote verification = normalised substring of any log entry, no keyword check.
5. JC-14 — a run is the stretch between owner pauses; turns are `next` calls; `resume` starts a new run.
6. JC-08 — shares are fractions of the quote; work shares must sum to `workFraction`, gate shares ≤ `gatesFraction`.
7. JC-31 — fence loser saves an orphan branch and resets to the remote.
8. JC-47 — landing and booking triggered inside `next`/`record`, no extra commands.
9. JC-41 — effort via `effort:` frontmatter plus `-gate` twin definitions per rung.
10. JC-67 — "plus the round folder" grants only the step's artifacts and the JC trails.

## 12. Traceability

- Mapping: no requirement→component table. `SPEC.md` §2 gives twelve design principles that "name the owner sentence it serves" by owner file (not per-sentence citations) and reference the implementing modules in prose. Every module section carries owns/depends-on/depended-on-by; every JC has an `Affects` field and 66 of 71 are tagged inline. A proposed `docs/ARCHITECTURE.md` (`16`) would hold "one section per feature sentence of the owner's SPEC.md ... naming the modules and functions" — described, not written.
- Inconsistencies flagged in the owner's files (each is a JC): `allowUpstream` comment "TODO: Implement upstream mechanics" vs the rule that every key is used (JC-06); `steps: CHAT-TO-PLAN: 0` implies a gate but no `CHAT-TO-PLAN-GATE` prose exists (JC-07); comments name `testPaths` and the carry-forward files but `project.yaml` has no such keys, against "every setting ... appears in these files" (JC-18); "hashed baseline" vs "failing test with diff" (JC-04); the "suggestion required" rule lives only in COMMON-GATE prose while code must not depend on prose (JC-30); AGENTS.md grants "the round folder" while also reserving runner state to the runner (JC-67); COMMON-STEP-END's `{{ agents.DEFINED_AND_UNDEFINED_JUDGMENT_CALLS }}` matches a `##` heading only after normalisation (JC-60); "never the producer's transcript" vs "prior findings with their resolutions" (JC-49); `maxRoundAttempts` and "bounded" with no defined base/number (JC-15, JC-16); `local.yaml` named "local" but needed by every clone (JC-51); COMMON-STEP-END called "a message produced at the end of every step" (JC-23); no LANDING prose file exists (JC-25).

## 13. Gaps against the brief

- Folder structure, other files: complete; `pyproject.toml`, `.gitignore`, `settings.json`, agent-definition template and `ci.yml` are given verbatim (`14`, `20`).
- Source files and functions: 34 modules with owns/depends headers; most signatures carry params, types, return and errors. Shortfalls: `commands.cmd_*` are listed generically ("each `-> CommandResult`"); `history.py` builders have untyped parameters; `state.py` gives 18 sub-dataclasses by name only, fields inferable from the JSON example; `prompts.Limits`, `context.SpendSummary`, `ownerlog.Log`, `checks.CheckReport`, `suite.ApplyReport`, `findings.GateOutcome` are named inline without their own entries; `next_action`, `landing`, `pauses.pause` take `world`/`lr`/`questions: list` untyped; `hooks/owner_log_hook.py` has only `main()`.
- Internal inconsistencies: `SPEC.md` §4 calls `paths` a leaf but `03` has `paths.py` "Depends on: `config`"; `judgment_calls.py`'s depends-on omits `steps` though `append_line` validates against `steps.names()`; `context.all_rounds_spend -> float` yet "the returned `SpendSummary(total, skipped)`" (`06`); `ownerlog.read -> list[Entry]` yet returns a "wrapper `Log(entries, skipped)`" (`14`); `doctor --show STEP [--gate]` (`15`) and `--debug` (`03` `main`) are absent from the CLI table/invocation line; `07` `describe` contains an unresolved authorial aside ("is generated from it by `index`? No: ...").
- Docs: nine files described by section lists and audience, not written; acceptable for the brief but `LEDGER.md`'s worked example is only named.
- Tests: 36 test files with named cases and assertions; probe test file names not given; three pairs are listed jointly (`test_state.py / test_history.py`, `test_agentdefs.py / test_install.py`, `test_doctor.py / test_index.py`) so per-file ownership of cases is approximate; no direct tests of `fake_driver.py`/`stub_agent.py`; no test named for `commands.load_world`/`parse_token_flags` beyond `test_cli.py`.
- Not specified: lint/format/type tooling; `__init__.py`; the exact text of the AGENTS.md-derived docs; how `install --python` is discovered on Windows beyond JC-40.
- Drift into line-by-line implementation: `gitops.py` prescribes exact git flags (`--force-with-lease=<b>:<sha>`, `-c core.hooksPath=/dev/null`, `status --porcelain=v1 -z --untracked-files=all`, `ls-tree -r -l`, `merge --no-ff --no-edit`); `suite.apply` prescribes source-surgery rules (import block copy, blank-line handling, numeric suffixes, empty-file deletion); `index.purpose_of` per-extension extraction rules; `schemas.extract_json` scan strategy; the full prompt layout and plumbing headings; HISTORY.md line format; hook stdout/exit rules; `verify.run` environment variables.
