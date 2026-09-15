# 06 — Rendering and prompt assembly: `templates.py`, `context.py`, `prompts.py`

## `src/templates.py` — the `{{ ns.KEY }}` engine

**Owns:** token syntax, recursive expansion, cycle and depth guards, unresolved-token
reporting. Knows nothing about what the namespaces mean. **Depends on:** `errors`.
**Depended on by:** `prose` (listing tokens), `context`, `prompts`, `doctor`,
`steps` (lint).

Syntax: `{{` optional spaces, namespace (`[a-z]+`), a dot, key (`[A-Za-z0-9_.-]+`),
optional spaces, `}}`. Anything else that looks like `{{ ... }}` is left untouched and
reported as malformed by `find_malformed`.

- `Token` (frozen dataclass): `ns: str`, `key: str`, `raw: str`, `start: int`, `end: int`.
- `find_tokens(text: str) -> list[Token]` — in order of appearance.
- `find_malformed(text: str) -> list[str]` — `{{ ... }}` spans that are not tokens.
- `Resolver` (Protocol): `resolve(ns: str, key: str) -> str | None` — `None` means
  unknown.
- `render(text: str, resolver: Resolver, max_depth: int = 8) -> str` — replaces every
  token by its resolved value, itself rendered (so prose fragments may contain tokens);
  keeps a stack of `(ns, key)` to raise `RenderError("RENDER_CYCLE")` with the chain;
  raises `RenderError("RENDER_DEPTH")` past `max_depth`; collects **all** unknown tokens
  before raising `RenderError("RENDER_UNRESOLVED")` with `details["tokens"]`.
- `render_lenient(text: str, resolver: Resolver, max_depth: int = 8) -> tuple[str,
  list[Token]]` — same, but unknown tokens are left in place and returned; used by
  `doctor` so one bad token does not hide the others.
- `remaining_tokens(text: str) -> list[Token]` — tokens still present after rendering.
- `mask_namespace(text: str, ns: str, replacement: str) -> str` — replaces every token
  of one namespace by a literal; used to embed gate prose in producer prompts.

## `src/context.py` — the namespaces

**Owns:** the values behind `project.*`, `round.*`, `agents.*`, `prose.*`, and the
per-attempt `plumbing.*` slot. **Depends on:** `config`, `prose`, `steps`, `ledger`
(for `project.remaining`, `round.spend`), `schemas` (plan text), `state`, `templates`,
`errors`. **Depended on by:** `prompts`, `doctor`, `pauses` (owner messages reuse
`round.*` values).

- `RoundValues` (dataclass): `id`, `folder` (relative posix), `base_commit`, `plan`
  (plain text), `budget: float`, `spend: float`, `remaining: float`.
- `sample_round(cfg: ProjectConfig) -> RoundValues` — `0000`, folder from config,
  `0000000`, `(sample plan)`, 100.0, 0.0, 100.0; used by `doctor` and tests.
