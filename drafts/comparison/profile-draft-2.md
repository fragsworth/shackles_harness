# Profile: draft 2

Citations are the draft's file names and section titles; `JC-nn` are its judgment-call IDs; 00–11 are its component files.

## 1. Format and size

- 14 files, 173,719 bytes: `SPEC.md` 17,945 B (entry); `JUDGMENT-CALLS.md` 25,882 B; twelve `components/` files `00-repo-layout`, `01-paths-config`, `02-prompts`, `03-owner-state`, `04-git`, `05-record`, `06-money`, `07-round-cli`, `08-schemas`, `09-docs`, `10-tests-infra-and-units`, `11-tests-integration-and-probes` (129,892 B together).
- `SPEC.md` sections: §1 What the harness is, §2 Requirements inventory (owner statement → component table), §3 Shape of the system (seven-layer table), §4 The round end to end, §5 Cross-cutting rules, §6 Repository tree, §7 Component index, §8 Glossary, §9 Full traceability.
- Every component opens "Parent: `../SPEC.md`" and "stands alone for its level". Module sections (01–07) follow **Owns / Depends on / Depended on by**, a Python signature block with `#` comments for behaviour and raises, then rules. 08 is formats only ("nothing here is code"); 09 docs; 10–11 tests.
- Judgment calls cited inline as `JC-nn`; all 40 IDs appear inline in SPEC.md/components (verified). Each JC ends with "**Affects:** file § heading".
- Reading order: SPEC.md is "the entry point ... the map"; §7 lists components 00–11 in numeric order; 10/11 cross-link as part 1/part 2.

## 2. Language, runtime, packaging, tooling

- Python ≥ 3.11, git ≥ 2.38, a configured remote (00 §0.6). CI matrix Python 3.11 and 3.12 (00 §0.7).
- `harness/pyproject.toml`: pytest config only (`testpaths=["tests"]`, marker `live`, `-p no:cacheprovider`, `pythonpath=["src"]`); "No `[build-system]`, no packaging"; `run.py` puts its own directory on `sys.path` so modules import flat (00 §0.8).
- `requirements.txt`: `pyyaml>=6`, `pytest>=8`; "standard library plus PyYAML" (00 §0.8). No SDK; live probes shell out to the `claude` CLI (JC-40).
- Lint/format/type tools: not specified.
- CI: `.github/workflows/ci.yml`, one Ubuntu job — pip install, `run.py doctor --offline --json`, `pytest harness/tests -m "not live"`; red on unaccepted spec drift; probes never in CI (00 §0.7, JC-05).
- Scripts: only `harness/src/run.py` (16 subcommands, 07), which the hooks also call.
- Generated (00 §0.2): `INDEX.md`, `local.yaml`*, `spec-baseline/`, `.claude/agents/shackles-*.md`, `OWNER.log`*, `.worktrees/`* (* gitignored).

## 3. Repository layout

From 00 §0.2 (O owner, H hand-written, G generated, L living/charged):

```
REPO_ROOT/
  spec.yaml, SPEC.md   O
  CLAUDE.md   H  two lines pointing at harness/AGENTS.md
  .gitignore   H
  .claude/settings.json   H  UserPromptSubmit + SessionStart hooks
  .claude/agents/shackles-<rung>[-readonly].md   G
  .github/workflows/ci.yml   H
  harness/  (= HARNESS_ROOT)
    AGENTS.md, project.yaml, subAgents.yaml, locked_prose/*.txt   O
    CLAUDE.md -> AGENTS.md (symlink), README.md, pyproject.toml, requirements.txt   H
    INDEX.md, spec-baseline/{MANIFEST.json, mirrored copies}   G
    local.yaml*, OWNER.log*, .worktrees/*   G  gitignored
    archives/README.md, archives/rounds/NNNN/   H  "never charged"
    src/ (31 modules)  docs/ (5)  tests/ (39 files + probes/)   L
```

