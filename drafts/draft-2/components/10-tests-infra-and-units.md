# 10 — Tests, part 1: infrastructure and unit tests for files 01–04

Parent: [`../SPEC.md`](../SPEC.md). Part 2 is [`11-tests-integration-and-probes.md`](11-tests-integration-and-probes.md).
Everything under `harness/tests/`. Pytest, no plugins. Three rules the suite lives by:

1. **Mechanics tests never read the owner's files.** Every fixture repo is built by
   `specgen.py` from the step table and the config registry, one line per prose file. A
   rewrite of the owner's prose therefore fails exactly one test: `test_spec_drift.py`.
2. **Every path through the runner is driven by the stub agent**, never by a real one.
   Real agents appear only in `probes/`, opt-in, marked `live`.
3. **Git is real.** Fixtures create a real repository with a real bare remote in `tmp_path`;
   nothing mocks `git`.

## Shared infrastructure

### tests/conftest.py

Fixtures (function scope unless stated):
- `spec_root(tmp_path)` — a directory with the generated one-line spec set (`specgen.generate`).
- `repo(tmp_path, spec_root)` — a git repo at `tmp_path/repo` containing `spec.yaml`, `SPEC.md`,
  `harness/` with the generated owner files, a *copy* of `src/` (so the code under test is the
  checked-out code), empty `docs/`, `tests/` with one passing test, `archives/rounds/.gitkeep`,
  `.claude/settings.json` with the hook commands, generated agent definitions, an accepted
  spec baseline; committed on `main`; pushed to a bare remote at `tmp_path/remote.git` named
  `origin`. Returns a `Repo` record: `root`, `harness`, `remote`, `roots: Roots`, `cfg: Config`.
- `owner_log(repo)` — helper `say(text) -> Entry` that appends to `harness/OWNER.log` the way the hook does.
- `cli(repo)` — helper `run(*args, expect=0) -> dict | str` invoking `run.main` in-process with
  `--harness repo.harness --now <fixed clock>`; the clock is a fixture `clock` that tests advance.
- `stub(repo)` — the stub agent bound to the repo (see `stub_agent.py`).
- `driver(repo, stub, cli, owner_log)` — the drive loop (see `driveloop.py`).
- `started(repo, owner_log, cli)` — a repo with `say("please do X")` and `start` already run.

### tests/specgen.py — the generated one-line spec

