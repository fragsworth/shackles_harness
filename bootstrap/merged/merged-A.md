# shackles_harness — merged implementation plan (merged-A)

Merged from the six plans in `bootstrap/plans/` by one merge planner, against the spec (`spec.yaml` and the 20 files it lists) and `bootstrap/vision-harness-round-concurrency.md` (the summary). Written for one implementing agent, one session, Python 3.13 (`py -3.13`), PyYAML, pytest, git 2.45, Windows 11 / PowerShell. "Plan-N" cites `bootstrap/plans/plan-N.md`; "the summary" cites the concurrency document.

Reading order: §1 is the decision log (every consequential choice, its source, what was rejected). §2 is the design, normative. §3 tests, §4 the spec edits, §5 risks, §6 build order, §7 real-agent testing. Where this document and a spec file disagree on a **mechanical** fact, this document is wrong and §4/§5 is where the fix goes; where they disagree on **judgment wording**, the spec wins and no code may care.

Vocabulary: **spec files** = the files `spec.yaml` lists (owner-owned, change often, rendered or read by key, never parsed for wording). **H** = the harness root, the folder holding `project.yaml` (`harness/`). **R** = the repo root (`git rev-parse --show-toplevel`). **M** = the main checkout (`main_root`, summary §2.1). **runner** = `harness/src/run.py` and its package (deterministic, no LLM). **driver** = the LLM session that runs `next`/`record` and spawns sub-agents. **producer/gate** = the step agents. **round** = one branch `round/NNNN`, one worktree, one folder `harness/archives/rounds/NNNN/`.

---

## 1. Decision log

Each entry: the choice; where it came from; what was rejected and why. Entries marked **shared weakness** fix something all six plans got wrong.

