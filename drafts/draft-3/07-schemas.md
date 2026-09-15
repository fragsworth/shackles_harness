# 07 — Artifact, result and findings formats: `schemas.py`

## `src/schemas.py`

**Owns:** the exact shape of every JSON the runner reads (artifacts written by
producers, final messages of producers and gates), their validation, the extraction of
a JSON object from a chat-style final message, the plain-text rendering of a plan, and
the text that tells agents the shape. Hand-written checks, no external schema library.
**Depends on:** `config`, `steps`, `errors`, `tokens`. **Depended on by:**
`recording`, `context`, `prompts`, `landing`, `ledger` (archive token counts),
`suite`, `stub_agent` (tests).

Rule: every validator raises `InvalidError` with `details["problems"]` (a list of
`path: message` strings) and returns a typed object plus `warnings`. Unknown top-level
keys are problems (agents get the exact shape in their prompt) [JC-65].

### Extraction

- `extract_json(text: str) -> dict` — if the text contains ```` ```json ```` fences,
  the last fenced block; else the last balanced top-level `{ ... }` (string-aware
  scan); raises `InvalidError("NO_JSON")` when none parses [JC-28].
- `load_json_file(path: Path) -> dict` — reads UTF-8, runs `extract_json`; raises
  `InvalidError("MISSING_FILE")` for an absent file.
- `write_json(path: Path, obj: dict) -> None` — the repository-wide JSON style.

### `PLAN.json` (CHAT-TO-PLAN)

```json
{
  "text": "plain-English plan: scope, validation steps, non-goals, assumptions, quote rationale",
  "quote": 120.0,
  "questions": [
    {"n": 1, "text": "Which storage?", "options": {"A": "sqlite", "B": "files"},
     "answer": "B", "quote": "1. B, files are fine"}
  ],
  "todos": ["accepted open TODO, verbatim from docs/TODO.md"],
  "non_goals": ["..."], "validation_steps": ["..."], "assumptions": ["..."]
}
```
- `Question` (dataclass): `n`, `text`, `options: dict[str, str]`, `answer: str | None`,
  `quote: str | None`. `Plan` (dataclass): `text`, `quote: float`, `questions`,
  `todos`, `non_goals`, `validation_steps`, `assumptions`.
- `validate_plan(d: dict) -> tuple[Plan, list[str]]` — `text` non-empty; `quote` a
  number > 0; `n` unique and 1-based in order; each question has `text` and at least
  two lettered `options`; `answer` and `quote` are strings when present (any text is an
  answer); the four lists are lists of strings (may be empty). Does not check the log
  (that is `recording`).
- `unanswered(plan: Plan) -> list[int]` — question numbers without both `answer` and
  `quote` [JC-62].
- `plan_as_text(plan: Plan) -> str` — `text`, a blank line, then `Decisions:` and one
  line per question `n. <text> — answer: <answer> (owner: "<quote>")`; used for
  `round.plan` [JC-21].

### `AGENTS-PLAN.json` (PLAN-AGENTS)

```json
{
  "steps": {"PLAN-TO-SPEC": {"rung": "max", "share": 0.10,
            "subagents": [{"rung": "low", "count": 1}], "rationale": "..."}},
  "gates": {"PLAN-TO-SPEC": {"rung": "max", "share": 0.05, "rationale": "..."}},
  "refactor_share": 0.1,
  "notes": "..."
}
```
- `StepAssignment` (dataclass): `rung`, `share: float`, `subagents: list[tuple[str,
  int]]`, `rationale`. `GateAssignment`: `rung`, `share`, `rationale`. `AgentsPlan`:
  `steps: dict[str, StepAssignment]`, `gates: dict[str, GateAssignment]`,
  `refactor_share: float | None`, `notes: str`.
- `validate_agents_plan(d: dict, cfg: ProjectConfig, agents: AgentsConfig,
  overrides: Overrides) -> tuple[AgentsPlan, list[str]]` — problems: a step key that is
  not an agent step; a missing entry for any agent step except LANDING; a missing
  entry for a gate that is on; an unknown rung, or one above `maxAgent`; a negative
  share; work shares (non-skipped steps) not summing to `workFraction` ± 0.001; on-gate
  shares summing above `gatesFraction` + 0.001; sub-agent counts per step above
  `maxSimultaneousSubAgentsPerRound`. Warnings: a share below the matching
  `defaultShares` entry; `refactor_share` above `maxRefactorOverhead`; entries for
  skipped steps or off gates (ignored) [JC-08].
- `rung_for(plan: AgentsPlan | None, step: str, gate: bool, cfg: ProjectConfig) ->
  str` — the plan's rung, else `gateAgent` for gates and `defaultAgent` otherwise.
- `budget_for(plan: AgentsPlan | None, step: str, gate: bool, cfg, quote: float) ->
  float` — `share × quote`; without a plan, `defaultShares` value × quote, else 0.

### `SPEC.json` (PLAN-TO-SPEC)

```json
{
  "components": [{"id": "C1", "title": "...", "description": "...", "files": ["src/x.py"]}],
  "steps": [{"id": "S1", "title": "...", "description": "...", "components": ["C1"]}],
  "test_plan": [{"id": "T1", "description": "...", "components": ["C1"], "kind": "unit"}],
  "non_goals": ["..."], "refactors": ["..."]
}
```
- `SpecDoc` (dataclass) mirrors the shape. `validate_spec(d) -> tuple[SpecDoc,
  list[str]]` — ids unique per list; references resolve; `components` and `test_plan`
  non-empty; `kind` ∈ `unit | integration | system`; `non_goals` present (may be
  empty, warning). `SPEC.md` is not validated beyond existing and being non-empty.

### `SUITE.json` (TESTS-TO-SUITE)

```json
{"decisions": [{"test": "tests/test_x.py::test_y", "where": "suite", "reason": "..."}],
 "flags": ["a middle ground worth raising"]}
