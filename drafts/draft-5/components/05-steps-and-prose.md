# 05 — Steps & prose (`steps.py`, `prose.py`, `plumbing.py`)

**Purpose.** Hold the fixed step table as code, check it against the owner's data, and
turn locked prose into a finished prompt for one attempt. This component renders; it
never decides what happens next (that is 10) and never reads results.

**Owns.** The step table; the lint of table vs `project.yaml: steps` vs
`locked_prose/`; token syntax and the five namespaces; the mechanical text of
`PROCESS-INSTRUCTIONS` and `GATE-PROSE`; prompt assembly and size warning.

**Depends on.** 04 (`Config`, `Roster`, `Paths`, `agents_values`, `project_values`).
For `round.*` and plumbing inputs it takes plain dicts/dataclasses passed by the caller
(the engine builds them from STATE); it does not import 08 or 10.

**Depended on by.** 10 (engine) and 11 (doctor).

---

## `steps.py` — the step table

`class StepKind(Enum)`: `DRIVER` (done by the driver), `PRODUCER`, `CHECKPOINT`,
`RUNNER` (LANDING, no prompt unless a conflict), `PRODUCER_NO_GATE` (CLEANUP).

`class Step` (frozen): `name`, `kind`, `has_gate: bool`, `overview_prose: str | None`
(file stem), `gate_prose: str | None`, `overview_optional: bool` (LANDING only, JC-05),
`artifact_keys: tuple[str, ...]` (dotted `roundPaths.artifacts` keys), `inputs:
tuple[str, ...]` (artifact keys and `"living-tree"`, `"owner-words"`, `"todo"`,
`"clarifications"`, `"suite-run"`), `write_paths: tuple[str, ...]` (symbols resolved by
plumbing: `"round-folder"`, `"living"`, `"tests"`, `"living-minus-tests"`,
`"carry-forward"`, `"conflict-files"`), `read_only_gate: bool` (always True),
`skip_effect: str` (symbol read by `advance.py`, JC-21: `"not-skippable"`,
`"default-agents-plan"`, `"plan-is-spec"`, `"no-new-tests"`, `"no-code"`, `"all-to-suite"`,
`"skip-checkpoint"`, `"no-postmortem"`, `"no-cleanup-attempt"`).

`STEP_TABLE: tuple[Step, ...]` in run order:
```
CHAT-TO-PLAN          DRIVER          gate=no   overview CHAT-TO-PLAN-OVERVIEW      artifacts plan               writes round-folder     skip not-skippable
PLAN-AGENTS           PRODUCER        gate=yes  PLAN-AGENTS-OVERVIEW/-GATE           agentsPlan                   round-folder            default-agents-plan
PLAN-TO-SPEC          PRODUCER        gate=yes  PLAN-TO-SPEC-OVERVIEW/-GATE          spec, specProse              round-folder            plan-is-spec
CHECKPOINT-1          CHECKPOINT      gate=no   CHECKPOINT-OVERVIEW                  —                            —                       skip-checkpoint
SPEC-TO-TESTS         PRODUCER        gate=yes  SPEC-TO-TESTS-OVERVIEW/-GATE         —                            tests, round-folder     no-new-tests
SPEC-TO-IMPLEMENTATION PRODUCER       gate=yes  SPEC-TO-IMPLEMENTATION-OVERVIEW/-GATE —                           living-minus-tests, round-folder   no-code
TESTS-TO-SUITE        PRODUCER        gate=yes  TESTS-TO-SUITE-OVERVIEW/-GATE        suite                        round-folder            all-to-suite
CHECKPOINT-2          CHECKPOINT      gate=no   CHECKPOINT-OVERVIEW                  —                            —                       skip-checkpoint
LANDING               RUNNER          gate=no   LANDING-OVERVIEW (optional)          —                            conflict-files, round-folder   not-skippable
POSTMORTEM            PRODUCER        gate=yes  POSTMORTEM-OVERVIEW/-GATE            postmortem                   carry-forward, round-folder    no-postmortem
CLEANUP               PRODUCER_NO_GATE gate=no  CLEANUP-OVERVIEW                     —                            living, round-folder    no-cleanup-attempt
```
Fixed prose names the code requires besides the table: `COMMON-STEP-END` (appended to
every agent prompt). Any other `COMMON-*` file is the owner's business, reached only
through `{{ prose.X }}`.

- `step(name: str) -> Step` — raises `UnknownStepError`.
- `order() -> list[str]`, `after(name) -> str | None`, `agent_steps() -> list[str]`
  (kinds DRIVER/PRODUCER/PRODUCER_NO_GATE plus LANDING), `gated_steps() -> list[str]`.
- `required_prose_names() -> set[str]`, `optional_prose_names() -> set[str]`.
- `lint(cfg: Config, prose_names: set[str]) -> LintReport` — `LintReport(errors:
  list[str], warnings: list[str])`. Errors: a `steps` key unknown to the table; a table
  step missing from `steps`; `steps` order differs from the table (JC-39); a required
  prose file missing; a prose file `<X>-OVERVIEW.txt`/`<X>-GATE.txt` where `X` is not a
  table step; a gate prose file for a step whose table says no gate. Warnings: a
  `steps` value of 1 for a gateless step ("no effect"); a prose file not required,
  not optional and not `COMMON-*` (reported as unused unless referenced, which `prose.py`
  can tell doctor).

