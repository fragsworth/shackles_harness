# 08 — File formats: the round folder and every JSON the runner reads or writes

Parent: [`../SPEC.md`](../SPEC.md). This file is the single reference for the shape of
every file under a round folder. Loaders live in the modules named beside each format;
nothing here is code. All JSON is UTF-8, `indent=1`, keys in the order shown, trailing
newline. Paths in JSON are harness-relative unless said otherwise.

## 8.1 The round folder

Layout is read from `project.yaml roundPaths`; names below are today's values.

```
archives/rounds/NNNN/
  STATE.json                     runner   the only runner state (8.2)
  HISTORY.md                     runner   append-only log (file 03, history.py)
  OWNER.log                      runner   this round's slice of the owner's words (file 03)
  PLAN.json                      driver   CHAT-TO-PLAN (8.3)
  AGENTS-PLAN.json               producer PLAN-AGENTS (8.4)
  SPEC.json / SPEC.md            producer PLAN-TO-SPEC (8.5)
  SUITE.json                     producer TESTS-TO-SUITE (8.6)
  POSTMORTEM.md                  producer POSTMORTEM (8.7)
  DEFINED_JUDGMENT_CALLS.md      agents   one line per call, appended (8.8)
  UNDEFINED_JUDGMENT_CALLS.md    agents   same
  PROMPTS/<attempt>.txt          runner   the rendered prompt, verbatim as handed over
  PROMPTS/<attempt>-END.txt      runner   the rendered COMMON-STEP-END
  RESULTS/<attempt>.json         driver   the agent's final message, as saved (raw or JSON)
  FINDINGS/<STEP>-<n>.json       runner   the gate's verdict on producer attempt n (8.9)
  tests-archive/<path>.py        runner   archived test functions, moved by the runner
```

The runner-only files (`STATE.json`, `HISTORY.md`, `OWNER.log`, `PROMPTS/`, `FINDINGS/`)
are refused if a producer changes them (file 04, triage). Everything else in the folder
may be written by the attempt the file belongs to.

## 8.2 STATE.json

```json
{"schema": 1,
 "round": {"id": "0007", "folder": "archives/rounds/0007/", "branch": "round/0007",
           "worktree": "/abs/harness/.worktrees/round-0007", "base_commit": "<sha>",
           "started_at": "2026-09-15T10:00:00Z", "phase": "active", "pushed_sha": "<sha>"},
 "pause": null,
 "owner": {"decisions": [{"kind": "approve", "quote": "approved", "log_line": 12, "ts": "...",
                          "through_step": null, "skip_steps": [], "skip_gates": [], "question": null, "value": null, "reason": null}],
           "log_first_line": 9, "mode": "approve", "through_step": null,
           "skip_steps": [], "skip_gates": [], "hard_stop_multiple": 5},
 "steps": {"CHAT-TO-PLAN": {"status": "accepted", "producer_attempts": 1, "gate_attempts": 0,
                            "gate_rejections": 0, "accepted_attempt": "CHAT-TO-PLAN-1", "note": ""},
           "PLAN-AGENTS": {"status": "active", "...": "..."}},
 "open_attempt": {"name": "PLAN-AGENTS-1", "step": "PLAN-AGENTS", "role": "producer",
                  "agent_definition": "shackles-max", "rung": "max", "started_at": "...",
                  "budget_usd": 3.0, "prompt_file": "archives/rounds/0007/PROMPTS/PLAN-AGENTS-1.txt",
                  "result_file": "archives/rounds/0007/RESULTS/PLAN-AGENTS-1.json", "prompt_tokens": 4100, "refused": 0},
 "attempts": [{"name": "CHAT-TO-PLAN-1", "step": "CHAT-TO-PLAN", "role": "driver-plan", "rung": "max",
               "started_at": "...", "recorded_at": "...", "status": "DONE", "usd": 0.0, "measured": false,
               "refused": 0, "summary": "..."}],
 "findings": {"PLAN-TO-SPEC": []},
 "questions": [], "flags": [],
 "counters": {"turns": 2, "restarts": 0, "active_seconds": 900},
 "landing": null,
 "bill": null}
```

`bill` (filled by `ledger.make_bill`):
```json
{"quote": 100.0, "attempts": 41.2, "driver": 9.0,
 "living": {"usd": 12.5, "files": [{"path": "src/x.py", "before_tokens": 0, "after_tokens": 300, "usd": 85.0, "kind": "living"}],
            "tests_joined": 4, "tests_left": 0},
 "archive": {"plan": 2.1, "spec": 6.3, "postmortem_summary": 0.9},
 "total": 72.0, "over_quote_by": 0.0, "note": ""}
```

