# 32 — src/shackles/steps/ (the step table as code)

Parent: `30-src.md`. Owns the fixed step list, what each step is, what it
reads, writes and may edit, and the lint that checks the table against the
owner's data (`project.yaml`'s `steps`, the prose files, the roster). Depends
on: `config/`. Depended on by: `prompts/`, `engine/`, `quote/`, `checks/`.

```
steps/
  table.py    the eleven steps and their static properties
  lint.py     table vs project.yaml vs locked_prose vs roster
```

## table.py

Data:

- `Kind` enum: `PLAN` (done by the driver in chat), `PRODUCER` (sub-agent in a
  worktree), `CHECKPOINT` (driver pauses for the owner), `LANDING` (runner
  merges; conflict attempt possible), `CLEANUP` (producer, then the runner
  books).
- `Step` (frozen dataclass): `name: str`; `kind: Kind`; `overviewProse: str`
  (prose file stem, e.g. `PLAN-AGENTS-OVERVIEW`); `gateProse: str | None`
  (`PLAN-AGENTS-GATE`, or `None` for steps that can never have a gate);
  `artifacts: tuple[str, ...]` (keys of `roundPaths.artifacts` it writes);
  `inputs: tuple[str, ...]` (artifact keys it reads, in order); `declaredPaths:
  PathRule` (which living paths it may edit: `NONE`, `TESTS`,
  `LIVING_EXCEPT_TESTS`, `CARRY_FORWARD`, `ALL_LIVING`, `CONFLICTED`);
  `verify: VerifyRule` (`NONE`, `COLLECT`, `PASS`); `overridable: bool`;
  `skipDefault: str | None` (what happens when overridden); `usesShareOf:
  "work"|"gates"|None`.
- `TABLE: tuple[Step, ...]` — in run order, exactly:

| name | kind | gateProse | artifacts | inputs | declaredPaths | verify | overridable / skip default |
|---|---|---|---|---|---|---|---|
| CHAT-TO-PLAN | PLAN | `CHAT-TO-PLAN-GATE` (file may be absent) | plan | — | NONE | NONE | no (the plan cannot be skipped) |
| PLAN-AGENTS | PRODUCER | PLAN-AGENTS-GATE | agentsPlan | plan | NONE | NONE | yes / defaults from `defaultShares` and the default rungs |
| PLAN-TO-SPEC | PRODUCER | PLAN-TO-SPEC-GATE | spec, specProse | plan, agentsPlan | NONE | NONE | no |
| CHECKPOINT-1 | CHECKPOINT | — | — | all so far | NONE | NONE | yes / skipped |
| SPEC-TO-TESTS | PRODUCER | SPEC-TO-TESTS-GATE | — | plan, spec, specProse | TESTS | COLLECT | no |
| SPEC-TO-IMPLEMENTATION | PRODUCER | SPEC-TO-IMPLEMENTATION-GATE | — | plan, spec, specProse | LIVING_EXCEPT_TESTS | PASS | no |
| TESTS-TO-SUITE | PRODUCER | TESTS-TO-SUITE-GATE | suite | plan, spec | TESTS | PASS (after moves) | yes / every new test joins the suite |
| CHECKPOINT-2 | CHECKPOINT | — | — | all so far | NONE | NONE | yes / skipped |
| LANDING | LANDING | — | — | — | CONFLICTED | PASS | no |
| POSTMORTEM | PRODUCER | POSTMORTEM-GATE | postmortem | plan, spec, suite | CARRY_FORWARD | NONE | yes / no postmortem, no carry-forward edits |
| CLEANUP | CLEANUP | — | — | plan, spec, postmortem | ALL_LIVING | PASS | no |

`[JC-08]` records the overridable set and the skip defaults; `[JC-09]` the
inputs per step.

Functions (all pure):

- `step(name: str) -> Step` — raises `KeyError` on an unknown name (callers
  convert to `LintError`).
- `index_of(name: str) -> int`.
- `after(name: str) -> Step | None` — the next step in order, `None` after
  CLEANUP.
- `producers() -> tuple[Step, ...]`, `checkpoints() -> tuple[Step, ...]`,
  `gated() -> tuple[Step, ...]` (steps whose `gateProse` is not `None`).
- `gate_name(step: Step) -> str` — `<STEP>-GATE`.
- `prose_stems_expected() -> frozenset[str]` — every `overviewProse` and
  `gateProse` plus the common stems the plumbing includes by name
  (`COMMON-PROJECT`, `COMMON-ROUND`, `COMMON-OVERVIEW`, `COMMON-GATE`,
  `COMMON-STEP-END`, `CHECKPOINT-OVERVIEW`); used by lint and doctor to name
  prose files that match nothing.
- `attempt_id(step_name: str, role: "producer"|"gate"|"checkpoint"|"conflict", n: int) -> str`
  — `STEP-n`, `STEP-GATE-n`, `CHECKPOINT-1-n`, `LANDING-n`.

## lint.py

Data: `LintReport(errors: list[str], warnings: list[str], notes: list[str])`;
`ok` property = no errors.

- `lint(settings: Settings, roster: Roster, prose_dir: Path) -> LintReport` —
  the one entry point; runs every check below and concatenates. `start`
  refuses on any error; `doctor` prints all three lists.
- `check_step_switches(settings) -> LintReport` — every name in
  `project.yaml`'s `steps` must be in `TABLE` (error: "unknown step"); every
  table step must appear (error: "step missing from project.yaml"); the order
  in the file should match the table (warning); a value of 1 on a step whose
  `gateProse` is `None` is a note ("has no gate; setting has no effect"); a
  value of 1 on a step whose gate prose file is absent is an error ("gate on
  but no prose").
- `check_prose_files(prose_dir) -> LintReport` — every expected overview stem
  must exist (error); every gate stem for a gated step should exist (warning
  when absent: the gate renders as absent); every `.txt` in the folder must be
  an expected stem (warning: "prose file matches no step; never rendered").
- `check_unknown_keys(settings) -> LintReport` — `settings.unknown` non-empty
  is an error (each key named), because every setting must be used for
  something; `settings.defaulted` is a note per key.
- `check_roster(settings, roster) -> LintReport` — the four default rungs
  exist; `maxAgent` is on the ladder; `defaultShares` names only known steps
  (error otherwise) and fractions in `[0, 1]`.
- `check_round_paths(settings) -> LintReport` — `roundPaths.folder` contains
  `NNNN`; every key the code relies on exists (`artifacts.plan`,
  `artifacts.agentsPlan`, `artifacts.spec`, `artifacts.specProse`,
  `artifacts.suite`, `artifacts.postmortem`, `runner.state`, `runner.history`,
  `runner.ownerLog`, `attempts.prompts`, `attempts.results`,
  `attempts.findings`, `testsArchive`, `judgmentCalls.defined`,
  `judgmentCalls.undefined`); extra keys are notes.