## `prose.py` — loading and rendering

Token syntax: `{{ ns.NAME }}` with optional inner spaces; `ns ∈ {prose, project,
round, agents, plumbing}`; NAME is `[A-Za-z0-9_.-]+`. Anything else is left as text.

`class Namespaces`: `project: dict[str,str]`, `round: dict[str,str]`, `agents:
dict[str,str]`, `plumbing: dict[str,str]`. `class Rendered`: `text: str`, `unresolved:
list[str]` (tokens in `ns.NAME` form, in order, deduplicated), `used_prose: set[str]`.

- `load_prose(prose_dir: Path) -> dict[str, str]` — every `*.txt` → stem → content
  (UTF-8, trailing newline preserved). Raises `ProseError` on undecodable files.
- `render(name: str, prose: dict[str, str], ns: Namespaces, *, strict: bool) ->
  Rendered` — expands recursively; a `prose.X` cycle raises `ProseError` naming the
  chain; an unknown `prose.X` or unknown NAME in another namespace is recorded in
  `unresolved`, and, when `strict`, raises `UnresolvedTokenError(unresolved)` after
  rendering the whole thing (so all are named at once). Depth limit 20.
- `find_tokens(text: str) -> list[tuple[str, str]]` — `(ns, NAME)` pairs, in order.
- `referenced_prose(prose: dict[str,str]) -> set[str]` — names reachable from any file.
- `round_values(state_view: dict) -> dict[str, str]` — the `{{ round.* }}` namespace
  from a plain dict the engine supplies: `id`, `folder` (absolute worktree path),
  `base_commit`, `plan` (S2 `text` + a `Questions and answers:` block with the verbatim
  answers + `Overrides:` when any), `budget`, `spend`, `remaining`, `owner_words`
  (verbatim quotes since the last pause, newest last), `step`, `attempt`.

## `plumbing.py` — mechanical text

`class AttemptSpec` (frozen; built by the engine): `step: Step`, `n: int`, `kind`,
`rung: Rung | None`, `worktree: Path`, `round_folder: Path`, `inputs: list[Path]`,
`artifact_paths: list[Path]`, `write_roots: list[Path]`, `read_only: bool`,
`budget_usd: float`, `turn: int`, `max_turns: int`, `findings_text: str` (verbatim
S8 rendering for retries and gate turns, `""` when none), `resolutions_text: str`,
`owner_words_text: str`, `conflict_files: list[Path]`, `jc_command: str`,
`sub_agent_rung: Rung | None`, `sub_agent_max: int`, `agent_definition: str`,
`verify_command: list[str]`, `extra_notes: list[str]` (e.g. mechanical failure output).

- `process_instructions(a: AttemptSpec) -> str` — the numbered, mechanical text
  (identity; worktree and allowed write roots as absolute paths; inputs to read by path (JC-43); the
  artifact path(s); the exact final-message JSON shape for the kind, copied from S7; how
  to end DONE/NEEDS-OWNER/BLOCKED or PASS/FAIL; the judgment-call command line or the
  `judgment_calls` field; budget, turn `t of max`, prices of the rung; sub-agent rule
  with `maxSimultaneousSubAgentsPerRound` (JC-28); the constraints: no git
  commit/push, no edits to spec files, strays reverted; prior findings and resolutions
  verbatim; extra notes). Contains no judgment, no adjectives.
- `gate_prose_for(step: Step, prose: dict[str,str], ns: Namespaces) -> str` — renders the
  step's gate prose with the same namespaces (without `PROCESS-INSTRUCTIONS`, which is
  replaced by the sentence `(process instructions are given to the gate separately)`),
  or, for a gateless step, the fixed sentence `No gate judges this step; the owner does.`
  (JC-04).
- `assemble_prompt(a: AttemptSpec, prose: dict[str,str], ns: Namespaces, cfg: Config)
  -> Prompt` — `Prompt(text, tokens, warnings: list[str], unresolved: list[str])`:
  producer/driver → `render(overview)`; gate → `render(gate)`; conflict → `render
  (LANDING-OVERVIEW)` if present else the concatenation of rendered `COMMON-PROJECT`,
  `COMMON-ROUND`, `COMMON-OVERVIEW` (each only if it exists) and the process
  instructions (JC-05); checkpoint → `render(CHECKPOINT-OVERVIEW)` + the summary text
  passed in `extra_notes`. Every agent prompt then gets `\n\n` + `render(COMMON-STEP-END)`
  (JC-06). `tokens = ceil(len(bytes)/tokenBytes)`; a warning when above
  `promptTokenWarning`. Strict rendering: unresolved tokens raise
  `UnresolvedTokenError`.
- `placeholder_attempt(step: Step, kind, cfg, roster, paths) -> AttemptSpec` — the
  offline stand-in used by doctor (round `0000`, budget 0, worktree = harness root).

Errors: `ProseError`, `UnresolvedTokenError(names: list[str])`, `UnknownStepError`.

## Invariants
- The table is the only place step names are spelled in `src/`; other modules call
  `steps.step(name)`.
- Rendering is deterministic for equal inputs; the engine saves the produced text as the
  prompt file and never re-renders an issued attempt.
- Plumbing text contains every absolute path the agent needs; agents never have to guess
  a location.

## Covered by
`tests/test_steps.py`, `tests/test_prose.py`, `tests/test_plumbing.py`.
