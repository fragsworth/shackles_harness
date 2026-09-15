# 04 — Steps, prose, plumbing, prompts, agent definitions

`steps.py` is the fixed step table (code, linted against `project.yaml`). `prose.py` is a generic template engine over the owner's locked prose. `plumbing/` generates the mechanical instructions (`{{ plumbing.* }}`). `prompts.py` assembles and files an attempt's prompt. `agentdefs.py` generates the per-rung Claude Code agent definitions.

## 4.1 `src/shackles/steps.py` — the step table

**Owns:** the ordered list of steps and everything static about each step. **Depends on:** `errors`. **Depended on by:** `config`-independent lint in `doctor` and `commands/start`; `plumbing`, `prompts`, `checks`, `suite`, `landing`, `budget`, `limits`, `state`, `artifacts`, `tests/support/fakespec.py` (which generates the fake spec *from this table*).

- `@dataclass(frozen=True) class Step`: `name: str`; `kind: "driver"|"producer"|"checkpoint"|"landing"|"cleanup"`; `has_gate: bool`; `overview_prose: str | None` (file stem in `locked_prose/`, e.g. `PLAN-TO-SPEC-OVERVIEW`); `gate_prose: str | None` (e.g. `PLAN-TO-SPEC-GATE`); `artifacts: tuple[str, ...]` (keys of `roundPaths.artifacts` this step must write); `writes: tuple[str, ...]` (declared path roots relative to the harness root, before intersection with living paths; `"<round>"` means the round folder; `"<conflicts>"` means the landing conflict list; `"<root-docs>"` means `INDEX.md`+`README.md`); `inputs: tuple[str, ...]` (symbolic input names resolved by plumbing: `plan`, `agents_plan`, `spec`, `new_tests`, `living_tree`, `carry_files`, `round_folder`, `roster`, `conflicts`, `suite_stats`); `checks: tuple[str, ...]` (names of mechanical checks in [06] `checks.CHECKS`); `share_source: "defaultShares"|"agentsPlan"`; `agent_default_key: "defaultAgent"|"gateAgent"`; `overridable: bool`.
- `STEPS: tuple[Step, ...]` in this exact order, matching `project.yaml` today:

| name | kind | gate | overview / gate prose | artifacts | writes | checks |
|---|---|---|---|---|---|---|
| CHAT-TO-PLAN | driver | yes (prose may be absent) | CHAT-TO-PLAN-OVERVIEW / CHAT-TO-PLAN-GATE | plan | `<round>` | artifact-plan |
| PLAN-AGENTS | producer | yes | PLAN-AGENTS-OVERVIEW / -GATE | agentsPlan | `<round>` | artifact-agents-plan |
| PLAN-TO-SPEC | producer | yes | PLAN-TO-SPEC-OVERVIEW / -GATE | spec, specProse | `<round>` | artifact-spec, non-goals-carried (advisory) |
| CHECKPOINT-1 | checkpoint | no | CHECKPOINT-OVERVIEW / — | — | — | — |
| SPEC-TO-TESTS | producer | yes | SPEC-TO-TESTS-OVERVIEW / -GATE | — | `<testPaths>`, `<round>` | tests-collect, new-tests-exist |
| SPEC-TO-IMPLEMENTATION | producer | yes | SPEC-TO-IMPLEMENTATION-OVERVIEW / -GATE | — | `<living minus testPaths>`, `<round>` | verify-suite |
| TESTS-TO-SUITE | producer | yes | TESTS-TO-SUITE-OVERVIEW / -GATE | suite | `<testPaths>`, `<round>` | artifact-suite, suite-consistent, tests-collect |
| CHECKPOINT-2 | checkpoint | no | CHECKPOINT-OVERVIEW / — | — | — | — |
| LANDING | landing | no | LANDING-CONFLICT (plumbing template, no owner prose) / — | — | `<conflicts>` | conflict-only, no-markers, verify-suite |
| POSTMORTEM | producer | yes | POSTMORTEM-OVERVIEW / -GATE | postmortem | `<round>`, `<carry-files>` | artifact-postmortem, verify-suite |
| CLEANUP | cleanup | no | CLEANUP-OVERVIEW / — | — | `<living>`, `<round>`, `<root-docs>` | verify-suite |

Notes: CHAT-TO-PLAN and PLAN-AGENTS take their share from `defaultShares`; all others from `AGENTS-PLAN.json`. Checkpoints are not overridable by `override` (they are governed by delegation and the `steps` flags); CHAT-TO-PLAN is not overridable ("the plan itself cannot be skipped"); LANDING and CLEANUP are not overridable (JC-24). The carry-forward files are `docs/TODO.md` and `docs/CLARIFICATIONS.md` (code constants, JC-25).