- Two roots (00 §0.1, JC-01): REPO_ROOT = git toplevel; HARNESS_ROOT = first ancestor of `src/run.py` holding `project.yaml`; owner paths resolve against HARNESS_ROOT; `spec.yaml` searched HARNESS_ROOT then parents; "Nothing else may assume that HARNESS_ROOT is exactly `REPO_ROOT/harness/`."
- `.gitignore` (00 §0.4): `harness/OWNER.log`, `harness/local.yaml`, `harness/.worktrees/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
- Rounds at `archives/rounds/NNNN/` per `roundPaths` (08 §8.1), the round's OWNER.log slice committed there (JC-03); worktrees `.worktrees/round-NNNN/` and `landing-NNNN/` (04). Owner files are "never written by any code in this repository" (00 §0.3); generated files sit outside `src/`, `docs/`, `tests/` "so their tokens are never charged" (JC-02).

## 4. Actors and roles

- **Owner**: chats in Claude Code; every prompt logged verbatim by the hook; decides only via quotes the driver classifies (kinds approve, delegate, delegate-through, override, answer, abandon, hard-stop-multiple, note, accept-spec — 03 control.py).
- **Driver**: "the agent sitting in the owner's chat"; runs `run.py`; performs CHAT-TO-PLAN and checkpoints itself (`Next.action` self/chat); spawns every other agent with the prompt file verbatim; saves the final message; records; relays owner words as verbatim quotes (SPEC §1; 09 §4).
- **Runner**: `harness/src/run.py` + `src/`, "plain Python; it never talks to a model"; the only committer/pusher; renders, verifies, triages, tests, bills (SPEC §1, §3).
- **Producer sub-agents**: one fresh agent per attempt from `shackles-<rung>`, cwd = round worktree; may spawn **helper sub-agents** bounded by AGENTS-PLAN and `maxSimultaneousSubAgentsPerRound` (02; JC-20).
- **Gate sub-agents**: read-only twin `shackles-<rung>-readonly` (Read, Grep, Glob); return verdict, rulings, findings (02 agentdefs; 05).
- **Landing-conflict agent**: role `landing-conflict`, attempts `LANDING-1`/`-2`, cwd = landing worktree, declared = conflicted files (04).
- **Hooks** (00 §0.5): `UserPromptSubmit` → `hook prompt` appends to `OWNER.log`, always exit 0; `SessionStart` → `hook session-start` reports agent-def staleness and baseline status, "regenerates nothing" (JC-06).
- **CI job** (00 §0.7); **stub agent** and **drive loop** in tests (10); **live probe agent** = real `systemTestAgent` rung via `claude -p` (11); a **second runner** on another checkout may claim the next id (11 case 19).

## 5. Architecture: the main mechanisms

a. **Step table** — `steps.py` `TABLE`, 11 literal `Step` rows (kind, performer, `has_gate`, artifacts, inputs, declared path classes, verify mode, prose names, `overridable`); `steps.lint` demands the owner's `steps` match set and order. Step names and the token grammar are the only owner-shaped things in code (SPEC §5).

b. **Round lifecycle** — `round.py`, "a sequencer with no rules of its own", the only caller of `state.save`, round commits and `push_cas`; state is `STATE.json` in the round folder inside the worktree, "the runner's only state" (03): seven phases, nine pause reasons; `next` returns `Next` (spawn/self/chat/done) and is idempotent while an attempt is open (07).

c. **Prompt assembly** — `{{ ns.KEY }}` grammar with namespaces prose/project/round/plumbing/agents (02); `prose.py` reads files, `render.py` expands `prose.*` recursively (depth ≤ 8) collecting every unresolved token, `plumbing.py` writes the mechanical instructions with "no judgment language of its own", `agentsmd.py` serves AGENTS.md sections. Prose is rendered verbatim, never interpreted; STEP-END is the prompt's last section and a separate `-END.txt` (JC-14); a step without overview prose gets the three COMMON files + instructions (JC-12).

d. **Owner channel** — `ownerlog.py` (hook-written JSONL, round slice, `verify_quote` = verbatim substring, JC-17); `control.py` (closed `Kind` vocabulary, `Decision` carrying quote and `log_line`; the driver classifies, the runner only verifies); `round.owner` applies effects and fences; every decision is a `history.py` event with its quote; flags surface at the next `chat` (03, 07).

e. **Git** — `gitops.py` thin wrappers; claim = `push_cas(expected=None)` on `round/NNNN`; every state change ends `save → commit → push_cas(expected = pushed_sha)`, `PushRejected` → `LockLost` exit 4 (07); one worktree per round (JC-20); `landing.py` merges in a landing worktree at `main_before`, clean + green suite → `push_ff` with lease, textual conflict → reference commit and attempts `LANDING-1`/`-2` judged by `judge_resolution` (JC-22/23); `sync.py` ≤ 3 cycles, conflicts pause (JC-24); abandon syncs the round folder only (JC-35).

f. **Results/findings** — `results.py` owns the producer (DONE/NEEDS-OWNER/BLOCKED) and gate (PASS/FAIL, rulings, findings with quote/text/suggestion) JSON contracts and lenient `extract_json` (JC-26); `findings.py` owns states open/resolved/disputed/withdrawn/settled/flagged/dropped, upheld-twice = settled, the verdict-wins rewrite (JC-27), repeats of withdrawn quotes dropped; one `FINDINGS/<STEP>-<n>.json` per gate attempt (05).

g. **Money** — `tokens.estimate = ceil(bytes/tokenBytes)` is the only estimate; `pricing.py` prices measured usage when the driver passes `--usage`, else estimates (JC-29); `quote.py` holds the quote and per-pool share caps (JC-30/31); `ledger.py` computes the living charge on the net diff main_before→tip (cap tiers, base cost, carry-forward flat rate JC-32, tests × `testBaseCost`), archive charges, `make_bill`, and `remaining_project` by scanning round bills (JC-33); `limits.py` hard stops (round multiple vs projected living charge before landing; per attempt), turns, active-time wall clock (JC-19), restarts (JC-18) — a `Hit` "always pauses the round ... never ends it" (06, 03).

h. **Checks** — at `record`, `worktree.triage` keeps declared/round-folder changes, reverts strays (noted) and refuses edits to runner-only or non-append judgment files; `verify.py` checks artifacts present and parseable, no conflict markers, and runs `pytest -m "not live" <testPaths>` (collect or suite per `step.verify`, timeout `verifyTimeoutSeconds`) on DONE only — a red suite refuses the record and re-runs the same attempt; `suite.py` moves archived test functions by AST span (JC-28) (04, 05).

i. **Doctor/lint/index** — `doctor.run` renders every step × role with a synthetic round and emits 17 check ids (config, steps, prose, per-prompt unresolved tokens and size, AGENTS.md sections, agent defs, baseline, hooks, OWNER.log, remote, INDEX, roster); `index_text`/`write_index` build `INDEX.md` (`<path> — <purpose>`); `steps.lint`, `quote.lint_agents_plan`, `localyaml.write` (02, 01, 06).

j. **Robustness to owner edits** — owner numbers/paths/prose/rungs/prices are read at every command; `config.DEFAULTS` (`testPaths`, `mainBranch`, `remote`, `promptWarnTokens`) are each named by doctor; unknown keys/steps refuse start (JC-08); `speclock` baseline + hashes, `test_spec_drift.py` failing with a unified diff, `start` refusing drift, `accept-spec --quote` (JC-04/38); mechanics tests use `specgen.py` fixtures and "never read the owner's files", its token-set table being "the one place that must be updated if the owner introduces a new token"; prompts render from the worktree's committed prose (11 case 20).

## 6. Module inventory

31 modules under `harness/src/` (SPEC §6 agrees); 204 `def` lines; 69 class definitions, 68 distinct names (`Decision` is defined in both `control.py` and `suite.py`); each module has its own `HarnessError` subclass (01).

| Module | Responsibility | Classes |
|---|---|---|
| `paths.py` | root discovery, path conversion, generated-file names | `HarnessError`, `PathsError`, `Roots` |
| `config.py` | load/validate the owner YAMLs; `DEFAULTS`, `REQUIRED`; unknown keys; `project_view` | `ConfigError`, `Agent`, `Roster`, `RoundPaths`, `Config` |
| `steps.py` | fixed `TABLE`, `lint`, `gated`, `checkpoints_on`, `prose_names` | `StepsError`, `Step` |
| `localyaml.py` | build/write derived `local.yaml` atomically | — |
| `speclock.py` | enumerate/hash/compare/accept spec files; diffs | `SpecLockError`, `SpecFile`, `Drift` |
| `prose.py` | read `locked_prose/`, tokenise, classify names | `ProseError`, `Token` |
| `agentsmd.py` | AGENTS.md sections by normalised heading | `AgentsMdError` |
| `render.py` | token resolution, unresolved reporting, size | `RenderError`, `RoundView`, `Context`, `Rendered` |
| `plumbing.py` | PROCESS-INSTRUCTIONS, GATE-PROSE, driver instructions, STEP-END | `AttemptFacts` |
| `agentdefs.py` | write/check `.claude/agents/shackles-*.md` | `AgentDefsError` |
| `doctor.py` | offline health report; `INDEX.md` | `Check`, `Report` |
| `ownerlog.py` | hook writer, round slice, `verify_quote` | `OwnerLogError`, `Entry` |
| `control.py` | decision kinds, validation, `make`, mode queries | `ControlError`, `Decision` |
| `state.py` | `STATE.json` schema, atomic load/save, pause/resume | `StateError`, `State` (refers to undefined `StepState`) |
| `history.py` | `HISTORY.md` append/event | — |
| `attempts.py` | attempt names; prompt/end/result/findings files | `Files` |
| `limits.py` | every bound → `Hit`; `check_before_next` | `Hit` |
| `gitops.py` | every git invocation, typed results, CAS/lease pushes | `GitError`, `PushRejected`, `Change` |
| `worktree.py` | round worktree, declared prefixes, `triage`/`revert` | `WorktreeError`, `Triage` |
| `landing.py` | pre-landing hard stop, merge, conflict attempt, `judge_resolution` | `LandingError`, `MergeOutcome` |
| `sync.py` | bounded post-landing sync, `update_control_checkout` | `SyncError`, `SyncResult` |
| `results.py` | final-message contracts, `extract_json`, validation | `ResultError`, `Question`, `Response`, `JudgmentCall`, `Usage`, `ProducerResult`, `RawFinding`, `Ruling`, `GateResult` |
| `findings.py` | finding lifecycle, `reconcile`, flags, FINDINGS file | `Finding`, `FindingView` |
| `verify.py` | test runs with timeout, artifact checks, markers | `VerifyError`, `TestRun`, `Verdict` |
| `suite.py` | test-function enumeration by AST, `SUITE.json`, archive by span | `SuiteError`, `TestFn`, `Decision` |
| `tokens.py` | the one token estimate | — |
| `pricing.py` | usage → USD, estimate, `attempt_cost` | `Priced` |
| `quote.py` | PLAN/AGENTS-PLAN loaders, `lint_agents_plan`, budgets, rungs | `QuoteError`, `StepShare`, `AgentsPlan`, `Plan` |
| `ledger.py` | living charge, archive charges, `make_bill`, `remaining_project` | `FileCharge`, `LivingCharge` |
| `round.py` | sequencer: `start`, `next`, `record`, `owner`, `resume`, `abandon`, `finish`, `judgment` | `RoundError`, `LockLost`, `Refused`, `Next` |
| `run.py` | CLI dispatch, exit codes 0/1/2/3/4, `main(argv) -> int` | — |

## 7. Data contracts

| Format (source) | Content | Persisted |
|---|---|---|
| `STATE.json` (08 §8.2; 03) | schema, round{…phase, pushed_sha}, pause, owner{decisions, mode, …}, steps{}, open_attempt, attempts[], findings{}, questions[], flags[], counters{turns, restarts, active_seconds}, landing, bill{quote, attempts, driver, living, archive, total, …} (06) | round folder in worktree; committed, fenced |
| `PLAN.json` (08 §8.3) | plan_md, quote_usd, scope/non_goals/assumptions/validation_steps, questions with `answer_quote`, todos_accepted, refactor_fraction, two estimates | round folder; driver; `quote.load_plan` |
| `AGENTS-PLAN.json` (08 §8.4) | steps{STEP:{agent,sub_agents,share,notes}}, gates{…}, refactor_share, rationale_md | round folder; `quote.load_agents_plan` |
| `SPEC.json` + `SPEC.md` (08 §8.5) | components[], steps[], test_plan_md, integration_tests_md, non_goals, refactors[] | round folder; `verify.load_spec_json` |
| `SUITE.json` (08 §8.6) | tests[{file,name,decision,reason}], flags[] | round folder; `suite.load_suite_json` |
| `POSTMORTEM.md` (08 §8.7) | first heading must be `## Summary` | round folder |
| `DEFINED_/UNDEFINED_JUDGMENT_CALLS.md` (08 §8.8) | header + `- [<attempt>] <text>`, append-only | round folder |
| `FINDINGS/<STEP>-<n>.json` (08 §8.9) | gate_attempt, producer_attempt, verdict, rulings, findings with state, notes | round folder; runner |
| `PROMPTS/<attempt>.txt`, `-END.txt`; `RESULTS/<attempt>.json`; `tests-archive/<path>.py` (08 §8.1) | rendered prompt; STEP-END; final message raw or JSON; archived tests | round folder |
| `HISTORY.md` (03) | `## <ts>  <attempt/event>  <status>  $<usd>` + summary + `- verdict/reverted strays/note` | round folder; append-only |
| `OWNER.log` (08 §8.11; 03) | JSONL `{ts, session, text}`; round slice adds `line` | `harness/OWNER.log` (ignored); round slice committed |
| `local.yaml` (08 §8.10; 01) | absolute roots, defaults_applied, unknown_keys, steps_effective, gates_in_order, agent_definitions, baseline_status, current_round | `harness/local.yaml` (ignored) |
| `spec-baseline/MANIFEST.json` + copies (00 §0.10; 01) | `{relative path: sha256, bytes}` | committed |
| Agent definitions (02); `.claude/settings.json` (00 §0.5); `INDEX.md` (02) | front matter name/description/model/effort/tools + one-line body; exactly two hook commands; `<path> — <purpose>` sorted | `.claude/agents/`; repo root; `harness/`; all committed |
| `Next` JSON; `record` return; error JSON (07) | action, attempt/step/role, agent_definition, rung, read_only, cwd, prompt/end/result files, budget_usd, max_helpers, reason, warnings, flags, questions, bill, postmortem_summary; `{accepted, reasons, next_hint}`; `{error, code}` | stdout |
| `docs/TODO.md`, `docs/CLARIFICATIONS.md` lines (09) | `- [ ] R0007 P2: …`; `- [ ] R0007 C1: … — owner: "…"` | carry-forward files |
| Hook payload (03) | keys `prompt`, `session_id`; unknown shapes stored whole | stdin of `hook prompt` |

