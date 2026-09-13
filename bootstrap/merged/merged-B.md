# merged-B: the bootstrap plan for `shackles_harness`

Merge of the six plans in `bootstrap/plans/`, for one implementing agent in one session. "Spec files" are the files `spec.yaml` lists. "H" is `harness/` (the directory holding `project.yaml`); paths are H-relative unless absolute. "The summary" is `bootstrap/vision-harness-round-concurrency.md`. Section 1 records every consequential choice; sections 2-7 are normative; section 8 is the real-agent testing recommendation.

## 0. Facts verified on this machine (read-only probes, 2026-09-12)

- `py -3.13` = Python 3.13.2 with PyYAML 6.0.3 and pytest 9.1.1. git 2.45.2.windows.1 (the conda MinGW build); `sh.exe` is on PATH from the same conda env, but nothing below depends on it: test hooks are Python scripts with an absolute-interpreter shebang, which plan 6 verified this git runs.
- Claude Code CLI 2.1.266 at `%APPDATA%\Claude\claude-code\2.1.266\claude.exe`, **not on PATH**. `--help` lists `--print`, `--output-format`, `--model`, `--effort`, `--max-budget-usd`, `--json-schema`, `--tools`, `--disallowedTools`, `--permission-mode`, `--permission-prompts`, `--no-session-persistence`, `--system-prompt`; `--system-prompt-file` is accepted but hidden (named only in the `--bare` text); there is **no `--max-turns`**. Plans 1, 2 and 4 put `--max-turns` in their agent command; plans 5 and 6 were right.
- Git facts four plans probed and agree on: an empty-lease push prints `*` on a win, `=` with exit 0 when the branch already exists at our commit, `!` with exit 1 otherwise; `git merge-tree --write-tree` exists and lists conflicted files; `rev-parse --git-common-dir` distinguishes linked worktrees; `git branch -f main` refuses while `main` is checked out; `git init --bare` leaves HEAD on `master`; `shutil.rmtree` needs an `onexc` chmod handler.
- The worktree is at 8769287 (four commits: prose and config, `spec.yaml`, the concurrency summary, the six plans).

## 1. Decision log

Each entry: the choice, the plan(s) it came from, what was rejected and why.

