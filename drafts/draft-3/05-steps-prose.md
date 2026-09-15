# 05 — The step table and the locked prose: `steps.py`, `prose.py`

## `src/steps.py` — the step table is code

**Owns:** the fixed list of steps, what each step is (kind, artifacts, write scopes,
verify mode, prose names), the override rules, and the lint that compares the table
with `project.yaml` and the prose directory. **Depends on:** `config`, `prose`,
`errors`. **Depended on by:** `next_action`, `recording`, `checks`, `prompts`,
`context`, `landing`, `doctor`, `fixture_spec` (tests), `schemas` (validating
AGENTS-PLAN coverage).

The owner's `SPEC.md` says the step list is assumed fixed and the table is code,
lint-checked against the spec's data. Adding or renaming a step means editing this
file and `project.yaml` together.

### Types

- `Kind` (Enum): `CHAT` (the driver produces in chat), `PRODUCER` (a spawned agent),
  `CHECKPOINT` (owner pause), `RUNNER` (runner work, agent only on conflict).
- `Scope` (Enum): `ROUND` (the step's artifacts and the two judgment-call trails inside
  the round folder), `TESTS` (`testPaths`), `LIVING_MINUS_TESTS`, `LIVING`,
  `CARRY_FORWARD` (`carryForwardFiles`), `CONFLICTED` (the files named by the landing
  attempt).
- `Verify` (Enum): `NONE`, `COLLECT` (tests collect), `SUITE` (suite passes),
  `SUITE_AFTER_APPLY` (suite passes after SUITE.json is applied).
- `Step` (frozen dataclass): `name: str`, `kind: Kind`, `gate_capable: bool`,
  `overview_prose: str | None` (prose file stem), `gate_prose: str | None`,
  `artifact_keys: tuple[str, ...]` (keys of `roundPaths.artifacts`),
  `scopes: tuple[Scope, ...]`, `verify: Verify`, `freezes_tests_after: bool`,
  `tests_frozen_during: bool`, `contingent_agent: bool`, `books_charges: bool`,
  `skippable: bool`, `is_agent_step` property (`kind in {CHAT, PRODUCER}`).
- `LintReport` (dataclass): `errors: list[str]`, `warnings: list[str]`, `ok` property.
- `Overrides` (dataclass): `skip_steps: list[str]`, `skip_gates: list[str]`.

### The table (`TABLE: tuple[Step, ...]`)

| name | kind | gate | overview / gate prose | artifacts | scopes | verify | notes |
|---|---|---|---|---|---|---|---|
| CHAT-TO-PLAN | CHAT | capable | `CHAT-TO-PLAN-OVERVIEW` / `CHAT-TO-PLAN-GATE` (optional file) | plan | ROUND | NONE | not skippable |
| PLAN-AGENTS | PRODUCER | capable | `PLAN-AGENTS-OVERVIEW` / `PLAN-AGENTS-GATE` | agentsPlan | ROUND | NONE | |
| PLAN-TO-SPEC | PRODUCER | capable | `PLAN-TO-SPEC-OVERVIEW` / `PLAN-TO-SPEC-GATE` | spec, specProse | ROUND | NONE | |
| CHECKPOINT-1 | CHECKPOINT | no | `CHECKPOINT-OVERVIEW` / — | — | — | NONE | shared prose file |
| SPEC-TO-TESTS | PRODUCER | capable | `SPEC-TO-TESTS-OVERVIEW` / `SPEC-TO-TESTS-GATE` | — | TESTS, ROUND | COLLECT | freezes tests after |
| SPEC-TO-IMPLEMENTATION | PRODUCER | capable | `…-OVERVIEW` / `…-GATE` | — | LIVING_MINUS_TESTS, ROUND | SUITE | tests frozen during |
| TESTS-TO-SUITE | PRODUCER | capable | `…-OVERVIEW` / `…-GATE` | suite | ROUND | SUITE_AFTER_APPLY | |
| CHECKPOINT-2 | CHECKPOINT | no | `CHECKPOINT-OVERVIEW` / — | — | — | NONE | |
| LANDING | RUNNER | no | `LANDING-OVERVIEW` (optional file) / — | — | CONFLICTED, ROUND | SUITE | contingent agent; not skippable |
| POSTMORTEM | PRODUCER | capable | `POSTMORTEM-OVERVIEW` / `POSTMORTEM-GATE` | postmortem | CARRY_FORWARD, ROUND | SUITE | |
| CLEANUP | PRODUCER | no | `CLEANUP-OVERVIEW` / — | — | LIVING, ROUND | SUITE | books charges; not skippable |

`STEP_END_PROSE = "COMMON-STEP-END"` is appended to every agent prompt; the table
requires it to exist. Gate prose for the two optional entries (CHAT-TO-PLAN gate,
LANDING overview) is used when present and ignored when absent [JC-07].

### Functions

- `table() -> tuple[Step, ...]`; `names() -> list[str]`; `by_name(name: str) -> Step`
  (raises `UsageError("UNKNOWN_STEP")`); `index_of(name: str) -> int`;
  `after(name: str) -> Step | None`; `between(a: str, b: str) -> list[Step]`.