```python
def generate(dest: Path, *, steps_flags: dict[str, int] | None = None,
             config_overrides: dict | None = None, prose_overrides: dict[str, str] | None = None,
             agents: dict | None = None) -> None
```
Writes: `spec.yaml` (lists the same five entries as the owner's), `SPEC.md` (one line),
`harness/AGENTS.md` (a heading `## DEFINED AND UNDEFINED JUDGMENT CALLS` with one line),
`harness/project.yaml` (every `config.REQUIRED` key with small round numbers, `steps:` from
`steps.TABLE` with the given flags, default flags all 1 so gates are exercised),
`harness/subAgents.yaml` (two rungs `max` and `low`, tiny prices), and for every prose
name in `steps.prose_names()` plus the four COMMON files and COMMON-STEP-END, a single
line such as `PLAN-TO-SPEC-OVERVIEW {{ prose.COMMON-PROJECT }} {{ prose.COMMON-ROUND }} {{ plumbing.GATE-PROSE }} {{ plumbing.PROCESS-INSTRUCTIONS }}`
with the same token set the real file uses (token sets are a table in this module, the
one place that must be updated if the owner introduces a new token — the drift test
points there).

### tests/stub_agent.py — the scripted agent (JC-37)

```python
BEHAVIOURS: dict[str, str]     # name -> one-line description, rendered into docs/TESTING.md

class StubAgent:
    def __init__(self, repo: Repo): ...
    def script(self, attempt_pattern: str, behaviour: str, **kw) -> None   # e.g. ("PLAN-TO-SPEC-GATE-1", "gate_fail", findings=2)
    def act(self, nxt: dict) -> None       # performs the scripted behaviour for the spawn/self described by `next`'s JSON:
                                           # edits the worktree, writes the result file; default behaviour is "done"
    def usage_for(self, attempt: str) -> dict | None
```
Behaviours (each is a small function): `done` (writes a valid artifact for the step and a
DONE result), `needs_owner` (one question), `blocked`, `stray_edit` (touches a file outside
declared paths), `edit_spec_file`, `edit_runner_file` (STATE.json), `truncate_jc_file`,
`missing_artifact`, `invalid_json`, `prose_wrapped_json`, `edits_frozen_tests`,
`breaks_tests` (implementation that fails the suite), `slow` (sleeps past the timeout),
`writes_judgment_calls` (uses the CLI tool), `helpers_over_limit` (declares more helpers),
`gate_pass`, `gate_pass_with_findings`, `gate_fail` (n blocking), `gate_fail_no_blocking`,
`gate_repeat_withdrawn`, `gate_missing_ruling`, `dispute` / `resolve` (producer responses),
`dispute_settled`, `suite_split` (SUITE.json with some archive decisions), `suite_incomplete`,
`postmortem` (Summary first, edits carry-forward files), `postmortem_no_summary`,
`conflict_resolve` / `conflict_leave_markers` / `conflict_stray`, `plan_ok` / `plan_unanswered`,
`agents_plan_ok` / `agents_plan_over_pool` / `agents_plan_bad_rung`, `cleanup_noop`, `flags`.

### tests/driveloop.py — the fake driver

```python
def drive(repo: Repo, cli, stub: StubAgent, owner_log, *, on_chat: Callable[[dict], list[tuple]] | None = None,
          max_steps: int = 200) -> list[dict]
    # Loops next -> stub.act -> record until `done` or a chat the on_chat callback does not answer;
    # on_chat returns owner decisions as (kind, quote, params) tuples which are said into the log
    # and handed to `owner`; returns every `next` JSON seen, for assertions.
def approve_all(nxt: dict) -> list[tuple]        # answers checkpoints/approval with "approved", questions with "1. a"
def delegate_all(nxt: dict) -> list[tuple]
```

### tests/gitfix.py — git helpers for tests
`commit_on_main(repo, path, content)`, `remote_sha(repo, branch)`, `branches(repo)`,
`tree_files(repo, rev, prefix)`, `move_main(repo)` (a foreign commit on the remote main).

---

## Unit test files, one per module (files 01–04)

Each file tests one module through its public functions. Listed as *case → assertion*.

**test_paths.py** — `discover` finds harness and repo roots from a nested start · finds
`spec.yaml` in a parent · errors without `project.yaml` · errors outside git · `to_repo`/
`to_harness` round-trip and `None` outside · `under` with equal, nested, sibling paths.

**test_config.py** — loads the generated files · every REQUIRED key missing one at a time →
ConfigError naming it · wrong type → error naming key and expected type · `defaulted` lists
`testPaths`, `mainBranch`, `remote`, `promptWarnTokens` when absent and none when present ·
`unknown` lists an extra key · `gatesFraction+workFraction != 1` → error · `allowUpstream: 1`
→ error · `maxAgent` not a rung → error · steps flags accept 0/1/true/false and reject 2 ·
`Roster.rank` order is file order · `at_or_below` excludes rungs above the ceiling ·
`project_view` renders lists as JSON strings and numbers as plain text · `steps` keeps
file order.

**test_steps.py** — TABLE names are unique and match `project.yaml` order from specgen ·
`lint` reports a missing step, an extra step, a reordered pair, a flag on a no-gate step
(note) · `by_name` unknown → StepsError · `gated(cfg)` respects flags · `checkpoints_on` ·
`prose_names` contains every OVERVIEW/GATE name used by TABLE · every producer's `declared`
includes `round_folder` · CHAT-TO-PLAN and LANDING are not overridable.

**test_localyaml.py** — `build` has no key whose value came from the owner's free text
(vision absent) · `write` is atomic (temp file gone) · `current_round` null without a
state · `steps_effective` marks overrides from a state.

**test_speclock.py** — `list_files` expands the glob in sorted order · missing non-glob entry
→ error · spec.yaml not listing itself → error · `compare` clean after `accept` · editing a
prose file → `changed` with a unified diff mentioning the file and the changed line ·
adding a prose file → `added` · deleting → `removed` · `status` is `missing` before any
accept · `accept` replaces the baseline atomically and removes stale mirrored files.

**test_spec_drift.py** — *the guard* (JC-38), run against the real repository (not a fixture): the
real spec files equal `harness/spec-baseline/`; on failure the assertion message is
`Drift.diff_text` plus "run: python3 src/run.py accept-spec --quote ..."; a missing baseline
fails with the same instruction. Skipped only when the test is not running inside a
checkout that has `spec.yaml` (never in CI).

**test_prose.py** — `available` lists names without `.txt` · `read` unknown → ProseError ·
`tokens_in` finds `{{ a.B }}`, `{{a.B}}`, ignores `{ a.B }` and `{{ a }}` · `inventory`
covers every file · `classify_names` sorts OVERVIEW/GATE/COMMON/unknown.

**test_agentsmd.py** — heading normalisation of the judgment-calls heading · section
text spans to the next heading of same or higher level · nested headings stay inside ·
unknown key → AgentsMdError · `keys` order is document order.

**test_render.py** — resolves each namespace · unresolved tokens are collected, not raised
· `strict` raises naming all of them with positions · prose recursion two levels deep ·
a cycle A→B→A → RenderError listing the chain · `round.plan` containing `{{ project.vision }}`
is not expanded · `gates_line` marks off gates "(off)" and lists in step order and says
"none" for a table with no gates (monkeypatched TABLE) · `est_tokens` equals
`tokens.estimate` · `project.remaining` and `round.remaining` render with two decimals.

**test_plumbing.py** — producer instructions contain: worktree path, every declared prefix,
every spec file, each input and artifact, the judgment command with `--worktree`, the
budget line or "no specific budget", the helper limit, the verify command and timeout when
the step verifies, every open finding id with `needs response` for blocking ones, every
owner answer verbatim, the JSON example from `results`, the STEP-END text last · gate
instructions say read-only and list disputed ids first · `gate_prose` prefixes the "off
this round" line when off or overridden and never contains an unresolved token · driver
instructions list every `control.KINDS` entry with its CLI form · no line of any
instruction contains the words "sensible" or "judgment" outside the STEP-END quote (a
crude check that the module stays mechanical).

**test_agentdefs.py** — `expected` yields two files per rung with `model`, `effort`, `tools`
· readonly twin has no Edit/Write/Bash · `write` removes a stale `shackles-old.md` · `stale`
empty after write, lists a file after editing subAgents.yaml prices? — no: prices do not
appear in definitions, so a price edit is *not* stale; a model edit is.

**test_doctor.py** — clean fixture → no errors, notes for defaulted keys · unresolved token
in a prose file → error naming file and token · unknown prose file → warning · gate on
without prose → error · stale agent defs → error · drift → error with file list · missing
OWNER.log → warning · missing hook → error · rung above ceiling as `gateAgent` → error ·
`--offline` skips the remote check · `index_text` lists every src/docs/tests file once,
sorted, with the docstring first line · `to_json` round-trips.

**test_ownerlog.py** — `append_from_hook` with a Claude-shaped payload stores `prompt` and
`session_id` · unknown payload stores the whole text · `read` tolerates a malformed line ·
`starting_line` is the last line · `refresh_round_slice` copies only new lines and keeps
root line numbers · `verify_quote` exact substring hit, trailing-whitespace tolerant,
case-sensitive miss, returns the most recent hit.

**test_control.py** — `make` with a quote not in the log → ControlError · every kind's
validation: unknown step, CHAT-TO-PLAN/LANDING override refused, question 0 refused,
negative multiple refused · `approval_mode` latest wins · `effective_overrides` unions ·
`hard_stop_multiple` default vs override.

**test_state.py** — `new` → `save` → `load` round-trip equals · schema mismatch → StateError
· `next_pending` in table order · `pause`/`resume` set and clear; restarts counted only for
blocked/limit/hard-stop · `save` atomic · `find_round_folders`.

**test_history.py** — `append` format matches the template exactly · `event` line ·
append-only across calls.

**test_attempts.py** — names for producer, gate, landing · `gate_name_for`/`producer_of`
inverse · `files_for` paths use `roundPaths` names from config, not literals.

**test_limits.py** — each bound one below, at, and above; `hard_stop_attempt` None without
budget; `check_before_next` order.

**test_gitops.py** — against a fixture repo: `push_cas` with `expected=None` succeeds once
and raises `PushRejected` the second time · lease mismatch raises · `status` parses renames
and untracked · `diff_names` rename detection · `merge` clean and conflicted returns paths
and leaves markers · `conflicted_paths` · `show_file` None when absent · `worktree_add`/
`_list`/`_remove`.

**test_worktree.py** — `declared_prefixes` per PathClass with `testPaths` default and
override · `triage` keeps declared, strays the rest, strays a spec file even under a
declared prefix, refuses a truncated judgment file, refuses STATE.json edits · `revert`
restores tracked and removes untracked · `create`/`remove` lifecycle.

**test_landing.py** — clean merge → `finish` pushes main, `main_before` recorded · foreign
commit on main during landing → retried, then succeeds · conflict → `MergeOutcome.conflicted`
lists the files and `reference_commit` exists · `judge_resolution`: markers left → problem;
stray outside conflicted set → reverted; suite failure → problem; clean → empty ·
projected living charge over the multiple → returns a hard-stop pause without touching main.

**test_sync.py** — post-landing commits reach main · main moved by a foreign commit to an
unrelated file → merged in one extra cycle · conflict on docs/TODO.md → SyncError("conflict")
· `only_prefixes` keeps only the round folder · `update_control_checkout` fast-forwards a
clean main checkout, declines a dirty one with a note.