1. **Owner words are interpreted by the driver, never by the runner; the runner verifies the quote against the owner log.** The driver (the CHAT-TO-PLAN agent, whose prompt carries the owner's word list) maps the owner's words to commands (`start --quote`, `approve`, `delegate [--through]`, `answer`, `override`, `abandon`, each with `--quote "<owner's exact words>"`); when `<M>/harness/OWNER.log` exists the runner refuses a quote that is not a verbatim substring of a log line after the relevant timestamp. From plan-2 (driver commands with `--quote`) and plan-6 (`--quote` must match the log). Rejected: runner-side regexes on the words (plans 1, 3, 5, 6) because a word list in the runner is mechanical behavior depending on the wording of `CHAT-TO-PLAN-OVERVIEW.txt`, and the sibling's phantom approval came from exactly that mechanism; the first-word rule (plan-4) because it makes the owner's chat stilted. Reading "unambiguous conversational context" is a DEFINED JUDGMENT CALL the prose assigns to the chat agent; the runner only checks the words are the owner's.
2. **Landing pushes `HEAD:refs/heads/<main>` to origin; rounds are cut from `origin/<main>`.** No local `main` ref is moved first, so `main` may be checked out anywhere (this machine parks the checkout on `claude/bootstrap` and its rules say cut from origin). From plans 2, 4, 5, 6. Rejected: the summary's `git branch -f main` with the "main not checked out" precondition (plans 1, 3).
3. **Landing conflicts converge through an agent attempt measured against the auto-merged tree.** On L1 the runner leaves the merge in progress, re-enters SPEC-TO-IMPLEMENTATION with the conflicted files listed, and measures M1/M2 against `git merge-tree --write-tree`'s tree so only the agent's hand edits are judged. From plans 4 and 5 (verified `merge-tree --write-tree` on this git). Rejected: committing conflict markers (plan-2; leaves a broken commit in history), a snapshot of every blob (plan-1; heavier), abort-and-checkpoint only (plan-6; pushes every conflict to the owner, against I7's "a conflict degrades to more agent work"). Plan-6's human hand-merge stays as the exit when `maxRoundAttempts` is exhausted.
4. **No `index.jsonl`; the round folder's `STATE.json` is the record, and the post-round sync is a bounded merge-and-push step (FINISH).** **Shared weakness**: all six kept the summary's append-only `index.jsonl` and its "timid" `sync_main`; two rounds appending at EOF conflict in git, and a round whose fast-forward loses to a sibling leaves its POSTMORTEM and index line orphaned on the round branch forever (nothing ever merges them). `spend --project`, `round.history` and `rounds` aggregate `STATE.json` across round folders and live branches. FINISH merges `origin/<main>` and pushes like LANDING (plan-2 §4.12 item 3), re-running verify and the suite only when the tail touched files outside the archives and docs.
5. **Carry-forward TODOs and CLARIFICATIONS live in `docs/TODO.md` and `docs/CLARIFICATIONS.md`, living files that POSTMORTEM edits and CHAT-TO-PLAN reads verbatim.** From plan-2. Rejected: parsing `## TODO` headings out of POSTMORTEM.md (plans 1, 3, 5; wording-dependent) and feeding the last three whole postmortems (plan-4; loses older items, bloats prompts).
6. **The step table is runner-owned data (`harness/src/runner.yaml: steps`), gates are derived from prose file names and the `gates` map.** From plans 1, 5, 6 (data) and plan-1 (derived gates). Rejected: the table in code (plans 2, 3; a reorder needs a code change), dynamic placement of unknown steps and letting the `gates` map reorder the pipeline (plan-4; clever, surprising), and treating a missing producer prose file as "step skipped" (plan-3; silent). A missing producer prose file makes `start` refuse (plan-2); `override` is the explicit way to skip.
7. **Every spec file is pinned per round at `spec_commit`** (prose, `project.yaml`, `subAgents.yaml`, `spec.yaml` itself, all read with `git show`). From plans 1, 3, 4. Rejected: live config with pinned prose (plan-6) because a sibling landing a config key mid-round is the summary's failure #2, and a gate flip mid-round has an explicit tool (`override`).
8. **Spec drift: a baseline in `harness/archives/spec-baseline.json` plus an append-only `spec-acks.jsonl`; the pytest test fails on drift with diffs and a review checklist; `start` refuses on drift; LANDING raises checkpoint `spec-changed` rather than a red suite.** From plan-5 (archives, acks), plan-2 (checklist), plans 1 and 5 (never L2). Rejected: the baseline under `tests/` (plans 2, 3, 4; living and charged), file copies beside the manifest (plan-6; git already has the bytes), warn-only at runtime (plan-6; the owner asked for an alert an agent must act on).
9. **The gate's `verdict` is authoritative; `blocking` flags are normalized to it and the inconsistency logged.** From plan-1. Rejected: deriving the verdict from the flags (plans 2–6) because "FAIL iff a blocking finding" encodes today's `COMMON-GATE` semantics into the runner; the verdict is the gate's explicit call and survives a rewording of the finding rules.
10. **Mechanical checks run at `record`, on the attempt's own diff; strays and frozen-test edits are reverted and noted, verify red blocks.** From plan-6 (per-attempt diff, so merges never trip M1) and plan-2 (revert out-of-scope changes). Rejected: measuring from `step_starts` (plans 1, 3, 4; the summary's non-convergence came from cumulative diffs) and failing the attempt for a stray file (plans 2, 4; a retry costs more than reverting one file — the gate sees the note, and a stray that verify needed surfaces as M3).
11. **Cost precedence `--cost` > `--usage` priced by the roster > estimate = the run's budget; driver cost is the flat `driverUsdPerStep`; owner cost per checkpoint is `costToWaitForOwner + ownerHourlyRate × ownerHoursPerCheckpoint` (default 0.1 h, overridable per resume with `--minutes`).** From plans 2 and 4 (estimate = share), plans 1, 2, 3, 5, 6 (flat driver), plans 3 and 4 (hours-per-checkpoint key). Rejected: `spawnCost` as the estimate (plans 1, 3, 6; under-reports to near zero and blinds the hard stop) and transcript-measured driver cost (plan-4; the sibling's double-counting mess, and the owner configured a flat figure).
12. **`maxFailuresBeforeStop` counts FAILs per producer; `maxRoundAttempts` caps `retries` (failure-limit resumes, UPSTREAM re-entries, landing re-entries, out-of-band edits), raising `round-limit` once.** From plans 1, 3, 4 (per step) and plans 5, 6 (resumes). Rejected: a round-wide FAIL total (plans 2, 6) because `PLAN-AGENTS-OVERVIEW` says to expect one or two rejections per gated step.
13. **NEEDS-OWNER with the gate disabled: approved mode asks the owner; delegated mode proceeds on the stated assumption and records it in `UNDEFINED_JUDGMENT_CALLS.md` and `pending_questions`. BLOCKED always pauses.** From plans 2 and 3 (delegated proceeds), plans 2, 4, 6 (BLOCKED is a checkpoint). Rejected: retrying BLOCKED (plans 1, 5; narrowing is the owner's call).
14. **Judgment calls: gates (read-only) return them in their verdict JSON and the runner appends them; producers append to the files; an append-only check guards the files; counts go to HISTORY, STATE, checkpoints, POSTMORTEM.** From plan-3 (the gate gap) and plan-5 (its append-only check).
15. **Read-only gates by construction in driver mode: generated `.claude/agents/shackles-{producer,gate}-<rung>.md` definitions carrying model, effort and tools from `subAgents.yaml`; a soft-reset undoes a producer's commit; a gate that changed files has the changes discarded.** From plans 4, 5, 6 (definitions), plans 4, 5, 6 (M0), plan-3 (G1). New: one definition per rung, generated by the runner, because the Agent tool takes model and effort from the definition (plans 3–5 assumed effort could not be set).
16. **A prompt is the rendered prose file and nothing else; `plumbing.*` blocks come from templates in `harness/src/plumbing/`; each prose include renders once per document; code gates get a runner-made diff file; `ERRATA.md` is an unhashed round file; prompts carry paths, not bodies.** From plans 3 and 4 (templates, render-once, `(as above)`), plans 2 and 6 (diff file), plan-6 (errata), plan-1 (paths not bodies). Rejected: prepending a header and AGENTS.md (plan-1; the plumbing names AGENTS.md by absolute path instead), shrinking oversized prompts (plan-5; a size warning suffices when bodies are not inlined).
17. **An unparseable or invalid result makes `record` exit 2 with nothing consumed; the driver re-asks or records `--infra-error`; after `infraRetries` infra errors at one attempt, finding I1 routes as a mechanical FAIL.** From plan-2 (`--infra-error`) and plan-3 (I1). Rejected: consuming the attempt with a synthesized finding (plan-4; wastes a budgeted run on a transport failure).
18. **Headless mode is secondary and config-driven**: `agentCommand` template, `{claude}` resolution order, `--json-schema`, no `--max-turns` (advisory in the prompt), process-tree kill on timeout, `doctor --probe-cli` for a cents-cost real check. From plans 5 and 6 (probed the installed CLI 2.1.266). The suite exercises headless only through the stub.
19. **Tests: partial integration in throwaway repos, in-process driving, Python-written origin hooks with an absolute-interpreter shebang, the narrowed-refspec race trick; whole suite under four minutes.** From the summary and plan-6 (Python hooks, verified). Rejected: sh hooks as the only race device (plan-3 found no `sh`; others found it — Python hooks remove the question).
20. **Real-agent testing is a ladder: stub suite → single-step probes with clean and planted-defect fixtures → sandbox end-to-end → the owner's real run; the driver's Agent tool is the primary spawner, headless optional.** All six converge here; the `probe`/`sandbox` commands follow plans 1, 5, 6; plan-5's `--manual` mode is the default because headless is unverified on this machine.
21. **Paths in config, artifacts, prompts and findings are relative to H, `..` allowed; the runner converts to repo-relative for git.** From plans 3, 4, 5, 6 (`AGENTS.md` is headed `# harness/`). Rejected: repo-relative (plans 1, 2).
22. **Runner skew is a warning (`runner_skew` in the action and stderr), the documented rule being "drive a round with its own worktree's `run.py`".** From plans 3 and 5. Rejected: automatic re-exec (plan-4; surprising) and refusal (plan-2; blocks recovery).
23. **Spec edits: exactly the two one-token placeholder fixes (§4); no gate-language relaxation until probe scorecards show gates cannot pass.** All six.
24. **Tests are byte-frozen from SPEC-TO-TESTS acceptance through LANDING; a wrong test is UPSTREAM; `ERRATA.md` gives producers a place to record a frozen input's defect without unfreezing anything.** From all six (freeze) and plan-6 (errata).
25. **A rendered checkpoint or `done` always tells the driver the exact next command and the exact text to relay** (`record_command`, `owner_message`, `how_to_resume`). From plans 2 and 3. The driver's freedom is spawning and relaying.

---

## 2. Design

### 2.1 Principles the implementer applies everywhere

- The runner reads spec files only through `config.py` (keys, with typed defaults) and `render.py` (text with `{{ }}` tokens). It never matches a phrase from prose. The only structural conventions used: token grammar `{{ ns.key }}`; prose file naming `<STEP>-OVERVIEW.txt`, `<STEP>-GATE.txt`, `COMMON-*.txt`; YAML keys; `roundPaths` values; the `N`-run in `roundPaths.folder`.
- Every machine-parsed word (statuses, verdicts, finding fields, resolution and ruling words, the `KEY:` contract lines) is emitted by the runner into `{{ plumbing.PROCESS-INSTRUCTIONS }}` and parsed by the runner. `docs/PROCESS.md` carries a "wording-adjacent rules" table (§2.15) listing every place a runner rule mirrors prose; the drift test's failure message points at it.
- Unknown is a warning, never a crash: unknown config keys are kept and exposed; missing keys take documented defaults with a `doctor` warning; an unresolvable token renders as `[unresolved: ns.key]` and is reported; an unknown prose file is reported, not loaded.
- Everything the runner knows is in files committed after every step. No daemon, database, lock server, lease, heartbeat or TTL. Git is the lock manager.
- Every command is idempotent or refuses (exit 2); never double-applies. Every state write is atomic (`tmp` + `os.replace`, retried five times on `PermissionError`), UTF-8, LF. Every spec-text read strips a BOM and normalizes CRLF/CR to LF before hashing or rendering.
- No `shell=True`. Every subprocess is an argv list with `cwd`, `capture_output=True`, `text=True`, `encoding="utf-8"`, `errors="replace"`; git calls add `-c user.name=<gitIdentity.name> -c user.email=<gitIdentity.email>`, `GIT_TERMINAL_PROMPT=0`, and a timeout (`gitTimeoutSeconds`, network ops ×3). A string `verify`/`suiteCommand` is split with `shlex.split(cmd, posix=os.name != "nt")`. Timeouts kill the process tree (`CREATE_NEW_PROCESS_GROUP` + `taskkill /T /F /PID`; `killpg` elsewhere).
- Paths are compared after `os.path.normcase` and slash normalization; prefix checks use `PurePosixPath.parts` (`src/` must not match `src2/`). Timestamps are UTC `%Y-%m-%dT%H:%M:%SZ`. JSON is written `indent=2, ensure_ascii=False` with a trailing newline. Every path printed in an action or a prompt is absolute; every path stored in state or artifacts is H-relative POSIX.
- `src/`, `docs/`, `tests/` are living and charged per token from the first real round: dense code, no docstrings restating code, no defensive code for impossible states, no module-level side effects (`run.main(argv) -> int` builds everything from `--root`).

### 2.2 Repository layout after the build

```
CLAUDE.md                     3 lines: entry harness/AGENTS.md; runner `py -3.13 harness/src/run.py --help`; spec files are the owner's
README.md                     what it is, quick start, how to run the suite, the test ladder (§7)
.gitignore                    .worktrees/  harness/OWNER.log  harness/DRIVER.json  harness/PLAN-DRAFT.json  harness/runner.local.yaml  __pycache__/  *.pyc  .pytest_cache/
pytest.ini                    testpaths = harness/tests; addopts = -q -p no:cacheprovider; markers slow, real
.claude/settings.json         hooks: UserPromptSubmit and SessionStart -> py -3.13 harness/src/owner_log_hook.py
.claude/agents/               shackles-producer-<rung>.md, shackles-gate-<rung>.md, generated by `run.py agents --write` (§2.13)
spec.yaml  bootstrap/         the owner's; unchanged
harness/
  AGENTS.md project.yaml subAgents.yaml locked_prose/     spec files; unchanged except §4
  INDEX.md                    routing, one grep-able `alias, alias -> path` line each
  docs/PROCESS.md             normative rules, one sentence per line (merge-friendly)
  docs/DRIVER.md              operating a round from a chat session, command by command
  docs/TESTING.md             suite map, fixtures, stub modes, probes, sandbox, baseline procedure
  docs/TODO.md                carry-forward, `## round NNNN` sections appended and pruned by POSTMORTEM; seeded by the bootstrap
  docs/CLARIFICATIONS.md      carry-forward, same shape
  src/run.py                  entry: sys.path insert, argparse, dispatch, exit codes
  src/runner.yaml             runner-owned settings and the step table (§2.3, §2.4)
  src/plumbing/producer.txt gate.txt chat.txt <STEP>.txt   the PROCESS-INSTRUCTIONS templates (§2.5)
  src/owner_log_hook.py       stdlib-only hook script (§2.13)
  src/shackles/__init__.py config.py steps.py render.py schemas.py gitx.py round.py checks.py ledger.py landing.py specbase.py agents.py doctor.py sandbox.py probe.py
  tests/conftest.py fixtures.py stub_agent.py test_*.py fixtures/toy/ fixtures/defects/ fixtures/replays/
  archives/
    spec-baseline.json        accepted hashes of spec.yaml and every listed file (§2.14)
    spec-acks.jsonl           one line per acceptance, append-only
    probes/RUNS.jsonl         one line per real-agent probe or sandbox run (§7)
    rounds/NNNN/              round folders, exactly as `roundPaths` says
```

Size budget: `src/` ≈ 2,600 lines of Python (no module over 700), plumbing ≈ 150 lines, docs ≈ 450 lines, tests ≈ 2,500 lines. `harness/archives/` and `.claude/` are not living (uncharged).

### 2.3 Configuration (`config.py`)

`load(root, spec_commit=None) -> Config`. Sources, later wins: `DEFAULTS` (code; every key the runner reads, valued as `project.yaml` is today) < `harness/src/runner.yaml` < `harness/project.yaml` (owner keys win so the owner can adopt an operational key later without a bootstrap edit) < `harness/runner.local.yaml` (gitignored, machine-local: the `claude` path). `subAgents.yaml` (path from `project.subAgentsFile`) loads into `cfg.roster` keyed by rung. When `spec_commit` is given, `spec.yaml`, `project.yaml`, `subAgents.yaml` and the locked prose are read with `git show <spec_commit>:<path>`; `runner.yaml` and `runner.local.yaml` are always read from the working tree (they are the runner's, not the round's). Missing keys and type mismatches become `cfg.warnings` (one-line strings) printed by `doctor`, written to HISTORY at `start`, and included as `warnings` in every `next` action; a structurally unusable file (not a mapping) is an error.

Derived: `cfg.id_width` = length of the `N`-run in the last component of `roundPaths.folder` (default 4); `cfg.gates()` = ordered `{name: bool}` from `project.gates` (absent gate ⇒ disabled + warning; any truthy value ⇒ enabled); `cfg.paths.*` for every `roundPaths` entry, `livingSourcePaths`, `lockedProsePath`, `archivesPath`, all H-relative, resolved to repo-relative with `..` allowed and refused if they escape R; `cfg.rung(key)` → roster entry (unknown key → warning, falls back to `maxAgent`, then the first roster key).

`runner.yaml` (committed, runner-owned, every key overridable):

```yaml
mainBranch: main
worktreeDir: .worktrees            # repo-root relative; must be gitignored (start refuses otherwise)
branchPrefix: round/
pushAttempts: 5                    # bounds the claim loop and both push loops
infraRetries: 3
gitTimeoutSeconds: 120
gitIdentity: {name: shackles-runner, email: runner@shackles.local}
suiteCommand: [py, -3.13, -m, pytest, -q, harness/tests, -m, "not real"]   # cwd = R; the project's permanent suite
suiteTimeoutSeconds: 1800
settleAfterUpholds: 2              # wording-adjacent: COMMON-GATE "upheld twice is settled"
ownerHoursPerCheckpoint: 0.1       # attention estimate priced at project.ownerHourlyRate; resume commands may pass --minutes
runBudgetMultiple: 2               # headless --max-budget-usd = step budget x this; budgets are targets
promptWarnBytes: 120000            # W2 warning above this
historyNoteChars: 2000
testPatterns: {".py": "^\\s*(async\\s+)?def\\s+test_\\w+", ".js": "\\b(it|test)\\s*\\(", ".ts": "\\b(it|test)\\s*\\("}
cleanupExtraPaths: ["docs/", "INDEX.md"]          # CLEANUP may touch these besides implPaths
carryForwardFiles: ["docs/TODO.md", "docs/CLARIFICATIONS.md"]   # POSTMORTEM may edit these; CHAT-TO-PLAN reads them
modelAliases: {claude-fable-5-1: fable, claude-opus-5: opus, claude-sonnet-5: sonnet}
envelopePrefixes: ["<task-notification", "<system-reminder", "[SYSTEM NOTIFICATION", "<wake ", "<webhook-payload", "<event "]
claudeSearchPaths: ["%APPDATA%/Claude/claude-code/*/claude.exe", "~/.local/bin/claude"]
agentCommand: ["{claude}", "--print", "--output-format", "json", "--system-prompt-file", "{prompt_file}",
               "--model", "{model}", "--effort", "{effort}", "--max-budget-usd", "{budget_cap_usd}",
               "--json-schema", "{result_schema}", "{tool_flags}", "--permission-mode", "bypassPermissions",
               "--no-session-persistence", "{task}"]
agentTask: "Do the task in your system prompt. Your final message must be exactly the JSON object it specifies and nothing else."
gateToolFlags: ["--tools", "Read", "Grep", "Glob"]
producerToolFlags: ["--disallowedTools", "Bash(git push:*)", "Bash(git commit:*)", "Bash(git reset:*)", "Bash(git checkout:*)", "Bash(git clean:*)", "Bash(git merge:*)", "Bash(git rebase:*)", "Bash(git tag:*)"]
scrubEnv: [GH_TOKEN, GITHUB_TOKEN, GIT_ASKPASS]
steps: [...]                       # §2.4; the `checkpoint:` attributes are wording-adjacent: "Checkpoint after this step"
```

`project.yaml` keys the runner reads, each with a code default equal to today's value: `budget`, `hardStopBudgetMultiple`, `lostValuePerHour`, `ownerHourlyRate`, `costToWaitForOwner`, `planCostPerWord`, `specCostPerWord`, `livingFileTokenCap`, `livingFileCostPerToken`, `livingFileCostPerTokenOverCap`, `livingFileBaseCost`, `testBaseCost`, `tokenBytes`, `maxRefactorOverhead`, `gates`, `defaultShares`, `livingSourcePaths`, `lockedProsePath`, `archivesPath`, `roundPaths`, `maxSimultaneousSubAgentsPerRound`, `maxRoundAttempts`, `maxFailuresBeforeStop`, `maxTurnsPerRun`, `maxRunWallClockHours`, `verifyTimeoutSeconds`, `gatesFraction`, `workFraction`, `estOutputFraction`, `driverUsdPerStep`, `subAgentsFile`, `maxAgent`, `gateAgent`, `systemTestAgent`; `shackles` and `currency` are rendered only. §2.11 says how each number is used.

### 2.4 Pipeline (`steps.py`)

`runner.yaml: steps` lists producers and mechanical steps in order. Gates are derived: producer X has gate `X-GATE` iff `<lockedProsePath>/X-GATE.txt` exists at `spec_commit`; it is enabled iff `cfg.gates()["X-GATE"]` is true. The `approval` row is the mechanical `CHAT-TO-PLAN-GATE` named in `project.gates`.

```yaml
steps:
  - {name: CHAT-TO-PLAN, kind: chat, artifact: plan}                       # done by the driver before start
  - {name: CHAT-TO-PLAN-GATE, kind: approval}                              # mechanical: plan schema + verified quote
  - {name: PLAN-AGENTS, kind: producer, artifact: agentsPlan}
  - {name: PLAN-TO-SPEC, kind: producer, artifact: spec, checkpoint: spec-review}
  - {name: SPEC-TO-TESTS, kind: code, writes: testPaths, accept: freezeTests}
  - {name: SPEC-TO-IMPLEMENTATION, kind: code, writes: implPaths, verify: true}
  - {name: TESTS-TO-SUITE, kind: producer, artifact: suite, accept: archiveTests}
  - {name: CLEANUP, kind: code, writes: cleanup, verify: true, suite: true, checkpoint: pre-landing}
  - {name: LANDING, kind: landing}
  - {name: POSTMORTEM, kind: producer, artifact: postmortem, writes: carryForward}
  - {name: FINISH, kind: finish}
```

Conventions: `artifact` keys index `project.roundPaths.artifacts` (`spec` also implies `specProse`); `writes` names a path set (`testPaths`/`implPaths` from SPEC.json; `cleanup` = implPaths ∪ `cleanupExtraPaths` ∪ living paths not under testPaths; `carryForward` = `carryForwardFiles`); a producer's prose file is `<NAME>-OVERVIEW.txt`; a gate's is `<NAME>-GATE.txt`; every producer may write its own artifacts and the round folder. `accept` effects run when the producer is **accepted** (its gate PASSes, or it is DONE with clean mechanical checks when the gate is disabled or overridden); `checkpoint` names the review checkpoint raised after acceptance unless delegated through the step; the step table is the only place checkpoint placement lives.

Loader validation (errors stop every command): unique names; kinds in {chat, approval, producer, code, landing, finish}; exactly one `chat`, `approval`, `landing`, `finish`, in that relative order with `landing` after every code step and `finish` last. Cross-checks against the spec (warnings from `doctor`, errors from `start`): every producer/code step has its `-OVERVIEW.txt` (start: error "step X has no prose; restore the file or override X"); every `<X>-GATE.txt` names a table step (else "prose for unknown step"); every `project.gates` key is a derived gate or `CHAT-TO-PLAN-GATE` and their order agrees with the table's order (warning: the table wins); every other `locked_prose/*.txt` is `COMMON-*` or named by a step (else "unknown prose file"); `maxAgent`, `gateAgent`, `systemTestAgent` are roster keys.

Overrides (`--override A,B` at start, or `override --steps` later): named steps and gates are skipped this round with a HISTORY line. Not overridable: CHAT-TO-PLAN, CHAT-TO-PLAN-GATE, PLAN-TO-SPEC (nothing runs without a spec), LANDING, FINISH. Overridden producer defaults: PLAN-AGENTS → `defaultShares` and default rungs; TESTS-TO-SUITE → every changed test joins the suite; SPEC-TO-TESTS → no tests, nothing frozen; SPEC-TO-IMPLEMENTATION, CLEANUP, POSTMORTEM → skipped. An overridden or disabled gate auto-passes with `FINDINGS/<GATE>-<n>.json` = `{"verdict":"PASS","findings":[],"source":"disabled"|"override"}`; mechanical checks still run.

Delegation: `delegated: null | "all" | "through:STEP"` skips review-class checkpoints (`spec-review`, `pre-landing`) at or before STEP. Stop-class checkpoints (`approval` after a plan change, `needs-owner`, `blocked`, `failure-limit`, `round-limit`, `hard-stop`, `upstream-plan`, `spec-changed`, `spec-edits`, `infra`, `finish-conflict`) are never skipped.

### 2.5 Rendering and prompts (`render.py`, `src/plumbing/`)

**Engine.** Tokens `\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}`. Namespaces: `prose.NAME` → `<lockedProsePath>/NAME.txt` at `spec_commit`, rendered recursively (depth ≤ 6; a cycle renders `[include cycle: NAME]`); **each prose file renders at most once per document** — a second include renders `(NAME: as above)`. `plumbing.NAME` → §below. `project.*`, `round.*`, `step.*`, `agent.*`, `paths.*` → dotted lookup in the context. Value formatting: `str` verbatim; `int` as is; `float` via `repr` with a trailing `.0` stripped (`0.1`, `12.5`, `10`); `bool` `true`/`false`; `None` `none`; list/dict compact JSON with `ensure_ascii=False` (so `{{ project.gates }}` renders `{"CHAT-TO-PLAN-GATE": 0, ...}`). Unresolved → `[unresolved: ns.key]` in place, collected into the render result's `warnings`, appended to HISTORY (`FLAG (runner): unresolved tokens …`) and to the action's `warnings`. Raw text (artifacts, diffs, AGENTS.md) is never passed through the engine.

**Prompt assembly.** A producer prompt is the rendered `<STEP>-OVERVIEW.txt`; a gate prompt the rendered `<STEP>-GATE.txt`; nothing is prepended or appended, except that a prose file lacking the `plumbing.PROCESS-INSTRUCTIONS` token gets the block appended after a blank line (with a warning), so an agent always receives its contract. The prompt is written to `PROMPTS/<STEP>-<attempt>.txt`; for a code step's gate the runner also writes `PROMPTS/<STEP>-<attempt>.diff` (`git diff <step_start_commit> HEAD -- <write paths>`) and names it in `DIFF_FILE:`. A prompt over `promptWarnBytes` yields warning W2, never truncation.

**`plumbing.PROCESS-INSTRUCTIONS`** = render of `src/plumbing/<kind>.txt` (`producer.txt` for producer and code steps, `gate.txt`, `chat.txt`) followed by `src/plumbing/<STEP>.txt` when it exists (step-specific mechanics: SPEC.json fields for PLAN-TO-SPEC, the roster and pies for PLAN-AGENTS, the keep/archive partition for TESTS-TO-SUITE, the carry-forward files for POSTMORTEM, the `start` command and the word→command table for CHAT-TO-PLAN). The templates are runner-owned; their wording is free to change; only the `KEY:` lines and the JSON contracts are load-bearing (tests and the stub parse them).

**`plumbing.GATE-PROSE`** (inside a producer prompt) = the producer's `<STEP>-GATE.txt` rendered in **embed mode**: includes already rendered in this document render `(NAME: as above)`; `plumbing.PROCESS-INSTRUCTIONS` renders `(gate mechanics omitted; see docs/PROCESS.md)`; `agent.*` renders `<the artifact you produce>`; other tokens render normally. A disabled or overridden gate prefixes one line: `(This gate is disabled this round: a DONE result with clean mechanical checks passes. The standard below still applies.)` A step with no gate file renders a one-line runner description from the table; for CHAT-TO-PLAN: `The gate is mechanical: the runner validates PLAN.json and requires the owner's approval words, quoted verbatim, before the round starts.`

**Context namespaces.** `paths`: `harness_root`, `repo_root`, `worktree`, `agents_md`, `run_py`, `round_folder` (absolute). `project`: every loaded key plus `remaining` (= `budget` − project-wide spend) and `spent`, added only when `project.yaml` lacks the key. `round`: `id` (`NNNN`), `number`, `folder` (H-relative), `branch`, `base_commit`, `spec_commit`, `plan` (PLAN.json as text: summary, then Scope / Validation / Non-goals / Assumptions bullets, quote, todos), `budget`, `spend`, `remaining`, `budgets` (per step), `history` (last five rounds as `round N: quoted X actual Y (outcome)`), `todos` and `clarifications` (the carry-forward files' text verbatim, or `none`), `judgment_files` (both absolute paths), `judgment_counts`, `errata` (ERRATA.md text or `none`), `mode`, `owner_log` (the slice). Before a round exists (`plan`, `render --fixture`) every `round.*` renders `none yet`. `step`: `name`, `kind`, `attempt`, `budget`, `budget_cap`, `max_turns`, `wall_clock_hours`, `retry_cost` (the producer's per-run budget; for a gate, its producer's), `agent` (`name (model, effort)`), `sub_agents` (allowed count), `gate` (name or `none`), `gate_enabled`, `mechanical_checks` (ids with one-line meanings), `tools` (`read-only`|`all`). `agent`: `artifact_path`, `result_file`, `diff_file`, `inputs` (absolute paths this step reads), `write_paths`, `frozen_paths`, `verify`, `findings` (the latest findings for this producer with the producer's resolutions and the gate's rulings, plus carried findings, as JSON, or `none`), `previous` (the previous final message, or `none`), `question`, `assumption`, `conflicts` (conflicted paths during a merge attempt, else `none`), `sibling_paths`, `roster` (compact list of `{key, name, model, effort, spawnCost}`), `schema` (the artifact or result schema, pretty JSON).

**`src/plumbing/producer.txt`** (the load-bearing shape; the implementer may improve wording):

```
PROCESS INSTRUCTIONS (mechanical; written and parsed by the runner; follow exactly).
STEP: {{ step.name }}
KIND: {{ step.kind }}
ATTEMPT: {{ step.attempt }}
ROUND: {{ round.id }}
WORKTREE: {{ paths.worktree }}
HARNESS: {{ paths.harness_root }}
ARTIFACT: {{ agent.artifact_path }}
RESULT_FILE: {{ agent.result_file }}
WRITE_PATHS: {{ agent.write_paths }}
Paths in this prompt are relative to HARNESS unless absolute; use absolute paths in tools. Read {{ paths.agents_md }} first: its bullets are invariants. INDEX.md beside it routes.
Inputs: {{ agent.inputs }}
You may create or change files only under WRITE_PATHS and the round folder {{ paths.round_folder }}. Frozen, do not touch: {{ agent.frozen_paths }}. Files listed in spec.yaml are the owner's: change one only when genuinely necessary, minimally; every such change is shown to the owner as a diff before the round lands.
Never run git commit, push, reset, checkout, clean, merge, rebase or tag; the runner commits your work. Write nothing to RESULT_FILE: your final message is the result and the driver saves it.
Budget for this run: ${{ step.budget }} (a target). Turns: about {{ step.max_turns }}. Wall clock: {{ step.wall_clock_hours }} h. Sub-agents you may run at once: {{ step.sub_agents }}; their cost is yours; report them in sub_agents.
Judgment calls: append one line per call to {{ round.judgment_files }}; never rewrite existing lines. A defect in a frozen input you may not change goes to ERRATA.md in the round folder, one line, then proceed on your stated reading.
Findings to resolve (every id must appear in resolutions as fixed, disputed or deferred; a settled id cannot be disputed; deferred goes to the postmortem): {{ agent.findings }}
Your previous final message: {{ agent.previous }}. ARTIFACT holds your previous attempt; revise it in place.
Merge in progress, conflicted files to resolve this attempt (edit, then git add each one; run verify; nothing else): {{ agent.conflicts }}
Verify command, run from the repo root: {{ agent.verify }}
Artifact contract: {{ agent.schema }}
Checked mechanically before any gate: {{ step.mechanical_checks }}. A failure returns to you as a finding without spending a gate.
Final message: exactly one JSON object and nothing else:
{"status": "DONE" | "NEEDS-OWNER" | "UPSTREAM" | "BLOCKED", "notes": "<one paragraph>", "question": "<NEEDS-OWNER: the question and the value at stake>", "assumption": "<NEEDS-OWNER: what you built on meanwhile>", "target": "<UPSTREAM: the earlier producer step whose artifact is wrong; quote the contradiction in notes>", "resolutions": {"<id>": {"status": "fixed" | "disputed" | "deferred", "reason": "<why>"}}, "cost_usd": <optional>, "usage": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, "sub_agents": [{"agent": "<rung>", "usage": {...}} | {"agent": "<rung>", "cost_usd": 0}]}
Omit fields that do not apply. Then: DONE -> {{ step.gate }} (enabled: {{ step.gate_enabled }}) after the mechanical checks. NEEDS-OWNER -> the gate rules on the question (withdrawn: judged on your assumption; upheld: the round pauses and the owner's answer returns to you as a finding). UPSTREAM -> the round returns to the target step with your notes as a finding. BLOCKED -> the round pauses for the owner.
```

`gate.txt` differs: `KIND: gate`, `READ_ONLY: true`, `DIFF_FILE:` line, no WRITE_PATHS; "You are read-only: read anything, write nothing, run nothing that changes files; a run that changes files has the changes discarded. You see the artifact (or DIFF_FILE), its inputs, prior findings with the producer's resolutions, the producer's final message at RESULTS/…, and the judgment-call files; never the producer's transcript."; `The producer's question, if any: {{ agent.question }} (assumption: {{ agent.assumption }})`; `Already checked mechanically: {{ step.mechanical_checks }}. Do not repeat them.`; `A FAIL costs ${{ step.retry_cost }} (the producer's retry) plus this gate again.`; the verdict contract:

```
{"verdict": "PASS" | "FAIL", "findings": [{"id": "F<n>", "quote": "<verbatim text judged>", "reason": "<why>", "suggestion": "<what would prevent the FAIL>", "blocking": true | false}], "rulings": {"<id>": {"status": "upheld" | "withdrawn", "quote": "<verbatim>"}}, "needs_owner": {"status": "upheld" | "withdrawn", "reason": "<why; withdrawn: the answer to assume>"}, "judgment_calls": {"defined": ["<one line each>"], "undefined": ["<one line each>"]}, "notes": "<one line>", "cost_usd": <optional>, "usage": {...}}
Ids continue from F<max prior id>. Omit rulings and needs_owner when there is nothing to rule on. Your judgment calls go in judgment_calls; the runner appends them to the round's files. Then: PASS -> the round advances; FAIL -> the producer runs again with your findings, then this gate again.
```

`chat.txt` (rendered by `run.py plan`, no round): inputs = `docs/TODO.md`, `docs/CLARIFICATIONS.md`, the last three landed rounds' `POSTMORTEM.md` paths, the quote-versus-actual history, `spend --project`; the PLAN schema; the word→command table (approve/approved → `start --plan F --quote "<words>"`; delegate/delegated → add `--delegated`; delegate through STEP → `--delegated --through STEP`; override + names → `--override A,B`; the plan itself cannot be skipped); write the draft to `harness/PLAN-DRAFT.json` with `presented_at` set when the plan is shown; on the owner's word run `start`.

The machine-readable contract is the last occurrence of each `KEY:` line (`STEP`, `KIND`, `ATTEMPT`, `ROUND`, `WORKTREE`, `HARNESS`, `ARTIFACT`, `RESULT_FILE`, `WRITE_PATHS`, `DIFF_FILE`). The stub agent and `probe` parse these.

### 2.6 Schemas (`schemas.py`)

A ~100-line validator: `type` (object/array/string/number/integer/boolean/null, unions), `required`, `properties`, `additionalProperties` (default true), `items`, `enum`, `minimum`, `minItems`, `pattern`; errors are `NAME: path message` strings used verbatim in findings and asserted verbatim in tests. Schemas are Python dicts; `run.py schema NAME` prints one; `agents.py` emits JSON Schema for `--json-schema`.

- **PLAN** required: `presented_at` (UTC `…Z`), `quote_usd` (> 0), `summary`, `scope[]` (≥ 1), `validation[]` (≥ 1), `non_goals[]`; optional `assumptions[]`, `todos {id: {todo, status: taken|deferred, reason, budget_usd}}`, `owner_words [{at, text}]`, `title`; `round` set by `start`.
- **AGENTS_PLAN** required: `round`, `shares {work {STEP: f}, gates {STEP: f}}` (keys as `defaultShares`: gates keyed by the producer's name); optional `agents {STEP: rung}`, `gateAgents {GATE: rung}`, `subAgents {STEP: int}`, `notes`. Rules (S2): keys are present steps; rungs exist; each map sums to 1 ± 0.01 over present steps (absent or mechanical steps count 0); `subAgents` ≤ `maxSimultaneousSubAgentsPerRound`.
- **SPEC** required: `round`, `summary`, `verify` (string or argv list), `implPaths[]` (≥ 1), `testPaths[]`, `nonGoals[]`; optional `verifyTimeoutSeconds`, `refactorShare` (0..1), `testPlan`, `notes`. Rules (S3): H-relative POSIX paths inside R; `implPaths`/`testPaths` disjoint by path parts; none inside the round folder, `lockedProsePath`, or a spec file; `refactorShare ≤ maxRefactorOverhead`; `SPEC.md` exists.
- **SUITE** required: `round`, `keep[]`, `archive[]`, `notes`; optional `raise_with_owner[]`. Rules (T1): every test file added or modified this round under `testPaths` (`git diff --name-only <base_commit> -- <testPaths>` plus untracked) appears exactly once; listed paths exist.
- **POSTMORTEM.md**: non-empty.
- **RESULT** (producer final message) required: `status` ∈ DONE|NEEDS-OWNER|UPSTREAM|BLOCKED; optional `notes`, `question`, `assumption`, `target`, `resolutions {id: {status: fixed|disputed|deferred, reason}}`, `cost_usd`, `usage {input, output, cache_read, cache_write}`, `sub_agents []`. Consistency: NEEDS-OWNER ⇒ `question`; UPSTREAM ⇒ `target` is an earlier producer.
- **FINDINGS** (gate final message) required: `verdict` ∈ PASS|FAIL, `findings [] {id, quote, reason, suggestion, blocking}`; optional `rulings {id: {status: upheld|withdrawn, quote}}`, `needs_owner {status, reason}`, `judgment_calls {defined [], undefined []}`, `notes`, `cost_usd`, `usage`. The runner adds `source` (`gate`, `mechanical`, `disabled`, `override`, `landing`, `upstream`, `blocked`, `owner`, `runner`), `step`, `attempt`.
- **STATE**: §2.7. **ACTION**: §2.8.

Result extraction (`agents.extract_json(text)`): the whole text; else the content of a ```` ``` ```` fence; else the last balanced top-level `{…}` that parses. Applied to whatever the driver saved (`record` accepts raw text). Normalization on gate results: missing or duplicate finding ids become `<GATE>-<attempt>.F<n>`; a missing `suggestion` becomes `(none given)` with a HISTORY note; a new finding whose whitespace-normalized `quote` equals a withdrawn finding's is dropped as non-blocking with a HISTORY note (mechanical support for "do not re-raise a withdrawn finding"); the verdict is authoritative — PASS with a blocking finding ⇒ flags set non-blocking; FAIL with none blocking ⇒ findings kept as given; either mismatch is a HISTORY line.

### 2.7 Round data model (`round.py`)

Round id: int, rendered zero-padded to `cfg.id_width`. Branch `<branchPrefix><NNNN>`; worktree `<M>/<worktreeDir>/<NNNN>`; tags `<branchPrefix><NNNN>-landed`, `-abandoned`; folder = `roundPaths.folder` with the `N`-run replaced, under H. Next id = `1 + max(local round-folder ids, origin `round/<digits>` branch ids)`; tails must be ASCII digits; tags never count.

Round folder (names from `roundPaths`; the ones below are today's): `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SPEC.md`, `SUITE.json`, `POSTMORTEM.md`, `STATE.json`, `HISTORY.md`, `OWNER.log` (slice), `PROMPTS/<STEP>-<n>.txt` (+ `.diff`), `RESULTS/<STEP>-<n>.json`, `FINDINGS/<STEP>-<n>.json` (gate verdicts) and `FINDINGS/<STEP>-<n>.mechanical.json`, `tests-archive/`, `DEFINED_JUDGMENT_CALLS.md`, `UNDEFINED_JUDGMENT_CALLS.md` (created at `start` with a one-line header each), `ERRATA.md` (created empty, append-only, never hashed). Runner-owned files agents may not write: `STATE.json`, `HISTORY.md`, `OWNER.log`, `PROMPTS/`, `RESULTS/`, `FINDINGS/`, `tests-archive/` (a change to one is reverted and flagged, M0).

**`STATE.json`** (validated on every save; unknown keys rejected):

```
round int; branch; mode "worktree"|"no-branch"; created_at; status active|checkpoint|finished|abandoned
step; attempts {step: n}; failures {step: n}; infra_errors {step: n}; retries int
step_starts {step: sha}; step_commits {step: sha}; last_runner_commit sha; inputs_hash {PLAN, SPEC}
budget_usd; spend {entries [], agent_usd, driver_usd, owner_usd, living_usd}; words_charged {plan, spec}
base_commit; spec_commit; approval {quote, at, verified bool, source} | null; delegated null|"all"|"through:STEP"; overrides []
pending_action {step, attempt} | null; checkpoint {kind, step, raised_at, artifact, question, how_to_resume} | null; review_due STEP|null
pending_question {question, assumption} | null; pending_questions []; owner_answers []
last_findings {producer: relpath}; carried_findings []; deferred_findings []; findings_ledger {id: {upheld_count, settled, withdrawn, quote}}
tests_frozen_at sha|null; merge_pending {target, target_sha, automerge_tree, conflicted []} | null
hard_stop_raised bool; round_limit_raised bool; owner_since; landed_at; finished_at; abandoned_at; main_before
judgment_counts {defined, undefined}; spec_edits []; spec_edits_approved bool; runner_skew bool
```

No worktree key (derivable), no lock/lease/pid/owner field: ownership is "can I still push this branch".

`HISTORY.md` is append-only: `## <UTC> <STEP> attempt <n> — <event>` then bullets (status or verdict, cost and source, findings ids, notes truncated to `historyNoteChars`, judgment-call deltas, living estimate for code steps); `## <UTC> CHECKPOINT <kind> …`, `## <UTC> RESUME <command> — quote: "<owner words>"`, `## <UTC> LANDING …`, `## <UTC> SPEC EDIT` (with the diff), and single `FLAG (runner|driver): …` lines for anomalies.

Aggregation across rounds (`spend --project`, `round.history`, `rounds`): every local round folder's `STATE.json`, plus for every `origin/round/*` branch (after a fetch, best effort) the `STATE.json` read with `git show`, de-duplicated by id preferring the more advanced `attempts`. Live siblings count toward `project.remaining`.

### 2.8 CLI (`run.py`)

`py -3.13 harness/src/run.py [--root DIR] [--round N] [--verbose] <command> …`. `--root` is a checkout or a round worktree (default: the nearest ancestor of cwd containing `spec.yaml`, else the invoking `run.py`'s repo); `--round` selects the round (default: the branch `round/<id>` of `--root`, else the single unfinished local round, else required). Every command prints exactly one JSON object on stdout; humans read stderr. Exit codes: `0` ok/finished, `1` error, `2` usage / invalid input / guard refusal, `3` check failed or drift, `10` checkpoint. `sys.stdout.reconfigure(encoding="utf-8")` at startup. Every command is also callable in-process: `run.main(argv) -> int`.

| Command | Reads | Writes / prints |
| --- | --- | --- |
| `doctor [--probe-cli] [--json]` | environment, spec, config, git, baseline | report `{errors, warnings, info}`; exit 3 on errors (§2.14) |
| `plan` | working-tree spec, carry-forward docs, aggregated rounds | the rendered CHAT-TO-PLAN prompt and the PLAN schema; no round needed |
| `render --step S [--attempt N] [--fixture] [--all]` | round or a synthetic context | prompts to stdout; never touches state |
| `schema NAME` | — | the schema |
| `agents --write` | roster | `.claude/agents/*.md` regenerated; without `--write` prints the roster and drift |
| `spec check\|diff\|accept [--note T]` | spec files, baseline | `accept`: baseline + ack line (§2.14); exit 3 on drift |
| `start --plan F --quote T [--delegated [--through STEP]] [--override A,B] [--budget X] [--branch NAME] [--base REF] [--no-branch] [--accept-spec --note T] [--no-push]` | plan, origin, owner log | claim, worktree, round folder, start commit + push; prints `{round, folder, branch, worktree, runner}` |
| `next [--no-push] [--discard]` | STATE, owner log, git | mechanical effects, prompt, STATE, commit; prints an action, a checkpoint (10) or done |
| `record --step S --attempt N [--result F] [--cost USD \| --usage IN,OUT,CR,CW] [--agent RUNG] [--infra-error TEXT] [--no-push]` | result file, STATE | RESULTS/, FINDINGS/, STATE, HISTORY, commit + push (the fence) |
| `approve --quote T [--minutes M]` · `delegate [--through STEP] --quote T` · `answer --text T --quote T` · `override --steps A,B --quote T` · `abandon --reason R [--quote T]` | STATE, owner log | resume/transition, OWNER slice, HISTORY, commit + push |
| `run --until checkpoint\|step\|done [--no-push]` | — | headless loop: next → agentCommand → record |
| `status [--json]`, `spend [--project]`, `rounds [--prune]`, `cost` (living-charge preview of the current diff), `judgment-calls` | STATE, git | read-only, except `--prune` removes worktrees of finished/abandoned rounds |
| `check` | STATE, git, verify/suite | the current step's mechanical checks or the landing check; nothing recorded, pushed, tagged or charged (I9); exit 3 on findings |
| `owner --say TEXT [--at TS]` | — | appends a line to `<M>/harness/OWNER.log` (hookless environments, tests) |
| `sandbox --new DIR [--task toy] [--origin]` | this repo | `DIR/origin.git` + `DIR/repo` (§7) |
| `probe --step S [--seed clean\|defect] [--agent RUNG] [--exec] [--dir DIR]` · `probe check --dir DIR` | fixtures | a temp sandbox positioned at S and the action; the scorecard (§7) |

Action JSON (`next`, exit 0): `{"kind": "producer"|"gate", "round", "step", "attempt", "prompt_file", "result_file", "artifact", "diff_file", "worktree", "runner", "agent": {"key", "name", "model", "model_alias", "effort", "agent_type"}, "tools": "read-only"|"all", "budget_usd", "budget_cap_usd", "max_turns", "wall_clock_hours", "sub_agents", "spend", "record_command", "warnings": [], "runner_skew"}`. Checkpoint (exit 10): `{"kind": "checkpoint", "checkpoint": {"kind", "step", "raised_at", "artifact", "question"}, "owner_message", "how_to_resume": ["approve --quote ...", ...], "pending_questions", "undefined_judgment_calls": [last 5 lines], "spend"}`. Done: `{"kind": "done", "status", "main_synced", "landed_at", "finished_at", "pending_questions", "spend", "hint": "git pull --ff-only in the main checkout"}`.

### 2.9 Protocol

**Planning (driver, in chat).** `run.py plan` → converse → write `harness/PLAN-DRAFT.json` with `presented_at` when the plan is shown → on the owner's word, `start`. The driver's reading of the words is a DEFINED JUDGMENT CALL under `CHAT-TO-PLAN-OVERVIEW`; the quote is the evidence.

**`start`**, in order (nothing is created before step 5):
1. Load config from the working tree; loader errors → exit 1. Drift (§2.14) → exit 3 listing files and `spec accept`/`--accept-spec` unless `--accept-spec --note` is given.
2. Validate the plan file (PLAN schema; `presented_at` parses; `quote_usd > 0`; `--override` names are overridable table steps or gates; `--through` is a table step). Exit 2 on failure.
3. Quote verification: when `<M>/harness/OWNER.log` exists and `CHAT-TO-PLAN-GATE` is enabled, `--quote` (whitespace-normalized) must be a substring of a log line whose timestamp ≥ `presented_at`; else exit 2 `quote not found in owner log after <presented_at>`. When the gate is disabled or the log is absent the quote is recorded with `verified: false` and a HISTORY line.
4. Worktree-mode preconditions (skipped with `--no-branch`): `git check-ignore -q <worktreeDir>` and `harness/OWNER.log`; `git ls-remote --exit-code origin HEAD`; git ≥ 2.38 (for `merge-tree --write-tree`); `core.longpaths` unset on Windows is a warning with the command to set it.
5. Claim (§2.12): `git fetch origin`; base = `--base` else `origin/<mainBranch>`; CAS loop; `git worktree add -b <branch> <M>/<worktreeDir>/<NNNN> <base>`. With `--no-branch`: id = 1 + highest local folder id, current checkout and branch, base = HEAD, no fetch/CAS/worktree/push.
6. With the worktree (or checkout) as root: create the round folder and its files (§2.7); `PLAN.json` (copy, `round` set); `STATE.json` (`base_commit = spec_commit = HEAD`, `status active`, `step = CHAT-TO-PLAN-GATE` (the first `next` runs it and advances), `approval` recorded, `delegated`, `overrides`, `attempts {CHAT-TO-PLAN: 1}`, `owner_since = min(previous round's landed_at|abandoned_at, presented_at)`); `HISTORY.md`; the owner-log slice; ledger: the CHAT-TO-PLAN estimate entry (its `defaultShares` budget), `driverUsdPerStep`, plan words × `planCostPerWord` (`words_charged.plan`); config warnings → HISTORY; with `--accept-spec` the rewritten baseline and ack line. `git add -A`, commit `round NNNN: start`, `git push -u origin <branch>`. Print `{round, folder, branch, worktree, runner}` (`runner` = the worktree's `harness/src/run.py`).

**`next`**, in order:
1. Load STATE. `finished`/`abandoned` → print done (`main_synced` from state), exit 0.
2. Runner skew: sha256 of `src/run.py` + `src/shackles/*.py` of the running copy versus `<root>/harness/src` → `runner_skew` (warning only).
3. Out-of-band edits: re-hash `PLAN.json` → changed ⇒ `approval = null`, `step = CHAT-TO-PLAN-GATE`, downstream counters reset, `retries += 1`, HISTORY. Re-hash `SPEC.json` + `SPEC.md` → changed after PLAN-TO-SPEC's acceptance ⇒ `step = SPEC-TO-TESTS`, downstream reset, `retries += 1`. `ERRATA.md` is not hashed.
4. Tree state. `merge_pending` set and `MERGE_HEAD` exists → expected, keep. `merge_pending` set and no `MERGE_HEAD` (crash before the merge started) → re-run `git merge --no-commit --no-ff <target_sha>`. `MERGE_HEAD` without `merge_pending` → `git merge --abort`, infra error. `HEAD != last_runner_commit` → `git reset --soft <last_runner_commit>`, HISTORY `M0: agent commit undone`. Dirty tree (`git status --porcelain`, ignored files excluded): if `pending_action` is set and every dirty path lies within that step's write paths ∪ the round folder → exit 2 `unrecorded work for STEP attempt N: record it, or run next --discard` (never delete a producer's unrecorded work); otherwise, or with `--discard`: `git checkout -- .`, `git clean -fd` (never `-x`), `infra_errors[step] += 1`, HISTORY.
5. Refresh the owner-log slice from `<M>/harness/OWNER.log` (lines with timestamp ≥ `owner_since`, envelopes filtered) into the round's `OWNER.log`.
6. `status == checkpoint` → print the checkpoint, exit 10. (`next` never scans for words; the resume commands change state.)
7. Hard stop (§2.11) → checkpoint `hard-stop` once.
8. Loop over mechanical work until an agent run is due:
   - `CHAT-TO-PLAN-GATE`: PLAN schema (S1 ⇒ checkpoint `approval` carrying the errors); `approval` present ⇒ advance; absent ⇒ checkpoint `approval`.
   - overridden step or gate ⇒ HISTORY, defaults, advance.
   - disabled gate ⇒ auto-PASS file, acceptance effects, advance.
   - `review_due` set and not delegated through it ⇒ checkpoint (kind from that step's `checkpoint` attribute, artifact path), `review_due = null`; delegated ⇒ HISTORY `checkpoint skipped (delegated)`.
   - `LANDING` ⇒ §2.12; `FINISH` ⇒ §2.12.
   - producer, code step, or enabled gate ⇒ `attempt = attempts[step] + 1`; `step_starts[step]` if absent; render the prompt (and the diff for a code gate); `pending_action = {step, attempt}`; save; commit `round NNNN: STEP attempt N prompt` (no push); `last_runner_commit = HEAD`; print the action; exit 0.

**`record`**:
1. Guards: `status == active`, `state.step == S`, `N == attempts[S] + 1`, `pending_action == {S, N}`; else exit 2 with the reason (replays and out-of-order records are refused, never double-applied).
2. `--infra-error TEXT` (no result): `infra_errors[S] += 1`, tree reset as in `next` step 4 (the result file excepted), HISTORY, commit; at `infraRetries` at this attempt ⇒ finding `I1` ("no valid result after N runs: narrow the step") routed as a mechanical FAIL; exit 0.
3. Read `--result` (default: the action's `result_file`), extract JSON, validate RESULT or FINDINGS; failure ⇒ exit 2 with the errors, nothing consumed (the driver re-asks the agent for JSON only, or records `--infra-error`).
4. Copy the normalized JSON to `RESULTS/<S>-<N>.json`; `attempts[S] = N`; `pending_action = null`; ledger: agent entry (§2.11), `sub_agents` entries, driver entry.
5. **Gate**: G1: if the tree is dirty beyond the result file ⇒ discard (`checkout -- .`, `clean -fd`), HISTORY `G1: gate changed files; discarded`. Apply rulings to `findings_ledger` (upheld ⇒ `upheld_count += 1`, settled at `settleAfterUpholds`; withdrawn ⇒ recorded with the quote; a ruling on an unknown or settled id is ignored with a HISTORY note); drop re-raised withdrawn findings; normalize (§2.6); append `judgment_calls` lines to the two files with suffix ` (via runner, <GATE>-<n>)`; write `FINDINGS/<GATE>-<N>.json`. `needs_owner.upheld` (and a pending question) ⇒ checkpoint `needs-owner` with the question. Otherwise PASS ⇒ `step_commits[gate] = HEAD`, non-blocking findings → `carried_findings`, a withdrawn question's answer → finding `Q1` (non-blocking, "assume: …") appended to `carried_findings` and one line to `DEFINED_JUDGMENT_CALLS.md`, acceptance effects of the producer (§2.4), `review_due` if the producer has a checkpoint, advance. FAIL ⇒ `failures[producer] += 1`, `last_findings[producer]`, `step = producer`, limits (§2.11).
6. **Producer**: resolutions ⇒ ledger (`disputed` on a settled id ⇒ note `S2`, treated as upheld; ids missing from resolutions ⇒ non-blocking note `R1`; `deferred` ⇒ moved to `deferred_findings`). Judgment-file delta counted (`judgment_counts`); J1 append-only check; M5 spec-edit detection (§2.14). Then by status:
   - `DONE`: code step ⇒ M0, M1, M2 (revert + note), M3 verify (blocking), and for CLEANUP the suite (M4, blocking) — all on the attempt's diff (§2.10); artifact step ⇒ S1 schema + rules (blocking). `git add -A`, commit `round NNNN: S attempt N` (a merge commit when `MERGE_HEAD` exists; `merge_pending` cleared only if no unmerged entries remain, else finding `L3` blocks). Blocking findings ⇒ `FINDINGS/<S>-<N>.mechanical.json`, `failures[S] += 1`, `last_findings`, stay on S, limits. Clean ⇒ `step_commits[S] = HEAD`; for PLAN-TO-SPEC the X1 overlap warning (§2.12), carried to its gate; advance to the gate (enabled) or accept directly (disabled/overridden: effects, `review_due`, advance).
   - `NEEDS-OWNER`: commit work; `pending_question`; gate enabled ⇒ advance to the gate; disabled ⇒ mode approved ⇒ checkpoint `needs-owner`; delegated ⇒ one line `(runner) assumed: <assumption>` appended to `UNDEFINED_JUDGMENT_CALLS.md`, `pending_questions` += the question, HISTORY, treat as DONE.
   - `UPSTREAM`: commit work; `target` must be an earlier producer (else finding `S1` to S); finding `U1` (quote = notes) attached to the target's next attempt; downstream `attempts`, `failures`, `step_starts`, `step_commits`, `last_findings`, `tests_frozen_at` (when the target is at or before SPEC-TO-TESTS) reset; `retries += 1`; `step = target`; target `CHAT-TO-PLAN` ⇒ checkpoint `upstream-plan`; an in-progress merge is aborted.
   - `BLOCKED`: commit work; finding `B1` (quote = notes); checkpoint `blocked`.
7. Save, commit, `git push -u origin <branch>` (worktree mode, unless `--no-push`). Rejected non-fast-forward push ⇒ `RunnerError("another runner owns this round (push rejected)")`, exit 1, state committed locally and not advanced further (the fence). Any other push failure (network) ⇒ exit 1; the state is committed locally, a replayed `record` is refused by the guard, and the next state-changing command pushes again. Print `{"kind": "recorded", "round", "next_step", "spend"}`.

**Owner commands** (each appends `<UTC>\t[quoted by driver] <quote>` to the round's OWNER slice when no shared log exists, verifies the quote against the log when it does, charges owner cost when resuming a checkpoint, writes `## RESUME`, saves, commits, pushes):
- `approve`: at `approval` ⇒ record approval, advance. At `spec-review`/`pre-landing` ⇒ continue. At `failure-limit` ⇒ reset that step's `failures`, `retries += 1`, continue. At `round-limit`, `hard-stop` ⇒ continue (raised once per round). At `spec-changed`/`spec-edits` ⇒ `spec accept --note "approved by owner: <quote>"` on the round branch, then continue. At `needs-owner`/`blocked`/`upstream-plan` ⇒ exit 2 `this checkpoint needs answer --text` (for `upstream-plan`, editing `PLAN.json` then `approve` is the re-plan path: the edit re-enters the approval gate). At `finish-conflict` ⇒ continue (the hand merge is committed by the runner: `git add -A`, commit).
- `delegate [--through STEP]`: `approve` plus `delegated`.
- `answer --text T`: the text becomes blocking finding `O1` (`source: owner`) for the checkpoint's step (`needs-owner`, `blocked`: the current producer, next attempt; `spec-review` ⇒ PLAN-TO-SPEC; `pre-landing` ⇒ CLEANUP; `upstream-plan` ⇒ exit 2, edit the plan), `owner_answers` += `{at, text}`, `retries += 1` for review checkpoints, continue.
- `override --steps A,B`: adds to `overrides` (steps not yet accepted; protected names refused with exit 2); allowed at any status.
- `abandon --reason R`: any status; `status = abandoned`, tag `round/NNNN-abandoned`, commit, push best-effort. After `landed_at` the landed code stays; the folder stays on the branch.

**Checkpoint charges**: raising one books `costToWaitForOwner + ownerHourlyRate × ownerHoursPerCheckpoint` (`--minutes M` on the resume replaces the hours estimate with `M/60`); `approval` also books plan words once; PLAN-TO-SPEC's acceptance books `specCostPerWord × words(SPEC.md)` once (`words_charged`).

### 2.10 Mechanical checks (`checks.py`)

Every check returns findings `{id, quote, reason, suggestion, blocking, source: "mechanical"}`; ids are stable and tested. The attempt's diff = files that differ between the working tree and `base`, plus untracked non-ignored files, minus the result file; `base = merge_pending.automerge_tree if merge_pending else HEAD`.

| Id | When | Check | Effect |
| --- | --- | --- | --- |
| S1 | artifact steps, CHAT-TO-PLAN-GATE | artifact missing, unreadable, or failing its schema and rules (§2.6) | blocking |
| S2 | any producer | a `disputed` resolution on a settled id | note; dispute ignored |
| R1 | any producer | finding ids missing from `resolutions` | note |
| M0 | every `next`/`record` | HEAD moved past `last_runner_commit`; or a runner-owned round file changed | soft reset / revert; note |
| M1 | code steps, POSTMORTEM | a changed path outside `write_paths` ∪ round folder ∪ `merge_pending.conflicted` | the stray files reverted (`git checkout -- <f>`, untracked deleted); note listing them |
| M2 | SPEC-TO-IMPLEMENTATION, CLEANUP | a `testPaths` file differs from `tests_frozen_at` (merge attempt: from the automerge tree); conflicted test files exempt with a note "merged test; review" | reverted; note |
| M3 | code steps with `verify` | `SPEC.verify` non-zero or timed out (`verifyTimeoutSeconds`, spec value wins); quote = last 3000 chars | blocking |
| J1 | every producer | a judgment-call file lost or changed an existing line (`git diff <last_runner_commit> -- <files>` has a `-` line); `ERRATA.md` likewise | restored from HEAD; note |
| M4 | CLEANUP | `suiteCommand` red or timed out (`suiteTimeoutSeconds`) | blocking |
| M5 | every producer | a spec file changed (§2.14) | never blocking; diff to HISTORY, `spec_edits` |
| G1 | any gate | the gate's run changed files | discarded; note |
| T1 | TESTS-TO-SUITE | the keep/archive partition rule | blocking (part of S1) |
| W2 | any prompt | rendered prompt > `promptWarnBytes` | warning in the action |
| X1 | PLAN-TO-SPEC DONE | declared paths overlap a live sibling's (§2.12) | non-blocking, carried |
| L1, L2, L3 | LANDING and the merge attempt | conflict; verify/suite red on the merged tree; unmerged entries left at `record` | §2.12 |
| I1 | `record --infra-error` | `infraRetries` infra errors at one attempt | blocking |

Acceptance effects: SPEC-TO-TESTS ⇒ `tests_frozen_at = HEAD`; TESTS-TO-SUITE ⇒ `git mv` each `archive` path into `tests-archive/<basename>` (collision ⇒ `<dir>__<basename>`), commit; reuse rule: on re-entry, if `SUITE.json` exists and its path set equals the current changed-test set, TESTS-TO-SUITE auto-accepts with a HISTORY line. `check` runs the current step's checks (or the landing check at LANDING) without recording; exit 3 on blocking findings.

### 2.11 Costs (`ledger.py`)

Entries `{step, attempt, usd, source, at, note, detail?}`; buckets by source: `agent_usd` ← `cli` (`--cost` or `result.cost_usd`), `usage` (`--usage` or `result.usage` priced per rung: `input×in + output×out + cache_read×cr + cache_write×cw` per MTok; a bare total priced with the `estOutputFraction` blend), `estimate` (neither: the run's budget, flagged in HISTORY and the next prompt); every agent entry is at least the rung's `spawnCost`; `sub_agents` entries the same way. `driver_usd` ← `driverUsdPerStep` per `record` and once at `start`. `owner_usd` ← checkpoints and word charges (§2.9). `living_usd` ← LANDING and FINISH (below). `time_usd` = `lostValuePerHour × hours` from `created_at` to now (frozen at `finished_at`/`abandoned_at`), computed on read, not stored. `total_usd` = buckets + time.

Budgets: `share(S)` = AGENTS-PLAN value; else `defaultShares.work[S]` (gates: `defaultShares.gates[producer]`); else an equal split of the unassigned remainder (`workFraction × quote − Σ explicit producer shares` over unassigned present producers; `gatesFraction × quote` likewise over unassigned enabled gates). `budget(S)` = `quote × workFraction × share` (producers) or `quote × gatesFraction × share` (gates); `budget_cap = budget × runBudgetMultiple` (headless `--max-budget-usd`); `step.retry_cost` = the producer's `budget + driverUsdPerStep`. `maxTurnsPerRun` and `maxRunWallClockHours` are advisory in prompts and the headless timeout.

Living charge, exactly once per landed round at LANDING against the tip actually merged (`target`, else `base_commit`), and once more at FINISH for the tail diff (`landed_tip..HEAD`): for every file under `livingSourcePaths` present at either end (`__pycache__`, `*.pyc` excluded), `n = ceil(bytes / tokenBytes)`, `price(n) = min(n, cap) × livingFileCostPerToken + max(n − cap, 0) × livingFileCostPerTokenOverCap`; charge `price(after) − price(before)`, `+livingFileBaseCost` per created file, `−livingFileBaseCost` per deleted file, `+testBaseCost × Δ(matches of testPatterns[ext])` over kept files under `testPaths` ∩ living paths (archived tests are in the round folder, not living). `cost` previews the same number against `base_commit`.

Limits: `failures[producer] ≥ maxFailuresBeforeStop` ⇒ checkpoint `failure-limit` ("approve resets the count; change PLAN/SPEC; or abandon"). `retries > maxRoundAttempts` ⇒ checkpoint `round-limit` once. `total_usd > hardStopBudgetMultiple × budget_usd` ⇒ checkpoint `hard-stop` once, evaluated after every entry and before every prompt, never while another checkpoint is being raised.

### 2.12 Concurrency, landing, finish (`gitx.py`, `landing.py`)

Invariants I1–I11 of the summary hold, with I3's exception widened to the owner log (read) and, without an origin, a fast-forward of a clean main checkout; I10 is enforced in headless mode (env scrub, tool flags) and by construction in driver mode (agent definitions) with M0 as the backstop. No lease, heartbeat, TTL or takeover.

**Claim** (`start`): `git fetch origin`; ids from `refs/remotes/origin/<branchPrefix><digits>` and local folders; loop `pushAttempts` times: `git push --porcelain --force-with-lease=refs/heads/<branch>: origin <base>:refs/heads/<branch>`; **won ⇔ exit 0 and a stdout line starting with `*`** (`=` loses even at exit 0; `!` loses); explicit `--branch` pushes exactly once and errors on a loss; otherwise `rid += 1` without re-fetch; exhausted ⇒ `round id: push rejected N times, last <branch>`. A failed `git worktree add` leaves the claim claimed (ids are cheap; a rerun takes the next id).

**Fence**: every state-changing command commits and pushes the round branch non-forced; rejection aborts with the fixed message. `runner` in every action names the worktree's `run.py`.

**LANDING** (inside `next`; `attempts[LANDING] += 1`). Check phase (`landing_check(mutate)`; `check` calls it with `mutate=False`; never pushes, tags, charges or moves a branch):
1. `git fetch origin` when an origin exists; `target = origin/<main>` if it exists, else local `<main>` if it exists, else `None`; `main_before = target sha`.
2. Target not already contained in HEAD: `git merge-tree --write-tree --name-only HEAD <target>`; exit 1 (conflicts) ⇒ finding `L1` quoting the conflicted paths; with `mutate`: `merge_pending = {target, target_sha, automerge_tree: <the printed oid>, conflicted: [...]}`, `git merge --no-commit --no-ff <target_sha>` (the tree now holds markers), `retries += 1`, `last_findings[SPEC-TO-IMPLEMENTATION]`, `step = SPEC-TO-IMPLEMENTATION`; return. Clean ⇒ `git merge --no-edit <target>` (a merge commit on the round branch).
3. `spec check` on the merged tree: drift not explained by this round's own `spec_edits` ⇒ checkpoint `spec-changed` (never L2).
4. `SPEC.verify` then `suiteCommand`, each under its timeout ⇒ red ⇒ finding `L2` (tail quoted) ⇒ `retries += 1`, `step = SPEC-TO-IMPLEMENTATION`.
Land phase (only after a clean check):
```
for attempt in 1..pushAttempts:
    living = living_charge(target or base_commit)          # priced against the tip actually merged
    if target is None: break                                # no-branch / no main
    ok = push origin HEAD:refs/heads/<main>  if has_origin  else fast_forward_local_main()
    if ok: break
    if attempt == pushAttempts: raise RunnerError("landing: push of <main> rejected N times")   # state not saved; rerun lands again
    findings = landing_check(mutate=True); if findings: return                                   # re-fetch, re-merge, re-verify, re-suite
book living (once); tag -f round/NNNN-landed; landed_at = now; step_commits[LANDING] = HEAD; advance
```
Local `main` convenience after an origin push: `git fetch origin <main>:<main>` when `<main>` is not checked out in any worktree, else a FLAG (the checkout catches up with `git pull --ff-only`). `fast_forward_local_main()` (no origin): `<main>` not checked out anywhere ⇒ `git branch -f <main> HEAD`; the main checkout on `<main>` and clean ⇒ `git -C <M> merge --ff-only <branch>`; otherwise error naming the fix.

**The merge attempt** (conflict convergence): the SPEC-TO-IMPLEMENTATION prompt carries `agent.conflicts` and the merge-in-progress line; the allowed set is `implPaths` ∪ round folder ∪ `conflicted`. At `record` DONE: unmerged index entries remain ⇒ finding `L3`, blocking, the tree stays merging; else the runner's `git add -A` + commit produces a merge commit; M1/M2 are measured against `automerge_tree` (only hand edits are judged; conflicted files are allowed; a conflicted frozen test is a note); M3 runs; `merge_pending` cleared. UPSTREAM, BLOCKED, `--infra-error` or a discard during the attempt ⇒ `git merge --abort`, `merge_pending = null`. The pipeline then continues normally (gate, TESTS-TO-SUITE with the reuse rule, CLEANUP and its checkpoint, LANDING, which now finds the target contained). `round-limit` is the exit for a conflict that will not converge: at that checkpoint the owner may hand-merge in the worktree and `approve`.

**FINISH** (after POSTMORTEM's acceptance): `git fetch origin`; merge `origin/<main>` (no origin: nothing); conflict ⇒ checkpoint `finish-conflict` ("resolve in the worktree, git add, then approve"; the runner commits); if the tail `git diff --name-only <landed tip> HEAD` touches anything outside `archivesPath` and `docs/`, run verify and the suite (red ⇒ `L2` ⇒ SPEC-TO-IMPLEMENTATION, as at landing); push `HEAD:refs/heads/<main>` in the same bounded loop; book the tail's living delta; `finished_at`, `status = finished`, `main_synced = true`. Without an origin, the local fast-forward rule. `next` then prints done.

**X1 overlap warning**: at PLAN-TO-SPEC's DONE (clean checks), for every `origin/round/*` branch not tagged `-landed`/`-abandoned` (after a fetch, best effort), read its `SPEC.json` with `git show`; a prefix overlap of `implPaths`/`testPaths` ⇒ non-blocking finding naming the round and paths, carried to SPEC-TO-IMPLEMENTATION, and `agent.sibling_paths`.

**`rounds [--prune]`**: every round (local folders, origin branches, tags, worktrees) with status, step, spend, outcome; claimed-but-empty ids (branch tip == base, no folder); `--prune` removes worktrees of finished/abandoned rounds (`git worktree remove --force`, `git worktree prune`) and nothing else.

### 2.13 Owner log, hook, driver, agents

**Hook** (`src/owner_log_hook.py`, wired in `.claude/settings.json` for `UserPromptSubmit` and `SessionStart`, command `py -3.13 harness/src/owner_log_hook.py`): reads the JSON on stdin; resolves M from `CLAUDE_PROJECT_DIR` or cwd via `git rev-parse --git-common-dir` (a session in a worktree still logs to the shared file); writes `<M>/harness/DRIVER.json` `{session_id, transcript_path, updated_at}` on both events; on `UserPromptSubmit` appends `<UTC Z>\t<message with backslash and newline escaped>` to `<M>/harness/OWNER.log` unless the prompt is empty, starts with an `envelopePrefixes` entry, or env `SHACKLES_SUBAGENT` is set (the headless loop sets it). Never raises. `owner --say` is the fallback. `doctor` warns when the hook is not configured or the log does not exist; the runner degrades to unverified quotes.

**Driver mode (primary).** Per action: spawn a fresh sub-agent with `subagent_type = action.agent.agent_type` and the task message `Prompt file: <prompt_file>` (the agent definition's body says "Read it first and follow it exactly; your final message must be exactly the JSON object it specifies"), never `isolation: worktree` (the round worktree is the isolation); save the final message to `result_file` exactly as returned; run `action.record_command` adding `--cost` when the tool reported a dollar figure, `--usage` when it reported tokens, else nothing. Exit 10 ⇒ relay `owner_message` in chat and stop; on the owner's words run the matching command with `--quote`. Exit 1 with `another runner owns this round` ⇒ stop and report. Never do a gate's job, never edit an artifact or result, never commit or push. Use the worktree's own `run.py`.

**Agent definitions** (`agents --write`): for every roster rung, `.claude/agents/shackles-producer-<rung>.md` (frontmatter `model: <alias>`, `effort: <effort>`, default tools, `disallowedTools` as `producerToolFlags` if the frontmatter honours it) and `shackles-gate-<rung>.md` (`tools: Read, Grep, Glob`). The body is fixed. A test asserts the files match the roster; `doctor` reports drift. The implementer verifies once, by spawning one of each on a scratch prompt, that the frontmatter keys `model`, `effort`, `tools` are honoured on this Claude Code build (`claude --version`), and records the result in DRIVER.md. Effort not honoured ⇒ DRIVER.md says so; headless mode sets `--effort`.

**Headless mode** (`run`, `probe --exec`): `agentCommand` with `{claude}` (resolution: env `SHACKLES_CLAUDE` → `runner.local.yaml: claude` → `shutil.which("claude")` → newest match of `claudeSearchPaths` → error naming all four), `{prompt_file}`, `{model}`, `{effort}`, `{budget_cap_usd}`, `{result_schema}` (RESULT or FINDINGS as JSON Schema, one argv element), `{tool_flags}` (expands in place to `gateToolFlags` or `producerToolFlags`), `{task}`; `cwd` = the worktree's H; env minus `scrubEnv` plus `SHACKLES_SUBAGENT=1`, `PYTHONUTF8=1`; timeout `maxRunWallClockHours` with process-tree kill. Envelope: `data = json.loads(stdout)`; result = `data["structured_output"]` if an object, else `extract_json(data["result"])`; `total_cost_usd` → `--cost`; `usage`, `num_turns`, `session_id`, `is_error` stored beside the result. Non-zero exit, `is_error`, timeout or unparseable output ⇒ `record --infra-error`, retry; `infraRetries` failures ⇒ exit 1. `doctor --probe-cli` runs one `--print` call on the `low` rung with a $0.05 cap asking for `{"ok": true}` under `--json-schema`. `--max-turns` does not exist in CLI 2.1.266: turns are advisory.

### 2.14 Spec baseline and spec edits (`specbase.py`)

`harness/archives/spec-baseline.json` = `{"accepted_at", "commit", "note", "spec_yaml": sha256, "files": {"<path>": {"sha256", "lines"}}}` over `spec.yaml` and every path it lists, hashed after BOM strip and CRLF/CR→LF. `check(root) -> {changed: [{path, diff}], added, removed, missing, spec_yaml_changed, baseline_missing}` ("added" = newly listed, "removed" = delisted or absent on disk, `diff` from `git diff <commit> -- <path>` when the commit exists locally, else `content changed, n → m lines`, truncated to 200 lines). `accept(root, note)` rewrites the baseline and appends `{"at", "commit", "note", "changed": [...]}` to `spec-acks.jsonl`. `spec check` (exit 3 on drift), `spec diff`, `spec accept --note`.

`harness/tests/test_spec_baseline.py::test_spec_files_unchanged_since_baseline` fails on any drift with the categorized lists and diffs, then the review checklist verbatim: (1) `run.py doctor`; (2) `run.py render --all` and read the affected prompts; (3) a step or gate added, renamed or removed ⇒ update `runner.yaml: steps`; (4) a `project.yaml` key changed ⇒ `config.DEFAULTS`; (5) reconcile the wording-adjacent rules table in `docs/PROCESS.md`; (6) run the suite; (7) `run.py spec accept --note "<what you reviewed>"` in the same commit. The root is a parameter (env `SHACKLES_ROOT` or the fixture) so the meta-test can point it at a temp copy.

`test_spec_baseline_meta.py` proves the detector: on a temp copy of the repo — clean ⇒ `{}`; one word changed in a prose file ⇒ `changed` with a diff containing the word; whitespace-only change ⇒ still changed; CRLF/BOM rewrite ⇒ clean; a path added to `spec.yaml` ⇒ `added`; a listed file deleted ⇒ `removed`; `spec.yaml` edited ⇒ `spec_yaml_changed`; baseline deleted ⇒ `baseline_missing`; `accept` then `check` ⇒ clean; CLI exit codes 0/3; and the real test function raises `pytest.fail.Exception` naming the file and the checklist when run against the mutated copy, passes after `accept`, and is collected (`pytest --collect-only` names it). Milestone 1 ships this so every later commit of the build runs under the alarm.

A round that edits a spec file (M5): after every recorded attempt the runner diffs the spec files against `base_commit`; changes are appended to HISTORY under `## SPEC EDIT` as a fenced unified diff, stored in `spec_edits`, and before LANDING the runner raises checkpoint `spec-edits` (`owner_message` = the diff) regardless of delegation; `approve` accepts the baseline on the round branch. The bootstrap's own edit (§4) is flagged the same way in the implementer's report.

### 2.15 Documents

- `INDEX.md` (≤ 40 lines): `process, rules, checkpoints, disputes -> docs/PROCESS.md`; `driving a round, spawning, record, recovery -> docs/DRIVER.md`; `tests, fixtures, stub, probes, sandbox, baseline -> docs/TESTING.md`; `config, defaults -> src/runner.yaml (runner), project.yaml (owner), runner.local.yaml (machine)`; `steps, pipeline -> src/runner.yaml`; `runner, commands, exit codes -> src/run.py --help`; `contracts, result JSON, verdict JSON -> src/plumbing/`; `schemas -> src/shackles/schemas.py`; `prose, prompts -> locked_prose/, run.py render`; `rounds, archives -> archives/rounds/`; `owner log, driver pointer, hook -> src/owner_log_hook.py, .claude/settings.json`; `agent definitions -> .claude/agents/, run.py agents`; `spec files, drift -> spec.yaml, archives/spec-baseline.json, run.py spec`; `todo, clarifications -> docs/TODO.md, docs/CLARIFICATIONS.md`.
- `docs/PROCESS.md` (≤ 250 lines, one sentence per line): roles; files and the H-relative path rule; the step table and derived gates; statuses and the lifecycle; owner words → commands and the quote rule; outcomes and routing tables; findings, disputes, settlement, deferral, errata; checkpoints, delegation, overrides; limits and the hard stop; mechanical checks (the id table); costs; freeze and archive rules; landing, the merge attempt, FINISH; concurrency invariants; spec files, the baseline, flagged edits; the **wording-adjacent rules table**: `settleAfterUpholds` ↔ COMMON-GATE "upheld twice"; status/verdict/resolution/ruling vocabulary ↔ COMMON-OVERVIEW and COMMON-GATE; the step table's `checkpoint` attributes ↔ PLAN-TO-SPEC and CLEANUP "Checkpoint after this step" and the `gates` comments; step order ↔ `gates` order; owner words ↔ the CHAT-TO-PLAN word list (the driver's mapping); gate read-only ↔ AGENTS.md; carry-forward files ↔ POSTMORTEM "TODOs"/"CLARIFICATIONS"; judgment-call files ↔ AGENTS.md and COMMON-PROJECT; escape hatches (`--discard`, `--no-push`, `--base`, `owner --say`, hand merge at a checkpoint).
- `docs/DRIVER.md` (≤ 80 lines): the exact operating sequence on this machine (`doctor` → `plan` → chat → `PLAN-DRAFT.json` → the word → `start` → the loop with the Agent-tool parameters → checkpoint etiquette → cost flags → `push rejected`, crash, L1, `spec-changed`).
- `docs/TESTING.md` (≤ 80 lines): commands, fixtures, stub modes, the baseline procedure, the real-agent ladder with costs.
- `docs/TODO.md`, `docs/CLARIFICATIONS.md`: one header line, then `## round NNNN` sections; the bootstrap seeds TODO.md with §5's deferred items.
- `README.md`, `CLAUDE.md` as in §2.2.

---

## 3. Test strategy

**Principles.** Partial integration, no mocks of git or the filesystem; every scenario runs the real runner in a throwaway repo under `tmp_path` built by `sandbox.build()`, with the LLM replaced by `stub_agent.py`. In-process `run.main(argv)` for nearly everything (Windows process spawn is slow); `subprocess` only where the CLI itself is the subject. Hermetic git: `GIT_CONFIG_GLOBAL` = an empty temp file, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, fixed author/committer, `core.autocrlf=false`, `core.longpaths=true`, `PYTHONUTF8=1`. Cleanup with `shutil.rmtree(onexc=chmod_and_retry)` after `git worktree prune`. Targets on this machine: `-m "not slow and not real"` under 60 s; the whole non-real suite under 4 minutes; no network; no user git config touched. No test asserts on any sentence of the owner's prose.

**Fixtures** (`tests/fixtures.py`, `conftest.py`). `Repo(tmp, project=None, runner=None, prose=None, files=None, owner_lines=None, gates=None)`: copies `spec.yaml`, `harness/{AGENTS.md, project.yaml, subAgents.yaml, locked_prose, src, docs, INDEX.md}` and a fresh accepted baseline into `tmp/repo`, applies overrides (so tests vary config and prose without touching spec files), adds the toy project (`harness/src/toy/text.py`, `harness/tests/toy/test_text.py`), writes `.gitignore` (with `<worktreeDir>/`), `runner.local.yaml` (`agentCommand` → `[sys.executable, <abs stub path>]`, `suiteCommand` scoped to `harness/tests/toy`), `git init -b main`, commits. Methods: `run(*argv, subprocess=False) -> Result(code, json, stdout, stderr)`, `start/next/record/approve/...`, `act(action, mode)`, `play(until=STEP, modes={...})` (drives `next`/stub/`record` in-process to a step in seconds), `owner(text, at=None)`, `state()`, `git(...)`, `head()`, `dirty()`, `tags()`, `add_origin()` (bare, `symbolic-ref HEAD refs/heads/main`, absolute path), `clone()` ("another machine"), `view(worktree)`. `Origin`: `sha(ref)`, `branches()`, `install_reject_hook(pattern, n|"all")`, `install_move_and_reject_once_hook(refname, to_ref)`, `hook_log()` — hooks written in Python with an absolute `sys.executable` shebang and LF newlines (verified to run on this git by plan-6). `stub_agent.py`: parses the last `STEP:`/`KIND:`/`ATTEMPT:`/`WORKTREE:`/`HARNESS:`/`ARTIFACT:`/`RESULT_FILE:`/`WRITE_PATHS:`/`DIFF_FILE:` lines; writes canned artifacts from `fixtures/toy/canned/<STEP>.*`; prints the CLI envelope `{"result": "<json>", "structured_output": {...}, "total_cost_usd": 0.01}`; `perform()` is the in-process entry. Modes via `STUB_MODE` or `STUB_SCRIPT` (JSON `{"STEP:attempt"|"STEP"|"*": mode}`): `pass`, `pass_nb` (non-blocking findings), `fail`, `dispute`, `uphold`, `withdraw`, `needs_owner`, `q_uphold`, `q_withdraw`, `upstream`, `blocked`, `garbage`, `fence`, `prose_wrapped`, `deferred`, `commit` (M0), `stray` (M1), `touch_tests` (M2), `break` (M3), `dirty_gate` (G1), `rewrite_judgment` (J1), `spec_edit` (M5), `big` (W2), `resolve` (L1 attempt), `leave_unmerged` (L3), `slow`, `replay` (`STUB_REPLAY=<dir>`), plus `STUB_ARCHIVE=1`, `STUB_JUDGMENT=n`, `STUB_COST`, `STUB_LOG=<file>` (argv, cwd, env keys per call).

**Test files and what they assert.**
- `test_spec_baseline.py`, `test_spec_baseline_meta.py`: §2.14.
- `test_config.py`: layering order; every key's default when deleted; unknown keys kept; wrong types warn; `NNNN`/`NNN` width; `gates` map order and absent ⇒ disabled; roster fallback; `..` paths refused when escaping R; CRLF/BOM normalization; pinned reads via `git show` (change `project.yaml` after `start` ⇒ the round still sees the old value).
- `test_steps.py`: loader validation; derived gates from prose files and flags; every cross-check fires on a crafted variant (gate removed, `CLEANUP-GATE` added with prose and flag ⇒ it runs, step renamed, unknown prose file, reordered `gates`); `start` refuses a missing producer prose; overrides skip and protected names refuse; delegation semantics including `through:STEP`; checkpoints raised where configured and not when delegated.
- `test_render.py`: grammar and whitespace; every namespace; value formatting; include depth, cycle, render-once with `(as above)`; unresolved marker and warnings, never an exception; raw insertion does not expand tokens inside artifacts; every locked prose file renders with the synthetic context and the unresolved set is exactly the known set (`{project.ownerReviewCostPerWord}` before §4, empty after); embed mode for GATE-PROSE (LLM gate, mechanical, disabled); PROCESS-INSTRUCTIONS present exactly once even when the token is removed; the `KEY:` lines present and last; prompts rendered from `spec_commit` (edit prose mid-round ⇒ prompt unchanged); `render --step` never changes state; W2.
- `test_schemas.py`: validator behaviours; each schema with a good and a bad example and the exact messages; extraction from bare, fenced and prose-wrapped text; gate normalization (ids, suggestion, withdrawn re-raise dropped, verdict authoritative both ways); STATE round-trip and unknown-key rejection.
- `test_round_flow.py` (`--no-branch`, fast): `start` validates before any git write (a bad plan creates nothing) and creates every file; quote verification (log present: match / no match ⇒ exit 2; log absent ⇒ unverified; gate disabled ⇒ unverified); action shape with absolute paths and `record_command`; `record` guards (wrong step/attempt/status, replay ⇒ exit 2, nothing changes); infra path (`garbage` ⇒ exit 2 ⇒ `--infra-error` ×3 ⇒ I1); the `pending_action` protection and `--discard`; M0 soft reset; every producer status × gate enabled/disabled × approved/delegated per §2.9; gate PASS/FAIL; carried findings rendered downstream; dispute → uphold → settled → S2; withdrawn not re-raised; `deferred` reaches POSTMORTEM's prompt; NEEDS-OWNER through an enabled gate withdrawn (Q1) and upheld (checkpoint); UPSTREAM to each earlier producer and to CHAT-TO-PLAN; BLOCKED; every checkpoint kind and every resume command including `--minutes`, `answer` ⇒ O1, `override` at runtime, `abandon` from each status; limits (failure-limit resets on approve, round-limit once, hard stop once); out-of-band PLAN/SPEC edits re-enter, ERRATA.md does not; crash recovery (STATE saved but commit missing; result saved but not recorded ⇒ rerun resumes); a full round gates-off and gates-on to `done` asserting every `roundPaths` file, one HISTORY entry per attempt, `finished`, the tag, `main_synced`; a delegated run raises no review checkpoint; an approved run raises exactly two and completes after two `approve`s.
- `test_checks.py`: each check triggered by a stub mode with the exact id and effect (revert verified, in-scope work kept and committed); freeze and re-freeze; archive move and collision; the reuse rule; T1 partition; J1 restore; M5 diff in HISTORY and the `spec-edits` checkpoint even when delegated; `check` never records.
- `test_ledger.py`: cost precedence and the `spawnCost` floor; usage pricing per rung and the blend; driver entries; owner entries per checkpoint kind and word charges once; living charge arithmetic on constructed diffs (cap crossing, refund, base costs, test-count delta per extension, files outside living paths free, round folder free); time cost frozen at finish; budgets and shares with and without AGENTS-PLAN and with disabled gates; `retry_cost`; `spend --project` including a live sibling read from its branch; `round.history`.
- `test_judgment_calls.py`: files created with headers; producer lines counted; gate lines appended via the runner with the suffix; runner assumption lines; counts in STATE, HISTORY, checkpoint messages; `ERRATA.md` rendered.
- `test_owner_log.py`: hook script driven with stdin JSON for both events (main-checkout resolution from a worktree cwd, envelope and `SHACKLES_SUBAGENT` suppression, escaping round-trips, never raises); the slice from `owner_since`; `owner --say`.
- `test_concurrency.py` (`slow`; local bare origin; subprocess for the CLI-level ones): claim (stdout shape, worktree on `round/0001` at `origin/main`, origin ref == worktree HEAD, main checkout untouched, no `OWNER.log` in the worktree); lost race via a narrowed fetch refspec for both `=` and `!` shapes with `assertNothingCreated` (no folder in any commit, no worktree, no local branch, clean, still on the starting branch); reject-all hook ⇒ exactly `pushAttempts` pushes logged and the fixed error; explicit `--branch` taken ⇒ one push; `worktree add` failure keeps the claim; id sourcing ignores `round/003-x`, `round/abc`, tags; preconditions refused (worktreeDir not ignored, origin missing); fence (another clone moves the branch ⇒ `record` exits 1 with the message); landing after a sibling moved main (`check` merges only; then `run --until done` leaves `origin/main == round tip` with both rounds' files and one living entry equal to this round's diff); move-and-reject-once hook ⇒ retry inside one `next`, `attempts[LANDING] == 1`; reject-all on main ⇒ exit 1, no tag, no living entry, state at LANDING, lands on rerun; **conflict**: L1 names the file, the tree is left merging with markers in exactly that file, `merge_pending` set; `resolve` ⇒ a two-parent commit, M1/M2 against the automerge tree pass, a resolution that also edits an unconflicted frozen test is reverted with a note, `leave_unmerged` ⇒ L3, UPSTREAM during the attempt aborts the merge, then the round lands with both sides' content; L2 routes to SPEC-TO-IMPLEMENTATION; `spec-changed` at landing when main carries an unaccepted prose edit; FINISH: tail merges and pushes after a sibling moved main (docs-only tail skips checks; a code tail runs them), `finish-conflict` on a TODO.md collision, two rounds' `STATE.json` aggregate; no-origin landing with main parked and with main checked out and clean; `X1`; `rounds --prune`; `runner_skew`; a `project.yaml` key added on main does not break a round pinned at an older `spec_commit`.
- `test_cli.py` (subprocess): `--help`, exit codes, one-JSON-object stdout, `--root`/`--round` resolution, `doctor --json` on the fixture repo and each precondition, `render --fixture`, `spec check` exit 3, `agents` drift, `owner --say`.
- `test_headless.py`: `run --until step|checkpoint|done` with the stub as `{claude}`; argv carries the rung's model/effort, tool flags in the right order, `--json-schema`; env scrubbed and `SHACKLES_SUBAGENT` set; cwd = H; `structured_output` preferred, fenced text accepted; garbage ⇒ 3 infra errors ⇒ exit 1; `slow` ⇒ process-tree kill; `probe`/`sandbox` on the stub with a scorecard.
- `test_docs.py`: INDEX.md targets exist; every CLI command appears in DRIVER.md or PROCESS.md; every `runner.yaml` key is commented; the agent definitions match the roster; no source file shares an 8-word window with a locked prose file (mechanical behavior cannot silently depend on wording).
- `test_replays.py`: `fixtures/replays/` (recorded real `RESULTS/` and artifacts, populated by §7) drive the validators and `record` routing; empty until the first real run, asserted thereafter.

**Bootstrap acceptance**: `py -3.13 -m pytest` green; `doctor` clean on this machine except items it cannot verify (`claude` flags without `--probe-cli`); `sandbox --new <tmp> --origin` then `run --until done` with the stub, gates on, finishes; `render --all` shows no unresolved token after §4.

---

## 4. Spec-file edits (exact, minimal, flagged)

One defect: two prose files reference `{{ project.ownerReviewCostPerWord }}`, which `project.yaml` does not define (it defines `planCostPerWord` and `specCostPerWord`). Without the edit the two prompts read `Assume a cost of $[unresolved: project.ownerReviewCostPerWord] per word …`: the runner tolerates it, but the sentence is false to the agent. The fix uses the owner's own, more specific keys:

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

Procedure: apply in its own commit titled `SPEC EDIT (owner review required): resolve ownerReviewCostPerWord (2 lines)` with this diff in the body; take the baseline after it (`spec accept --note "bootstrap: placeholder rename"`); repeat the diff under a heading "Spec edits made, awaiting your approval" in the implementer's final report. If the owner declines, revert the commit and re-accept: the `[unresolved]` marker keeps rounds runnable. The rejected alternative (adding `ownerReviewCostPerWord: 0.1` to `project.yaml`) duplicates a value the owner already split.

No edit to `AGENTS.md`, `project.yaml`, `subAgents.yaml` or any gate prose. Gate language is not relaxed: `COMMON-GATE`'s cost rule already tempers the per-line "Fail" lists; §7's defect/clean probes measure whether clean artifacts pass; if they fail on wording alone, the report proposes the smallest edit (to `COMMON-GATE`, never the per-gate lists) as a flagged diff for the owner. Observed and deliberately untouched: `subAgents.yaml`'s `high` rung is named "Fable 5.1 Low" (the runner uses keys only).

---

## 5. Risks and open questions, each with the resolution taken

1. **`ownerReviewCostPerWord`**: the two-line edit (§4); the marker fallback if declined.
2. **Checkpoint placement, `maxRoundAttempts`, `maxFailuresBeforeStop`, `ownerHourlyRate` charging are interpretations** (comments and prose, no formula): all live in `runner.yaml`/`DEFAULTS`, are named in the hand-off report, and change without touching a spec file; the owner may adopt `ownerHoursPerCheckpoint` (or a `steps` override) into `project.yaml`, which wins over `runner.yaml`.
3. **Approval when `CHAT-TO-PLAN-GATE` is 0** (today): the quote is recorded unverified and the round runs with checkpoints unless `--delegated`. Confirm with the owner.
4. **Gates may fail everything under the strict per-line "Fail" prose**: measured first by probes (§7); no edit before evidence.
5. **The Agent tool and effort/tools per definition**: verified once in the build; DRIVER.md records what is honoured; headless mode is exact.
6. **`claude.exe` not on PATH, `--system-prompt-file` hidden, no `--max-turns`, flags drift with app updates**: the template is config; `runner.local.yaml` pins the path; `doctor --probe-cli` verifies for cents; `--append-system-prompt-file` is the documented fallback if `--system-prompt-file` is rejected.
7. **Hook execution on Windows** (shell quoting, `py` on the hook's PATH): the command is the bare `py -3.13 …`; milestone 1 verifies with a piped payload and one real prompt; `owner --say` is the fallback and quotes degrade to unverified.
8. **Quote verification is an honesty check, not security**: `owner --say` lets a driver fabricate a line; HISTORY records every quote and its verification; the owner's log is theirs to audit.
9. **Cost unknown in driver mode**: estimate = run budget, flagged; the hard stop still bounds spend; headless mode is exact.
10. **Living charge shock**: at $0.25 per token a 200-line test file books ≈ $800; it is the owner's number and a ledger figure only; `cost` previews it; flag in the report that quotes will be dominated by living tokens.
11. **The harness is its own project**: a round editing `src/shackles/round.py` changes the runner driving it; runner pinning by convention, `runner_skew` warning, the suite at CLEANUP and LANDING; PROCESS.md advises checkpoints on for such rounds; a landing merge brings a sibling's runner in only at LANDING.
12. **Two live rounds on the same living files**: X1 warns, landing arbitrates, the merge attempt converges, `round-limit` hands a stubborn conflict to the owner. Sentence-per-line docs reduce conflicts.
13. **Suite speed on Windows**: in-process driving, `slow` marker, shared played-to-step repos per read-only test class; budget 4 minutes, written into TESTING.md.
14. **`merge-tree --write-tree` semantics** (git 2.45 documents exit 1 and marker-bearing blobs): milestone 5 confirms with one fixture test; fallback if a git build misbehaves: base = pre-merge HEAD, allowed = conflicted files only.
15. **Prompt size**: bodies are referenced by path, only the plan text, findings and the previous message are inlined; W2 warns; PLAN-TO-SPEC-GATE's own "too large" criterion stays with the gate.
16. **`git clean` near `.claude/worktrees/`**: `worktreeDir` (`.worktrees`) must be ignored (refused otherwise); `doctor` warns when `.claude/worktrees/` is not ignored; never `-x`.
17. **A `roundPaths` or `gates` key renamed by the owner**: names are read from `project.yaml`, defaults cover absence, `doctor` and the drift test report; only the `N`-run rule is fixed.
18. **A brand-new step prose file** (`REVIEW-OVERVIEW.txt`): reported as "unknown prose file"; a round adds it to `runner.yaml: steps`; automatic ordering from prose alone is not attempted.
19. **`SHACKLES_SUBAGENT` and a second interactive session on the repo** both log to the same OWNER.log: acceptable (it is the owner's log); quotes are verified against timestamps, and HISTORY shows the line acted on.
20. **`git push` to GitHub needs credentials in the runner's environment while agents get none**: the runner inherits the session's; `scrubEnv` strips them only for spawned agents; `doctor` checks `git ls-remote origin`.
21. **Deferred (seeded into `docs/TODO.md`)**: transcript-measured driver cost; a `projectRoot` key for a target project outside `harness/`; lease/TTL for dead claims (`rounds` reports them); exact tokenizers; cross-round path arbitration beyond X1; a status UI; automatic gate relaxation.

---

## 6. Implementation sequence (one session; each milestone ends green and committed on a `claude/bootstrap-*` branch, never `main`)

| M | Build | Accept when |
| --- | --- | --- |
| 0 | `.gitignore`, `pytest.ini`, `README.md`, `CLAUDE.md`, package skeleton, `gitx.py` (run, ok, head, `main_root`, hermetic env), `sandbox.build()` + `fixtures.py` (`Repo`, `Origin`, Python hooks), the toy project, a hook-fires probe test | hooks fire on this git; the fixture builds a repo in under 2 s |
| 1 | `config.py` (layering, defaults, pinned reads), `specbase.py`, baseline + acks, `test_config.py`, `test_spec_baseline*.py` (including the meta-test) | the alarm fails on a one-byte prose change and its self-test passes; from here every commit runs under the alarm |
| 2 | `steps.py`, `schemas.py`, `render.py`, plumbing templates, `plan`/`render`/`schema`/`doctor` (static parts), `test_steps.py`, `test_render.py`, `test_schemas.py` | every prose file renders with exactly the known unresolved set; `doctor` honest about the missing pieces |
| 3 | `round.py` (`start --no-branch`, `next`, `record`, owner commands, routing, checkpoints, limits), `ledger.py`, `owner_log_hook.py`, `stub_agent.py`, `play()`, `test_round_flow.py`, `test_ledger.py`, `test_owner_log.py`, `test_judgment_calls.py` | a stub round runs to `finished` in no-branch mode with gates off and on; every routing cell has a test |
| 4 | `checks.py` (all ids), freeze/archive/reuse, living charge, `cost`, `check`, `status`, `spend`, `abandon`, `rounds`, `test_checks.py` | each check triggers, reverts and routes as specified |
| 5 | `landing.py`: claim, worktrees, fence, LANDING, the merge attempt, FINISH, X1, `--prune`, `runner_skew`; `test_concurrency.py` | two stub rounds land concurrently on a local origin in either order; the conflict test lands; FINISH merges after a sibling |
| 6 | `agents.py`: headless `run`, `{claude}` resolution, `--json-schema`, `doctor --probe-cli`, `agents --write` + definitions, `probe`, `sandbox` CLI; `test_headless.py`, `test_cli.py` | headless stub round finishes; probe scorecards round-trip on the stub; one real spawn of each definition kind verified |
| 7 | `docs/PROCESS.md`, `DRIVER.md`, `TESTING.md`, `TODO.md`, `CLARIFICATIONS.md`, `INDEX.md`; `test_docs.py`; the §4 commit; `spec accept`; final `doctor`, `render --all`, full suite; the report (spec diff, interpretations of §5, defaults in use, every WARN, suite time) | §3's acceptance list |

If the session runs short, milestones 6–7's `probe`/`sandbox`/headless parts are the ones to defer with a TODO; never the baseline test, the state machine, or the fence.

---

## 7. Real-agent testing

**The owner's loop**: a tiny throwaway task through the harness end to end with gates off, then with gates on, later runs varying checkpoints, approval skips and gate effectiveness. **What the six plans proposed**: all six keep an end-to-end run as a late tier and add a cheaper one in front — single-step probes on canned round state (plan-1 `probe`/`probe-check` with defect fixtures; plan-2 a `smoke` matrix with emit/collect modes; plan-3 `probe --check` scorecards plus a replay corpus; plan-4 opt-in pytest gate and step replays with a cost log; plan-5 `systemtest --step` with `--manual` and `--changed`; plan-6 `probe --seed clean|defect`, `selftest`, `tests/real/`). They differ only in packaging.

**Recommendation: the ladder below, with the owner's loop as its third rung, moved into a sandbox.** Cost figures use `subAgents.yaml` prices and the sibling's observed $1–6 per step at `max`.

0. **Stub suite** (free, minutes): every mechanical variation the owner listed — checkpoints, approval skips, delegation through a step, overrides, disputes, UPSTREAM, BLOCKED, limits, hard stop, out-of-band edits, races, conflicts, fences — is a deterministic test (§3). No agent money is spent on mechanics.
1. **Single-step probes** (`probe --step S [--seed clean|defect] [--agent RUNG]`): builds a sandbox (temp clone + local bare origin), plays the stub round on the toy task to just before S, applies the seed (`fixtures/defects/<GATE>/`: a spec sentence contradicting the plan; tests not covering a spec component; an implementation with a feature beyond the spec; a suite decision archiving the only regression test; a postmortem with an incomplete trace), runs `next`, and prints the action; the driver spawns one real sub-agent with the Agent tool (default) or `--exec` runs headless; `probe check --dir` records the result and scores it (`{contract_valid, schema_valid, paths_confined, verify, verdict_expected, quote_contains_planted, judgment_lines, cost, turns}`), appending a line to `archives/probes/RUNS.jsonl` and copying real results into `fixtures/replays/`. Costs: producers at `low` ≈ $0.2–0.5 each (8 prompts ≈ $3); gates must run at the configured `gateAgent` rung to say anything about gate effectiveness — 6 gates × 2 seeds at `max` ≈ $1–3 each ≈ $15–35. Runs in parallel; a failure names one prompt. This is the only rung that measures the two things the owner is worried about — can a clean artifact pass, does a planted defect fail — because an end-to-end run of a tiny task contains nothing defective on purpose. Rerun after any prose or plumbing change (`spec check` says which steps' prose changed).
2. **Sandbox end-to-end** (`sandbox --new DIR --origin`, then a real round on the toy task): gates off then gates on, `systemTestAgent` (`medium`), `--delegated` first, then with checkpoints answered in chat. ≈ $10–25 per pass at `medium`; nothing touches the real origin or the id sequence; the run is repeatable; a second round started from a second clone exercises real concurrency (≈ +$10–25). Copy its `PROMPTS/` and `RESULTS/` into `fixtures/replays/` so the runner's handling of real messages is asserted forever at zero cost.
3. **The owner's real run** on the repo, as intended, once rungs 1–2 are green.

Why cheaper and more comprehensive: an end-to-end round is ~16 sequential agent runs (≈ $30–100 at `max`), exercises one path once, stops learning at the first gate that refuses a reasonable artifact, and cannot attribute a failure to a prompt, a gate, or a mechanism; rungs 0–1 cover every mechanical branch for free and every prompt and both gate verdict directions for the price of a few steps, in parallel, with ground truth; rung 2 then confirms the whole loop once per significant runner change rather than per prose tweak. The gate-language decision (§4) is made from rung 1's scorecards, not from a guess.
