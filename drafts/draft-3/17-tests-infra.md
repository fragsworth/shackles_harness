# 17 — Test infrastructure: the generated spec, the stub agent, the fake driver, git fixtures, probes

Mechanics tests never read the owner's real prose or `project.yaml`: they run on a
spec generated from the code's own step table and config schema, so a prose rewrite
fails only `test_spec_drift.py`. Every path of the runner is driven by a stub agent
with scripted behaviours through the same `next`/`record` functions the driver uses.
Real agents run only in opt-in probes.

## `tests/fixture_spec.py` — the one-line-per-file spec

**Owns:** generating a complete fixture repository content. **Depends on:**
`steps` (names), `config` (`example_project_dict`, `example_agents_dict`).

- `FixtureSpec` (dataclass): `repo_root: Path`, `harness_root: Path`, `steps:
  list[str]`.
- `generate(repo_root: Path, gates_on: dict[str, int] | None = None, checkpoints_on:
  bool = True, extra_prose: dict[str, str] | None = None, drop_prose: list[str] =
  ()) -> FixtureSpec` — writes:
  - `spec.yaml`: the same `files:` list as the real one (relative paths).
  - `SPEC.md`: one line.
  - `harness/AGENTS.md`: `# harness/` and three level-2 sections, one line each:
    `## ADVICE`, `## INVARIANTS`, `## DEFINED AND UNDEFINED JUDGMENT CALLS`.
  - `harness/project.yaml`: `config.example_project_dict(steps.names())` with
    `steps` overridden by `gates_on` and checkpoints set from `checkpoints_on`,
    dumped as YAML (defaulted keys omitted so `defaulted_keys()` is non-empty).
  - `harness/subAgents.yaml`: `config.example_agents_dict()` (rungs `max`, `low`).
  - `harness/locked_prose/`: for every step, `<STEP>-OVERVIEW.txt` = `<STEP>-OVERVIEW
    {{ prose.COMMON-PROJECT }} {{ prose.COMMON-ROUND }} {{ plumbing.GATE-PROSE }}
    {{ plumbing.PROCESS-INSTRUCTIONS }}` (checkpoints share `CHECKPOINT-OVERVIEW.txt`
    = `CHECKPOINT-OVERVIEW {{ round.id }}`; LANDING gets none); for every
    gate-capable step `<STEP>-GATE.txt` = `<STEP>-GATE {{ prose.COMMON-GATE }}
    {{ plumbing.PROCESS-INSTRUCTIONS }}`; fragments `COMMON-PROJECT.txt` =
    `COMMON-PROJECT {{ project.vision }} {{ project.gates }} {{ project.remaining }}
    {{ project.livingSourcePaths }}`, `COMMON-ROUND.txt` = `COMMON-ROUND {{ round.id }}
    {{ round.folder }} {{ round.base_commit }} {{ round.plan }} {{ round.budget }}
    {{ round.spend }} {{ round.remaining }}`, `COMMON-OVERVIEW.txt` = `COMMON-OVERVIEW`,
    `COMMON-GATE.txt` = `COMMON-GATE`, `COMMON-STEP-END.txt` = `COMMON-STEP-END
    {{ agents.DEFINED_AND_UNDEFINED_JUDGMENT_CALLS }}`; `extra_prose` adds or replaces
    files; `drop_prose` removes stems.
  - the living skeleton: `harness/src/app.py` (a docstring and `def add(a, b)`),
    `harness/docs/TODO.md`, `harness/docs/CLARIFICATIONS.md`, `harness/tests/test_app.py`
    (one passing test importing `app`), `harness/pyproject.toml` (pytest
    `pythonpath = ["src"]`, `testpaths = ["tests"]`), `harness/INDEX.md` (empty; the
    fixture calls `install` which regenerates it), `harness/archives/rounds/.keep`.
- `prose_line(stem: str) -> str` — the generated line for a stem (tests assert
  rendered prompts contain these markers, e.g. `PLAN-AGENTS-OVERVIEW`).

## `tests/gitfixtures.py` — repositories

