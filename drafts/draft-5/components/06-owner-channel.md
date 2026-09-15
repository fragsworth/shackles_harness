# 06 — Owner channel & agent definitions (`ownerlog.py`, `hooks.py`, `agentdefs.py`)

**Purpose.** Everything that connects the chat session to the runner without the runner
ever interpreting prose: the log of the owner's words, the hooks that write it, the
verification of verbatim quotes against it, and the agent definition files that make
the Agent tool spawn sub-agents at the right rung.

**Owns.** `OWNER.log` (format S9), the round slice, quote verification, the two hook
entry points, `.claude/agents/*.md` generation and staleness.

**Depends on.** 04 (`Paths`, `Roster`, `localyaml`). Nothing else.

**Depended on by.** 10 (`round_start` refuses without a log; `round_owner` verifies
quotes; CLEANUP writes the slice), 11 (doctor reports), 03 (`setup`, `hook`).

---

## `ownerlog.py`

`class Entry` (frozen): `i: int`, `ts: str`, `session: str`, `kind: "prompt"|"marker"`,
`text: str`.

- `append(log: Path, kind: str, text: str, session: str, now: datetime) -> Entry` —
  appends one JSON line (S9) with `i` = previous count + 1; creates the file; uses an
  exclusive lock (`fcntl.flock`) for the append; never rewrites earlier lines.
- `read_all(log: Path) -> list[Entry]` — tolerant: a corrupt line is skipped and counted
  in `Entry`-less `read_report(log) -> (entries, skipped: int)`.
- `exists_and_nonempty(log: Path) -> bool` — the `start` precondition ("without a log,
  start refuses"; a file with only marker lines counts as a log, JC-07).
- `normalize(text: str) -> str` — Unicode NFC, all whitespace runs → single space,
  strip. The only transformation ever applied to owner words.
- `verify_quote(log: Path, quote: str, after_index: int) -> Match | None` — `Match(i,
  ts, text)` for the first entry with `i > after_index` and `kind == "prompt"` whose
  normalized text contains the normalized quote; empty quote → `None`. Never raises on
  a missing log (returns `None`).
- `slice(log: Path, first_index: int, last_index: int | None) -> list[str]` — raw lines
  with `first_index <= i <= last_index` (to EOF when `None`), byte-preserved.
- `write_slice(lines: list[str], dest: Path) -> None` — the round's `OWNER.log`.
- `last_index(log: Path) -> int` — 0 when absent.

Errors: none raised in normal operation; `OwnerLogError` only when the file cannot be
opened for append.

## `hooks.py` — thin entry points (called by `run.py hook <name>`)

Both read Claude Code's hook JSON from stdin and print only what the hook contract
allows. Both must never fail the owner's prompt: every exception is caught and reported
as a single stderr line, exit 0.

- `hook_prompt(stdin_json: dict, paths: Paths, now: datetime) -> int` — takes `prompt`
  (str) and `session_id` (str, `"unknown"` when absent) and calls `ownerlog.append(...,
  kind="prompt")`. Prints nothing on success (so nothing is injected into the chat).
- `hook_session_start(stdin_json: dict, paths: Paths, now: datetime) -> int` — (1)
  appends a `marker` entry `session-start <session_id>` (creating the log); (2)
  regenerates `local.yaml` via `localyaml.derive_local`/`write_local`; (3) if
  `agentdefs.is_stale(...)`, prints one line to stdout for the driver: `shackles: agent
  definitions are stale; run 'python3 src/run.py setup' and restart this session`
  (JC-10); (4) if a round is paused (a `STATE.json` with `status == "paused"` in the
  newest worktree), prints `shackles: round NNNN is paused (<kind>); run 'python3
  src/run.py next'`. Exit 0 always.

## `agentdefs.py`

- `definition_text(rung: Rung, role: "work"|"gate", roster_sha: str) -> str` — S13.
  The `gate` role gets the read-only `tools:` list (JC-44); `work` gets no `tools:` line
  (inherits all). `effort` is written exactly as in the roster (the Agent tool reads it
  only from a definition loaded at session start; this is why they are files, not
  flags).
- `expected_files(roster: Roster) -> dict[str, str]` — filename → text for every rung
  and both roles.
- `write_all(agents_dir: Path, roster: Roster) -> list[Path]` — writes the expected
  files and deletes any `shackles-*.md` not expected (other agent files are left alone).
- `current_hash(agents_dir: Path) -> str` — sha256 over the sorted `shackles-*.md`
  contents; `""` when none.
- `is_stale(agents_dir: Path, roster: Roster) -> list[str]` — names of files missing,
  differing from `expected_files`, or extra `shackles-*.md`; empty means current.
- `definition_name(rung_key: str, role: str) -> str` — `shackles-<rung>-<role>`, the
  value the engine puts in `next` output (`agent_definition`) and in the process
  instructions.

## Invariants
- Owner words are stored verbatim; the only derived form is `normalize`, used
  symmetrically on both sides of a comparison and never persisted.
- No function here interprets a quote: `verify_quote` answers "does this text appear
  after that point", nothing more.
- A quote that appears only *before* `after_index` does not verify; the engine sets
  `after_index` to the log index at which the current pause began, so an old "approve"
  cannot approve a new plan.
- Agent definitions are a pure function of the roster; regenerating twice is a no-op.

## Covered by
`tests/test_ownerlog.py`, `tests/test_hooks.py`, `tests/test_agents_defs.py`.