## 8.3 PLAN.json (written by the driver; loader `quote.load_plan`)

```json
{"plan_md": "the plan in plain English, what the owner reads and approves",
 "quote_usd": 100.0,
 "scope": ["..."], "non_goals": ["..."], "assumptions": ["..."], "validation_steps": ["..."],
 "questions": [{"n": 1, "text": "...", "options": {"a": "...", "b": "..."}, "answer_quote": "1. b"}],
 "todos_accepted": ["text of accepted TODO lines"],
 "refactor_fraction": 0.1,
 "living_charge_estimate_usd": 15.0, "archive_cost_estimate_usd": 8.0}
```
Required: `plan_md` non-empty, `quote_usd > 0`, every question has a non-null
`answer_quote` (verified against the round's OWNER.log at record: "no round starts with
unanswered questions"). `round.plan` renders `plan_md`.

## 8.4 AGENTS-PLAN.json (loader `quote.load_agents_plan`)

```json
{"steps": {"PLAN-TO-SPEC": {"agent": "max", "sub_agents": 0, "share": 0.10, "notes": ""},
           "SPEC-TO-TESTS": {"agent": "high", "sub_agents": 1, "share": 0.15, "notes": ""}},
 "gates": {"PLAN-TO-SPEC": {"agent": "max", "sub_agents": 0, "share": 0.06, "notes": ""}},
 "refactor_share": 0.1,
 "rationale_md": "why these choices"}
```
Keys are step names (gates keyed by the step they judge). Lint rules: file 06.

## 8.5 SPEC.json and SPEC.md (loader `verify.artifacts_parse` → `spec_loader` in `verify.py`)

`SPEC.md` is free prose for the owner. `SPEC.json` is the machine-read companion:
```json
{"components": [{"id": "C1", "name": "...", "description_md": "...", "paths": ["src/x.py"], "test_plan_md": "..."}],
 "steps": [{"id": "S1", "component": "C1", "description_md": "..."}],
 "test_plan_md": "high-level test plan covering the whole implementation",
 "integration_tests_md": "...",
 "non_goals": ["carried from the plan"],
 "refactors": [{"description": "...", "estimated_fraction": 0.05}]}
```
Required: ≥ 1 component; `test_plan_md` non-empty; `non_goals` present (may be empty only
if the plan's were). Sum of `refactors[].estimated_fraction` > `maxRefactorOverhead` is a
HISTORY warning, not a refusal (advisory).

## 8.6 SUITE.json (loader `suite.load_suite_json`)

```json
{"tests": [{"file": "tests/test_x.py", "name": "test_foo", "decision": "suite", "reason": "..."},
           {"file": "tests/test_x.py", "name": "test_bar_slow", "decision": "archive", "reason": "..."}],
 "flags": ["middle ground worth raising: ..."]}
```
Every test new this round appears exactly once. `flags` become owner flags.

## 8.7 POSTMORTEM.md

Markdown. The first heading must be `## Summary`; its section is what the runner charges
at `postMortemCostPerSummaryToken` and shows the owner at round end. Later sections are
free; the producer's edits to `docs/TODO.md` and `docs/CLARIFICATIONS.md` carry the
decisions forward (formats in file 09).

## 8.8 Judgment-call files

One line per call: `- [<attempt>] <text>`. The runner writes a one-line header on start
(`# Defined judgment calls, round NNNN` / `# Undefined ...`) and refuses any change that is
not an append (file 04, triage). Gate calls are appended by the runner from the gate's
final message with the gate attempt name.

## 8.9 FINDINGS/<STEP>-<n>.json (writer `findings.to_findings_file`)

```json
{"gate_attempt": "PLAN-TO-SPEC-GATE-2", "producer_attempt": "PLAN-TO-SPEC-2", "verdict": "FAIL",
 "rulings": [{"finding": "F1", "ruling": "withdrawn", "quote": "..."}],
 "findings": [{"id": "F2", "state": "open", "blocking": true, "quote": "...", "text": "...", "suggestion": "...", "upheld_count": 0}],
 "notes": ["F4 dropped: repeats withdrawn F1", "blocking by verdict: F2"]}
```

## 8.10 local.yaml

Generated, gitignored, no user input (file 01, `localyaml.py`). YAML with the keys listed
there; agents may read it to learn absolute paths and which defaults are in force.

## 8.11 OWNER.log (root and round slice)

One JSON object per line: `{"ts": "...", "session": "...", "text": "..."}`. The round
slice carries an extra `"line": <root line number>` per entry so quotes can name their
source line. Never rewritten.