- `round_values(cfg, state: RoundState, rp: RoundPaths) -> RoundValues` — reads the
  approved plan through `schemas.plan_as_text` (the plan's `text` followed by its
  numbered questions and the owner's answer quotes) [JC-21]; spend from
  `ledger.round_total(state)`.
- `gates_text(cfg: ProjectConfig) -> str` — the gate-capable steps in table order,
  each as `NAME: on|off` from `cfg.steps`, comma-space joined [JC-22].
- `project_value(cfg, agents, key: str, all_rounds_spend: float) -> str | None` —
  `remaining` → `budget − all_rounds_spend` formatted with two decimals; `gates` →
  `gates_text`; else `config.render_value(cfg.value_at(key))`; `None` for unknown keys.
- `class Context` (implements `templates.Resolver`): built by `build(cfg, agents,
  bundle, round_vals: RoundValues, all_rounds_spend: float)`. `resolve(ns, key)`:
  `project` → `project_value`; `round` → the field of `round_vals` (`budget`, `spend`,
  `remaining` formatted with two decimals); `agents` → `bundle.agents_sections[key]`;
  `prose` → `bundle.texts[key]` (raw; the engine renders it); `plumbing` →
  `self.plumbing.get(key)`; unknown namespace or key → `None`.
  `set_plumbing(values: dict[str, str]) -> None`; `with_plumbing(values) -> Context`
  (copy).
- `all_rounds_spend(harness_root, cfg) -> float` — sums `ledger.total` of every
  `STATE.json` under `archives/rounds/*/` in the given checkout (used for
  `project.remaining`); unreadable files are skipped with a warning list attached to
  the returned `SpendSummary(total, skipped)`.

## `src/prompts.py` — assembling a prompt file

**Owns:** the layout of every prompt, the mechanical PROCESS-INSTRUCTIONS text, the
GATE-PROSE preview, the size warning, writing `PROMPTS/` files, and the offline
render-everything used by `doctor`. **Depends on:** `templates`, `context`, `prose`,
`steps`, `config`, `schemas` (result-format text), `tokens`, `paths`, `errors`.
**Depended on by:** `next_action`, `landing`, `doctor`.

### Layout of every agent prompt

```
SHACKLES HARNESS · ROUND <id> · STEP <name> · ATTEMPT <n> · ROLE <producer|gate|chat|landing>
---- AGENTS.md ----
<AGENTS.md verbatim>
---- STEP ----
<the step's overview prose (producers, chat, landing) or gate prose (gates), rendered>
<if that prose contained no {{ plumbing.PROCESS-INSTRUCTIONS }}: the plumbing block>
---- STEP END ----
<COMMON-STEP-END rendered>
```

AGENTS.md appears verbatim because the owner defines a DEFINED judgment call as one
made from "its instructions, AGENTS.md, and the locked prose rendered into it". The
step-end reminder is the tail of the same prompt rather than a second message [JC-23].

### Types

- `Role` (Enum): `CHAT`, `PRODUCER`, `GATE`, `LANDING`.
- `AttemptSpec` (dataclass): `step: Step`, `attempt: int`, `role: Role`, `rung: str`,
  `budget_usd: float`, `worktree_harness: Path`, `branch: str`, `artifact_paths:
  list[str]` (relative), `declared_paths: list[str]`, `inputs: list[str]` (relative
  paths of the artifacts and files this attempt should read), `prior_findings:
  list[FindingView]` (id, severity, status, quote, text, suggestion, resolutions),
  `resolutions_required: list[str]`, `owner_decisions: list[str]` (verbatim quotes),
  `round_tests: list[str]` (`file::function`, TESTS-TO-SUITE only), `conflicted:
  list[str]`, `diff_text: str | None`, `diff_path: str | None`, `limits: Limits`
  (`max_turns_per_run`, `max_simultaneous_subagents`, `verify_timeout_seconds`),
  `result_path: str`, `jc_command: str`, `frozen_note: str | None`.
- `RenderedPrompt` (dataclass): `text: str`, `tokens: int`, `warnings: list[str]`.

### Functions

- `assemble(spec: AttemptSpec, ctx: Context, bundle: ProseBundle, cfg:
  ProjectConfig) -> RenderedPrompt` — builds the plumbing values, sets them on a copy
  of the context, renders the layout above, appends the plumbing block when the prose
  lacked the token (warning recorded), adds the size warning. Raises `RenderError`.
- `process_instructions(spec: AttemptSpec, cfg: ProjectConfig) -> str` — the
  mechanical block, in fixed sections with fixed headings: `WHERE YOU WORK` (absolute
  worktree harness path, branch, "do not commit, do not push, do not run `next` or
  `record`"); `WHAT YOU MAY CHANGE` (declared paths; the frozen-tests note when set;
  gates: "nothing: you are read-only"); `WHAT TO PRODUCE` (artifact paths; for
  code steps, "your changes in the declared paths"); `INPUTS` (paths); `PRIOR FINDINGS`
  (each verbatim with its status and any resolutions; "none" when empty; the list of
  ids that require a resolution); `OWNER DECISIONS` (quotes verbatim); `ROUND TESTS`
  (TESTS-TO-SUITE); `CONFLICTED FILES` (landing); `LIMITS` (budget, turns, sub-agents [JC-48],
  verify timeout); `JUDGMENT CALLS` (the exact `jc` command with step and attempt
  filled in; gates: "list them in your final message"); `FINAL MESSAGE` (the exact JSON
  shape from `schemas.describe(role)` and the rule that the runner parses it).
  Contains no judgment language.
- `gate_prose_preview(step: Step, bundle: ProseBundle, ctx: Context) -> str` — the
  rendered gate prose with `plumbing.*` tokens masked to
  `[gate process instructions omitted]` [JC-24]; `(no gate prose for <STEP>)` when the
  file is absent; used as the value of `plumbing.GATE-PROSE`.
- `landing_prompt_body(bundle: ProseBundle) -> str` — `LANDING-OVERVIEW` when present;
  otherwise a fixed header line plus `{{ prose.COMMON-PROJECT }}`,
  `{{ prose.COMMON-ROUND }}`, `{{ prose.COMMON-OVERVIEW }}` for those that exist, then
  `{{ plumbing.PROCESS-INSTRUCTIONS }}` [JC-25].
- `chat_prompt_note() -> str` [JC-69] — one fixed paragraph appended to the CHAT-TO-PLAN
  plumbing: the driver is the producer, where `PLAN.json` goes, the `record` command
  shape with `--decision`/`--quote`, and that every quote must be verbatim owner words.
- `size_warning(text: str, cfg: ProjectConfig) -> str | None` — when
  `tokens.text_tokens` exceeds `promptWarnTokens` [JC-26].
- `write_prompt(rp: RoundPaths, spec: AttemptSpec, rendered: RenderedPrompt) ->
  Path` — writes `PROMPTS/<STEP>-<n>.txt` (gate: `<STEP>-GATE-<n>.txt`); when
  `spec.diff_text` is longer than the warning threshold it is written to
  `PROMPTS/<STEP>-<n>.diff` and referenced by path instead of inlined [JC-27].
- `render_all(bundle, cfg, agents, ctx_sample: Context) -> dict[str,
  RenderedPrompt]` — for every step: its producer/chat prompt (attempt 1, sample
  values) and, when gate prose exists, its gate prompt; also the landing prompt.
  Uses `render_lenient`; the dict values carry unresolved tokens in `warnings`. Used by
  `doctor`.