## 8. Testing

- Rules (10): mechanics tests "never read the owner's files"; every runner path is driven by the stub agent; "Git is real" — real repo and bare remote in `tmp_path`, "nothing mocks `git`".
- Infrastructure, 5 files (10): `conftest.py` fixtures `spec_root`, `repo` (git repo with generated owner files, a *copy* of `src/`, accepted baseline, pushed to bare `tmp_path/remote.git` as `origin`; returns `Repo{root, harness, remote, roots, cfg}`), `owner_log` (`say(text) -> Entry`), `cli` (`run(*args, expect=0)`, in-process `run.main` with `--harness` and a fixed `--now`), `clock`, `stub`, `driver`, `started`; `specgen.py` `generate(dest, *, steps_flags, config_overrides, prose_overrides, agents)` writing all five owner files (gates all on, two rungs) with one line per prose name carrying "the same token set the real file uses"; `stub_agent.py` `class StubAgent` (`script`, `act`, `usage_for`) with `BEHAVIOURS`, 38 named behaviours covering producer, gate, plan, suite, postmortem and conflict paths (JC-37); `driveloop.py` `drive(repo, cli, stub, owner_log, *, on_chat=None, max_steps=200) -> list[dict]`, `approve_all`, `delegate_all`; `gitfix.py` five git helpers (names only).
- Files: 39 under `tests/` (5 infra; 31 unit, one per module, `run.py` via `test_cli.py`; `test_spec_drift.py`; `test_integration.py`; `test_docs.py`) + `probes/` (`live_agent.py` + 5 `test_probe_*.py`) = 45. Split: unit 32 files; integration 1 file with 22 numbered whole-round cases (happy path through abandon, limits, landing conflict/hard stop, sync conflict, two runners, idempotent driver; listed in 11); docs 1 file, 8 checks; live 5 probes.
- Live probes (11): skipped unless `SHACKLES_LIVE=1`, marker `live`; `probes/live_agent.py` wraps `claude -p --output-format json --model <model>` (override `SHACKLES_LIVE_CMD`); rung `systemTestAgent`; each "plants one defect and asserts the agent's *mechanical* behaviour, never its wording"; cost printed; never in CI (JC-40). Cases: gate catches a planted contradiction; gate rules on a dispute first; producer output parses valid; judgment-tool line appears; stray discipline.
- Assertions: every unit file is "case → assertion"; the drift test's message is `Drift.diff_text` + "run: python3 src/run.py accept-spec --quote ..." (JC-38); `test_plumbing.py` word-list guard for "sensible"/"judgment" (JC-39); `test_docs.py` regenerates the step table and driver loop and asserts verbatim equality, plus key names, token targets, the symlink; `test_round.py` asserts every state change leaves the remote round branch at the local tip and a foreign push → `LockLost` "writes nothing"; case 16 compares a hand-computed bill to `bill.total`.

