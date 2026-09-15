# 00 — Cross-component contracts

This file holds the formats and conventions that more than one component reads or writes. Nothing here is code; each format is owned by exactly one module (named in each section), and every other module treats it as opaque data obtained through that owner's functions. `docs/FORMATS.md` ([09]) is the agent-facing copy of the same information.

## 0.1 CLI convention (owner: `run.py`, [02])

- Invocation: `python <harness>/src/run.py [--root PATH] [--human] COMMAND [options]`. `--root` is the harness root (directory containing `project.yaml`); default is the parent of `src/`. `--human` renders the JSON result as indented text; the JSON is still the contract.
- stdout: exactly one JSON object. On success `{"ok": true, "command": "...", ...}`. On failure `{"ok": false, "error": {"code": "...", "message": "...", "detail": {...}}}`.
- stderr: free-form diagnostics only.
- Exit codes: `0` ok · `1` unexpected exception · `2` refused (a precondition, validation or state rule stopped the command; nothing was changed) · `3` fence broken (the remote round branch moved under us; local state is stale) · `4` usage error (bad arguments).

## 0.2 Error taxonomy (owner: `shackles/errors.py`, [02])

`HarnessError(code: str, message: str, detail: dict = {}, exit_code: int = 2)` is the base. Subclasses, all with a fixed `code` string equal to the class name in kebab case:
`UsageError`(4) · `RefusedError`(2) and its children `ConfigError`, `StepTableError`, `ProseError`, `DriftError`, `OwnerLogError`, `QuoteNotFoundError`, `StateError`, `MessageError`, `ArtifactError`, `DecisionError`, `LimitError`, `GitError`, `SpawnError` · `FenceError`(3). Modules raise these; only `run.py` catches them.

## 0.3 Identifiers

