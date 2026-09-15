# 08 — Doctor, agent invocation, the prompt hook

`doctor.py` is the offline health check that renders every prompt and names what is wrong. `invoke.py` runs an agent outside the chat session (helpers via `spawn`, probes in tests) behind a small protocol with a stub implementation. `hooks/owner_log.py` is the standalone prompt hook.

## 8.1 `src/shackles/doctor.py`

**Owns:** the list of checks, their severities, the report, and regeneration of generated files. **Depends on:** `config`, `specfiles`, `prose`, `steps`, `prompts` (`render_offline`), `plumbing`, `agentdefs`, `localcfg`, `ownerlog`, `gitops` (remote probe; skipped with `--offline`), `charges` (token counts). **Depended on by:** `commands/doctor`, `commands/start` (preflight), `commands/accept_spec`, `tests/test_doctor.py`.

- `@dataclass class Report`: `errors: list[Finding]`, `warnings: list[Finding]`, `notes: list[Finding]`, `rendered: dict[str, int]` (attempt kind key like `PLAN-TO-SPEC:producer` → prompt tokens), `defaulted_keys`, `unused_keys`, `unresolved_tokens: list[str]`, `unknown_steps: list[str]`, `unused_prose: list[str]`; `Finding(check: str, message: str, detail: dict)`; `ok -> bool` (no errors); `to_json()`.
- `run_all(session, *, offline: bool, write: bool) -> Report` — runs every check below in order, collecting instead of raising; when `write` is true, regenerates agent definitions and `local.yaml` after the checks (never when errors exist).
- Checks (name → severity → what it does):
  - `spec-files` → error — `spec.yaml` parses; every listed file/glob resolves; each file is readable.
  - `config` → error — `Config.load` succeeds; unused keys → error each; type errors → error each; defaulted keys → **note** each ("defaulted: testPaths = ['tests/']").
  - `roster` → error — `AgentRoster.load`; price dates older than 90 days → warning (JC-60).
  - `step-table` → error — `steps.lint(cfg.values["steps"])` problems; fills `unknown_steps`.
  - `prose-files` → error — every step's `overview_prose` that must run exists; a gated step whose gate is on has its `gate_prose` (else error); gate prose absent while the gate is off → note; prose files referenced by no step and included by no other prose → warning (`unused_prose`); COMMON-STEP-END missing → warning.
  - `render` → error — for every step × kind (driver, producer, gate where applicable, conflict for LANDING, checkpoint, pause, cleanup) `prompts.render_offline` with the synthetic round; unresolved tokens → error listing token and file; cycles → error; token counts recorded in `rendered`; a prompt above `promptSizeWarnTokens` → warning.
  - `agents-md` → error — `AGENTS.md` has at least one `## ` heading; every `agents.*` token used by prose resolves.
  - `plumbing-templates` → error — every template exists and its placeholders are all supplied by the views.
  - `agent-defs` → warning (error under `--check`) — `agentdefs.check` problems.
  - `hook` → error — `.claude/settings.json` registers the hook command; `src/hooks/owner_log.py` exists.
  - `owner-log` → warning — `OWNER.log` missing/empty (start will refuse; doctor only warns so a fresh clone can be checked).
  - `baseline` → error — `spec.baseline.json` loads; drift → **error** with the changed-file list (the diff is left to `spec-drift`).
  - `git` → error unless `--offline` (then note) — inside a repository; a remote exists; `fetch` works; main branch detected.
  - `python-and-deps` → error — Python ≥ 3.11, PyYAML importable, pytest importable.
  - `archives` → warning — `archivesPath` exists; `.gitkeep` orphaned if the path moved.
  - `worktrees` → note — leftover `.worktrees/round-*` for rounds already `done`/`abandoned`.
- `regenerate(session) -> list[str]` — `agentdefs.write_all` + `localcfg.generate/save`; returns written paths.
- `synthetic_round() -> dict[str, str]` — lives in `prompts`; doctor calls it.

## 8.2 `src/shackles/invoke.py`

**Owns:** running one agent on one prompt outside the chat session, the slot cap for simultaneous helpers, and the stub used by tests. **Depends on:** `config` (roster), `localcfg` (claude command), `messages`, `paths`, `errors`. **Depended on by:** `commands/spawn`, `tests/probes/*`, `tests/support/stub_driver.py` (uses `StubInvoker`).

- `class Invoker(Protocol)`: `run(self, *, rung: Rung, prompt: str, cwd: Path, read_only: bool, timeout_s: int) -> InvokeResult`.
- `@dataclass class InvokeResult`: `text: str` (the agent's final message text), `usage: dict | None` (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `total_cost_usd` when the tool reports it), `duration_s: float`, `exit_code: int`, `stderr_tail: str`.
- `class CliInvoker(Invoker)`: `__init__(self, command: str, agent_name: Callable[[str, bool], str], runner: Callable = subprocess.run)`; runs the Claude Code CLI headless with the generated agent definition of the rung (`--agent <name>`), JSON output, no interactive permissions prompts, `cwd` set to the worktree harness root; parses usage from the JSON envelope when present; non-zero exit → `SpawnError` with the stderr tail. The exact flag set lives in one constant `CLI_ARGS` so it can be corrected in one place (JC-61).
- `class StubInvoker(Invoker)`: `__init__(self, script: Callable[[InvokeRequest], InvokeResult])` — returns whatever the test's script says; records every request in `self.calls`.
- Slots: `acquire_slot(rs: RoundState, cap: int, runtime_dir: Path) -> Slot` — a directory of lock files under `<worktrees dir>/round-NNNN.slots/`; more than `cap` live locks → `SpawnError("helper cap reached")`; `Slot.release()`; stale locks (dead pid) are reaped (JC-62).
- `invoke_for_spawn(session, rs, *, rung: str, prompt_file: Path, read_only: bool) -> InvokeResult` — glue used by the `spawn` command: checks the rung exists and is within `maxAgent`, acquires a slot, runs the invoker from `invoker_from_env(...)`, releases.
- `invoker_from_env(session) -> Invoker` — `CliInvoker` by default; when the environment variable `SHACKLES_INVOKER=stub` is set, a `StubInvoker` whose script is read from the JSON file named by `SHACKLES_STUB_SCRIPT` (a list of `InvokeResult`-shaped objects consumed in order, the last one repeating). This is the only test seam in the module and is what `test_cmd_spawn.py` and the stub-driven round tests use.

## 8.3 `src/hooks/owner_log.py` — the prompt hook

**Owns:** appending one JSON line per owner prompt to `OWNER.log` ([00] §0.10). **Depends on:** the standard library only; it must not import `shackles` (a broken package must not silence the log). **Depended on by:** `ownerlog.py` (reads what it writes), `doctor` (checks it exists), `.claude/settings.json`.

- `main() -> int` — read all of stdin, parse JSON (on failure: log a line with `prompt: ""` and `error: "unparsable hook payload"` rather than exit non-zero, JC-63); take `prompt` (fallback keys `user_prompt`, `input`), `session_id`, `cwd`; append `{"ts", "session", "cwd", "prompt"}` to `<harness>/OWNER.log` where `<harness>` = the grandparent directory of this file (`src/hooks/` → `src/` → harness); always exit 0 so the hook never blocks the owner.
- `harness_root() -> Path`, `append_line(path: Path, record: dict) -> None` (open in append mode, one `json.dumps` per line, `ensure_ascii=False`, flush).
- The hook writes nothing else and prints nothing (a printed line would be injected into the conversation by some hook types).