## 9. Docs

- `harness/README.md` (00 §0.6): what it is (quoting no owner text), requirements, install, first-time setup (`doctor`, `agents`, restart, `accept-spec --quote`), driver loop verbatim from PROCESS.md (test-synced), running tests.
- `harness/archives/README.md` (00 §0.9): three lines. Root `CLAUDE.md`: two lines routing to `harness/AGENTS.md`; `harness/CLAUDE.md` symlink (00 §0.2). `harness/INDEX.md`: generated (02).
- `docs/PROCESS.md` (09): < 2,500 tokens; 12 sections — what a round is, roles, generated step table, driver loop, owner words, pauses, final messages, findings, path discipline, judgment calls, limits, git; opens with "the code is the authority".
- `docs/MONEY.md` (09): < 1,200 tokens; token estimate, attempt cost, quote/shares, hard stops, living charge (five-step algorithm verbatim), archive charges, bill/remaining; "Every number is a config key name, never a value".
- `docs/TESTING.md` (09): < 900 tokens; specgen, stub behaviours (generated list), drive loop, probes, drift test, how to add a test.
- `docs/TODO.md` (09): carry-forward, `- [ ] R0007 P2: <proposal> (from POSTMORTEM issue 1; plan: "…")`; "Removing a line is a refund".
- `docs/CLARIFICATIONS.md` (09): carry-forward, `- [ ] R0007 C1: <question> — plan: "…" — owner: "<exact owner words>" — judgment call: …`.

