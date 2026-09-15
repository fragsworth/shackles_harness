# 70 — Contracts shared across components

Parent: `SPEC.md` §5. The small data shapes that cross component boundaries.
Each shape is *owned* by one module (named in brackets), which holds its
validator; every other component only reads or builds instances. This file
documents them so a reader of any component file can see what it exchanges.
`docs/CONTRACTS.md` is the agent-facing copy of the JSON ones.

## 1. CLI conventions [cli.py]

- stdout: exactly one JSON object per invocation. stderr: human lines.
- exit 0 ok; 2 refused: `{"refused": "<reason>", "details": {...}}`; 1 crash.
- All paths in outputs are absolute. All times UTC ISO-8601. Money as floats.

## 2. `next` actions [engine/advance.py]

```json
{"action": "SPAWN", "attempt": "PLAN-AGENTS-1", "step": "PLAN-AGENTS",
 "role": "producer|gate|conflict", "phase": "work|step-end",
 "agent": "shackles-max", "rung": "max", "readOnly": false,
 "promptFile": "/abs/.../PROMPTS/PLAN-AGENTS-1.txt",
 "resultFile": "/abs/.../RESULTS/PLAN-AGENTS-1.json",
 "worktree": "/abs/.../.worktrees/0001-PLAN-AGENTS-1", "budgetUsd": 12.5,
 "then": "python /abs/harness/src/run.py record PLAN-AGENTS-1 --tokens <N>"}

{"action": "SELF", "attempt": "CHAT-TO-PLAN-1", "step": "CHAT-TO-PLAN",
 "promptFile": "...", "resultFile": "...", "writes": ["/abs/.../PLAN.json"],
 "then": "owner verbs, then record CHAT-TO-PLAN-1"}

{"action": "OWNER", "reason": "CHECKPOINT|QUESTIONS|NEEDS-OWNER|BLOCKED|LIMIT|HARD-STOP|LEASE|VERIFY|SYNC",
 "attempt": "...|null", "message": "<relay verbatim>", "items": ["..."],
 "questions": [{"n": 1, "text": "...", "options": {"a": "...", "b": "..."}}],
 "accepts": ["approve", "delegate", "override", "answer", "abandon", "resume"],
 "promptFile": "<checkpoint prompt for the driver, when reason is CHECKPOINT>"}

{"action": "END", "round": "0001", "outcome": "landed|abandoned", "totalUsd": 123.4}
```

## 3. Final messages [round/results.py]

Producer (and conflict attempt):
```json
{"status": "DONE|NEEDS-OWNER|BLOCKED", "summary": "one paragraph",
 "questions": [{"n": 1, "text": "...", "options": {"a": "...", "b": "..."}}],
 "narrow": "what to narrow (BLOCKED)",
 "resolved": [{"finding": "F1", "how": "..."}],
 "disputes": [{"finding": "F2", "argument": "..."}],
 "flags": ["for the owner at the next pause"],
 "judgmentCalls": [{"kind": "defined|undefined", "text": "one line"}],
 "subAgentsUsed": 0}
```
Gate:
```json
{"verdict": "PASS|FAIL", "summary": "...",
 "rulings": [{"finding": "F2", "ruling": "upheld|withdrawn", "quote": "..."}],
 "findings": [{"id": "F3", "quote": "<artifact text judged>", "text": "...",
               "suggestion": "what would prevent the FAIL", "blocking": true,
               "forOwner": false, "repeats": "F1"}],
 "judgmentCalls": [...]}
```
Driver (CHAT-TO-PLAN, checkpoints):
```json
{"status": "DONE", "summary": "...", "shownItems": ["..."], "judgmentCalls": [...]}
```
Step-end follow-up (only in `follow-up` delivery): `{"judgmentCalls": [...]}`.

## 4. Artifacts [round/artifacts.py]

- `PLAN.json`: `title, scope, nonGoals[], assumptions[], validationSteps[],
  todosAccepted[], questions[{n,text,options,answerQuote}], quote{total,
  agentsUsd, livingUsd, archiveUsd, driverUsd, notes}, refactorUsd?,
  ownerQuotes[]`.
- `AGENTS-PLAN.json`: `steps{STEP:{agent,subAgents,share,note}},
  gates{STEP:{agent,share,note}}`.
- `SPEC.json`: `summary, components[{name,text,paths[],tests[]}],
  implementationSteps[{n,text,component}], testPlan[], integrationTests[],
  nonGoals[], refactor{text,estimatedUsd}`; `SPEC.md` is free prose.
- `SUITE.json`: `tests{"file::function": "suite|archive"}, flags[]`.
- `POSTMORTEM.md`: prose; first section heading `## Summary` (priced).
- `FINDINGS/<attempt>.json` [round/findings.py]: `attempt, gateAttempt,
  verdict, findings[Finding], rulings[], summary, notes[]` with `Finding =
  {id, quote, text, suggestion, blocking, forOwner, state, upheldCount,
  raisedIn, repeats}`.

## 5. `STATE.json` [round/state.py]

The fields of `34-src-round.md`, `schema: 1`. Ledger block
[ledger/ledger.py]: `entries[{at, kind, attempt, step, usd, usage{inputTokens,
outputTokens, cacheReadTokens, cacheWriteTokens, source}, note}], booked{...}
| null, total`.

## 6. Read-only views [round/state.py builds; prompts/ consumes]

- `RoundView(id, folder_rel, base_commit, plan_text, budget, spend, remaining,
  gates_line, steps_done[], calls_defined[], calls_undefined[], owner_items[])`.
- `AttemptView(id, step, role, rung, worktree, inputs[{key, path}],
  artifact_paths[], declared_paths[], budget_usd, turn, max_turns,
  sub_agents, verify_rule, timeout_s, prior_findings_path, resolved_path,
  disputes_path, run_py_path, conflicted[], auto_merged_commit)`.

## 7. Prompt tokens [prompts/tokens.py]

`{{ prose.STEM }}`, `{{ project.key }}` (+ `remaining`, `gates`),
`{{ round.id|folder|base_commit|plan|budget|spend|remaining }}`,
`{{ plumbing.PROCESS-INSTRUCTIONS|GATE-PROSE }}`, `{{ agents.SLUG }}`.
Unknown tokens stay verbatim and are named.

## 8. Owner log lines [round/owner_log.py; written by agents/hooks.py]

`{"ts": "...", "session": "...", "text": "..."}` — one JSON object per line,
both in `harness/OWNER.log` and in the round's `OWNER.log` slice.

## 9. Judgment-call lines [round/judgment_calls.py]

`- <UTC> [<attempt>] <one line>` appended to `DEFINED_JUDGMENT_CALLS.md` or
`UNDEFINED_JUDGMENT_CALLS.md`.

## 10. Commands' outputs [commands/*]

`start` -> `{round, branch, baseCommit, folder}`; `record` -> `{attempt,
status, cost{usd, source}, notes[], next}`; `owner` -> `{verb, phase, pause,
next}`; `judgment` -> `{appended}`; `doctor` -> `{problems[], warnings[],
notes[], ok}`; `setup` -> `{agents[], hooksInstalled, local, restartSession}`;
`accept-spec` -> `{accepted[], changed[]}`; `status` -> the state summary.