- `make_origin(tmp: Path) -> Path` — `git init --bare`; default branch `main`.
- `make_clone(origin: Path, dest: Path) -> Path` — clone, set a local identity.
- `commit_all(repo: Path, message: str) -> str`; `push_main(repo: Path) -> None`.
- `advance_main_elsewhere(origin: Path, tmp: Path, files: dict[str, str], message:
  str) -> str` — a throwaway clone that commits the given files on `main` and pushes;
  returns the new sha (simulates another landing or an owner commit).
- `branch_sha(origin: Path, branch: str) -> str | None`.
- `read_at(origin: Path, ref: str, path: str) -> str | None`.

## `tests/conftest.py` — fixtures

- `clock` — `FakeClock(start="2026-01-01T00:00:00Z")` with `now() -> str` and
  `advance(seconds)`; every runner call in tests passes `clock.now()`.
- `fixture_repo(tmp_path, clock)` — `make_origin` + `make_clone` +
  `fixture_spec.generate` + `commit_all` + `push_main` + `install.install(harness,
  python=sys.executable)` + `specfiles.accept` + commit + push; yields
  `FixtureRepo(origin, repo_root, harness_root, spec: FixtureSpec)`.
- `world(fixture_repo)` — `commands.load_world(harness_root)`.
- `say(fixture_repo, clock)` — a function `say(text) -> str` that appends an entry
  to the fixture's `OWNER.log` (what the hook would do) and returns the text.
- `stub(fixture_repo)` — a `StubAgent` with default behaviours.
- `driver(world, stub, say, clock)` — a `FakeDriver`.
- `started(driver, say)` — a round started with `say("please build X")` and
  `rounds.start(world, quote, now)`; yields the `LoadedRound`.
- `approved(started, driver)` — the round taken through CHAT-TO-PLAN with the stub's
  `PLAN.json` (no questions) and `record --decision approve`.
- `real_repo_root()` — the parent of the real `harness/` (found from this file's
  location); used only by `test_spec_drift.py` and `test_spec_lint.py`.
- `pytest_configure` registers the `probe` marker; probes are skipped unless
  `SHACKLES_PROBES=1`.

## `tests/stub_agent.py` — scripted behaviours

**Owns:** doing, in the worktree, what a real agent would do for a given action, in a
scripted way, and writing the final message file. **Depends on:** `schemas`
(shapes), `steps`, `paths`; it may run `run.py jc` as a subprocess.

- `StubAgent(script: dict[str, list[str]] | None = None, default_producer: str =
  "done", default_gate: str = "pass")` — `script` maps `STEP` or `STEP-GATE` to a
  queue of behaviour names consumed one per attempt; when exhausted the default
  applies. `act(action: Action) -> str` performs the behaviour and returns its name;
  asserts the prompt file exists, starts with the header line and contains the
  step's generated prose marker. `history: list[tuple[str, int, str]]` records what
  it did.

Producer behaviours (each writes a valid `DONE` message unless stated):