- Round id: zero-padded decimal, width = number of `N` characters in `project.yaml` `roundPaths.folder` (`NNNN` → 4). Ids are allocated by [06] gitops from the maximum of existing round folders on `origin/<main>` and existing `shackles/round-*` remote branches, plus one.
- Round branch: `shackles/round-<id>`.
- Attempt ids: `<STEP>-<n>` for driver, producer and conflict attempts of a step (n from 1); `<STEP>-GATE-<n>` for gate attempts. The pair (attempt id) is unique within a round and never reused.
- Finding ids: `F-<STEP>-<k>`, k from 1 per step, assigned by [05] findings when a gate message is accepted.
- Question ids: integers from 1, global within the round, assigned by [05] state when questions are registered (the plan's questions first, then each NEEDS-OWNER set in order).
- Ledger entry ids: `L-<k>`, k from 1 per round.

## 0.4 Round folder layout (owner: `paths.RoundPaths`, [03]; file names come from `roundPaths` in `project.yaml`)

Using the current values: `archives/rounds/NNNN/` containing `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SPEC.md`, `SUITE.json`, `POSTMORTEM.md`, `STATE.json`, `HISTORY.md`, `OWNER.log`, `PROMPTS/<attempt>.txt`, `RESULTS/<attempt>.json`, `FINDINGS/<STEP>-<n>.json`, `tests-archive/<original relative path under the test path>`, `DEFINED_JUDGMENT_CALLS.md`, `UNDEFINED_JUDGMENT_CALLS.md`. Plus, not listed by the owner and written only by the runner: `PROMPTS/PAUSE-<k>.txt` and `PROMPTS/CHECKPOINT-<i>-<n>.txt` (driver-facing summaries, see 0.12). (JC-01)

## 0.5 `STATE.json` (owner: `state.py`, [05]) — the runner's only state

```
{
  "schema": 1,
  "round": {"id": "0007", "folder": "archives/rounds/0007/", "branch": "shackles/round-0007",
            "base_commit": "<sha of origin/main at start>", "created_at": ts, "approved_at": ts|null,
            "ended_at": ts|null, "worktree": "<absolute path>"},
  "status": "planning" | "awaiting-owner" | "running" | "paused" | "done" | "abandoned",
  "pause": null | {"kind": "checkpoint"|"needs-owner"|"blocked"|"limit"|"mechanical"|"hard-stop"|"drift"|"sync",
                   "reason": str, "step": str|null, "attempt": str|null, "questions": [int], "narrow": str|null,
                   "since": ts, "limit": str|null},
  "mode": {"delegation": "approve"|"delegate", "through": str|null},
  "overrides": {"steps": [str], "gates": [str]},
  "limit_overrides": {"<limit key>": number},
  "cursor": {"step": str, "phase": "produce"|"gate"|"await-owner"|"land"|"done", "step_index": int},
  "open_attempt": str|null,
  "attempts": [ {"id": str, "step": str, "kind": "driver"|"producer"|"gate"|"conflict", "n": int,
                 "judges": str|null, "agent": str|null, "opened_at": ts, "recorded_at": ts|null,
                 "status": "DONE"|"NEEDS-OWNER"|"BLOCKED"|"PASS"|"FAIL"|"INVALID"|"SKIPPED"|null,
                 "accepted": bool|null, "mechanical": [str], "strays": [str], "spend_usd": number|null,
                 "spend_source": "measured"|"estimated"|null, "prompt": str, "result": str|null,
                 "prompt_tokens": int, "warnings": [str]} ],
  "counters": {"turns": int, "restarts": int, "rejections": {"<STEP>": int}, "active_seconds": number,
               "active_since": ts|null},
  "plan": null | {"quote_usd": number, "text": str, "non_goals": [str], "validation_steps": [str]},
  "questions": [ {"id": int, "attempt": str, "text": str, "options": [{"letter": str, "text": str}],
                  "answer": null | {"quote": str, "at": ts}} ],
  "agents_plan": null | {"steps": {...}, "gates": {...}},
  "findings": [ {"id": str, "step": str, "raised_in": str, "judges": str, "quote": str, "text": str,
                 "suggestion": str, "blocking": bool, "state": "open"|"fixed"|"disputed"|"withdrawn"|"settled"|"note",
                 "upheld": int, "history": [{"at": ts, "by": str, "event": str, "note": str}]} ],
  "flags": {"pending": [{"attempt": str, "text": str}], "delivered": [{"attempt": str, "text": str, "at": ts}]},
  "decisions": [ {"kind": str, "quote": str, "at": ts, "targets": [str], "through": str|null,
                  "question": int|null, "limit": str|null, "value": number|null} ],
  "ledger": {"entries": [ {"id": str, "kind": "agent"|"helper"|"driver"|"living"|"archive"|"carry"|"adjustment",
                           "attempt": str|null, "usd": number, "source": "measured"|"estimated"|"computed",
                           "detail": {...}, "at": ts} ], "total_usd": number},
  "landing": null | {"main_before": sha, "landed": sha|null, "conflicts": [str], "sync_tries": int, "synced": bool},
  "suite_moves": [ {"from": str, "to": str, "attempt": str} ],
  "fence": {"remote_sha": sha|null},
  "owner_log": {"slice_from": ts}
}
```
Rules: written atomically (temp file + rename); every write is followed by a fence commit+push by the calling command; unknown top-level keys are preserved on load (forward compatibility, because rounds may modify the runner).

## 0.6 Final-message schemas (owner: `messages.py`, [05])

The agent's final message must be exactly one JSON object. The driver saves it unchanged to `RESULTS/<attempt>.json`.

Producer / driver / conflict attempts:
```
{"status": "DONE"|"NEEDS-OWNER"|"BLOCKED", "summary": str,
 "questions": [{"n": int, "text": str, "options": [{"letter": str, "text": str}]}],   // required non-empty iff NEEDS-OWNER
 "narrow": str,                                                                          // required iff BLOCKED
 "flags": [str], "resolutions": [{"finding": str, "resolution": "fixed"|"disputed", "note": str}],
 "judgment_calls": [{"kind": "DEFINED"|"UNDEFINED", "text": str}]}
```
Gate attempts:
```
{"status": "PASS"|"FAIL", "summary": str,
 "rulings": [{"finding": str, "ruling": "upheld"|"withdrawn", "quote": str}],
 "findings": [{"quote": str, "text": str, "suggestion": str, "blocking": bool}],
 "flags": [str], "judgment_calls": [{"kind": "DEFINED"|"UNDEFINED", "text": str}]}
```
Missing optional arrays default to empty. Extra keys are ignored. A message that is not a JSON object, or whose `status` is not allowed for the attempt kind, or that lacks a required field, is `INVALID` (mechanical rejection).

## 0.7 Artifact schemas (owner: `artifacts.py`, [05])

- `PLAN.json`: `{"text": str (plain-English plan), "scope": [str], "validation_steps": [str], "non_goals": [str], "assumptions": [str], "quote_usd": number > 0, "refactor_fraction": number in [0,1], "todos_accepted": [str], "questions": [{"n": int, "text": str, "options": [≥2 of {"letter", "text"}]}]}`.
- `AGENTS-PLAN.json`: `{"steps": {"<STEP>": {"agent": rung, "share": fraction, "helpers": [{"rung": rung, "count": int, "purpose": str}], "expected_retries": int}}, "gates": {"<STEP>": {"agent": rung, "share": fraction}}, "notes": str}`. Validation rules in [05] artifacts.
- `SPEC.json`: `{"summary": str, "components": [{"id": str, "name": str, "description": str, "files": [str]}], "implementation_steps": [{"id": str, "text": str, "components": [str]}], "test_plan": [{"id": str, "text": str, "components": [str], "kind": "unit"|"integration"}], "non_goals": [str], "refactors": [{"text": str, "share": fraction}], "validation_steps": [str]}`. `SPEC.md` is free prose for the owner.
- `SUITE.json`: `{"tests": [{"file": str, "name": str, "decision": "suite"|"archive", "reason": str}], "middle_ground_flags": [str]}`.
- `POSTMORTEM.md`: Markdown whose first heading is `Summary` (any level) followed by the summary; later sections are free.
- `DEFINED_JUDGMENT_CALLS.md` / `UNDEFINED_JUDGMENT_CALLS.md`: one line per call: `- [<attempt id>] <text>`; header line `# DEFINED JUDGMENT CALLS — round NNNN` written by the runner at start.

## 0.8 `FINDINGS/<STEP>-<n>.json` (owner: `findings.py`, [05]) — the gate's verdict on producer attempt n

```
{"step": str, "judges": "<STEP>-<n>", "gate_attempt": "<STEP>-GATE-<m>", "verdict": "PASS"|"FAIL", "summary": str,
 "findings": [ {finding record as in STATE.findings} ],       // all findings of this step with current state
 "dropped": [ {"quote": str, "text": str, "note": "repeats withdrawn <id>"} ],
 "rulings": [ {"finding": str, "ruling": str, "quote": str, "missing": bool} ],
 "resolutions_seen": [ {"finding": str, "resolution": str, "note": str} ],
 "mechanical": [str], "inputs": {"artifact": [str], "inputs": [str], "verify": null | {"passed": bool, "summary": str}} }
```
This file (not `RESULTS/`) is what the next gate and the next producer attempt are pointed at, so a gate never sees a producer transcript.

## 0.9 `HISTORY.md` (owner: `history.py`, [05])

Append-only Markdown. Entry kinds and their headings:
`## <ts> ATTEMPT <id> opened` (kind, agent, prompt path, prompt tokens, warnings) · `## <ts> ATTEMPT <id> recorded` (status, accepted, spend with source, strays reverted, mechanical notes, findings summary, flags, judgment-call counts, then the final message in a fenced `json` block) · `## <ts> OWNER <kind>` (verified quote in a blockquote, targets/through/question/limit) · `## <ts> RUNNER <event>` (pause, resume, skip, landing, conflict, sync, charges booked with breakdown, suite moves, drift, fence) · `## <ts> ROUND <status>`.

## 0.10 `OWNER.log` lines (owner: `hooks/owner_log.py` writes, `ownerlog.py` reads, [08]/[05])

JSON lines, one per owner prompt: `{"ts": ts, "session": str, "cwd": str, "prompt": str}`. The round's slice (`archives/rounds/NNNN/OWNER.log`) has the same format and contains every line with `ts >= STATE.owner_log.slice_from`.

## 0.11 `spec.baseline.json` (owner: `specfiles.py`, [03])

```
{"schema": 1, "files": {"<path relative to spec.yaml's dir>": "sha256:<hex>"},
 "accepted_commit": sha|null, "accepted_at": ts, "accepted_by": "owner-quote"|"by-owner-flag"|"bootstrap", "note": str}
```

## 0.12 `next` outputs (owner: `commands/next_.py`, [02])

`{"ok": true, "kind": K, ...}` where K is one of:
- `"none"` — no round exists; `hint: "run start"`.
- `"driver"` — the driver itself must do the step (CHAT-TO-PLAN): `attempt`, `prompt_file`, `result_file`, `artifact_file`, `worktree`.
- `"producer"` — spawn a read-write sub-agent: `attempt`, `step`, `agent` (`shackles-<rung>`), `read_only: false`, `prompt_file`, `result_file`, `worktree`, `budget_usd`, `warnings`.
- `"gate"` — spawn a read-only sub-agent: as above with `agent` = `shackles-<rung>-gate`, `read_only: true`, `judges`.
- `"checkpoint"` — stop and talk to the owner: `step`, `summary_file`, `flags`, `unblocks: ["approve", "delegate", "delegate-through", "abandon", "override"]`.
- `"owner"` — the round is paused: `pause` (as in STATE), `questions` (open, with ids and options), `flags`, `summary_file`, `unblocks`.
- `"done"` — the round ended: `status`, `total_usd`, `folder`.
All paths are absolute.

## 0.13 `local.yaml` (owner: `localcfg.py`, [03]) — generated, gitignored, no user input

```
generatedAt: ts
harnessRoot: /abs · repoRoot: /abs · specYaml: /abs
git: {remote: origin, remoteUrl: str, mainBranch: main}
python: {executable: str, version: str}
claude: {command: "claude", found: bool, version: str|null}
agentDefinitions: [relative paths]
specBaseline: {acceptedCommit: sha|null, drift: bool}
effectiveConfig: {<every registered key with its effective value>}
defaultedKeys: [str] · ownerLog: {path: str, entries: int}
```
Readers may use only `git.*` and `claude.command`; everything else is diagnostic.

## 0.14 Rendered prompt files (owner: `prompts.py`, [04])

`PROMPTS/<attempt>.txt` is UTF-8 plain text: the step's overview or gate prose fully rendered, with `{{ plumbing.* }}` tokens replaced by the generated mechanical instructions, followed by the rendered `COMMON-STEP-END` prose as the final section. The file is handed to the agent verbatim; nothing is added by the driver.