- `agent_steps() -> list[Step]` — CHAT, PRODUCER, and RUNNER steps with a contingent
  agent (the steps an agents plan must cover; LANDING optional).
- `gate_capable_steps() -> list[Step]`; `checkpoints() -> list[Step]`.
- `gate_prose_name(step: Step) -> str | None`; `overview_prose_name(step) -> str | None`.
- `expected_prose_names() -> tuple[set[str], set[str]]` — (required, optional) stems the
  table references, `COMMON-STEP-END` included in required.
- `lint(cfg: ProjectConfig, bundle: prose.ProseBundle) -> LintReport` — errors: the
  ordered keys of `cfg.steps` differ from `names()` (message lists both); a gate-capable
  step whose gate setting is 1 has no gate prose file; a required prose stem is
  missing; a file in the prose directory is neither an expected stem nor `COMMON-*`,
  or is not a `.txt`; `roundPaths.artifacts` lacks a key the table references, or has
  a key no step references; `defaultShares.gates` names a step that is not gate-capable;
  a prose token references a prose stem that does not exist (delegates to
  `templates.find_tokens`). Warnings: gate setting 1 on a non-gate-capable step ("no
  effect"); a `COMMON-*` file referenced by no token of any expected prose (unused);
  an overview prose lacking `{{ plumbing.PROCESS-INSTRUCTIONS }}` (it will be
  appended); a gate prose lacking it (same).
- `parse_overrides(spec: str, cfg: ProjectConfig) -> Overrides` — comma-separated
  entries; `STEP` skips a step, `STEP-GATE` skips its gate. Raises `UsageError` for an
  unknown name, a non-skippable step (`CHAT-TO-PLAN`, `LANDING`, `CLEANUP`) [JC-12], or a
  gate of a step that is not gate-capable.
- `gate_is_on(step: Step, cfg: ProjectConfig, overrides: Overrides) -> bool` — capable,
  setting 1, gate prose exists, not overridden.
- `resolve_scopes(step: Step, cfg: ProjectConfig, round_folder_rel: str,
  artifact_rels: list[str], jc_rels: list[str], conflicted: list[str] = ()) ->
  list[str]` — turns the step's scopes into relative path prefixes (directories end
  with `/`) and exact files the attempt may change: `ROUND` → the step's artifact files
  plus the judgment-call trails (not the whole folder) [JC-67]; `TESTS` → `testPaths`;
  `LIVING_MINUS_TESTS` → living paths, with test paths subtracted at check time;
  `LIVING` → living paths; `CARRY_FORWARD` → those files; `CONFLICTED` → the given
  files. Used by `checks.classify_changes`.
- `checkpoint_covered(step: Step, through: str | None) -> bool` — a checkpoint is
  covered by `delegate through STEP` when its index is ≤ the index of STEP; `through =
  None` with mode `delegate` covers all.

## `src/prose.py` — locked prose and AGENTS.md as data

**Owns:** reading `lockedProsePath/*.txt` and `AGENTS.md`, naming rules, sections.
Never interprets wording. **Depends on:** `templates` (to list tokens), `errors`.
**Depended on by:** `steps` (lint), `context`, `prompts`, `doctor`, `commands`.

- `ProseBundle` (dataclass): `dir: Path`, `texts: dict[str, str]` (stem → raw text,
  `.txt` files only, sorted), `other_files: list[str]` (non-`.txt` entries, for lint),
  `agents_md: str`, `agents_sections: dict[str, str]`.
  Methods: `text(stem) -> str` (raises `KeyError`); `has(stem) -> bool`;
  `tokens_in(stem) -> list[templates.Token]`; `stems() -> list[str]`;
  `classify(stem) -> tuple[str, str]` → `("overview", STEP)` for `<STEP>-OVERVIEW`,
  `("gate", STEP)` for `<STEP>-GATE`, `("common", NAME)` for `COMMON-<NAME>`,
  `("other", stem)` otherwise.
- `load(prose_dir: Path, agents_md: Path) -> ProseBundle` — raises
  `RefusedError("PROSE_DIR")` if the directory or `AGENTS.md` is missing; reads UTF-8;
  normalises line endings to `\n`.
- `section_key(heading: str) -> str` — uppercase, every run of non-alphanumerics
  becomes `_`, leading and trailing `_` stripped (`## DEFINED AND UNDEFINED JUDGMENT
  CALLS` → `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`, `## ADVICE.` → `ADVICE`) [JC-60].
- `split_sections(markdown: str) -> dict[str, str]` — bodies of every `## ` heading
  (level 2 only), keyed by `section_key`, body without the heading line, trimmed; plus
  `FULL` → the whole file. Duplicate keys: the later section wins and a warning is
  attached to `ProseBundle.warnings: list[str]`.
- `referenced_stems(bundle: ProseBundle, roots: set[str]) -> set[str]` — the closure of
  `prose.*` tokens reachable from the given stems (for the unused-fragment warning).