1. **The runner owns mechanics, the spec owns judgment; the runner never matches a prose phrase.** All six. The only structural conventions used: `{{ ns.key }}` tokens, prose file names `<STEP>-OVERVIEW.txt` / `<STEP>-GATE.txt` / `COMMON-*.txt`, YAML keys, `roundPaths` values, the `N`-run in `roundPaths.folder`.
2. **Owner words are interpreted by the driver and delivered to the runner as commands with the exact quote.** Plan 2. Rejected: regex or first-word parsing of `approve/delegate/override/abandon` from the owner log (plans 1, 3, 4, 5, 6). The word list lives in locked prose, the prose requires "unambiguous conversational context" (a judgment call), and a renamed word would silently hang or phantom-approve a round. The runner verifies each quote against the hook-written owner log when that log exists and records it either way.
3. **The step table is code (`pipeline.py`), cross-checked against the spec's data by lint and tests.** Plans 2, 3, 4, 6 over the yaml tables of 1 and 5: a yaml table is a second source of truth whose only editor can also edit code; the cross-check (gate keys and order, prose file names, artifact keys) is what makes a structural spec change loud.
4. **Config layering: code `DEFAULTS` < `project.yaml` < `harness/local.yaml` (gitignored).** Plans 2 and 4 minus their committed runner yaml (also in 1, 5, 6): a committed defaults file duplicates `DEFAULTS`. `run.py config` prints the effective config and the source of each key.
5. **Prose is pinned at `prose_commit`; config is read from the worktree.** Plan 6. Rejected: pinning `project.yaml` and `subAgents.yaml` too (1, 3, 4): AGENTS.md freezes only prose, a live config lets the owner flip a gate in the worktree mid-round, and a sibling's landing cannot reach the worktree before LANDING anyway.
6. **Spec-change guard: `harness/tests/spec_baseline.json` (LF/BOM-normalized sha256 per file plus the accepted commit), a pytest test that fails with the categorized list and a `git diff`, `spec status|diff|accept`, an append-only `harness/archives/spec-changes.jsonl` line per acceptance, and a meta-test that runs the real test against a mutated temp copy.** Plans 1, 2, 4 (shape), 5 (jsonl audit), 6 (self-test cases). Rejected: copying every spec file into a baseline folder (6), bloat; git supplies the diff.
7. **`start` refuses on drift (`--accept-spec` folds acceptance into the start commit); an in-round spec edit is diffed into HISTORY after every `record` and forces a `spec-edit` checkpoint before LANDING regardless of delegation.** Plan 1 (start), plans 3 and 5 (in-round). Rejected: `next` blocking on drift mid-round (2): the worktree's spec only changes when the round changes it.
8. **Mechanical checks run at `record` on the uncommitted diff, and out-of-scope changes are reverted before the commit.** Plan 2 (revert), plan 6 (uncommitted diff). Rejected: cumulative `step_starts..HEAD` diffs with `mech_ok` bookkeeping in `next` (1, 3, 5): more state, and a cumulative base is exactly what made the sibling's conflict path non-convergent.
9. **A landing conflict becomes one agent attempt measured against the auto-merge tree from `git merge-tree --write-tree`.** Plans 4 and 5. Rejected: a `landing-conflict` checkpoint asking the owner to hand-merge (6): resolving a merge is a judgment call, and a delegated round would stall; the hand-merge stays available for free because an already-merged tree makes LANDING's merge a no-op. Rejected: plan 1's blob snapshot, which merge-tree replaces with one command.
10. **Landing pushes `HEAD:refs/heads/<main>`; rounds start from `origin/<main>`; local `main` is updated best-effort.** Plans 2, 4, 5, 6. Rejected: `git branch -f main` first (the summary, plan 1): it needs `main` parked, an unenforced precondition that failed late in the sibling.
11. **`sync_main` is a bounded merge-and-push loop, and `harness/archives/**/*.jsonl` carry `merge=union`.** Plan 2 (loop); the attribute is new. All six repeated the summary's claim that append-only JSONL "merges cleanly"; under git's three-way merge two rounds appending at EOF conflict. One `.gitattributes` line fixes it.
12. **Result contract: producers `DONE|NEEDS-OWNER|UPSTREAM|BLOCKED` with `resolutions` (`fixed|disputed|deferred`); gates `PASS|FAIL` with findings, rulings and `needs_owner`; the verdict is normalized to FAIL iff a blocking finding exists or the question is upheld.** Plans 2, 3, 6 (normalization); 1, 4, 6 (`deferred`). Rejected: the verdict overriding the flags (1): COMMON-GATE defines blocking by cost, so the flags are the primary datum.
13. **Invalid result JSON is saved raw, counted as an infrastructure error with its cost booked, and `record` exits 2 with "rerun the same attempt"; `infraRetries` failures raise an `infra` checkpoint.** Plan 5. Rejected: consuming the attempt with a finding (4), since a fresh agent on the same prompt is cheaper than a retry cycle; rejected: exit 2 with nothing recorded (1, 6), which loses the spend.
14. **`plumbing.GATE-PROSE` is rendered in embed mode: each prose include renders at most once per document, a nested `PROCESS-INSTRUCTIONS` renders empty, a disabled gate gets a one-line note.** Plan 4. Rejected: stripping lines made solely of include tokens (1), a rule about line layout.
15. **Prompts open with `AGENTS.md` verbatim and unrendered; inputs are paths; gates of code steps get a runner-written diff file.** Plan 1 (header), plan 3 (raw insertion after substitution), plans 2 and 6 (diff file). Read-only gates cannot run `git diff`, so the runner must.
16. **The TODO/CLARIFICATION feed to CHAT-TO-PLAN is the last N landed rounds' `POSTMORTEM.md` verbatim.** Plan 4. Rejected: `- ` lines under `## TODO`-style headings (1, 3, 5, 6), wording-dependent; rejected: separate `docs/TODO.md` files (2), a second home the prose does not name.
17. **NEEDS-OWNER with the gate disabled: checkpoint `question` unless delegated, in which case the round proceeds on the assumption and logs it to `UNDEFINED_JUDGMENT_CALLS.md`.** Plan 3. `BLOCKED` is a checkpoint (2, 3, 4, 6). `UPSTREAM` re-enters the target with finding `U1` and counts a re-entry (all six).
18. **`maxFailuresBeforeStop` is per producer step; `maxRoundAttempts` counts re-entries (UPSTREAM, out-of-band edits, L1/L2).** Plans 1, 3, 4. Rejected: a round-wide FAIL cap (2, 6): PLAN-AGENTS prose expects one or two rejections per gated step, so three in total would stop every round. Both readings are flagged to the owner (section 5).
19. **Costs: an agent run by `--cost`, else `--tokens N [--agent RUNG]` priced with the `estOutputFraction` blend, else the step budget as an estimate, always at least `spawnCost`; driver flat `driverUsdPerStep` per `record`; owner `costToWaitForOwner + ownerHourlyRate x ownerMinutesPerCheckpoint / 60` per checkpoint plus the plan and spec word charges; time computed on read; living charged once at LANDING against the tip merged.** Plans 3, 5, 6 (blend), 1 and 4 (a default for owner minutes), all (living). Rejected: transcript-cursor driver costing (4): fragile, and `driverUsdPerStep` is what the owner configured.
20. **Judgment-call files are created at start, append-only (check M4), counted per attempt and per round, and a gate's calls are appended by the runner from its verdict JSON.** Plans 3 and 5. Gates are read-only, so the prose's instruction that every step append to the files cannot be followed literally by gates; flagged to the owner.
21. **Read-only gates by construction: `.claude/agents/shackles-gate.md` with `tools: Read, Grep, Glob`, headless `--tools Read Grep Glob`, and G1 (a gate run that dirties the tree is discarded as an infrastructure error).** Plans 4, 5, 6 (definitions), 3 (G1).
22. **The driver hands a sub-agent the prompt file's path with a fixed one-line wrapper; the file is the whole, unaltered instruction.** Plan 6. Rejected: pasting the content into the task (1, 4): it doubles the driver's context per step across the 20-40 spawns of a round; "verbatim" is satisfied because nothing is altered or summarized.
23. **The headless `agentCommand` matches the installed CLI: no `--max-turns`, `--json-schema` for the result shape, `{claude}` resolved env > `local.yaml` > PATH > newest `%APPDATA%` version; `maxTurnsPerRun` is advisory text.** Plans 5 and 6. `doctor --probe-cli` makes one capped real call only when asked.
24. **Mechanics tests run against a generated minimal spec (same structure, one line of prose per file); only the real-spec tests read the owner's files.** Plan 4. Rejected: copying the real prose into every fixture (1, 3, 5, 6): a prose rewrite should fail the baseline test, not two hundred mechanics tests.
25. **Real-agent loop: stub suite, then single-step probes with clean and planted-defect seeds, then the owner's end-to-end loop in a sandbox clone, then the real repository.** All six converge; `probe`/`sandbox` from 1, 3, 6; `--manual` from 5; the replay corpus from 2, 3, 5.
26. **Cut from the bootstrap** (each appears in some plan): `prune --apply` and `clean` (the `rounds` report suffices), the `smoke` matrix (subsumed by `probe`), `spec adopt` mid-round, a `push` command (`next` pushes when the branch is ahead), `judgment-calls`/`schema`/`agents`/`log`/`cost` commands (`status`, `render` and `config` cover them), transcript costing, `ERRATA.md` (the owner's `UNDEFINED_JUDGMENT_CALLS.md` already serves that purpose), the `SessionStart` hook and `DRIVER.json`, per-extension test patterns beyond Python, `tierOverride` (use `--agent` on probes and `agentOverride` in `local.yaml`).
27. **Spec edits: the two one-token `ownerReviewCostPerWord` fixes in their own commit, the baseline taken after; no gate-language relaxation until defect probes produce data.** Unanimous.

## 2. Design

### 2.1 Principles the implementer applies everywhere

- Unknown is a warning, never a crash: a missing config key takes its default; an unresolvable token renders `[unresolved: ns.key]`; an unknown prose file is reported, not loaded; a type mismatch is a usage error naming the key.
- Every command prints exactly one JSON object on stdout; humans read stderr. Exit codes: 0 ok or finished, 1 error, 2 usage, guard refusal or invalid input, 3 check failed or spec drift, 10 checkpoint. `sys.stdout.reconfigure(encoding="utf-8")` at startup.
- Every state change is a commit on the round branch; every command is idempotent or refuses with exit 2; rerunning the command that crashed resumes.
- Windows first: argv lists (never `shell=True`), `text=True, encoding="utf-8", errors="replace"`, `PYTHONUTF8=1` for child Pythons, `Popen` plus `taskkill /T /F /PID` on timeout (`killpg` elsewhere), atomic writes (`tmp` then `os.replace`, retried five times on `PermissionError`), `shutil.rmtree(onexc=chmod_and_retry)`, `os.path.normcase` for path equality, `PurePosixPath.parts` for prefix checks (`src/` never matches `src2/`), POSIX paths in every file.
- Paths in config, artifacts, prompts, findings and STATE are H-relative; the runner alone converts to repo-relative for git and refuses a path that escapes the repository. `..` is allowed so a target project beside `harness/` can declare `../app/`. Printed actions carry absolute paths for `worktree`, `harness`, `prompt_file`, `result_file`, `diff_file`.
- Timestamps are UTC `%Y-%m-%dT%H:%M:%SZ`. JSON files are `indent=2, ensure_ascii=False`, LF, trailing newline.
- Density is charged: no docstrings restating code, no defensive code for impossible states, docs one sentence per line.

### 2.2 Layout

```
CLAUDE.md                    3 lines: read harness/AGENTS.md; drive a round per harness/docs/DRIVER.md; runner: py -3.13 harness/src/run.py --help
README.md                    what it is, quick start, how to run the suite, the four test levels and their cost
.gitignore                   .worktrees/  .claude/worktrees/  harness/OWNER.log  harness/local.yaml  harness/DRAFT-PLAN.json  __pycache__/  *.pyc  .pytest_cache/
.gitattributes               harness/archives/**/*.jsonl merge=union
pytest.ini                   testpaths = harness/tests; markers slow, real; addopts = -q -p no:cacheprovider -m "not real"
.claude/settings.json        UserPromptSubmit hook: py -3.13 harness/src/owner_log_hook.py
.claude/agents/shackles-gate.md          tools: Read, Grep, Glob; model: inherit
.claude/agents/shackles-producer.md      disallowedTools: Bash(git commit:*) Bash(git push:*) Bash(git tag:*) Bash(git reset:*) Bash(git checkout:*) Bash(git clean:*) Bash(git merge:*) Bash(git rebase:*)
spec.yaml, bootstrap/        the owner's, unchanged
harness/
  AGENTS.md project.yaml subAgents.yaml locked_prose/   spec files (two flagged one-token edits, section 4)
  INDEX.md                   routing: `alias, alias -> path`, one line each
  docs/PROCESS.md            normative rules (2.16)
  docs/DRIVER.md             driving a round from a chat session, command by command
  docs/TESTING.md            suite map, fixtures, stub modes, probes, baseline procedure
  src/run.py                 shim: insert src on sys.path; from shackles.cli import main; sys.exit(main())
  src/owner_log_hook.py      stdlib-only hook script
  src/shackles/              cli.py config.py pipeline.py render.py contract.py schemas.py procs.py gitops.py
                             ledger.py checks.py owner.py round.py landing.py specguard.py agents.py doctor.py
  src/shackles/plumbing/     producer.txt gate.txt CHAT-TO-PLAN.txt and optional <STEP>.txt extras
  tests/                     conftest.py fixtures.py stub_agent.py spec_baseline.json spec_waivers.json test_*.py
  tests/fixtures/spec/       generated minimal spec template (2.17)
  tests/fixtures/toy/        the toy project (src/toy/text.py, tests/toy/test_text.py)
  tests/fixtures/canned/     the stub's artifacts per step
  tests/fixtures/defects/    planted-defect artifacts per gate with expect.json
  tests/fixtures/replays/    real RESULTS/ and artifacts copied from paid runs (empty at delivery)
  archives/rounds/NNNN/      round folders, exactly project.yaml roundPaths
  archives/rounds/index.jsonl   one line per finished or abandoned round
  archives/spec-changes.jsonl   one line per baseline acceptance
```

Sizes to aim for: runner about 1,800 lines with no module over 400; plumbing about 100; tests about 1,800; docs about 250. Everything under `harness/src`, `harness/docs`, `harness/tests` is living and charged per token from the first real round on.

### 2.3 Configuration (`config.py`)

`load(harness_root)` returns one mapping built as `DEFAULTS` updated by `project.yaml` updated by `local.yaml` (if present); the roster comes from the file named by `subAgentsFile` (default `subAgents.yaml`) as `cfg.agents[rung]`. Unknown keys are kept and exposed to templates. Every key the runner reads is in `DEFAULTS` with today's value from `project.yaml`, so a sibling landing a new key never breaks an in-flight round.

Derived: `cfg.id_width` = length of the longest `N`-run in the last component of `roundPaths.folder` (default 4); `cfg.gates` = ordered `{name: bool}` from `project.gates` (absent gate = disabled, non-0/1 coerced by truthiness with a warning); `cfg.round_folder(id)`, `cfg.artifact(key)`, `cfg.living_paths()` from `roundPaths`, `livingSourcePaths`, `lockedProsePath`, `archivesPath`; `cfg.rung(key)` with fallback to `maxAgent` then the first roster key, each fallback a warning.

Runner-owned keys in `DEFAULTS` (any may be set in `project.yaml` or `local.yaml`):

```yaml
mainBranch: main
worktreeDir: .worktrees            # repo-relative; must be gitignored (start refuses otherwise)
pushAttempts: 5                    # bounds the claim loop, the landing push loop and sync_main
infraRetries: 3
checkpointsAfter: [PLAN-TO-SPEC-GATE, CLEANUP]   # review checkpoints; the plan's approval is `start` itself
ownerMinutesPerCheckpoint: 10      # attention estimate priced at ownerHourlyRate
minRunUsd: 1.0                     # floor of a run's hard cap
promptTokenWarn: 60000             # W2 above this (bytes / tokenBytes)
postmortemFeedRounds: 3            # postmortems fed to CHAT-TO-PLAN
findingQuoteMaxChars: 600
testFunctionPattern: '^\s*(async\s+)?def\s+test_\w+'
suiteCommand: [py, -3.13, -m, pytest, -q, tests, -m, "not real"]   # cwd = H; the permanent suite
suiteTimeoutSeconds: 1800
agentCommand: ["{claude}", --print, --output-format, json, --system-prompt-file, "{prompt_file}", --model, "{model}",
               --effort, "{effort}", --max-budget-usd, "{budget_cap_usd}", --json-schema, "{result_schema}",
               --no-session-persistence, "{tool_flags}", --permission-mode, bypassPermissions, "{task}"]
agentTask: "Do the task in your system prompt. Your final message must be exactly the JSON object it specifies."
claudePath: null                   # null: SHACKLES_CLAUDE env, then PATH, then newest %APPDATA%\Claude\claude-code\*\claude.exe
gateToolFlags: [--tools, Read, Grep, Glob]
producerToolFlags: [--disallowedTools, "Bash(git commit:*)", "Bash(git push:*)", "Bash(git tag:*)", "Bash(git reset:*)", "Bash(git checkout:*)", "Bash(git clean:*)", "Bash(git merge:*)", "Bash(git rebase:*)"]
scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]
modelAliases: {claude-fable-5-1: fable, claude-opus-5: opus, claude-sonnet-5: sonnet}   # Agent-tool model names
gitIdentity: {name: shackles-runner, email: runner@shackles.local}
envelopePrefixes: ["<system-reminder", "<task-notification", "[SYSTEM NOTIFICATION", "<wake ", "<webhook-payload", "<event "]
agentOverride: null                # local.yaml: force one rung for every step (cheap real runs)
```

Owner keys and their single meaning: `budget` (project target; `project.remaining` = budget minus the project-wide tally), `hardStopBudgetMultiple` (round hard stop at multiple x quote; also the per-run cap multiple), `lostValuePerHour` (time cost), `ownerHourlyRate` and `costToWaitForOwner` (per checkpoint), `planCostPerWord` and `specCostPerWord` (once each, 2.11), the living-token keys and `testBaseCost`, `tokenBytes` (2.11), `maxRefactorOverhead` (SPEC rule in S1), `gates`, `defaultShares`, `gatesFraction`, `workFraction` (2.11), the path keys, `maxSimultaneousSubAgentsPerRound` (AGENTS-PLAN rule; enforced by instruction), `maxRoundAttempts` (re-entry cap), `maxFailuresBeforeStop` (per-step cap), `maxTurnsPerRun` (advisory), `maxRunWallClockHours` (headless timeout), `verifyTimeoutSeconds`, `estOutputFraction` (token pricing blend), `driverUsdPerStep`, `subAgentsFile`, `maxAgent`, `gateAgent`, `systemTestAgent` (probe and e2e default rung), `currency` and `shackles` (rendered only).

### 2.4 Pipeline (`pipeline.py`)

`PIPELINE` is an ordered list of `Step(name, kind, artifact, writes, checks, on_accept)`; kinds `plan` (done by the driver before `start`), `approval` (mechanical), `producer` (JSON or prose artifact), `code` (a producer whose artifact is a diff), `gate`, `landing`. Lookups other modules use: `step(name)`, `producer_of(gate)`, `gate_of(producer)`, `index(name)`, `earlier_producers(name)`, `next_after(name)`.

| # | Step | Kind | Artifact (`roundPaths` key) | Writes | Checks at record | On acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | CHAT-TO-PLAN | plan | `plan` | round | PLAN schema (at `start`) | |
| 2 | CHAT-TO-PLAN-GATE | approval | | | approval block present when enabled | plan word charge |
| 3 | PLAN-AGENTS | producer | `agentsPlan` | round | S1 | |
| 4 | PLAN-AGENTS-GATE | gate | | | | |
| 5 | PLAN-TO-SPEC | producer | `spec` + `specProse` | round | S1, W1 | spec word charge |
| 6 | PLAN-TO-SPEC-GATE | gate | | | | review checkpoint |
| 7 | SPEC-TO-TESTS | code | diff | `testPaths` | M1 | |
| 8 | SPEC-TO-TESTS-GATE | gate | | | | freeze: `tests_frozen_at = HEAD` |
| 9 | SPEC-TO-IMPLEMENTATION | code | diff | `implPaths` (+ conflicted files on a merge attempt) | M1 M2 M3 (L3 on a merge attempt) | |
| 10 | SPEC-TO-IMPLEMENTATION-GATE | gate | | | | |
| 11 | TESTS-TO-SUITE | producer | `suite` | round | S1 S2 | archive move (`git mv` each `archive` path into `testsArchive/`, collisions get a numeric suffix) |
| 12 | TESTS-TO-SUITE-GATE | gate | | | | |
| 13 | CLEANUP | code | diff | `implPaths` + living paths minus `testPaths` + `INDEX.md` | M1 M2 M3 M5 | review checkpoint (pre-landing) |
| 14 | LANDING | landing | | | L1 L2 | living charge, tag, `landed_at` |
| 15 | POSTMORTEM | producer | `postmortem` | round | non-empty file | |
| 16 | POSTMORTEM-GATE | gate | | | | finish: index line, `sync_main` |

"Acceptance" of a producer X is X-GATE's PASS, or X's DONE passing its checks when X-GATE is disabled or overridden. Every on-acceptance effect and every `checkpointsAfter` entry hangs on acceptance.

Rules:
- A gate runs iff `cfg.gates[name]` is true, `locked_prose/<name>.txt` exists at `prose_commit`, and it is not overridden; otherwise it is skipped with a HISTORY line and `FINDINGS/<GATE>-<n>.json` = `{"verdict": "PASS", "findings": [], "source": "disabled|override|no-prose"}` so the archive shape is uniform. Mechanical checks still run.
- A producer with no `<NAME>-OVERVIEW.txt` at `prose_commit` is a `start` error naming the file ("restore it or override the step"); a gate with `gates: 1` and no prose file is disabled with a warning.
- Overridable: every gate, PLAN-AGENTS (defaults: `defaultShares`, `maxAgent`, `gateAgent`), SPEC-TO-TESTS (no tests; the frozen set is empty), TESTS-TO-SUITE (keep every test), CLEANUP (skipped; the pre-landing checkpoint still applies), POSTMORTEM (the round finishes after LANDING). Not overridable: CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, PLAN-TO-SPEC, SPEC-TO-IMPLEMENTATION, LANDING.
- Lint (run by `doctor`, strictly by `start`, as warnings elsewhere): every key of `project.gates` names a pipeline gate and the keys appear in pipeline order; every pipeline gate is a key of `project.gates`; every `locked_prose/*.txt` is `COMMON-*` or names a pipeline step; every `roundPaths.artifacts` key the table uses exists; `maxAgent`, `gateAgent`, `systemTestAgent` are roster keys; `checkpointsAfter` names pipeline steps; every listed spec file exists; `worktreeDir` is ignored; the hook is configured. A structural change the owner makes therefore shows up in `doctor`, at `start`, and in the spec-structure test (3.4).

### 2.5 Rendering (`render.py`, `contract.py`)

Grammar: `\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}`. Namespaces:
- `prose.NAME`: `locked_prose/NAME.txt` read with `git show <prose_commit>:<path>` when a round exists, from the working tree otherwise; rendered recursively; depth 8; a cycle renders `[cycle: NAME]`. Each prose file renders at most once per document; a second include renders empty.
- `plumbing.PROCESS-INSTRUCTIONS`: `plumbing/producer.txt` or `gate.txt` by kind, followed by `plumbing/<STEP>.txt` when it exists, rendered with the same context. `plumbing.GATE-PROSE` in a producer's prompt: the producer's gate file rendered in embed mode (includes already present render empty, a nested `PROCESS-INSTRUCTIONS` renders empty); prefixed by `(This gate is disabled this round: a DONE that passes the mechanical checks is accepted. The standard below still applies.)` when disabled or overridden; for a mechanical gate, one runner sentence describing it. Any other `plumbing.X` renders `plumbing/X.txt` if present.
- `project.*`: every config key with dotted access, plus `remaining`, `spent`, `agents` (the roster as compact JSON).
- `round.*`: `id` (padded), `number`, `folder`, `worktree` (absolute), `harness_root` (absolute), `branch`, `base_commit`, `prose_commit`, `plan` (PLAN.json rendered as text: summary, then Scope, Validation, Non-goals, Assumptions as bullets, then the quote and the todos; extra keys as JSON), `budget`, `spend`, `remaining`, `status`, `step`, `history` (index rows as `round N: quoted X actual Y (outcome)`, last 5), `postmortems` (the POSTMORTEM.md of the last `postmortemFeedRounds` landed rounds, oldest first, each under `## round NNNN`, or `none`), `judgment_files` (both absolute paths), `judgment_calls` (both files' text), `owner_log` (this round's slice). Before a round exists every `round.*` except `history`, `postmortems`, `remaining` renders `n/a`.
- `step.*`: `name`, `kind`, `attempt`, `budget`, `budget_cap`, `max_turns`, `wall_clock_hours`, `retry_cost`, `agent` (rung), `model`, `model_alias`, `effort`, `producer`, `gate`, `gate_enabled`, `artifact`, `artifact_contract` (generated from the schema), `diff_file`, `result_file`, `prompt_file`, `write_paths`, `frozen_paths`, `inputs` (paths), `checks` (ids with one-line meanings), `findings` (open findings with resolutions and rulings as JSON, or `none`), `carried` (non-blocking findings and owner answers, or `none`), `previous` (the previous final message or `none`), `question`, `sub_agents`, `conflicts`, `next_finding_id`, `after_done`, `after_needs_owner`, `after_pass`.

Values: strings verbatim; ints as is; floats via `repr` with a trailing `.0` stripped; bools `true`/`false`; None `none`; lists and dicts compact JSON with `ensure_ascii=False`. Unresolved tokens render `[unresolved: ns.key]`, are collected, printed to stderr, written to HISTORY as `FLAG (runner): unresolved ...`, and reported by `doctor`. Raw text (AGENTS.md, artifacts, diffs) is inserted after substitution so tokens inside it never expand.

A prompt is: `harness/AGENTS.md` verbatim, a blank line, then the rendered `<STEP>-OVERVIEW.txt` (producers) or `<STEP>-GATE.txt` (gates). If the prose has no `plumbing.PROCESS-INSTRUCTIONS` token the block is appended after a blank line (lint warns). The prompt is written to `PROMPTS/<STEP>-<attempt>.txt`; for the gate of a code step the runner also writes `PROMPTS/<GATE>-<attempt>.diff` = `git diff <step_starts[producer]> HEAD -- <declared paths>`. A prompt over `promptTokenWarn` tokens gets warning W2 in the action and HISTORY; nothing is truncated (inputs are paths, so prompts stay small).

`plumbing/producer.txt` (machine-readable lines are the `KEY:` lines; the last occurrence wins):

```
PROCESS INSTRUCTIONS (mechanical; generated and parsed by the runner; follow exactly).
STEP: {{ step.name }}
KIND: producer
ROUND: {{ round.id }}
ATTEMPT: {{ step.attempt }}
WORKTREE: {{ round.worktree }}
HARNESS: {{ round.harness_root }}
ARTIFACT: {{ step.artifact }}
RESULT_FILE: {{ step.result_file }}
WRITE_PATHS: {{ step.write_paths }}
FROZEN_PATHS: {{ step.frozen_paths }}
MERGE_IN_PROGRESS: {{ step.conflicts }}
Paths here are relative to HARNESS unless absolute; use absolute paths in tools. Budget for this run: ${{ step.budget }}, a target. Turns: about {{ step.max_turns }}. Wall clock: {{ step.wall_clock_hours }} h. Sub-agents you may run at once: {{ step.sub_agents }}; their cost is yours.
Inputs, by path: {{ step.inputs }}
Findings to resolve (every id must appear in your resolutions as fixed, disputed or deferred; a settled id cannot be disputed): {{ step.findings }}
Carried notes and owner answers: {{ step.carried }}
Your previous final message: {{ step.previous }}
Rules: create or change files only under WRITE_PATHS and the round folder {{ round.folder }}; never change FROZEN_PATHS; never run git commit, push, tag, reset, checkout, clean, merge or rebase, the runner commits your work; do not write RESULT_FILE, the driver saves your final message there. Files listed in spec.yaml are the owner's: change one only when genuinely necessary and minimally; the runner shows the owner the diff before the round lands. Append one line per judgment call to {{ round.judgment_files }}; never rewrite their existing lines.
Artifact: {{ step.artifact_contract }}
Checked mechanically before any gate: {{ step.checks }}. A failure returns to you as a finding without spending a gate.
Final message: exactly one JSON object and nothing else:
{"status": "DONE" | "NEEDS-OWNER" | "UPSTREAM" | "BLOCKED", "notes": "<one paragraph>", "question": "<NEEDS-OWNER: the question and the value at stake>", "assumption": "<NEEDS-OWNER: what you built on meanwhile>", "target": "<UPSTREAM: the earlier producer step whose artifact is wrong; quote the contradiction in notes>", "narrow": "<BLOCKED: what to narrow>", "resolutions": {"<id>": {"status": "fixed" | "disputed" | "deferred", "reason": "<why>"}}, "judgment_calls": {"defined": <count>, "undefined": <count>}}
Omit fields that do not apply. Then: DONE -> {{ step.after_done }}. NEEDS-OWNER -> {{ step.after_needs_owner }}. UPSTREAM -> the round returns to the target step with your notes as a finding. BLOCKED -> the round pauses for the owner.
```

`plumbing/gate.txt` differs in: `KIND: gate`, a `DIFF_FILE:` line, no write lines; then `You are read-only: read anything under WORKTREE, write nothing, run nothing that changes files; a run that changes files is discarded. You never see the producer's transcript.`; `Inputs, by path:`; `Already checked mechanically: {{ step.checks }}. Do not repeat them.`; `Prior findings with the producer's resolutions and rulings: {{ step.findings }}`; `The producer's question, if any: {{ step.question }}`; `The producer's final message: {{ step.previous }}`; `A FAIL costs ${{ step.retry_cost }} (the producer's retry) plus this gate again.`; then:

```
Final message: exactly one JSON object and nothing else; the driver saves it to RESULT_FILE:
{"verdict": "PASS" | "FAIL", "findings": [{"id": "F<n>", "quote": "<verbatim text judged>", "reason": "<why>", "suggestion": "<what would prevent the FAIL>", "blocking": true | false}], "rulings": {"<id>": {"status": "upheld" | "withdrawn", "quote": "<verbatim text>"}}, "needs_owner": {"status": "upheld" | "withdrawn", "reason": "<why; if withdrawn, the answer to assume>"}, "notes": "<one line>", "judgment_calls": {"defined": ["<one line each>"], "undefined": ["<one line each>"]}}
Omit rulings, needs_owner and judgment_calls when empty. Ids continue from {{ step.next_finding_id }}. Verdict is FAIL exactly when a finding is blocking or needs_owner is upheld. Then: PASS -> {{ step.after_pass }}. FAIL -> the producer runs again with your findings, then this gate again.
```

`plumbing/CHAT-TO-PLAN.txt` (rendered by `render --step CHAT-TO-PLAN` without a round): you are the driver in the owner's chat; inputs are `round.history`, `round.postmortems`, `project.remaining`; write PLAN.json (schema PLAN) to `harness/DRAFT-PLAN.json` with `presented_at` set when the plan is shown; when the owner's words approve or delegate, fill `approval` (`mode`, `through`, `overrides`, `words` verbatim) and run `py -3.13 harness/src/run.py start --plan harness/DRAFT-PLAN.json`; then follow `docs/DRIVER.md`. Its `GATE-PROSE` is the runner sentence `CHAT-TO-PLAN-GATE is mechanical: start validates PLAN.json and requires the owner's word recorded in it.`

Per-step extras (`plumbing/<STEP>.txt`, a few lines each): PLAN-AGENTS (the roster, the step list with gate flags, the pies, the sub-agent cap); PLAN-TO-SPEC (SPEC.json fields, `verify` run from H, `implPaths`/`testPaths` disjoint, `refactor` items within the cap, `nonGoals` carried verbatim, body `SPEC.md`, sibling declared paths); SPEC-TO-TESTS (write only under `testPaths`; tests freeze at acceptance); SPEC-TO-IMPLEMENTATION (tests are frozen; verify must pass within its timeout; on a merge attempt resolve exactly the listed files, keep both intents, do not run git merge or commit); TESTS-TO-SUITE (`keep`/`archive` partition of every test file changed this round; archived files move to `tests-archive/`); CLEANUP (verify and the permanent suite must be green); POSTMORTEM (inputs: HISTORY.md, FINDINGS/, RESULTS/, both judgment files, the owner-log slice, STATE.json spend versus quote; output POSTMORTEM.md).

`contract.STATUSES` and `contract.VERDICTS` hold the words; a spec-structure test asserts each appears somewhere in the locked prose so a rename by the owner fails a test instead of silently diverging.

### 2.6 Schemas (`schemas.py`)

A hand-written validator (`required`, `properties`, types `str int number bool list dict`, `enum`, `minimum`, `minItems`, `additionalProperties` default true) returning `["NAME: <path> <problem>", ...]`; no jsonschema dependency; the same dicts are emitted as JSON Schema for `--json-schema`.

- PLAN: required `presented_at`, `quote_usd` (> 0), `summary`, `scope[]`, `validation[]`, `non_goals[]`; optional `assumptions[]`, `todos{}`, `approval{mode: approved|delegated, through, overrides[], words}`, `owner_words[]`, `provided_artifacts{artifactKey: path}`; `round` set by `start`. Rules at `start`: `approval` present when CHAT-TO-PLAN-GATE is enabled; `overrides` name overridable steps; `through` names a pipeline step; every overridden producer that needs an artifact has a valid `provided_artifacts` entry.
- AGENTS_PLAN: required `round`, `agents{STEP: rung}`, `shares{work{STEP: f}, gates{STEP: f}}` (gates keyed by the producer's name, as `defaultShares` is); optional `gateAgents{GATE: rung}`, `subAgents{STEP: int}`, `notes`. Rules: rungs exist; each pie sums to 1 +/- 0.01 over present steps; `subAgents` <= `maxSimultaneousSubAgentsPerRound`.
- SPEC: required `round`, `summary`, `verify` (str or list), `implPaths[]` (non-empty), `testPaths[]`, `nonGoals[]`; optional `verifyTimeoutSeconds`, `refactor[{what, budget_usd}]`, `testPlan`. Rules: paths inside the repo, prefix-disjoint, none inside the round folder or `lockedProsePath` or a spec file; sum of `refactor[].budget_usd` <= `maxRefactorOverhead x budget_usd`; `SPEC.md` exists and is non-empty.
- SUITE: required `round`, `keep[]`, `archive[]`, `notes`; optional `raise_with_owner[]`. Rule S2: every test file changed since `base_commit` under `testPaths` appears in exactly one list; listed paths exist.
- POSTMORTEM.md: non-empty (no heading checks).
- RESULT and FINDINGS: as in 2.5; a FINDINGS `target` must be an earlier producer; ids must be unique within a verdict (duplicates are renamed `<GATE>-<n>.F<k>` with a HISTORY note).
- STATE: 2.7, validated on every save.

Result extraction (`agents.extract_json`): the whole message; then the last ```` ``` ```` fence; then the last balanced top-level `{...}`. Normalization with a HISTORY note when applied: verdict := FAIL iff any blocking finding or `needs_owner.upheld`; a finding without `suggestion` gets `(none given)`; a new finding whose whitespace-normalized quote equals a withdrawn finding's is dropped; quotes over `findingQuoteMaxChars` are truncated.

### 2.7 Data model

Round folder = `roundPaths` with the `N`-run replaced by the padded id; every file name comes from `roundPaths`. Runner-owned (agents may not write them; a change is reverted by M1): `STATE.json`, `HISTORY.md`, `OWNER.log`, `PROMPTS/`, `RESULTS/`, `FINDINGS/`, `tests-archive/`. Agents write artifacts and append to the two judgment-call files, which `start` creates with one header line each (not counted).

`STATE.json` (the runner's only state; `Round.save()` validates):

```
round int, id "NNNN", branch, mode worktree|no-branch, created_at, status active|checkpoint|finished|abandoned,
step, attempt_pending null|{step, attempt, prompt_commit}, attempts{step:int}, failures{step:int}, infra_errors{step:int},
round_retries int, step_starts{step:sha}, step_commits{step:sha}, inputs_hash{PLAN, SPEC}, budget_usd,
spend{entries[], agent_usd, driver_usd, owner_usd, living_usd}, base_commit, prose_commit,
approval{mode, through, words, at, source}, overrides[], checkpoint null|{kind, step, at, question, artifact, message},
pending_question null|{question, assumption}, findings_ledger{id:{step, attempt, quote, blocking, status open|fixed|disputed|withdrawn|settled|deferred, upholds}},
last_findings{producer:[paths]}, carried[] (non-blocking findings and owner answers), tests_frozen_at null|sha,
merge_pending null|{target_sha, automerge_tree, conflicted[]}, resume_step null|step, spec_edits[],
hard_stop_raised bool, round_limit_raised bool, landed_at, abandoned_at, main_before, judgment_calls{defined, undefined}, runner_commit
```

No worktree path (derivable), no lock, lease, pid or owner field: ownership is "can I still push this branch".

`HISTORY.md` is append-only: `## <UTC> <STEP> attempt <n>: <status or verdict>` with the agent's notes (capped at 2,000 chars), cost and source, finding ids, judgment-call deltas; `## <UTC> CHECKPOINT <kind> at <STEP>` with the message; `## <UTC> RESUME <command> quote: <words>`; `## <UTC> LANDING ...`; `## <UTC> SPEC EDIT` with a fenced diff; single `FLAG (runner|driver): ...` lines for anomalies.

Ledger entries `{at, step, attempt, usd, source, note}`; sources `agent-cli|agent-tokens|agent-estimate|driver|owner|living`; buckets recomputed on append; `time_usd` = hours from `created_at` to `landed_at`/`abandoned_at`/now x `lostValuePerHour`, computed on read; `total_usd` = buckets + time.

`archives/rounds/index.jsonl` line: `{id, quote_usd, spend{agent_usd, driver_usd, owner_usd, living_usd, time_usd, total_usd}, attempts, failures, round_retries, judgment_calls, outcome landed|abandoned, prose_commit, landed_at|abandoned_at}`, appended at finish or abandon on the round branch.

### 2.8 CLI (`py -3.13 harness/src/run.py [--root DIR] [--round N] <command>`)

`--root` is the repo root or a round worktree (default: the nearest ancestor of cwd containing `spec.yaml`); `--round` is inferred from the branch `round/<id>`, else the single unfinished round folder, else required.

| Command | Does | Writes |
| --- | --- | --- |
| `doctor [--probe-cli] [--json]` | environment, config, lint, spec drift, hook, `claude` resolution, renders every prompt on a fixture round and lists unresolved tokens, runner skew, live worktrees | nothing; exit 1 on errors |
| `config` | effective config with the source of each key | nothing |
| `render --step S [--attempt N] [--fixture]` | a prompt without side effects (CHAT-TO-PLAN needs no round) | stdout |
| `spec status|diff|accept [--note T]` | the spec-change guard (2.13) | baseline and audit line on accept |
| `start --plan F [--budget USD] [--branch NAME] [--no-branch] [--delegate [--through STEP]] [--accept-spec] [--agent RUNG]` | validate, claim, worktree, round folder, first commit and push; prints `{round, folder, branch, worktree, runner, record_hint}` | origin claim, worktree, round folder |
| `next [--discard] [--no-push]` | mechanical work until an agent run is due; prints an action, a checkpoint (exit 10) or `done` | round folder, commit |
| `record --step S --attempt N --result F [--cost USD | --tokens N [--agent RUNG]] [--spawns K] [--no-push]` | validate, checks, route, ledger, commit and push (the fence) | RESULTS/, FINDINGS/, STATE, HISTORY |
| `approve --quote T` / `delegate [--through STEP] --quote T` / `answer --text T --quote T` / `override --steps A,B --quote T` / `abandon --reason R --quote T` (all accept `--unverified`) | owner-driven transitions (2.9) | STATE, OWNER slice, HISTORY, commit and push |
| `status [--json]`, `spend [--project]`, `rounds` | read-only; `rounds` lists local folders, origin `round/*` branches, worktrees, tags and claimed-but-empty ids | nothing |
| `check` | the current step's mechanical checks, or the landing check phase at LANDING; nothing recorded | nothing shared (exit 3 on findings) |
| `run --until checkpoint|step|done [--no-push]` | headless loop: next, agent command, record | as above |
| `probe --step S [--seed clean|defect] [--agent RUNG] [--budget USD] [--manual]`, `probe --changed`, `probe --check RESULT_FILE` | one real agent on one canned step (section 8); `--changed` probes only the steps whose prose the baseline reports changed | a temp repo |
| `sandbox --dir D` | a temp clone with a local bare origin, the harness copied in, the toy project as target; prints the paths | D |

Action JSON (`kind: producer|gate`): `{round, step, kind, attempt, prompt_file, result_file, artifact, diff_file, agent, agent_type, model, model_alias, effort, budget_usd, budget_cap_usd, max_turns, wall_clock_hours, sub_agents, tools, worktree, runner, record_command, spend, warnings[]}`. Checkpoint JSON (exit 10): `{kind: checkpoint, checkpoint: {kind, step, at, question, artifact}, message, resume: [exact commands], spend}`. Done JSON: `{kind: done, status, main_synced, spend, hint}`. `record_command` is the exact next `record` line and `message` the exact text to relay: the driver's freedom is spawning and relaying.

### 2.9 Protocol

**Planning (driver, in chat).** `render --step CHAT-TO-PLAN`, converse, write PLAN.json with `presented_at`; when the owner speaks, fill `approval` and run `start`.

**`start`**, in order:
1. Lint strictly; refuse on spec drift unless `--accept-spec` (the error carries the categorized list and the two commands).
2. Validate the plan (schema and the `start` rules) before any git command, so a bad plan creates nothing. If CHAT-TO-PLAN-GATE is disabled and `approval` is absent, record `{mode: approved, source: gate-disabled}` (checkpoints on); `--delegate` sets `delegated` (`through` optional). If `<main_root>/harness/OWNER.log` exists and `approval.words` is set, the words (whitespace-normalized) must occur in a line dated >= `presented_at`, else exit 2 (`--unverified` overrides with a FLAG).
3. Preconditions unless `--no-branch`: `git check-ignore -q <worktreeDir>`; origin reachable (`git ls-remote --exit-code origin HEAD`); worktree path and local branch absent. Without an origin and without `--no-branch`: refuse.
4. Claim (2.12) and `git worktree add -b round/NNNN <main_root>/<worktreeDir>/NNNN origin/<main>`. `--no-branch`: id = highest local folder + 1, current checkout, no fetch, CAS, worktree or push.
5. With the worktree as root: create the folder and `PROMPTS/ RESULTS/ FINDINGS/` (`.keep`), PLAN.json (`round` set), provided artifacts, the two judgment files with headers, STATE (`base_commit = prose_commit = HEAD`, step CHAT-TO-PLAN-GATE, `attempts {CHAT-TO-PLAN: 1}`, `runner_commit`), HISTORY, the OWNER.log slice from `owner_since = min(previous round's landed/abandoned_at, presented_at)`, ledger entries: CHAT-TO-PLAN's default share as `agent-estimate`, `driver`, and `planCostPerWord x words(round.plan)`. With `--accept-spec`, the rewritten baseline and its audit line. `git add -A`, commit `round NNNN: start`, `git push -u origin round/NNNN`. Print one line.

**`next`**, in order:
1. `finished|abandoned` -> `sync_main` -> `done`.
2. If the branch is ahead of its upstream (a previous push failed), push now; a rejection is the fence error.
3. Out-of-band edits: re-hash PLAN.json and SPEC.json + SPEC.md. PLAN changed -> step CHAT-TO-PLAN-GATE, approval cleared (the driver re-approves with a new quote), downstream counts reset, `round_retries += 1`, HISTORY. SPEC changed after PLAN-TO-SPEC's acceptance -> step SPEC-TO-TESTS, downstream reset, `round_retries += 1`.
4. Tree state: (a) `MERGE_HEAD` present and not the expected merge attempt (`merge_pending` and `attempt_pending` for SPEC-TO-IMPLEMENTATION) -> `git merge --abort`, infra error. (b) Expected merge attempt already established -> re-print the action (step 9). (c) Dirty with `attempt_pending` and every dirty path inside that step's write paths plus the round folder -> exit 2 `uncommitted work for STEP attempt N: record it, or next --discard`. (d) Otherwise dirty -> `git checkout -- <H> <living paths>` and `git clean -fdq -- <H> <living paths>` (scoped, never the whole tree; never `-x`), `infra_errors[step] += 1`, HISTORY.
5. Refresh the OWNER.log slice from `<main_root>/harness/OWNER.log` when it exists.
6. Time accrual is computed, not stored; hard stop: `total_usd > hardStopBudgetMultiple x budget_usd` and not raised -> checkpoint `hard-stop`.
7. `status == checkpoint` -> print it, exit 10.
8. Loop over mechanical work: CHAT-TO-PLAN-GATE (validate approval; advance); a disabled or overridden gate (skip file, acceptance effects, advance); an overridden producer (skip with defaults, advance); a `checkpointsAfter` step just accepted and not delegated through -> checkpoint `review` (`artifact` = the spec files, or `git diff --stat base..HEAD -- <living paths>` for the pre-landing one); `spec_edits` non-empty and step == LANDING -> checkpoint `spec-edit` regardless of delegation; LANDING (2.12); `round_retries > maxRoundAttempts` and not raised -> checkpoint `round-limit`.
9. For the first step that needs an agent: attempt = `attempts[step] + 1`; `step_starts[step]` = HEAD if unset; render the prompt (and the diff file for a code gate); set `attempt_pending {step, attempt, prompt_commit}`; save; commit `round NNNN: STEP attempt N prompt` (no push); if `merge_pending` and step == SPEC-TO-IMPLEMENTATION: `git merge --no-commit --no-ff <target_sha>` (leaves the conflicted tree); print the action, exit 0. When `attempt_pending` already names this attempt (a crash or an infra error after the prompt commit), nothing is re-rendered or committed, but a pending merge that is not established is re-established before the action is printed.

**`record`**, in order:
1. Guard: `status == active`, `step == S`, `N == attempts[S] + 1`, `attempt_pending == {S, N}`; else exit 2 with the reason (replays and out-of-order records are refused, never double-applied).
2. Read the result file; extract JSON; validate RESULT or FINDINGS. Failure: save `RESULTS/<S>-<N>.raw.txt`, `infra_errors[S] += 1`, book the cost, commit, exit 2 `rerun the same attempt`; after `infraRetries` at the same attempt raise checkpoint `infra`. Otherwise copy to `RESULTS/<S>-<N>.json`.
3. Ledger: agent entry (`--cost` > `--tokens` priced by the rung (`--agent`, default the action's) with `spawnCost x --spawns` added > estimate = the step budget, flagged), floor `spawnCost`; driver entry.
4. M0: HEAD moved since `prompt_commit`. Normal attempt: `git reset --soft <prompt_commit>`, FLAG, continue. Merge attempt: infra error, `git merge --abort`, tree reset, exit 2 (the next `next` re-establishes the merge).
5. G1 (gates): a dirty tree -> reset, infra error, exit 2. Gates' `judgment_calls` lines are appended to the files by the runner with the suffix ` (via runner, <GATE>-<n>)`.
6. Producer DONE: apply `resolutions` to the ledger (a `disputed` on a settled id is ignored with a HISTORY note; `deferred` marks the finding deferred and carries it to POSTMORTEM); M4 (judgment files only grew); E1 (spec files changed: fenced diff to HISTORY, `spec_edits`); then the step's checks (2.10) on the uncommitted diff, reverting out-of-scope paths; `git add -A`; commit `round NNNN: S attempt N` (a merge commit on a merge attempt). Findings -> `FINDINGS/<S>-<N>.mechanical.json`, `failures[S] += 1`, `last_findings`, re-enter S at N+1, limit check. Clean -> `step_commits[S] = HEAD`; W1 at PLAN-TO-SPEC; acceptance effects when the gate is disabled; advance (to `resume_step` when set).
7. Producer NEEDS-OWNER: `pending_question`; gate enabled -> advance to the gate; disabled and not delegated -> checkpoint `question`; disabled and delegated -> append `- <S> attempt <N> assumed: <assumption> (runner: gate disabled, delegated)` to UNDEFINED_JUDGMENT_CALLS.md, HISTORY, continue as DONE.
8. Producer UPSTREAM: `target` must be an earlier producer (else finding S1 to S); `git merge --abort` if merging; finding `U1` (quote = notes) attached to the target; reset downstream `attempts`, `failures`, `step_starts`, `step_commits`, `last_findings`, `tests_frozen_at` (if the target is at or before SPEC-TO-TESTS), `merge_pending`, `resume_step`; `round_retries += 1`; target CHAT-TO-PLAN -> checkpoint `upstream-plan`.
9. Producer BLOCKED: finding `B1` (quote = narrow), `failures[S] += 1`, checkpoint `blocked`.
10. Gate: apply `rulings` (upheld: `upholds += 1`, settled at 2; withdrawn: closed, never re-raised); write `FINDINGS/<GATE>-<N>.json`; `needs_owner.upheld` -> checkpoint `question` (never skipped by delegation); `needs_owner.withdrawn` -> finding `Q1` (the answer to assume) carried to the producer. PASS -> `step_commits[GATE] = HEAD`, non-blocking findings to `carried`, acceptance effects, advance (or `resume_step`). FAIL -> `failures[producer] += 1`, `last_findings`, step = producer, limit check.
11. Limits: `failures[producer] >= maxFailuresBeforeStop` -> checkpoint `failure-limit`.
12. Save, append HISTORY, commit, push `origin round/NNNN` (non-forced). Rejected as non-fast-forward -> `RunnerError("another runner owns this round (push rejected)")`, exit 1; any other push failure -> exit 1 naming `next` (which pushes when ahead). Finished -> index line, `sync_main`.

**Owner commands** (each requires `--quote`, verified against the owner log after `checkpoint.at` when the log exists, appended to the round's OWNER.log slice as `<ts>\t[via driver]\t<quote>` and to HISTORY; each charges `costToWaitForOwner + ownerHourlyRate x ownerMinutesPerCheckpoint / 60` at the checkpoint's raise, not here):
- `approve`: `review` -> re-hash inputs, continue; `failure-limit` -> reset that step's failures, continue; `round-limit`, `hard-stop` -> set the raised flag, continue; `spec-edit` -> accept the baseline on the branch, continue; `upstream-plan` -> requires an edited PLAN.json, re-validated; `question`/`blocked` -> the same as `answer --text "proceed on your stated assumption"`.
- `delegate [--through STEP]`: approve plus `approval.mode = delegated`.
- `answer --text T`: `question`/`blocked` -> finding `O1` (blocking, source owner) to the current producer at attempt + 1; continue.
- `override --steps A,B`: allowed at any time for steps not yet accepted; refused names are usage errors.
- `abandon --reason R`: from any status before `landed_at`: tag `round/NNNN-abandoned`, index line, commit, push best-effort. After landing: refused with the hint `override --steps POSTMORTEM`.
Delegation skips only `review` checkpoints; `through:STEP` skips those at or before STEP.

### 2.10 Mechanical checks (`checks.py`)

Findings carry `{id, quote, reason, suggestion, blocking, source: mechanical}`; they are shown to the producer and are not disputable (only gate findings enter the dispute ledger).

| Id | When | Check |
| --- | --- | --- |
| S1 | DONE of an artifact step | artifact readable and valid (2.6), one finding per message; blocking |
| S2 | TESTS-TO-SUITE DONE | suite partition rule; blocking |
| M0 | every record | HEAD moved during the attempt (2.9 step 4) |
| M1 | every producer record | uncommitted paths outside write paths + round folder (+ conflicted files on a merge attempt); the paths are reverted (`git checkout -- p` for tracked, delete for untracked) and listed; blocking |
| M2 | every record after `tests_frozen_at` | uncommitted paths under `testPaths`; reverted; blocking; a conflicted test on a merge attempt is non-blocking `T1` instead |
| M3 | SPEC-TO-IMPLEMENTATION, CLEANUP | `SPEC.verify` (argv, or a string split with `shlex.split(posix=os.name != "nt")`) from H under `verifyTimeoutSeconds` (spec value wins); non-zero or timeout; quote = last 3,000 chars; blocking |
| M4 | every producer record | the judgment files only grew (`git diff <prompt_commit> -- files` has no `-` lines); a rewrite is reverted and reported; blocking |
| M5 | CLEANUP acceptance, LANDING | `suiteCommand` green within `suiteTimeoutSeconds`; blocking (at LANDING it is L2) |
| E1 | every producer record | a spec file changed since `base_commit`: not a failure; fenced diff to HISTORY, path added to `spec_edits`, `spec-edit` checkpoint before LANDING |
| G1 | every gate record | the run changed files; discarded as infra |
| W1 | PLAN-TO-SPEC DONE | non-blocking: a live sibling round (origin `round/*` without a landed/abandoned tag; its SPEC.json read with `git show`, errors ignored) declares an overlapping path |
| W2 | any prompt | non-blocking warning: prompt over `promptTokenWarn` tokens |
| L1, L2, L3 | LANDING and the merge attempt | 2.12 |
| U1, B1, O1, Q1 | routing | 2.9 |

On a merge attempt M1/M2 compare the tree that `git write-tree` produces after `git add -A` against `merge_pending.automerge_tree` (`git diff-tree -r --name-only`), so the sibling's changes never count; the changed set must lie within conflicted files + round folder; strays are restored from the automerge tree (`git checkout <tree> -- p`) and reported.

### 2.11 Costs (`ledger.py`)

- Step budget: producers `budget_usd x workFraction x shares.work[step]`, gates `budget_usd x gatesFraction x shares.gates[producer]`; shares from AGENTS-PLAN.json once accepted, else `defaultShares`, else an equal split of the remaining fraction over unassigned steps (gates: enabled ones only). `budget_cap = max(minRunUsd, budget x hardStopBudgetMultiple)`. `retry_cost` = the producer's budget + `spawnCost` + `driverUsdPerStep`.
- Agent run: `--cost` (source `agent-cli`); else `--tokens N` priced `N x (f x out + (1 - f) x in) / 1e6` with `f = estOutputFraction` and the rung's prices, plus `spawnCost x spawns` (source `agent-tokens`); else the step budget (source `agent-estimate`, flagged). Never below `spawnCost`.
- Driver: `driverUsdPerStep` per `record` and once at `start`.
- Owner: per checkpoint raised `costToWaitForOwner + ownerHourlyRate x ownerMinutesPerCheckpoint / 60`; at `start` `planCostPerWord x words(round.plan)`; at PLAN-TO-SPEC acceptance `specCostPerWord x words(SPEC.md)`; words are whitespace-split tokens.
- Living, once at LANDING against the tip actually merged (or `base_commit` in no-branch mode): for each file under `livingSourcePaths` in `git diff --name-status`, `tok(b) = ceil(b / tokenBytes)`, `price(t) = min(t, cap) x rate + max(t - cap, 0) x rateOver`, charge `price(after) - price(before)`, plus `livingFileBaseCost` for an added file and minus it for a deleted one; plus `testBaseCost x` (new matches of `testFunctionPattern` in kept files under `testPaths`); `__pycache__` and `*.pyc` excluded. Exactly one entry per landed round. `status` shows the same number computed against `base_commit` mid-round.
- Hard stop: after every append and before every render.
- `spend --project` = index totals + every unindexed round folder (live siblings read as `git show origin/round/X:STATE.json`, best effort); `project.remaining` = `budget` minus that.

### 2.12 Concurrency and landing (`gitops.py`, `landing.py`)

Invariants I1-I11 of the summary hold; I3's read-only exception is the owner log; I10 is enforced in headless mode (env scrub, tool flags) and by the agent definitions plus M0 in driver mode. No lease, heartbeat, TTL or takeover.

**Claim** (`start`): `git fetch origin`; ids = ints from `refs/remotes/origin/round/<tail>` with `tail.isascii() and tail.isdigit()` and from local folders; `rid = 1 + max`; loop `pushAttempts`: `git push --porcelain --force-with-lease=refs/heads/<branch>: origin origin/<main>:refs/heads/<branch>`; won iff exit 0 and a stdout line starts with `*` (`=` and `!` lose); explicit `--branch` pushes exactly once and errors on a loss; else `rid += 1` without re-fetching; exhausted -> `round id: push rejected N times, last <branch>`. A failed `worktree add` leaves the claim claimed; a rerun takes the next id.

**Fence**: every `record` and owner command pushes non-forced; a rejection is the fixed error. The driving runner is the worktree's own `run.py` (`runner` in the action; `next` warns `runner_skew` when the invoking `run.py` differs from `<root>/harness/src/run.py`).

**LANDING check phase** (also `check` at LANDING; never pushes, tags, charges or moves a branch): `git fetch origin`; target = `origin/<main>` if it exists, else local `<main>`, else none; `main_before` = target's sha. `git merge-tree --write-tree --name-only HEAD <target>`: conflicts -> finding `L1` (quote = the conflicted paths) with the worktree untouched; clean -> `git merge --no-edit <target>` (a merge commit, or a no-op), then verify and `suiteCommand` under their timeouts -> `L2` on red.

**Land phase** (inside `next`, after a clean check): loop `pushAttempts`: `living = living_charge(target or base_commit)`; no target or no-branch -> break; `git push origin HEAD:refs/heads/<main>` ok -> break; exhausted -> error, state unsaved, a rerun lands again; else re-run the check phase and route its findings. After the push: one living entry, `git tag -f round/NNNN-landed`, `landed_at`, local `<main>` updated by `git fetch origin <main>:<main>` when it is not checked out anywhere (else a FLAG). Without an origin: `git branch -f <main> HEAD` when not checked out; when the main checkout is on `<main>` and clean, `git -C <main_root> merge --ff-only <branch>`; otherwise an error naming the fix.

**Conflict re-entry (converges by construction)**: on `L1`: `merge_pending = {target_sha, automerge_tree, conflicted}`, `resume_step = LANDING`, `failures[SPEC-TO-IMPLEMENTATION] += 1`, `round_retries += 1`, step = SPEC-TO-IMPLEMENTATION. The next `next` renders the attempt (with `MERGE_IN_PROGRESS`, conflicted files in `WRITE_PATHS`) and establishes the merge after the prompt commit. `record`: `git ls-files -u` non-empty -> finding `L3` (unresolved files), attempt fails, the merge stays in progress; else `git add -A`, M1/M2 against the automerge tree (strays restored), commit (two parents), M3; findings -> a normal attempt (the merge commit stands); clean -> the gate; on acceptance jump to `resume_step`, where the check phase finds the target already contained. `L2` re-enters the same way without `merge_pending` (the merge commit already stands). A hand merge by the owner in the worktree works without any command: LANDING's merge becomes a no-op. `merge_pending` and `resume_step` are cleared by UPSTREAM and abandon.

**`sync_main`** (after finish and at every `done`; never raises): loop `pushAttempts`: `git fetch origin`; if `origin/<main>` is an ancestor of HEAD -> push `HEAD:refs/heads/<main>`, success -> `main_synced: true`; rejected -> retry; else `git merge --no-edit origin/<main>` (the union attribute merges `index.jsonl`); a conflict -> abort, `main_synced: false`, HISTORY `tail commits arrive with the next landing`. No verify or suite: post-landing commits touch only the round folder and the baseline. Without an origin, the local rule above.

**Rest**: `abandon` tags and pushes best-effort; `rounds` reports claimed-but-empty ids and dead worktrees (removal is the owner's); W1 at PLAN-TO-SPEC; prompts from `prose_commit`; config reads with defaults; landing order is free.

### 2.13 Spec-change guard (`specguard.py`, `tests/test_spec_baseline.py`)

`harness/tests/spec_baseline.json` = `{"accepted_at", "accepted_commit", "note", "spec_yaml": sha256, "files": {path: sha256}}` over `spec.yaml` and every file it lists; hashes are sha256 of bytes after a BOM strip and CRLF/CR -> LF. `check(repo_root) -> {changed, added, removed, missing, spec_yaml_changed, baseline_missing}` (`added` = listed but not in the baseline; `removed` = in the baseline but delisted; `missing` = listed but absent on disk). `accept(root, note)` rewrites the baseline with HEAD and appends `{"at", "commit", "note", "changed", "added", "removed"}` to `archives/spec-changes.jsonl`. `spec diff` prints `git diff <accepted_commit> -- <paths>` when the commit exists locally, else line counts.

`test_spec_files_unchanged_since_baseline` (root from `SHACKLES_ROOT` when set) fails with the categorized list, the diff (capped at 200 lines per file), and the instruction: "Review the effects: run `doctor` (pipeline and prose-file consistency, unresolved tokens), `render --step` for the affected steps, PROCESS.md's wording-adjacent table; a step, gate or artifact key change means `pipeline.py`; a config key change means `config.DEFAULTS`; then `spec accept --note "<what you reviewed>"` in the same commit." The meta-test (3.4) proves the test fires. `start` refuses while the check would fail; in-round edits follow 2.9.

### 2.14 Owner interface (`owner.py`, `owner_log_hook.py`)

The hook (`UserPromptSubmit`) reads the JSON on stdin, resolves the main checkout from `CLAUDE_PROJECT_DIR` or cwd via `git rev-parse --git-common-dir`, skips empty prompts and those starting with an envelope marker (`<system-reminder`, `<task-notification`, `[SYSTEM NOTIFICATION`, `<wake `, `<webhook-payload`, `<event `; the list in `DEFAULTS.envelopePrefixes`), ignores everything when `SHACKLES_SUBAGENT` is set, and appends `<UTC Z>\t<message with backslash and newline escaped>` to `<main_root>/harness/OWNER.log`. It never raises. The runner reads that file only to copy new lines into the round's slice and to verify quotes; `doctor` warns when the hook is not configured or the log does not exist (then quotes are recorded unverified with a FLAG).

Checkpoint `message`: kind, step, question or artifact path, spend versus quote, undefined judgment calls added since the last checkpoint (last 5 lines and the file's absolute path), and the exact resume commands. The driver relays it verbatim and stops.

### 2.15 Agent invocation (`agents.py`)

**Driver mode (primary).** Per action the driver calls the Agent tool with `subagent_type = agent_type` (`shackles-gate` or `shackles-producer`), `model = model_alias`, no worktree isolation (the round worktree is the isolation), and the task `Your instructions are the entire content of <prompt_file>. Read it now and follow it exactly; your final message must be exactly the JSON object it specifies and nothing else.` It saves the final message to `result_file` as returned and runs `record_command`, adding `--tokens N` when the tool reports a token total (else nothing: estimate). Effort cannot be set through the tool today; documented.

**Headless (`run`, `probe`, e2e).** `agentCommand` with `{claude} {prompt_file} {model} {effort} {budget_cap_usd} {result_schema} {tool_flags} {task}` substituted; `{tool_flags}` expands in place (`--tools`/`--disallowedTools` are variadic, so they sit before `--permission-mode` and the task is last); cwd = H in the worktree; env minus `scrubEnv` plus `SHACKLES_SUBAGENT=1`, `PYTHONUTF8=1`; timeout `maxRunWallClockHours`. Envelope: `data["structured_output"]` when an object, else `data["result"]` unwrapped; `total_cost_usd` -> `--cost`; `usage`, `num_turns`, `session_id`, `is_error` stored beside the result. Non-zero exit, `is_error`, timeout or unparseable output -> tree reset, infra error, retry; `infraRetries` -> exit 1. `doctor` prints the resolved path and `--version`; `doctor --probe-cli` runs one `--print` call on the `low` rung with a $0.05 cap asking for `{"ok": true}` under `--json-schema`, only when asked.

### 2.16 Documents

- `INDEX.md`: `alias, alias -> path` lines for process/rules/checkpoints/disputes (docs/PROCESS.md), driving a round (docs/DRIVER.md), config and defaults (`run.py config`, project.yaml, local.yaml), runner and exit codes (`run.py --help`), contracts (src/shackles/plumbing/, schemas.py), prose (locked_prose/, `run.py render`), rounds and index (archives/rounds/), owner log and hook, agent definitions, spec baseline (`run.py spec`, tests/spec_baseline.json), tests and probes (docs/TESTING.md).
- `docs/PROCESS.md` (normative, <= 200 lines, one sentence per line): principles; files and the harness-root path rule; the step table and acceptance; runner commands, exit codes, re-entry, the fence; the driver (never judge, never commit, run the worktree's runner, path-form spawning); contracts by reference; findings, disputes, settlement, `deferred`; checkpoints and owner commands; caps and stops; mechanical checks; costs; freeze and archive; landing, the merge attempt, `sync_main`; concurrency invariants; spec files (drift, in-round edits, flagging); the wording-adjacent table (each runner rule that mirrors prose: settled at 2 upholds, the status and verdict words, review checkpoints, step order, gates read-only, the owner word list interpreted by the driver); Windows notes.
- `docs/DRIVER.md` (<= 80 lines): `doctor`, `render --step CHAT-TO-PLAN`, plan in chat, `start`, the `next`/spawn/save/`record` loop with the Agent-tool parameters, what to do on exit 10 (relay `message`, wait, run the owner's command with `--quote`), on `push rejected`, on exit 2 from `record`, on `done` (`git pull --ff-only` in the main checkout).
- `docs/TESTING.md` (<= 80 lines): suite map, fixtures, stub modes, the baseline procedure, the four levels of section 8 with commands and expected cost.
- `README.md`, `CLAUDE.md` as in 2.2.

### 2.17 Fixture spec (`tests/fixtures/spec/`)

A generator builds a temp harness from a template: `AGENTS.md` (the real file copied, it is short), a `project.yaml` produced from the real one with living paths pointing at the toy project (`../src/`, `../tests/`, `docs/`) and every gate flag parameterized, the real `subAgents.yaml` shape, and one generated prose file per pipeline step containing only that step's name plus the includes and plumbing tokens the real files use (`{{ prose.COMMON-PROJECT }}`, `{{ prose.COMMON-ROUND }}`, `{{ prose.COMMON-OVERVIEW }}` or `COMMON-GATE`, `{{ plumbing.GATE-PROSE }}`, `{{ plumbing.PROCESS-INSTRUCTIONS }}`) and one `{{ project.* }}`, `{{ round.* }}`, `{{ step.retry_cost }}` token each. `spec="real"` copies the owner's files instead, for the real-spec tests only.

## 3. Test strategy

Partial integration, no mocks of git or the filesystem; every scenario runs the real runner in a throwaway repo under `tmp_path`; the LLM is the stub. Invocation is in-process (`cli.main(argv)` with captured stdout) except a handful of subprocess tests that pin the CLI contract. Hermetic git: `GIT_CONFIG_GLOBAL` = an empty temp file, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed author and committer, `core.autocrlf=false`, `core.longpaths=true`. Budget: `-m "not slow and not real"` under 60 s, the whole non-real suite under 4 minutes; a full stub round under 20 s.

### 3.1 Fixtures

- `Repo(tmp, gates=None, config=None, spec="fixture"|"real")`: temp repo with `harness/src` and `plumbing` copied, the fixture spec (2.17), the toy project, `.gitignore` with `<worktreeDir>/`, `.gitattributes`, `local.yaml` pointing `agentCommand` at the stub via `sys.executable` and `suiteCommand` at the toy's pytest, `git init -b main`, first commit. Methods: `run(*argv, subprocess=False) -> Result(code, json, stdout, stderr)`, `git`, `head`, `dirty`, `read/write/json`, `owner(text, at=None)` (writes an owner-log line with a controllable timestamp), `start`, `next`, `record`, `act(action, mode)`, `play(until=STEP, modes={...})` (drives next, stub, record in-process), `add_origin()` (bare, `symbolic-ref HEAD refs/heads/main`, absolute path, `main` pushed), `clone()` ("another machine"), `view(worktree)`.
- `Origin`: `sha(ref)`, `branches()`, `hook_log()`, `install_reject_hook(pattern, n|"all")`, `install_move_and_reject_once_hook(refname, to_ref)`; hooks are Python scripts with `#!<sys.executable>` (forward slashes), `newline="\n"`. A session-scoped probe installs a marker hook and pushes once; if the marker does not appear, hook-based tests `pytest.skip`. Lost-claim races use the narrowed-fetch-refspec trick (`remote.origin.fetch = +refs/heads/main:refs/remotes/origin/main`) and need no hook.
- `stub_agent.py`: invoked exactly like the CLI (argv from `agentCommand`), parses the last `STEP:`, `KIND:`, `ATTEMPT:`, `WORKTREE:`, `HARNESS:`, `ARTIFACT:`, `RESULT_FILE:`, `WRITE_PATHS:`, `MERGE_IN_PROGRESS:` lines, writes canned artifacts from `fixtures/canned/<STEP>.*` (SPEC-TO-TESTS writes `tests/toy/test_text.py` plus a scratch test; SPEC-TO-IMPLEMENTATION writes `src/toy/text.py`; TESTS-TO-SUITE archives the scratch test under `STUB_ARCHIVE=1`), appends judgment lines under `STUB_JUDGMENT=n`, and prints the CLI envelope `{"result": "<json>", "structured_output": {...}, "total_cost_usd": 0.01}`. Modes via `STUB_MODE` or `STUB_SCRIPT` (JSON `{"STEP:attempt"|"STEP"|"*": mode}`): `pass pass_nb fail dispute uphold withdraw needs_owner q_uphold q_withdraw upstream blocked garbage fence prose_wrapped deferred commit stray touch_tests break markers resolve rewrite_judgment edit_spec big slow replay`; `STUB_LOG=<file>` records argv, cwd and env keys per call; `perform()` is the in-process entry.

### 3.2 Unit tests (no git, milliseconds)

`test_render.py` (grammar, namespaces, once-per-document includes, depth and cycle, embed mode, value formatting, unresolved marker collected, raw insertion never expands, missing token appended); `test_config.py` (layering and sources, defaults for every deleted key, `NNNN`/`NNN` width, gates coercion and order, roster fallback, `..` paths, CRLF/BOM); `test_pipeline.py` (lookups; lint cases: gate missing from the map, map reordered, unknown prose file, gate without prose, `checkpointsAfter` unknown); `test_schemas.py` (each schema good and bad, exact messages, extraction from bare, fenced and prose-wrapped text, normalization, duplicate ids); `test_ledger.py` (budgets and equal split, blend pricing and floors, owner charges, living cases: added under cap, grown across the cap, shrunk, deleted with refund, new tests counted, non-living free, time cost, hard-stop threshold); `test_owner.py` (hook line escaping, envelopes, `SHACKLES_SUBAGENT`, quote verification windows, unverified FLAG); `test_specguard.py` (the categorized results on a temp copy: unchanged, one byte, whitespace-only, CRLF/BOM rewrite clean, added, removed, missing, spec.yaml changed, baseline missing, accept then clean, audit line appended).

### 3.3 Round tests (git, `--no-branch`, stub, in-process)

`test_round.py`: `start` validates before any git write (a bad plan creates nothing); refusals (unacked spec, missing approval with the gate enabled, quote not in the log, `--unverified`); folder, `.keep`s, judgment headers, STATE, HISTORY, start commit, ledger opening entries; every action field, absolute paths, `record_command`; prompt archived and committed; prompts render from `prose_commit` (edit prose mid-round, prompt unchanged); config read live (flip a gate in the worktree, honoured); record guards (wrong step, wrong attempt, replay, missing pending) exit 2 and change nothing; a full pass round to `done` with every gate enabled, asserting `step_commits`, `attempts`, PROMPTS/RESULTS/FINDINGS per step, the diff file for code gates, the archive move, freeze, index line, `judgment_calls` counts, `main_synced`; the same with every gate disabled (skip files with `source: disabled`, checkpoints still raised, delegated raises none, `--through PLAN-TO-SPEC-GATE` skips only the spec review); overrides (PLAN-AGENTS -> defaults; TESTS-TO-SUITE -> keep all; CLEANUP skipped; refused names).
`test_outcomes.py`: FAIL -> re-entry with findings and `failures`; dispute -> rulings, settled at two upholds, a further dispute ignored with a note; withdrawn never re-raised; carried findings and `deferred` rendered downstream and to POSTMORTEM; NEEDS-OWNER with the gate enabled (upheld -> `question` checkpoint even when delegated; withdrawn -> Q1), with the gate disabled (checkpoint; delegated -> assumption logged); `answer` -> O1; UPSTREAM to each earlier producer and to CHAT-TO-PLAN, downstream resets, `round_retries`, `round-limit`; BLOCKED -> checkpoint; failure limit -> checkpoint, approve resets; hard stop once; infra path (garbage twice -> rerun same attempt; `infraRetries` -> `infra` checkpoint; cost booked); M0 (`commit` mode) soft reset; G1 (a gate that writes) discarded; dirty-tree recovery scoped (an untracked file outside H and living paths survives) and counted; pending-work refusal and `--discard`; out-of-band PLAN and SPEC edits; in-round spec edit -> HISTORY diff and `spec-edit` checkpoint even when delegated, approve accepts; crash simulation (STATE saved but commit missing; result saved but not recorded) resumes.
`test_checks.py`: S1 messages verbatim; S2 partition; M1 stray reverted and in-scope kept; M2 touched test reverted; M3 red and timeout (process tree killed); M4 rewrite reverted; M5 at CLEANUP; W1 against a sibling branch's SPEC.json; W2 on a huge prompt; `check` never records and exits 3 on findings.
`test_cli.py` (subprocess): `--help`, exit codes, one-line `start` output, `doctor --json` on the fixture, `render --fixture`, `config`, runner-skew warning.

### 3.4 Real-spec tests (the only tests that read the owner's files)

`test_spec_baseline.py`: the guard (2.13) on the real repository; `test_guard_fires` runs the real test function against a mutated temp copy via `SHACKLES_ROOT` and asserts `pytest.fail.Exception` naming the file and containing the diff and the accept command, and passes on an untouched copy; one subprocess `pytest` on the temp copy proves collection and exit 1.
`test_spec_structure.py`: every listed file exists and loads; pipeline gates equal the `gates` keys in the same relative order; every producer and gate has its prose file and every prose file maps to a step or `COMMON-*`; `STATUSES`/`VERDICTS` words appear in the locked prose; roster keys referenced exist; every prompt renders via `render --fixture` with no `{{` left and no unresolved token outside `tests/spec_waivers.json` (empty after the section 4 edit). No test asserts on a sentence of the owner's prose.

### 3.5 Concurrency tests (`slow`; bare origin, clones, Python hooks)

Claim: stdout shape, worktree on `round/0001` at `origin/main`, origin ref == worktree HEAD, main checkout untouched, no `OWNER.log` in the worktree. Lost race via the narrowed refspec for `!` and `=`: `assertNothingCreated` (no folder in any commit per `git log --all`, no worktree, one local round branch, clean, still on the starting branch). Reject-all hook -> exactly `pushAttempts` pushes logged, the fixed error, nothing created. Explicit `--branch` taken -> one push. `worktree add` failure keeps the claim. Id sourcing ignores `round/003-x`, `round/abc`, tags. Preconditions: `worktreeDir` not ignored refused; no origin refused. Worktree operation: owner log read from the main checkout; `status`/`spend`/`check` under `--root`; `record` pushes from the worktree; `next` pushes when ahead. Fence: another clone moves the branch -> `record` exits 1 with the message. Landing after a sibling moved main: `check` merges only (no tag, ledger, push, local main); `run --until done` leaves `origin/main == round tip` with both rounds' files and one living entry equal to this round's diff. Move-and-reject-once hook -> `attempts[LANDING] == 1`, sibling file present. Reject-all on main -> exit 1, no tag, no living entry, state at LANDING, lands on rerun. Conflict: L1 names the file, worktree clean after `next` prints it, then the merge attempt tree has markers in exactly that file; `resolve` mode -> two-parent commit, M1/M2 against the automerge tree pass, `L3` when left unresolved, a stray during resolution restored, `T1` for a conflicted test, gate runs, round returns to LANDING and lands with both contents; a hand merge (test edits and commits in the worktree) lands without a command; L2 -> fix from the merge commit, lands. `sync_main` true, idempotent, and `index.jsonl` from two rounds merging cleanly through the union attribute; `false` on a genuine conflict. Runner skew warning. `rounds` report. W1.

### 3.6 Headless and probe tests

`run --until step|done` with the stub as `{claude}`: argv carries the right rung's model and effort per kind, tool flags in order, `--json-schema`, no `--max-turns`; env scrubbed and `SHACKLES_SUBAGENT` set (`STUB_LOG`); `structured_output` preferred, fenced `result` accepted; garbage -> retries then exit 1; `slow` mode -> timeout kills the tree. `probe --step S` with the stub positions the temp repo and prints an action; `probe --check` scores; every defect fixture loads and its `expect.json` validates. `sandbox --dir` builds and a stub `run --until done` finishes there. `test_docs.py`: INDEX aliases resolve; every CLI command appears in DRIVER.md or PROCESS.md; every `DEFAULTS` key appears in PROCESS.md; no source file shares an 8-word window with a locked prose file.

## 4. Spec-file edits (exact, minimal, flagged)

One defect: two prose files reference `project.ownerReviewCostPerWord`, which `project.yaml` does not define; it defines `planCostPerWord` and `specCostPerWord`. Without the edit the runner renders `[unresolved: project.ownerReviewCostPerWord]` in those two prompts (no crash) and the real-spec test needs a waiver.

```diff
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

Procedure: apply in a separate commit titled `SPEC EDIT (owner review required): resolve ownerReviewCostPerWord (2 tokens)` with this diff in the body; take the baseline after it (`spec accept --note "bootstrap: placeholder rename"`); repeat the diff under "Spec edits made, awaiting your approval" in the final report. If the owner declines, revert the commit and add `{"project.ownerReviewCostPerWord": "owner declined the edit; see merged-B section 4"}` to `spec_waivers.json`; the marker keeps rounds runnable. The alternative of adding `ownerReviewCostPerWord: 0.1` to `project.yaml` is rejected because the owner already split the value.

No other spec file is edited. Gate language is not relaxed: COMMON-GATE's cost rule already tempers the per-line "Fail" lists, and Level 1 defect/clean probes (section 8) will show whether clean artifacts fail on wording alone before anyone guesses; any relaxation would be proposed as a flagged diff, smallest first, to COMMON-GATE before any per-gate list.

## 5. Interpretations and spec tensions to flag to the owner (no edits)

1. `maxFailuresBeforeStop` is read per producer step (comment: "gate rejections before a round should stop"); `maxRoundAttempts` is read as the number of re-entries (UPSTREAM, out-of-band edits, landing L1/L2) before a `round-limit` checkpoint. Both are single counters in `DEFAULTS`, changeable without code.
2. Gates are read-only (AGENTS.md) yet COMMON-OVERVIEW and COMMON-PROJECT ask every step to append judgment calls to the round files: gates return them in the verdict JSON and the runner appends them.
3. `ownerHourlyRate` has no attention estimate in `project.yaml`; the runner uses `ownerMinutesPerCheckpoint: 10`, which the owner may set in `project.yaml`.
4. CHAT-TO-PLAN-GATE disabled (today's config) means no owner word is required at `start`; the round then runs with review checkpoints unless the plan or `--delegate` says delegated.
5. The review checkpoints (`checkpointsAfter`) and the step order live in the runner, derived from prose sentences and `project.yaml` comments; the owner may adopt `checkpointsAfter` into `project.yaml`.
6. POSTMORTEM's "the previous round" is read as "this round, now landed".
7. The living charge at $0.25 per token makes a 200-line file about $800 in the ledger and will dominate every quote; it is the owner's number and only a ledger figure.
8. `subAgents.yaml`'s `high` rung is displayed as "Fable 5.1 Low" (the runner uses keys only).
9. `maxTurnsPerRun` cannot be enforced (no CLI flag; the Agent tool has no cap); it is advisory text, and `--max-budget-usd` plus the wall clock are the hard caps in headless mode.
10. `maxRefactorOverhead` is enforced only on the SPEC's declared `refactor` budgets; the gate judges the rest.

## 6. Risks, with the recommended resolution

1. The Claude Code CLI updates and its flags or envelope drift: `agentCommand` is config, `doctor --probe-cli` verifies for cents, the parser accepts `structured_output` and text results.
2. Headless `bypassPermissions` may need `--dangerously-skip-permissions` or a desktop trust prompt: `doctor --probe-cli` is the check; the flag list is config.
3. Driver mode cannot set effort or read cost exactly: estimates are flagged; headless mode is exact and is what probes and e2e use.
4. The hook shell on Windows: the command is the bare `py -3.13 harness/src/owner_log_hook.py`; milestone 0 verifies it with one real prompt; the absolute Python path in `settings.json` is the fallback; `--unverified` keeps rounds moving.
5. A second interactive session on this repo also logs to OWNER.log: harmless, the log is the owner's; quotes are verified against timestamps and HISTORY records the line acted on.
6. Gates may fail everything under the strict "Fail" lists: measured by Level 1 probes before any wording changes (section 4).
7. The harness is its own project, so a round that edits `src/shackles/round.py` changes the runner driving it: the worktree's own runner drives the round, `runner_skew` warns, M5 runs the suite at CLEANUP, and PROCESS.md says rounds touching the runner should keep checkpoints on.
8. Sub-agents run with the driver's cwd: every prompt carries absolute `WORKTREE` and `HARNESS`; DRIVER.md forbids worktree isolation for round agents; M1 catches strays.
9. `git merge-tree --write-tree` semantics: verified on 2.45 by one fixture test in milestone 4 before the conflict path relies on it; fallback if a git build misbehaves is "allow only the conflicted files, measured from the pre-merge HEAD".
10. Two live rounds on the same living files: W1 warns early, the merge attempt converges, one-sentence-per-line docs keep conflicts small; not prevented, by design.
11. Suite speed on Windows: in-process invocation, `slow` marker, one played repo shared per read-only test class.
12. Windows file locking: `PermissionError` retries, `onexc` rmtree, the infra path tolerates a redo.
13. Push credentials: the runner inherits the session's git credentials; `scrubEnv` applies only to spawned agents; `doctor` checks `git ls-remote origin`.
14. Spec files changing under the implementer: the guard is milestone 0; a change after that fails the suite and is reviewed before continuing.
15. The `override` word or `abandon` appearing in ordinary conversation: irrelevant to the runner, which acts only on driver commands with quotes; DRIVER.md tells the driver to confirm in chat before `abandon`.

## 7. Implementation sequence

Each milestone ends with its tests green and one commit on a `claude/bootstrap-*` branch (never `main`; repo-local identity per the machine notes). No new dependencies. Tests first for every check and guard.

- **M0 scaffold and guard**: layout, `.gitignore`, `.gitattributes`, `pytest.ini`, `procs.py`, `gitops.py` (run, ok, head, main_root, hermetic env), `config.py` with `DEFAULTS` and `config`, `specguard.py`, `spec_baseline.json`, `test_config.py`, `test_specguard.py`, `test_spec_baseline.py` with the meta-test; the section 4 commit; baseline taken after it. Accept: the guard fails on a byte change and its self-test passes; `config` prints sources.
- **M1 rendering and contracts**: `pipeline.py`, `render.py`, `contract.py`, the plumbing files, `schemas.py`, `render`, `doctor` (without the CLI probe), the fixture spec generator, `test_render.py`, `test_pipeline.py`, `test_schemas.py`, `test_spec_structure.py`. Accept: every real prompt renders with zero unresolved tokens; lint clean on the real repo.
- **M2 one round, no origin**: `ledger.py`, `checks.py`, `owner.py` and the hook, `round.py` with `start --no-branch`, `next`, `record`, the owner commands, `status`, `spend`, `check`, `abandon`, local landing and `sync_main`, index line, the stub, `fixtures.py`, `test_round.py`, `test_outcomes.py`, `test_checks.py`, `test_ledger.py`, `test_owner.py`, `test_cli.py`. Accept: a stub round runs to `done` with every gate on and with every gate off in under 20 s; every routing row has a test.
- **M3 concurrency**: claim, worktrees, fence, `next` push-when-ahead, landing check and land phases, the merge attempt, `sync_main` loop, `rounds`, W1, preconditions, `Origin` fixtures, `test_concurrency.py`. Accept: two stub rounds land on a local origin in either order; the conflict test lands; the merge-tree fixture test passes.
- **M4 agents, probes, sandbox**: `agents.py`, `run`, `{claude}` resolution, `doctor --probe-cli`, `probe`, `sandbox`, the agent definitions, defect fixtures, `test_headless.py`, `test_probe.py`. Accept: stub headless `run --until done`; `probe` and `sandbox` with the stub; `doctor` finds `claude.exe` on this machine; both agent definitions verified once on a scratch task (gate cannot write; producer cannot commit).
- **M5 docs and hand-off**: PROCESS.md, DRIVER.md, TESTING.md, INDEX.md, README.md, CLAUDE.md, `test_docs.py`; the hook verified with one real prompt; final `doctor`, `spec status`, full suite with timing. The final report lists: the section 4 diff, every section 5 interpretation, every `doctor` warning, the suite time, and the section 8 commands with their expected cost.

Definition of done: every invariant in `harness/AGENTS.md` holds by construction and PROCESS.md names the mechanism for each; every command in DRIVER.md was executed once on the fixture; no test depends on a sentence of the owner's prose; `py -3.13 -m pytest` is green on this machine.

## 8. Real-agent testing

**The owner's loop.** A tiny throwaway task end to end with gates off, then with gates on, then variants (checkpoints, approval skips, gate effectiveness). Per pass: 8 producer runs (gates off) or 8 producers + 6 gates + the expected one or two retries per gated step (gates on); at the sibling's observed $1-6 per run on max-tier agents, roughly $10-40 per gates-off pass, $25-90 per gates-on pass, one to three hours each, sequential. Three weaknesses: a failure is hard to attribute (which prompt, which gate, which mechanism); paths a clean run never takes (dispute, UPSTREAM, NEEDS-OWNER, conflict, fence) stay untested; and "gate effectiveness" cannot be measured on a task with no planted defect, only "gates can be passed".

**What the plans proposed** (all six, converging): a free stub tier for every mechanical variant; a per-step real-agent tier with planted defects; the owner's loop kept as a later tier in a sandbox; a replay corpus so paid results become free regression tests.

**Recommended ladder.**

| Level | What | Cost, time | What it proves |
| --- | --- | --- | --- |
| 0 | the stub suite: every checkpoint, approval skip, override, cap, dispute, upstream, conflict, race, fence | free, minutes, every commit | the mechanics; cannot prove a real agent understands a prompt |
| 1 | `probe --step S --seed clean|defect [--agent low|medium] [--manual]`: a temp repo played to just before S, the real prompt, one real agent, `probe --check` scoring `{contract_valid, schema_valid, paths_confined, verify, judgment_lines, verdict_as_expected, cost, turns}` | about $0.5-3 per run; the full matrix of 8 producers + 6 gates x 2 seeds = 20 runs, about $10-40 on `medium`, less on `low`; runs in parallel in about 30 minutes | per-prompt comprehension and the result contract; gate discrimination against ground truth (a clean artifact must PASS, a planted defect must FAIL with a quote containing the planted text); which prose sentence a failure belongs to |
| 2 | the owner's loop in `sandbox --dir` (a temp clone with a local bare origin): `run --until done` gates off with `--delegate`, then gates on, then with checkpoints answered through `answer`/`approve --quote` and an `override`; two rounds from two clones for the concurrency | about $10-40 per pass on `systemTestAgent`; an hour each | the whole pipeline with real messages; nothing lands on the real `main` |
| 3 | the owner's tiny task on the real repository, once Levels 1-2 are green; its RESULTS/ and artifacts are copied into `tests/fixtures/replays/` and replayed by the stub's `replay` mode forever at zero cost | one round | the real environment, hooks and credentials |

Rerun Level 1 after every prose or contract change (`probe --changed` runs only the steps whose prose the baseline reports changed, a few dollars the same day); run Level 2 once per change to the runner's flow, not per prose tweak. A full validation is about $50-120 for more coverage than the owner's loop alone at $100-250, and every failure names one prompt or one mechanism. Level 1 is also the only place the gate-language question (section 4) gets data: if clean artifacts fail on wording alone in two of three probes of a gate, propose the smallest relaxation with the scorecards attached.