## 10. Notable or unusual decisions

1. Runner never spawns or calls a model; the driver spawns every agent; no SDK; the only test seam is `next`/`record`, so the stub is an in-process class (SPEC §1; JC-37).
2. Self-hosting on living paths: `src/`, `docs/`, `tests/` are charged per token; all generated files are kept outside them (00 §0.3; JC-02).
3. One worktree per round, one open attempt at a time; helpers are the producer's own sub-agents (JC-20).
4. No project ledger file; `remaining_project` scans every round's `STATE.json.bill` (JC-33).
5. Spec baseline is full copies plus hashes; CI red until `accept-spec` (JC-04, JC-38).
6. Unknown `project.yaml` keys refuse `start`; four defaulted keys (JC-07, JC-08).
7. SessionStart hook only reports; `run.py agents` regenerates and the session must restart; `effort:` front matter; read-only gate twins (JC-06, JC-13).
8. CHAT-TO-PLAN: record → gate → owner approve/delegate, accepted only after both (JC-34).
9. Textual landing conflicts get two agent attempts judged mechanically against a reference tree; a red suite after a clean merge pauses for the owner (JC-22, JC-23).
10. Abandon merges only the round folder to main; branch kept on the remote; bill without living charge (JC-35).
11. Refused records keep the attempt open under the same name, `refused += 1`, cost booked each time; not gate rejections (JC-36).
12. Round's OWNER.log slice committed (JC-03); wall clock = active seconds (JC-19).

