# 33 — src/shackles/prompts/ (rendering owner prose into prompts)

Parent: `30-src.md`. Owns the token namespaces, recursive substitution, the
runner-generated plumbing text, and the extraction of AGENTS.md sections. It
never interprets prose: it includes files by name, substitutes values by key,
and names what it cannot resolve. Depends on: `config/`, `steps/`. Depended on
by: `engine/attempts.py` (real prompts), `commands/doctor.py` (offline
render), the mechanics tests (generated prose).

```
prompts/
  tokens.py      the five namespaces and how each key resolves
  render.py      `{{ ns.key }}` substitution, recursion, unresolved-token report
  plumbing.py    PROCESS-INSTRUCTIONS and GATE-PROSE text, built from the attempt
  agents_md.py   sections of AGENTS.md by heading slug
```

## Token namespaces (`tokens.py`)

Syntax: `{{ ns.key }}` with optional inner spaces; `ns` one of the five below;
`key` is `[A-Za-z0-9_-]+`. Anything else is left verbatim and reported.

| namespace | resolves to | source |
|---|---|---|
| `prose.<STEM>` | the file `<lockedProsePath>/<STEM>.txt`, itself rendered (recursion) | `config.paths` |
| `project.<key>` | `config.project.render_value(settings, key)`; plus two derived keys: `project.remaining` (budget minus every round's booked total, from `ledger/`), `project.gates` (the gated steps in order with `on`/`off` for this round, e.g. `PLAN-AGENTS-GATE off, PLAN-TO-SPEC-GATE off, ...`) `[JC-11]` | settings, ledger, round state |
| `round.<key>` | `id`, `folder` (relative to harness root), `base_commit`, `plan` (plain-English rendering of PLAN.json, `34-src-round.md` `artifacts.render_plan`), `budget` (the approved quote), `spend`, `remaining` | round state |
| `plumbing.<KEY>` | `PROCESS-INSTRUCTIONS`, `GATE-PROSE` (`plumbing.py`) | the attempt |
| `agents.<SLUG>` | the body of the `## ` heading of AGENTS.md whose slug is `<SLUG>` | `agents_md.py` |

Data: `Token(ns: str, key: str, raw: str, span: tuple[int, int])`;
`RenderContext(settings, roster, paths, round: RoundView | None, attempt:
AttemptView | None, project_remaining: float | None, gates_line: str)` where
`RoundView` and `AttemptView` are the small read-only views defined in
`70-contracts.md` (no module here imports `round/state.py`; the engine builds
the views).

- `scan(text: str) -> list[Token]` — every well-formed token, in order.
- `resolve(token: Token, ctx: RenderContext) -> str | None` — the value or
  `None` when unresolvable (unknown namespace, unknown key, missing prose
  file, no round for a `round.` token). Pure except for reading prose files.

## render.py

Data: `Rendered(text: str, unresolved: list[Token], included: list[str],
estimatedTokens: int, warnings: list[str])`.

- `render_text(text: str, ctx: RenderContext, depth: int = 0) -> Rendered` —
  substitutes every token; `prose.` values are rendered recursively (depth
  limit 8, a cycle or overflow becomes an unresolved token with a warning);
  unresolved tokens are left verbatim in the text and listed. `estimatedTokens`
  uses the one estimate from `ledger/tokens.py` (bytes / `tokenBytes`, rounded
  up); a warning is added when it exceeds `promptWarnTokens`.
- `render_prose(stem: str, ctx: RenderContext) -> Rendered` — loads the file
  and calls `render_text`; a missing stem is one unresolved token and an empty
  text.
- `render_prompt(stem: str, ctx: RenderContext) -> Rendered` — the full prompt
  for an attempt: the head (`agents_md.full_text`, verbatim, under a fixed
  heading "AGENTS.md"), then `render_prose(stem)`; when the prose contains no
  `plumbing.PROCESS-INSTRUCTIONS` token the plumbing is appended at the end
  with a warning (the prose forgot the plumbing; the agent still gets its
  mechanics) `[JC-12]`.

Unresolved tokens never crash a real run: the prompt is written with them
verbatim, `HISTORY.md` gets a line naming them, and `doctor` fails on them.

## plumbing.py

Builds the two plumbing values from an `AttemptView`. Text only; no I/O.

- `process_instructions(view: AttemptView, ctx: RenderContext) -> str` — the
  mechanical block. Sections, in order, each a short labelled paragraph:
  1. Identity: step, role (producer / gate / driver), attempt id, rung.
  2. Where: absolute worktree path (producers), or "read-only; do not write
     anything" (gates), or "you are the driver in the owner's chat" (plan,
     checkpoint).
  3. Inputs: one line per input artifact with its absolute path; for gates,
     the artifact under judgment, the prior findings file(s) with resolutions,
     the producer's stated resolutions and disputes (paths).
  4. May edit: the declared paths, listed; the artifact path(s) to write; the
     round folder rule (artifact, judgment-call files only).
  5. Never: spec files (listed by name), other agents' artifacts, `STATE.json`,
     `HISTORY.md`, `PROMPTS/`, `RESULTS/`, `FINDINGS/`; no git commands that
     change history; no pushes.
  6. Budget and limits: this attempt's budget in currency, the step's share,
     the turn number of `maxTurnsPerGate`, `maxSimultaneousSubAgentsPerRound`
     and the sub-agent count the agent plan grants this step.
  7. Verification: what the runner will run at record (`COLLECT` / `PASS`) and
     the timeout.
  8. Judgment-call tool: the exact command
     `python <abs run.py> judgment defined|undefined "<one line>" --attempt <id>`
     (producers); "list them under `judgmentCalls` in your final message"
     (gates and the driver).
  9. Final message: the exact JSON shape the runner parses for this role
     (`70-contracts.md`), stated as a template, and the sentence "your final
     message must be that JSON object and nothing else".
  10. Step end: when `stepEndDelivery` is `inline`, the rendered
      `COMMON-STEP-END` under the heading "Before your final message"; when
      `follow-up`, one line saying a follow-up message will arrive `[JC-13]`.
- `gate_prose(view: AttemptView, ctx: RenderContext) -> str` — for a producer
  prompt: the rendered gate prose of the step (with `plumbing.` tokens inside it
  replaced by the sentence "(plumbing omitted here)" to avoid recursion), or
  the fixed sentence "No gate prose exists for this step." when the file is
  absent; preceded by "gate is off this round; the standard still applies"
  when the gate is off `[JC-14]`.
- `checkpoint_summary(view: AttemptView, ctx: RenderContext) -> str` — the data
  block for a checkpoint prompt: steps done with verdicts, the judgment-call
  files' contents, flags for the owner, spend vs quote, open notes; appended
  after the rendered `CHECKPOINT-OVERVIEW`.

## agents_md.py

- `slug(heading: str) -> str` — uppercase, non-alphanumerics to `_`, runs
  collapsed, leading/trailing `_` stripped ("DEFINED AND UNDEFINED JUDGMENT
  CALLS" -> `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`, "ADVICE." -> `ADVICE`).
- `sections(text: str) -> dict[str, str]` — bodies keyed by slug of every `## `
  heading; the text before the first `## ` is keyed `PREAMBLE`.
- `full_text(path: Path) -> str` — the whole file, verbatim.
- `section(path: Path, key: str) -> str | None`.