Functions:
- `by_name(name: str) -> Step` (`StepTableError` unknown), `index(name) -> int`, `after(name) -> Step | None`, `gated_steps() -> list[Step]`, `checkpoints() -> list[Step]`, `names() -> list[str]`.
- `lint(project_steps: dict[str, int]) -> list[str]` — compares the `steps` map from `project.yaml` with `STEPS`: same names, same order, values 0/1; returns a list of problems (empty = ok). `doctor` reports them; `start` raises `StepTableError`. Also flags a `1` on a step without a gate as a note (harmless per the owner's comment).
- `consumers() -> list[str]` — a static list of the places to revisit when the table changes (rendered by doctor as a note and written in `docs/ARCHITECTURE.md`): locked_prose file names, `roundPaths.artifacts`, `defaultShares`, `steps` map, `checks.CHECKS`, `plumbing/templates`, `fakespec`, stub-agent scenarios, `docs/PROCESS.md`.

## 4.2 `src/shackles/prose.py` — locked prose and the template engine

**Owns:** reading `locked_prose/*.txt` and `AGENTS.md`; the `{{ ns.KEY }}` syntax; recursive expansion; the report of unresolved tokens. **Depends on:** `paths`, `errors`. **Depended on by:** `prompts`, `plumbing` (for GATE-PROSE), `doctor`.

- Token syntax: `{{` optional spaces, `<ns>.<KEY>`, optional spaces, `}}`; `ns ∈ {prose, project, round, plumbing, agents}`; `KEY` matches `[A-Za-z0-9_.-]+`. Anything else is left as text.
- `@dataclass class ProseSet`: `files: dict[str, str]` (stem → text), `agents_sections: dict[str, str]` (see below), `dir: Path`.
  - `ProseSet.load(roots: Roots, locked_prose_path: str) -> ProseSet` — every `*.txt` in the directory (`ConfigError` if the directory is missing); `AGENTS.md` sections: split on lines starting with `## `; key = heading text uppercased, trailing punctuation stripped, non-alphanumerics collapsed to `_` (so `## DEFINED AND UNDEFINED JUDGMENT CALLS` → `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`, `## ADVICE.` → `ADVICE`); value = the section body without its heading.
  - `has(self, stem: str) -> bool`, `text(self, stem: str) -> str` (`ProseError` unknown stem), `stems(self) -> list[str]`.
- `@dataclass class Context`: `project: Mapping[str, str]`, `round: Mapping[str, str]`, `plumbing: Mapping[str, str]`, `agents: Mapping[str, str]`, `prose: ProseSet`.
- `@dataclass class Rendered`: `text: str`, `unresolved: list[str]` (tokens as written), `included: list[str]` (prose stems expanded, in order).
- `render(text: str, ctx: Context, *, max_depth: int = 20) -> Rendered` — expands `prose.*` recursively (cycle → `ProseError` naming the chain; depth overflow → `ProseError`), substitutes the other namespaces from the context maps, leaves unknown tokens verbatim and lists them. Substituted values are inserted as-is (no escaping; the prose is plain text).
- `render_stem(stem: str, ctx: Context) -> Rendered` — convenience.
- `find_tokens(text: str) -> list[tuple[str, str]]` — (ns, key) pairs, in order, duplicates kept.
- `references(ps: ProseSet) -> dict[str, list[str]]` — stem → the `prose.*` stems it includes (for doctor's unused-prose report).
- `gates_text(cfg_steps: dict[str, int], steps: Sequence[Step]) -> str` — the value of `{{ project.gates }}`: gated steps in table order as `NAME (on)` / `NAME (off)` joined by `, `; steps whose gate prose file is absent get `(off, no prose)`. (JC-26)
- `list_text(value: object) -> str` — lists → comma-joined, numbers → shortest repr, others → `str`.

Rules: this module never decides anything from prose content. The only structure it knows is the token syntax and `## ` headings.

## 4.3 `src/shackles/plumbing/` — the mechanical instructions

**Owns:** the text that replaces `{{ plumbing.PROCESS-INSTRUCTIONS }}` and `{{ plumbing.GATE-PROSE }}`, plus the driver-facing texts (checkpoint summary, pause summary, landing-conflict overview). **Depends on:** `steps`, `paths`, `prose` (to render the gate prose for GATE-PROSE), `config`, `state` (read-only views), `budget` (attempt budget), `findings` (open findings listing). **Depended on by:** `prompts`, `doctor`.

Files: `builder.py` and `templates/*.txt` (plain text with `${name}` placeholders substituted by `string.Template`; templates are living files so their wording is charged and editable by rounds). Templates: `producer.txt`, `gate.txt`, `driver.txt`, `conflict.txt`, `checkpoint.txt`, `pause.txt`, `cleanup.txt` (= producer plus the "runner books charges" note), `gate-absent.txt`, `gate-off.txt`.

Each template's sections (what it must contain, not its wording):
- **producer**: identity (step, attempt id, rung, attempt budget in USD and share, individual hard-stop multiple); working directory (absolute worktree harness root) and write policy (declared paths, "edits elsewhere are reverted, never spec files, never git"); inputs (resolved absolute paths and, for listings, the list); output (artifact path(s) and the FORMATS.md section name); helpers (the exact `spawn` command with `--root`, allowed rungs, the simultaneous cap, or "no helpers planned"); open findings to resolve (id, quote, text, suggestion, state, "settled ones must be fixed") and the `resolutions` rule; the judgment-call tool (exact command with `--root <worktree harness root>`, absolute path of the driver checkout's `run.py`, JC-27); the final-message schema (verbatim JSON skeleton from [00] §0.6) and "your final message must be exactly one JSON object".
- **gate**: identity; "read-only; you have no write tools"; artifact path(s); the producer's inputs; the FINDINGS file(s) with prior findings, their resolutions and which are disputed ("rule on each disputed finding before raising new ones"; "your verdict decides; blocking follows it; a repeat of a withdrawn finding is dropped"); verify result if any; finding format (quote, text, suggestion); judgment calls go in the message; the gate message schema.
- **driver** (CHAT-TO-PLAN): where `PLAN.json` goes (absolute path in the round worktree) and its format section; the owner-decision table — the runner's `owner --decision` kinds, and that the driver must pass the owner's words verbatim as `--quote`; the result file path and the `record` command; the checkpoint behaviour (wait in chat); "no round proceeds with unanswered questions".
- **conflict** (LANDING): the conflicted file list (absolute), the note that the tree is git's auto-merge with markers, "edit only these files; remove every marker; the suite must pass", the final-message schema.
- **checkpoint**: the file `next` writes for a checkpoint begins with the rendered `CHECKPOINT-OVERVIEW` prose (when that stem exists) and continues with this template: round id, steps done with status, spend/quote/remaining, assumptions from `PLAN.json`, both judgment-call files' contents, pending flags, open questions, "which decisions continue".
- **pause**: pause kind and reason, the attempt, open questions with ids and options, `narrow` text, pending flags, limits hit with counters and the decisions that unblock (`resume`, `answer`, `raise-limit`, `override`, `abandon`).
- **gate-absent** / **gate-off**: "No gate prose is defined for this step." / "This step's gate is off this round; the standard is unchanged:" followed by the gate prose.

Functions in `builder.py`:
- `@dataclass class AttemptView`: everything a template needs, assembled by `prompts`: `step: Step`, `attempt_id: str`, `kind: str`, `rung: Rung | None`, `budget_usd: float`, `share: float`, `worktree_harness: Path`, `declared_paths: list[str]`, `inputs: dict[str, list[str] | str]`, `artifact_paths: list[str]`, `open_findings: list[FindingRecord]`, `findings_files: list[str]`, `verify: dict | None`, `helpers: list[dict]`, `helper_cap: int`, `runner_path: Path`, `conflicts: list[str]`, `round_folder: Path`.
- `process_instructions(view: AttemptView) -> str` — picks the template by `view.kind` and fills it; raises `ProseError` when a template lacks a placeholder the view supplies (kept strict so a template edit cannot silently drop a section).
- `gate_prose(step: Step, cfg: Config, ps: ProseSet, ctx: Context) -> str` — renders the step's gate prose with `plumbing.PROCESS-INSTRUCTIONS` replaced by "(the gate's own process instructions)" and no recursion into GATE-PROSE; wraps with `gate-off.txt` when `cfg.step_gate_on` is false; returns `gate-absent.txt` when `step.gate_prose` is absent from the prose set or the step has no gate. (JC-28)
- `checkpoint_summary(view: CheckpointView) -> str`, `pause_summary(view: PauseView) -> str` — driver-facing texts; the views are small dataclasses of the fields listed above.
- `template(name: str) -> string.Template` — loads from `templates/`; `ProseError` if missing.

## 4.4 `src/shackles/prompts.py` — assembling and filing an attempt's prompt

**Owns:** the composition `overview/gate prose → render with context → append COMMON-STEP-END → write PROMPTS/<attempt>.txt`, the prompt-size warning, and opening the attempt in state. **Depends on:** `prose`, `plumbing`, `steps`, `config`, `state`, `budget`, `paths`, `findings` (open findings), `ledger` (spend/remaining for `round.*`, `project.remaining`). **Depended on by:** `commands/next_`, `commands/start`, `doctor` (offline rendering with a synthetic round).

- `round_values(rs: RoundState, cfg: Config, rp: RoundPaths) -> dict[str, str]` — `id`, `folder`, `base_commit`, `plan` (the plan's `text` plus a trailing "Owner answers:" list of every answered question `#id: <quote>`; `"(no approved plan yet)"` before approval, JC-29), `budget` (quote), `spend`, `remaining`, all as text.
- `project_values(cfg: Config, roster: AgentRoster, remaining_usd: float) -> dict[str, str]` — `cfg.prose_values()` plus `remaining` and `gates`.
- `build_context(session, rs: RoundState | None, plumbing: dict[str, str]) -> Context` — assembles the five namespaces; for `rs=None` uses `synthetic_round()` (id `0000`, base commit `0000000`, plan "(doctor sample plan)", budget 100, spend 0).
- `open_attempt(session, rs: RoundState, step: Step, kind: str, *, judges: str | None) -> Json` — allocate the attempt id (`state.next_attempt_id`), choose the rung (`budget.rung_for`), build the `AttemptView` (declared paths via `steps` ∩ living paths; inputs resolved by `resolve_inputs`), produce `plumbing` strings, render the prose stem (`ProseError` if unresolved tokens remain — listed), append the rendered `COMMON-STEP-END` (if that stem exists; otherwise nothing, noted), write the prompt file, compute `prompt_tokens = ceil(bytes / tokenBytes)`, add a warning when above `promptSizeWarnTokens`, register the attempt in state, and return the `next`-style object of [00] §0.12.
- `resolve_inputs(step: Step, rs, rp, roots) -> dict[str, list[str] | str]` — maps symbolic input names to absolute paths/listings: `plan`→PLAN.json, `agents_plan`, `spec`→SPEC.json+SPEC.md, `new_tests`→files under testPaths changed since `base_commit` (via an injected `changed_files` callable), `living_tree`→a listing of living paths, `carry_files`, `round_folder`→listing, `roster`→`roster.table_text()`, `conflicts`, `suite_stats`→count of test functions and files (from `suite.enumerate`).
- `render_offline(session, step: Step, kind: str) -> Rendered` — doctor's path: same as `open_attempt` but with the synthetic round, no state change, no file written.
- `step_end_text(ctx: Context) -> str` — rendered `COMMON-STEP-END` or empty.

Errors: `ProseError` (unresolved tokens, missing overview stem for a step that must run), `StateError` (an attempt is already open).

## 4.5 `src/shackles/agentdefs.py` — generated Claude Code agent definitions

**Owns:** the content of `.claude/agents/shackles-<rung>.md` and `shackles-<rung>-gate.md` and their freshness check. **Depends on:** `config` (roster), `paths`. **Depended on by:** `doctor`, `commands/accept_spec`, `tests/test_agent_defs.py`.

- `FRONTMATTER_KEYS: dict[str, str]` — the mapping of definition fields to frontmatter keys (`name`, `description`, `model`, `effort`, `tools`) kept in one table so a tooling change is one edit (JC-30).
- `producer_definition(r: Rung) -> str` — frontmatter: `name: shackles-<rung>`, `description: shackles harness producer, rung <rung> (<name>); spawned by the driver with a rendered prompt file` , `model: <model>`, `effort: <effort>`; body (fixed text): the agent's whole instruction is the message it receives; follow it; the runner parses the final message; never run git; never edit spec files; log judgment calls with the tool the message names.
- `gate_definition(r: Rung) -> str` — as above with `name: shackles-<rung>-gate`, `tools: Read, Grep, Glob` (read-only), body adds "you have no write tools; judge, quote, and answer in the final message".
- `expected_files(roster: AgentRoster) -> dict[str, str]` — relative path → content for every rung.
- `write_all(roots: Roots, roster: AgentRoster) -> list[str]` — writes, returns the paths; removes stale `shackles-*.md` files for rungs no longer in the roster.
- `check(roots: Roots, roster: AgentRoster) -> list[str]` — problems: missing, stale (content differs), orphaned files.
- `agent_name(rung: str, read_only: bool) -> str` — used by `next` output.
