# 14 — Owner log, judgment calls, agent definitions: `ownerlog.py`, `hooks/`, `judgment_calls.py`, `agentdefs.py`

## `src/ownerlog.py` — `OWNER.log`

**Owns:** the format of the owner log, appending from the prompt hook, reading,
verifying a quote, and copying the round's slice into the round folder. **Depends
on:** `errors`, `json`. **Depended on by:** `hooks/owner_log_hook.py`, `rounds`
(`start`, `abandon`), `recording`, `pauses` (`resume`), `doctor`, `commands`
(`owner-log`).

Format: JSON Lines, one object per owner prompt: `{"ts": "<UTC ISO>", "session":
"<session id or empty>", "cwd": "<cwd or empty>", "text": "<prompt verbatim>"}`. The
file lives at `<harness root>/<ownerLogPath>` (default `OWNER.log`), is gitignored,
and is per machine.

- `Entry` (frozen dataclass): `ts`, `session`, `cwd`, `text`.
- `append(path: Path, text: str, session: str, cwd: str, now: str) -> None` —
  appends one line; creates the file; never raises on a missing directory (creates it).
- `append_from_hook(stdin_json: str, path: Path, now: str) -> None` — parses the
  Claude Code `UserPromptSubmit` payload (`prompt`, `session_id`, `cwd`; unknown extra
  keys ignored; a payload without `prompt` is ignored); calls `append`.
- `read(path: Path) -> list[Entry]` — tolerant: malformed lines are skipped and
  counted in `read.skipped` (attribute on the returned list's wrapper
  `Log(entries, skipped)`); an absent file yields an empty log.
- `exists_and_nonempty(path: Path) -> bool`.
- `normalise(text: str) -> str` — whitespace runs → one space, trimmed.
- `verify(quote: str, sources: list[Path]) -> Entry | None` — the first entry, over
  all sources (the local log and the round's committed slice), whose normalised text
  contains the normalised quote; an empty quote never verifies [JC-13].
- `slice_since(path: Path, since_ts: str) -> list[Entry]`; `write_slice(entries:
  list[Entry], dest: Path) -> None` — the round's `OWNER.log` (same JSONL format),
  rewritten in full each time so it stays a faithful slice.
- `hook_command(python: str = "python") -> str` — the settings.json command string:
  `<python> "$CLAUDE_PROJECT_DIR/src/hooks/owner_log_hook.py"` [JC-40].

## `src/hooks/owner_log_hook.py` — the prompt hook

**Owns:** the executable that Claude Code runs on every owner prompt. **Depends on:**
`ownerlog` (imported by adjusting `sys.path` to `src/`). **Depended on by:** nothing
in code; `.claude/settings.json` names it.

- `main() -> int` — reads all of stdin, resolves the harness root as the parent of
  the `src/` directory containing this file, calls `ownerlog.append_from_hook` with
  the configured `ownerLogPath` (read directly from `project.yaml` with a fallback to
  `OWNER.log` if the config cannot be parsed, so a broken config never loses owner
  words); always exits 0; errors go to stderr only. Prints nothing to stdout (Claude
  Code would add stdout to the context).

## `src/judgment_calls.py` — the `jc` tool and ingestion

**Owns:** the line format of the two trails, appending from the CLI (producers) and
from final messages (gates and producers), and reading them for owner messages.
**Depends on:** `paths`, `errors`. **Depended on by:** `commands` (`jc`), `recording`
(ingest), `pauses` (reading since a timestamp).

Line format: `<UTC ISO> <STEP> attempt <n>: <line>` — one line per call; the line
text is the agent's, newlines replaced by spaces.

- `Kind` (Enum): `DEFINED`, `UNDEFINED`.
- `trail_path(rp: RoundPaths, kind: Kind) -> Path`.
- `append_line(rp: RoundPaths, kind: Kind, step: str, attempt: int, text: str,
  now: str) -> None` — raises `UsageError` for an empty text or an unknown step name
  (validated against `steps.names()` — the only reason this module sees `steps`).
- `ingest(rp: RoundPaths, step: str, attempt: int, calls: list[JudgmentCallLine],
  now: str) -> int` — appends every call from a final message; returns the count.
- `read_since(rp: RoundPaths, since: str | None) -> tuple[list[str], list[str]]` —
  (defined, undefined) lines with timestamp ≥ `since` (all when `None`).
- `cli_command(step: str, attempt: int, wt_harness: Path) -> str` — the exact command
  shown in plumbing: `python <wt_harness>/src/run.py jc --kind defined|undefined
  --step <STEP> --attempt <n> "<one line>"`.

## `src/agentdefs.py` — generated agent definitions and hook settings

**Owns:** the content of `.claude/agents/<rung>.md`, `.claude/agents/<rung>-gate.md`,
`.claude/settings.json`, and the staleness check that compares them with
`subAgents.yaml`. **Depends on:** `config`, `localstate`, `specfiles` (hashing),
`ownerlog` (hook command), `errors`. **Depended on by:** `install`, `doctor`,
`rounds` (preconditions), `next_action` (refuses to spawn when stale).

Agent definition (one per rung), frontmatter then a fixed body:

```
---
name: <rung>
description: shackles harness agent, rung <rung> (<display name>). Spawned by the driver with a prompt file given verbatim.
model: <model>
effort: <effort>
---
Follow the prompt you were given verbatim. It names your step, your inputs, where you
may write, and the JSON your final message must be. The runner parses that JSON.
```

The `-gate` twin adds `tools: Read, Grep, Glob` (read-only) and `description: … gate
(read-only)`. The `effort` field is what the owner's SPEC.md means by "the Agent tool
takes effort only from one loaded at session start" [JC-41].

- `agent_markdown(spec: AgentSpec, gate: bool) -> str`.
- `settings_json(python: str) -> dict` — `{"hooks": {"UserPromptSubmit": [{"hooks":
  [{"type": "command", "command": <ownerlog.hook_command(python)>}]}]}}`; when a
  `settings.json` already exists, `install` merges: other keys are kept, the harness
  hook entry is replaced or added (identified by the script name).
- `generate(agents: AgentsConfig, claude_dir: Path, python: str) -> list[Path]` —
  writes every definition and the settings file; returns the written paths.
- `expected_hashes(agents_path: Path, claude_dir: Path, hook_path: Path) -> dict[str,
  str]` — `subAgentsHash`, `agentDefsHash` (hash of the concatenated definitions),
  `settingsHash`, `hookHash`.
- `staleness(agents_path, claude_dir, hook_path, local: LocalState) -> list[str]` —
  human messages for every mismatch between current hashes and `local.generated`
  (e.g. `subAgents.yaml changed since install; run install and restart the session`);
  empty when fresh.
- `hook_installed(claude_dir: Path) -> bool` — the settings file contains a
  `UserPromptSubmit` command naming `owner_log_hook.py`.
- `definition_names(agents: AgentsConfig) -> list[str]` — `<rung>` and `<rung>-gate`
  for every rung; `next_action` uses them for `Action.agent_definition`.