## 11. Judgment calls

Total: 40 (JC-01 … JC-40) in `JUDGMENT-CALLS.md`, definition: "a judgment call is any choice that lands in your finished work that you are not confident in making correctly for any reason." Each entry: Choice / Alternatives / Why unsure / Labels / Affects.

Classification scheme, verbatim:

> Each call carries three labels.
>
> **Cause** (why I was not confident):
> - `SILENCE` — the inputs say nothing about this; I had to pick something.
> - `AMBIGUITY` — the inputs can be read more than one way; I picked one reading.
> - `CONFLICT` — two inputs disagree (or an input disagrees with itself); I picked a winner.
> - `ENVIRONMENT` — depends on how an external tool (Claude Code, git, pytest, the model API) behaves, and I could not verify that here.
> - `ENGINEERING` — the inputs allow several sound designs; I picked one on taste.
>
> **Reach**: `LOCAL` (one component) or `CROSS` (several components or the owner-visible surface).
>
> **Confidence**: `LOW` or `MEDIUM` (a `HIGH` confidence choice is not a judgment call).

Label tallies: Cause — AMBIGUITY 12, SILENCE 10, ENGINEERING 8, ENVIRONMENT 7, CONFLICT 3. Reach — CROSS 6 (JC-01, 03, 07, 11, 20, 27), LOCAL 34. Confidence — LOW 7 (JC-13, 18, 23, 28, 31, 39, 40), MEDIUM 33.