| name | what it does in the worktree |
|---|---|
| `done` | writes the step's minimal valid artifact: `PLAN.json` (text, quote 100, no questions), `AGENTS-PLAN.json` (shares from `defaultShares` filled to the fractions), `SPEC.json`+`SPEC.md`, a new passing test file `tests/test_round.py` referencing `app.mul`, `src/app.py` gaining `mul` so the tests pass, `SUITE.json` all `suite`, `POSTMORTEM.md` with a `## Summary`, CLEANUP no-op; LANDING: resolves markers by keeping the branch side |
| `done_questions` | `PLAN.json` with two questions answered with quotes (the test says them first) |
| `done_unanswered` | `PLAN.json` with a question lacking `answer` |
| `done_flags` | like `done` plus `flags: ["middle ground"]` |
| `done_jc` | like `done`, runs `run.py jc` twice (one defined, one undefined) and lists one more call in the message |
| `needs_owner` | writes a partial artifact and a `NEEDS-OWNER` message with one question |
| `blocked` | `BLOCKED` with `narrow` |
| `invalid_json` | writes `not json` to the result file |
| `prose_wrapped` | valid message inside prose and a ```json fence |
| `missing_resolution` | `done` without `resolutions` while findings are open |
| `fix_all` / `dispute_all` / `dispute_settled` | resolutions for every open finding as named |
| `stray_write` | `done` plus a file `src/stray.py` (or `docs/x.md` for steps whose scope excludes it) and `README-stray.md` at the harness root |
| `edit_spec_file` | `done` plus appends a line to `AGENTS.md` and `locked_prose/COMMON-GATE.txt` |
| `touch_runner_files` | `done` plus edits `STATE.json` and `HISTORY.md` in the round folder |
| `edit_frozen_tests` | `done` plus edits `tests/test_round.py` (SPEC-TO-IMPLEMENTATION) |
| `tests_no_collect` | writes a test file with a syntax error |
| `impl_tests_fail` | `done` but does not add `mul`, so the round tests fail |
| `suite_archive_all` / `suite_mixed` / `suite_missing` | SUITE.json variants (`suite_mixed`: first test archived) |
| `postmortem_no_summary` | POSTMORTEM.md without a Summary heading |
| `postmortem_edits_todo` | `done` plus appends a TODO and a CLARIFICATION line |
| `cleanup_removes` | deletes `src/app_old.py` (which `advance_main_elsewhere` may have added) and a test |
| `landing_markers` | leaves conflict markers in one conflicted file |
| `landing_stray` | resolves, then also edits a non-conflicted file |
| `big_artifact` | `SPEC.md` of 2 MB, to exercise archive pricing and prompt-size warnings |

Gate behaviours: `pass`, `pass_nonblocking` (PASS + one non-blocking finding),
`pass_blocking` (PASS + one blocking finding), `fail_blocking` (FAIL + one blocking
finding with a quote and suggestion), `fail_nonblocking_only`, `fail_two` (two
blocking findings), `fail_repeat` (a finding whose quote equals the first finding's
quote, for the withdrawn-repeat rule), `withdraw_all` (rulings withdrawn on every
disputed id, verdict PASS), `uphold_all` (rulings upheld, verdict FAIL),
`missing_ruling` (disputed ids but no rulings), `invalid_verdict`, `no_suggestion`
(blocking finding without suggestion), `gate_writes` (PASS but creates a file),
`gate_jc` (PASS with `judgment_calls`).

## `tests/fake_driver.py` — the loop

- `Trace` (dataclass): `actions: list[Action]`, `outcomes: list[RecordOutcome |
  HarnessError]`, `owner_turns: list[str]`.
- `FakeDriver(world, stub: StubAgent, say, clock, owner_script: list[tuple[str,
  dict]] | None = None, usage: Usage | None | Callable = None)` — `owner_script` is a
  queue of `(kind, args)` consumed at checkpoints and pauses: `("approve", {})`,
  `("delegate", {"through": "STEP"})`, `("abandon", {})`, `("resume", {...})`; each
  quote is generated as `"<kind> <n>"`, said through `say` first, then passed to
  `record`/`resume`/`abandon`. `usage` may be a callable of the action returning a
  `Usage`.
- `step() -> Action` — one `next`; for `chat`/`spawn` the stub acts and `record` is
  called (an `InvalidError` is caught and appended to the trace, the loop continues);
  for `checkpoint` and `paused` the owner script is consumed (no script → stop).
- `run(max_steps: int = 200) -> Trace` — until `done`, an unscripted pause, or the
  limit (assertion error).
- `run_until(step: str, phase: str) -> Trace`.

## `tests/probes/` — live agents (opt-in)

`conftest.py` there skips everything unless `SHACKLES_PROBES=1` and the `claude` CLI
is on PATH. `live_agent.py` provides `ClaudeCliAgent(rung: str, agents:
AgentsConfig)` with `act(action: Action) -> str`: runs `claude -p --model <model>
--output-format json` with the prompt file content on stdin, in the worktree, with
`--allowedTools` reduced for gates, saves the final text to the result file and
returns the reported usage as a `Usage` when present [JC-44]. Probes use the
`systemTestAgent` rung and the same fixture spec; each plants a defect and asserts the
harness reaction, not the agent's prose (file 19).