```
- `SuiteDecision` (dataclass): `test`, `where` (`suite | archive`), `reason`.
  `SuiteDoc`: `decisions`, `flags`.
- `validate_suite(d: dict, expected: set[str]) -> tuple[SuiteDoc, list[str]]` —
  problems: a `where` outside the two values; a decision for a test not in `expected`;
  a test in `expected` without a decision (listed by name); duplicates.

### `POSTMORTEM.md`

- `postmortem_summary(markdown: str) -> str | None` — the body under the first
  heading whose text is exactly `Summary` (any `#` level, case-insensitive), up to the
  next heading of the same or higher level; `None` when absent [JC-29].

### Producer / chat / landing final message

```json
{"status": "DONE", "summary": "what was done, briefly",
 "questions": [{"n": 1, "text": "...", "options": {"A": "...", "B": "..."}}],
 "narrow": "what to cut to fit budget or turns",
 "resolutions": [{"finding": "F1", "resolution": "fixed", "note": "..."}],
 "flags": ["for the owner at the next pause"],
 "judgment_calls": [{"kind": "defined", "line": "one short line"}]}
```
- `Result` (dataclass): `status` (`DONE | NEEDS-OWNER | BLOCKED`), `summary`,
  `questions: list[Question]`, `narrow: str | None`, `resolutions: list[Resolution]`
  (`finding`, `resolution` ∈ `fixed | disputed`, `note`), `flags: list[str]`,
  `judgment_calls: list[JudgmentCallLine]` (`kind` ∈ `defined | undefined`, `line`).
- `validate_result(d: dict, required_resolutions: list[str], settled: list[str]) ->
  tuple[Result, list[str]]` — problems: unknown status; `NEEDS-OWNER` without at least
  one question with two options; `BLOCKED` without `narrow`; a required finding id
  without a resolution; a `disputed` resolution for a settled finding; a resolution
  naming an unknown finding; `disputed` without a `note`. Warnings: an empty summary.

### Gate final message

```json
{"verdict": "FAIL", "summary": "...",
 "rulings": [{"finding": "F1", "ruling": "withdrawn", "quote": "the artifact text that settles it"}],
 "findings": [{"severity": "blocking", "quote": "text judged", "text": "why", "suggestion": "what would prevent the FAIL"}],
 "judgment_calls": [{"kind": "undefined", "line": "..."}]}
```
- `RawFinding` (dataclass): `severity` (`blocking | non-blocking`), `quote`, `text`,
  `suggestion`. `Ruling`: `finding`, `ruling` (`upheld | withdrawn`), `quote`.
  `FindingsDoc`: `verdict` (`PASS | FAIL`), `summary`, `rulings`, `findings`,
  `judgment_calls`.
- `validate_findings(d: dict, disputed: list[str]) -> tuple[FindingsDoc, list[str]]`
  — problems: unknown verdict; a disputed finding without a ruling; a ruling on an
  id not in `disputed` (warning, ignored); a finding without `quote` or `text`; a
  blocking finding without a non-empty `suggestion` [JC-30]. The verdict/severity
  consistency is not checked here; `findings.apply_verdict` makes the verdict win.

### Shape text for prompts

- `describe(role: str) -> str` — the exact example JSON above for `producer`
  (also used for `chat` and `landing`) or `gate`, with one line per field saying
  required/optional and allowed values. This is the only place the shape is written
  for agents; `docs/SCHEMAS.md` is generated from it by `index`? No: `docs/SCHEMAS.md`
  is hand-written and `test_schemas.py` asserts it contains every field name
  `describe` mentions, so the two cannot drift silently.