By theme (analyst's grouping):
- Platform/tooling facts (Claude Code, git, pytest, CI): 8 — JC-01, 05, 06, 13, 14, 26, 29, 40.
- Repository layout / what is committed: 3 — JC-02, 03, 04.
- Gaps in the owner files: config surface, step table, path classes: 6 — JC-07, 08, 09, 10, 11, 21.
- Prompt composition: 2 — JC-12, 15.
- Owner words, quote verification, approval order: 4 — JC-16, 17, 25, 34.
- Round lifecycle, limits, refused records: 3 — JC-18, 19, 36.
- Git semantics (worktrees, landing, sync, abandon): 5 — JC-20, 22, 23, 24, 35.
- Findings and suite mechanics: 2 — JC-27, 28.
- Money rules: 4 — JC-30, 31, 32, 33.
- Testing approach (taste): 3 — JC-37, 38, 39.

Ten most consequential (the six CROSS calls, then four LOCAL calls that change owner-visible behaviour):
1. JC-01 — HARNESS_ROOT found by walking up to `project.yaml`; `.claude/` at REPO_ROOT; `$CLAUDE_PROJECT_DIR` assumed = git root.
2. JC-03 — the round's OWNER.log slice is committed in the round folder.
3. JC-07 — `testPaths` invented as a defaulted config key.
4. JC-11 — declared paths are fixed per-step classes in `steps.py`, not narrowed by `SPEC.json`.
5. JC-20 — one worktree per round, one open attempt at a time.
6. JC-27 — PASS forces findings non-blocking into owner flags; FAIL with none blocking forces all blocking.
7. JC-08 — unknown `project.yaml` keys refuse `start`.
8. JC-29 — measured usage billed when supplied, else estimated; refused records booked.
9. JC-34 — CHAT-TO-PLAN is gated before the owner's approval is requested.
10. JC-35 — abandon merges only the round folder into main; branch stays on the remote.

## 12. Traceability

- Yes, tabular. `SPEC.md` §2 "Requirements inventory": 19 rows, owner statement → module. `SPEC.md` §9 "Full traceability": `AGENTS.md` rules (8 rows), `project.yaml` keys ("every key is used", 15 rows), `subAgents.yaml` (paragraph), locked-prose mechanical parts (14 rows).
- Inconsistencies/gaps in the owner's files the draft flags:
  - `testPaths` referenced by the living-charge commentary but defined nowhere (JC-07).
  - A gate flag exists for CHAT-TO-PLAN but no `CHAT-TO-PLAN-GATE.txt`; the comment says only LANDING and CLEANUP have "no gate" (JC-10; 01).
  - No `LANDING-OVERVIEW.txt` though a landing conflict "becomes one agent attempt" (JC-12).
  - "Enforced distribution of budget (sum to 1)" vs "A gate that is off does not incur a charge" (JC-30); `defaultShares` covers only three entries (JC-31).
  - No ladder-ordering rule; the `high` rung is named "Fable 5.1 Low" (JC-09).
  - Carry-forward file names appear only in a `project.yaml` comment (JC-21).
  - COMMON-STEP-END "produced at the end of every step" reads as a second message (JC-14).
  - "each is used for something" vs "robust to arbitrary changes" (JC-08); `AGENTS.md` says "grep INDEX.md" without a path (JC-02).
  - `allowUpstream: 1` refused as "not implemented" (01 config.load).
  - `maxRoundAttempts` "names neither the trigger nor what counts as minor"; "per run" undefined (JC-18, 19); "bounded sync" names no bound (JC-24); "one agent attempt" ambiguous (JC-23).
  - No owner file mentions CI (JC-05).

## 13. Gaps against the brief

Shortfalls:
- **Classes/functions incomplete in places.** `state.State`'s body is elided ("`...` fields as above") and `StepState`, returned by `State.step()`, is never defined (03). `config.REQUIRED` is only "every other key above, with its expected type" (01). `control.KINDS` is declared but its strings never written out (03; CLI forms only in 07's table). `run.py` has one signature, `main(argv) -> int` (07). `plumbing`'s instruction texts are described by section headings, not a template (02).
- **Test-infrastructure signatures partly missing.** `gitfix.py` helpers have names only; `probes/live_agent.py` has no signature; `conftest.py` fixtures are prose; integration cases are described by outcome, not test-function names (10, 11).
- **Dependency lists contradict the stated architecture.** SPEC §3: "Each layer depends only on layers below it", yet `plumbing` (02) depends on `results` (05); `render` (02) on `tokens` (06); `doctor` (02) on `gitops` (04), `ownerlog` (03); `landing` (04) on `verify` (05), `ledger` (06), `limits` (03). `results.py` lists "Depends on: paths" while `validate_producer` takes `Iterable[Finding]` from `findings.py`, which depends on `results` — mutual. `worktree` uses `speclock` and `quote` uses `ownerlog.Entry`, neither listed (04, 06).
- **Naming inconsistencies across files.** `verify.py` depends on "`schemas` (file 08 ...)" but 08 says "nothing here is code" and no such module exists (05); 08 §8.5 cites `spec_loader` while `verify.py` defines `load_spec_json`; `test_docs.py` puts the driver loop in "a constant in `doctor.py`" that `doctor.py` does not list (11, 02); `Decision.reason` (abandon) is "taken from the quote by the driver" but no CLI argument carries it (03, 07); `history.py` names `ledger` as a dependant that `ledger.py` does not list (03, 06).
- **Unresolved notation left in the spec.** The CHAT-TO-PLAN row of `steps.TABLE` reads `"CHAT-TO-PLAN-GATE"?` with a literal `?` (01). `gitops.merge`'s comment holds a mid-thought correction ("`git merge --no-ff --no-commit`? No: ...") (04); `test_agentdefs.py`'s text holds "prices? — no:" (10).
- **Tooling.** No lint/format/type tool named; hook payload keys and `$CLAUDE_PROJECT_DIR` semantics are assumed, as the draft itself flags (00 §0.5, JC-01).
- **Errors per function** appear as `raises` comments for loaders/validators/git but not for `history`, `ledger`, `tokens`, `attempts`, `limits` (03, 06), stated or implied pure.

Drift toward line-by-line implementation:
- `steps.TABLE` written as eleven literal Python constructor rows (01).
- Exact command lines and verbatim files fixed in the spec: `verify.test_command` argv, `--force-with-lease=refs/heads/<branch>:<expected>`, `git diff --name-status -M`, commit author "shackles runner <runner@shackles>" (04, 05); `.gitignore` (00 §0.4), the agent-definition file (02), the HISTORY template (03), the full `STATE.json` example (08 §8.2), CI steps (00 §0.7).
- Algorithms spelled step by step: living charge (06, five steps), `findings.reconcile` (05, four), `landing` (04, six), `round.next` (eight) and `round.record` (07); the draft's stated reason: "so it can be rewritten from that section alone" (SPEC §3).
