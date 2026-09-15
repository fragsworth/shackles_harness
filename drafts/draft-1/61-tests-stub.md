# 61 — harness/tests/stub/ (the stub agent)

Parent: `60-tests.md`. Owns the scripted stand-in for the driver, producers
and gates, and the temp-spec factory. It drives every path of the runner
without a model. Depends on: `shackles.commands` (called in-process through
`cli.main` with argv, exactly as the real driver would), `git`. Depended on
by: `mechanics/`, `live/` (reuses the driver loop with a real-agent adapter).

```
tests/stub/
  __init__.py
  spec_factory.py   generate a one-line-per-file spec set and a minimal living project
  repo_factory.py   temp clone + bare remote; helpers to move main or the round branch "elsewhere"
  behaviors.py      named scripted behaviors: what a stub producer/gate does and says
  driver.py         the loop: next -> act -> record, until END or a pause
```

## spec_factory.py

- `prose_stems(real_locked_prose: Path | None) -> list[str]` — the stems the
  table expects (`steps.table.prose_stems_expected`) plus, when given, any
  extra stems found in the real folder; the mechanics suite uses the expected
  set only.
- `make_spec(root: Path, project_overrides: dict = {}, roster_overrides: dict = {}, stems: list[str] | None = None, tokens: bool = True) -> SpecSet`
  — writes `spec.yaml` listing the same six patterns as the owner's; `SPEC.md`
  one line; `AGENTS.md` with the three headings the code slugs
  (`ADVICE.`, `INVARIANTS.`, `DEFINED AND UNDEFINED JUDGMENT CALLS`), one line
  each; `project.yaml` with every key the code reads (values small: budget
  1000, quote fractions as the owner's, limits 2/3/20/1, prices as the
  owner's) merged with overrides; `subAgents.yaml` with four rungs and the
  two overhead values; each prose file one line: `<STEM> {{
  plumbing.PROCESS-INSTRUCTIONS }}` for overviews and `<STEM>` for gates and
  commons, with a `{{ prose.COMMON-PROJECT }}` include in overviews when
  `tokens` is true so recursion is exercised. Returns `SpecSet(root, paths,
  settings)`.
- `make_living(root: Path) -> None` — `src/app.py` with one function,
  `tests/test_app.py` with one passing test, `docs/PROCESS.md`,
  `docs/CONTRACTS.md`, `docs/TODO.md`, `docs/CLARIFICATIONS.md`, `INDEX.md`
  listing them.

## repo_factory.py

- `make_repo(tmp: Path) -> RepoHandle` — bare + clone, identity, initial
  commit, push.
- `second_clone(handle) -> Path` — another clone of the bare, to simulate
  another runner or another machine.
- `move_main(handle, path: str, content: str) -> str` — commits a change to
  `main` in the second clone and pushes; returns the sha (for landing and
  sync tests).
- `move_round_branch(handle, branch: str) -> str` — pushes a foreign commit
  onto the round branch from the second clone (lease loss).
- `conflicting_main(handle, path, content) -> str` — a `main` change to a
  file the round also changes.

## behaviors.py

A behavior is a callable `(role, step, attempt, prompt_text, worktree: Path |
None, round_folder: Path) -> str` returning the final message text. Named
constructors, each returning such a callable; `Script` maps `(step, role,
n)` or `(step, role)` or `role` to a behavior with the most specific match
winning:

| behavior | what it does |
|---|---|
| `done_writing_artifact()` | writes a valid artifact for the step (plan/agents plan/spec/suite/postmortem from templates), for SPEC-TO-TESTS writes `tests/test_round.py` with one passing test, for SPEC-TO-IMPLEMENTATION edits `src/app.py`; returns DONE JSON |
| `done_with_failing_impl()` | implementation that makes the frozen test fail |
| `done_then_pass(n)` | fails verification for the first `n` attempts, then passes |
| `writes_stray(path)` | also writes a file outside the declared paths (a living path not allowed, a spec file, `STATE.json`) |
| `edits_spec_file(rel)` | edits an owner spec file in the worktree |
| `rewrites_judgment_file()` | truncates DEFINED_JUDGMENT_CALLS.md (append-only violation) |
| `logs_judgment_calls(k)` | runs `run.py judgment` `k` times from the worktree |
| `needs_owner(questions)` | NEEDS-OWNER with enumerated questions |
| `blocked(narrow)` | BLOCKED |
| `garbage()` | a final message with no JSON |
| `json_missing_fields()` | JSON lacking `status` |
| `prose_then_json()` | a paragraph followed by valid JSON |
| `mixed_suite_decisions()` | SUITE.json splitting one file |
| `flags(items)` | DONE with `flags` |
| `disputes(finding_ids)` | DONE resolving nothing and disputing the ids |
| `resolves_all()` | DONE listing every prior blocking finding under `resolved` |
| `gate_pass()` | PASS with no findings |
| `gate_fail(findings, blocking=True)` | FAIL with given findings (quotes taken from the artifact) |
| `gate_fail_no_blocking_flags()` | FAIL whose findings all say `blocking: false` |
| `gate_pass_with_blocking_flags()` | PASS whose findings say `blocking: true` |
| `gate_rules(rulings, then)` | rulings on prior disputes, then another behavior |
| `gate_repeats_withdrawn()` | raises a finding with the same quote as a withdrawn one |
| `gate_for_owner(items)` | PASS with `forOwner` findings |
| `gate_garbage()` | unparseable |
| `conflict_resolve()` | removes markers in conflicted files only |
| `conflict_touches_other()` | also edits a non-conflicted file |
| `conflict_leaves_markers()` | leaves a marker |
| `driver_plan(questions=[], quote=100)` | writes PLAN.json with the questions (unanswered) |
| `slow(seconds, then)` | sleeps then delegates (wall clock / timeout tests use tiny limits) |
| `big_prompt_result(bytes)` | returns a huge summary (size-estimate billing) |

`default_script()` — every step DONE with valid artifacts, every gate PASS,
the driver's plan approved: the happy path.

## driver.py

`StubDriver(spec: SpecSet, script: Script, owner_words: list[str] | callable)`
mirrors what `docs/PROCESS.md` tells the real driver, mechanically:

- `run_cli(self, *argv) -> dict` — calls `shackles.cli.main` in-process with
  cwd at the clone; parses the JSON on stdout; raises `StubRefused(reason)`
  on exit 2.
- `start(self) -> dict`, `next(self) -> dict`.
- `act(self, action: dict) -> dict | None` — `SPAWN`: read the prompt file,
  call the behavior with the worktree, write the result file, `record
  --tokens N` (N from the behavior's optional `tokens` attribute, else
  omitted); `SELF`: the driver behavior (`driver_plan`), then for
  CHAT-TO-PLAN hand over the scripted owner words (`answer`, then
  `approve`/`delegate`/`override`) through `owner_say`; `OWNER`: call
  `owner_words` to get the next verb, or stop and return the pause; `END`:
  return it.
- `owner_say(self, verb: str, text: str, **kw) -> dict` — appends `text` to
  `OWNER.log` (as the hook would) and runs `owner <verb> --quote text`.
- `run_round(self, max_actions: int = 200) -> RoundOutcome` — loops
  `next`/`act` until `END` or a pause it was not scripted to answer; returns
  the final `STATE.json`, `HISTORY.md` text, the list of actions taken, and
  the pause if any.
- `state(self) -> dict`, `history(self) -> str`, `findings(self, attempt) ->
  dict`, `ledger(self) -> dict` — readers for assertions.
- `main_tree(self, path) -> str | None` — file content at remote `main`.
