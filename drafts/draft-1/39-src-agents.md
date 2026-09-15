# 39 — src/shackles/agents/ (agent definitions and hooks)

Parent: `30-src.md`. Owns what the Claude Code session must have loaded
before a round: the generated agent definitions (one per rung and role) and
the hook block in `.claude/settings.json`, plus the handler the prompt hook
runs. Depends on: `config/` (roster, paths, local). Depended on by:
`commands/setup.py`, `commands/doctor.py`, `commands/hook.py`.

```
agents/
  definitions.py   .claude/agents/shackles-<rung>[-gate].md from subAgents.yaml
  hooks.py         the hook block; merge into settings.json; the owner-log handler
```

## definitions.py

Data: `AgentDef(file: str, name: str, description: str, model: str, effort:
str, tools: list[str] | None, body: str)`.

- `PRODUCER_TOOLS = None` (all tools) and `GATE_TOOLS = ["Read", "Grep",
  "Glob"]` — the read-only set for gates `[JC-28]`.
- `definitions_for(roster: Roster) -> list[AgentDef]` — two per rung:
  `shackles-<rung>` and `shackles-<rung>-gate`; `name` equals the file stem;
  `description` is one line naming the rung, model and effort and the role;
  `model` and `effort` copied from the rung; `body` is a fixed paragraph:
  follow the prompt you are given verbatim; your final message must be the
  JSON it names; gates: you may not write anything.
- `render(defn: AgentDef) -> str` — YAML frontmatter (`name`, `description`,
  `model`, `effort`, `tools` when not `None`) then the body.
- `write_all(paths: Paths, roster) -> list[Path]` — writes every definition
  into `<repo>/.claude/agents/`, removes stale `shackles-*.md` files for
  rungs no longer in the roster, returns the paths.
- `is_stale(paths, roster, local: Local | None) -> bool` — `local.rosterHash`
  differs from `roster.sha256`, or any expected file is missing or differs
  from its rendering.
- `agent_file_for(rung_key: str, role: producer|gate) -> str` — the `agent`
  value `next` returns.

## hooks.py

- `HOOK_BLOCK: dict` — the exact `hooks` object of `10-repository-root.md`
  (`UserPromptSubmit` -> `python harness/src/run.py hook owner-log`;
  `SessionStart` -> `python harness/src/run.py doctor --quiet`).
- `merge_into_settings(existing: dict | None) -> dict` — returns `existing`
  with the two hook entries present exactly once (matched by command string),
  every other key untouched.
- `write_settings(paths: Paths) -> str` — reads `.claude/settings.json` if
  present, merges, writes, returns the sha256 of `HOOK_BLOCK` for
  `local.hooksHash`.
- `is_installed(paths) -> bool`.
- `handle_owner_log(stdin_json: dict, log_path: Path, now: str) -> LogEntry | None`
  — the `UserPromptSubmit` handler: takes the hook's JSON (`prompt`,
  `session_id`), appends `{"ts", "session", "text"}` as one JSON line, returns
  the entry; an empty prompt appends nothing. Never raises to the caller
  (the hook must not block the chat): errors go to stderr and the return is
  `None`.
