# 14 — Probes (`tests/probes/`)

**Purpose.** Opt-in tests that run *real* agents through the real driver protocol on
small fixtures with planted defects, to check that the prose and the gates catch what
they are meant to catch. They are never part of the permanent suite run at `record`
(`verifyCommand` ignores `tests/probes`) and never run in CI (JC-32).

**Owns.** The live-agent adapter, the planted-defect fixtures, and the pass criteria.

**Depends on.** 03 (the CLI, driven as a subprocess), 06 (`agentdefs.definition_name`),
04 (`Config.systemTestAgent`), the `claude` CLI on PATH with credentials.

**Depended on by.** Nothing.

---

## Files
```
tests/probes/
├── conftest.py            skips everything unless SHACKLES_PROBES=1 and `claude` is on PATH
├── live_agent.py          the adapter that spawns one real agent per prompt
├── live_driver.py         a driver loop over run.py using live_agent for spawns
├── fixtures/
│   ├── ambiguous_spec/    a SPEC.json/SPEC.md pair with one sentence two implementers would read differently
│   ├── out_of_spec_impl/  an implementation diff that adds a function the spec never named
│   ├── uncovered_component/ a spec with three components and tests covering two
│   ├── bad_suite_choice/  a SUITE.json archiving the only regression test of a landed bug
│   └── postmortem_trace_gap/ a POSTMORTEM.md whose issue #2 names no plan line
└── test_probe_gates.py    one test per fixture
```

## `live_agent.py`
- `class LiveAgent`: `__init__(self, rung_key: str, role: "work"|"gate", cfg, roster,
  harness_root: Path)`.
- `run(self, prompt_file: Path, cwd: Path, timeout_s: int) -> tuple[dict, dict]` —
  runs `claude -p --output-format json --model <roster model> --agent
  <definition_name> --permission-mode <acceptEdits|plan for gate>` with the prompt text
  on stdin, parses the JSON envelope, returns `(final_message_json, usage)`; raises
  `ProbeError` on non-JSON or timeout. Usage columns map to the S1 `usage` keys.

## `live_driver.py`
- `run_round(repo: Path, plan: dict, answers: dict, mode: "delegate", max_attempts:
  int, agent_for: Callable[[str, str], LiveAgent]) -> State` — `start`; performs the
  CHAT-TO-PLAN driver step by writing the given plan; `owner delegate` with a quote
  first appended to OWNER.log by the test (through `hook prompt` with a fake stdin);
  loops `next`/spawn/`record --tokens-…` until `ended` or a pause or `max_attempts`.
- `plant(repo: Path, fixture: Path) -> None` — copies the fixture's files into the
  worktree at the step the fixture names (`fixture/PLANT.json`: `{"before_step":
  STEP, "files": {...}}`), so the gate judges the planted artifact instead of a real
  producer's.

## `test_probe_gates.py` (each marked `probe`, rung `cfg.systemTestAgent`)
- `test_plan_to_spec_gate_fails_ambiguity` — plant `ambiguous_spec`; assert the
  PLAN-TO-SPEC gate's verdict is FAIL and at least one finding quotes the planted
  sentence (substring after `normalize`).
- `test_implementation_gate_fails_out_of_spec` — plant `out_of_spec_impl`; assert FAIL
  with a finding quoting the extra function's name.
- `test_tests_gate_fails_uncovered_component` — plant `uncovered_component`; assert
  FAIL and a finding naming the third component.
- `test_suite_gate_fails_bad_archive` — plant `bad_suite_choice`; assert FAIL.
- `test_postmortem_gate_fails_trace_gap` — plant `postmortem_trace_gap`; assert FAIL
  and the finding references issue 2.
- `test_clean_fixture_passes` — no defect planted on a minimal real plan; assert the
  round reaches `CHECKPOINT-2` or `ended` without a FAIL verdict, and that the ledger
  shows every attempt `measured=True`.

Pass criteria are on S7 fields only (verdict, quotes), never on wording.

## Invariants
- A probe never touches the real repository: each builds a temporary clone with a bare
  remote exactly like `tests/conftest.py::repo`.
- Probes are budget-capped: `live_driver.run_round` stops after `max_attempts` (default
  6) and the test fails with the bill printed.

## Covered by
Themselves; `tests/test_repo_scaffold.py::test_probes_excluded_from_default_run`
asserts the pytest config and `verifyCommand` default ignore `tests/probes`.
