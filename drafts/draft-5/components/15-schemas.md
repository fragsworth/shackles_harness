# 15 — Schemas (every shape the runner reads or writes)

**Purpose.** One place for data shapes so that any module can be rewritten against the
shape alone. Each shape names its writer and its readers. Field types use Python
notation; `iso` is an ISO-8601 UTC timestamp string; `sha` is a 40-hex git object id;
`usd` is a float rounded to 4 places when written.

Validation of these shapes is done by the component that reads them (`results.py`
for results, `state.py` for STATE, `config.py` for the YAML files); this file is the
contract, not code.

## S1. `STATE.json` — writer: `state.py` (08); readers: engine (10), prose (05), ledger (09), CLI (03)
```
{ "schema": 1,
  "round_id": "0007", "folder": "archives/rounds/0007/", "branch": "round/0007",
  "base_commit": sha,                      # origin/main at claim
  "fence": sha | null,                     # last commit known pushed
  "created_at": iso, "updated_at": iso,
  "status": "claimed"|"planning"|"running"|"paused"|"landing"|"ended",
  "ended": {"reason": "landed"|"abandoned"|"failed", "at": iso} | null,
  "mode": {"kind": "checkpoints"|"delegated", "through": STEP | null},
  "overrides": {"steps": [STEP], "gates": [STEP]},
  "hard_stop_multiple": float | null,      # per-round temporary override (raise-hard-stop)
  "owner_words": [ {"verb": str, "quote": str, "args": dict, "log_index": int, "at": iso} ],
  "answers": { "1": "verbatim quote", ... },
  "quote_usd": usd | null,                  # the plan's quote once recorded
  "agents_plan": { "source": "PLAN-AGENTS"|"default", "steps": {...}, "gates": {...} } | null,   # S3 body
  "steps": { STEP: { "status": "pending"|"active"|"accepted"|"skipped",
                     "attempts": [ S1.attempt ], "rejections": int, "accepted_at": iso|null } },
  "current": {"step": STEP, "attempt": int, "kind": "driver"|"producer"|"gate"|"conflict",
              "prompt": "PROMPTS/STEP-n.txt", "result": "RESULTS/STEP-n.json", "issued_at": iso} | null,
  "pause": {"kind": "approval"|"checkpoint"|"needs-owner"|"blocked"|"limit"|"fence"|"landing",
            "step": STEP, "detail": str, "log_index_at_pause": int, "since": iso} | null,
  "flags": [ {"text": str, "step": STEP, "attempt": int, "shown": bool} ],
  "findings": { STEP: [ S8.finding ] },
  "limits": {"attempts_total": int, "started_at": iso, "landing_tries": int},
  "landing": {"main_before": sha|null, "landed_commit": sha|null, "conflict_files": [str],
              "auto_merged_tree": sha|null, "synced_commit": sha|null},
  "ledger": S10 }
S1.attempt = {"n": int, "kind": ..., "rung": str|null, "prompt": str, "result": str|null,
              "status": "issued"|"recorded"|"rejected"|"accepted",
              "outcome": "DONE"|"NEEDS-OWNER"|"BLOCKED"|"PASS"|"FAIL"|"MALFORMED"|"MECHANICAL-FAIL"|null,
              "issued_at": iso, "recorded_at": iso|null,
              "usage": {"in": int, "out": int, "cache_read": int, "cache_write": int, "measured": bool} | null,
              "cost_usd": usd|null, "notes": [str]}
```

## S2. `PLAN.json` — writer: driver (CHAT-TO-PLAN); readers: prose (`round.plan`), ledger, engine
```
{ "text": str,                              # the plan in plain English (what the owner approved)
  "scope": [str], "non_goals": [str], "assumptions": [str], "validation_steps": [str],
  "quote_usd": usd, "living_charge_estimate_usd": usd,
  "questions": [ {"number": int, "text": str, "options": [{"letter": "A", "text": str}]} ],
  "accepted_todos": [str] }
```
Mechanical checks at record: `text` non-empty, `quote_usd > 0`, question numbers 1..n
contiguous. Answers live in STATE (`answers`), not here (JC-26).

## S3. `AGENTS-PLAN.json` — writer: PLAN-AGENTS producer; reader: `advance.py`, `plumbing.py`, `ledger.py`
```
{ "steps": { STEP: {"agent": rung, "share": float, "sub_agents": {"rung": rung, "max": int} | null} },
  "gates": { STEP: {"agent": rung, "share": float} },
  "rationale": str }
```
Keys of `steps` must be exactly the agent-run steps of the step table (05); keys of
`gates` exactly the gated steps. Shares sum to 1 per map (±0.001); gates that are off
(table value 0, or overridden) must be 0. Rungs must exist and rank ≤ `maxAgent`.

## S4. `SPEC.json` — writer: PLAN-TO-SPEC; readers: engine (paths), prose (inputs). Free-form except:
```
{ "summary": str, "non_goals": [str], "components": [ {"name": str, "description": str, "files": [str]} ],
  "test_plan": str, "integration_tests": [str], "edge_cases": [str] }
```
Only `summary` and `components[].files` are read mechanically (declared write paths for
SPEC-TO-IMPLEMENTATION are the living paths regardless; `files` is informative).

## S5. `SUITE.json` — writer: TESTS-TO-SUITE; reader: `suite.py`
```
{ "decisions": [ {"path": "tests/test_x.py", "function": str|null, "place": "suite"|"archive", "why": str} ],
  "flags": [str] }
```
`path` must be a file changed or added by this round under `testPaths`. `function` null
means the whole file. A file with mixed function decisions is split by `suite.py`
(archived functions removed from the suite copy; the archive copy keeps the whole file).

## S6. `POSTMORTEM.md` — writer: POSTMORTEM; reader: ledger (Summary tokens), CLI (owner text)
Markdown. The first heading must be `# Summary` or `## Summary`; the runner charges the
bytes from that heading to the next heading of the same or higher level.

## S7. Result file `RESULTS/STEP-n.json` — writer: driver (verbatim final message); reader: `results.py`
Producer / driver / conflict:
```
{ "status": "DONE"|"NEEDS-OWNER"|"BLOCKED", "summary": str,
  "artifacts": [str],                       # paths relative to the worktree
  "resolutions": [ {"id": "F3", "resolution": "fixed"|"disputed", "text": str} ],
  "flags": [str], "questions": [str], "narrow": str|null,
  "judgment_calls": [ {"kind": "defined"|"undefined", "text": str} ] }
```
Gate:
```
{ "status": "DONE", "verdict": "PASS"|"FAIL", "summary": str,
  "rulings": [ {"id": "F3", "ruling": "upheld"|"withdrawn", "quote": str} ],
  "findings": [ {"quote": str, "issue": str, "suggestion": str, "blocking": bool} ],
  "flags": [str], "judgment_calls": [ {...} ] }
```
Unknown extra keys are kept (written back into HISTORY) and ignored. Missing optional
lists default to `[]`. `MALFORMED` is any parse or required-field failure.

## S8. `FINDINGS/STEP-n.json` — writer: `findings.py`; readers: `plumbing.py` (rendered into retries)
```
{ "step": STEP, "gate_attempt": int, "verdict": "PASS"|"FAIL",
  "findings": [ S8.finding ], "dropped_repeats": [ {"quote": str, "repeats": "F2"} ] }
S8.finding = {"id": "F3", "raised_in": int, "quote": str, "issue": str, "suggestion": str,
              "blocking": bool, "status": "open"|"fixed"|"disputed"|"upheld"|"settled"|"withdrawn"|"closed",
              "upheld_count": int, "history": [ {"at": iso, "by": "gate-2"|"producer-3", "event": str} ]}
```

## S9. `OWNER.log` line (harness root and round slice) — writer: `hooks.py`; reader: `ownerlog.py`
One JSON object per line: `{"i": int, "ts": iso, "session": str, "kind": "prompt"|"marker", "text": str}`.
`i` is the 1-based line index, assigned on append. The round slice is the subset of lines
with `i` in the round's `[claim_index, end_index]`, copied byte-for-byte.

## S10. Ledger (embedded in STATE) — writer: `ledger.py`
```
{ "attempts": [ {"step": STEP, "n": int, "rung": str, "usd": usd, "measured": bool} ],
  "driver_steps": [ {"step": STEP, "usd": usd} ],
  "living": {"files": [ {"path": str, "before_tokens": int, "after_tokens": int, "renamed_from": str|null, "usd": usd} ],
             "tests": {"joined": int, "left": int, "usd": usd},
             "carry_forward": [ {"path": str, "delta_tokens": int, "usd": usd} ],
             "usd": usd } | null,
  "archive": {"plan": usd, "spec": usd, "postmortem_summary": usd} | null,
  "time_context_usd": usd,                   # elapsed hours × lostValuePerHour, not billed
  "total_usd": usd }
```

## S11. `MANIFEST.json` (spec baseline) — writer/reader: `specfiles.py`
`{"schema": 1, "accepted_at": iso, "files": {"<rel path>": {"sha256": hex, "bytes": int}}}`.

## S12. `local.yaml` — writer: `localyaml.py`; readers: hooks, doctor, status
```
generated_at: iso            repo_root: abs path        harness_root: abs path
python: abs path             git: {remote: origin, main_branch: main, main_url: str}
spec_baseline_sha256: hex    roster_sha256: hex          agent_defs_sha256: hex
owner_log: abs path          worktrees_dir: abs path
```
No value comes from a chat or a prompt; each is derived from the file system or git.

## S13. Agent definition `.claude/agents/shackles-<rung>-<role>.md` — writer: `agentdefs.py`
Front matter: `name: shackles-<rung>-<role>`, `description: <roster name>, <role>`,
`model: <roster model>`, `effort: <roster effort>`, and for `gate`: `tools: Read, Grep, Glob, Bash(git diff:*), Bash(git show:*), Bash(git log:*)`.
Body: one paragraph: "Follow the prompt you were given verbatim. Your final message must
be the JSON it names." and the stamp line `<!-- shackles:roster-sha256=<hex> -->`.

## S14. `HISTORY.md` entry — writer: `history.py`
```
## <iso> STEP-n <kind> <rung> — <outcome>
- cost: $x.xxxx (measured|estimated) · attempts so far: n · spend: $y
- notes: <one per line: strays reverted, repeats dropped, limits hit, owner verb>
- final message: ```json … ``` (verbatim)
```

## S15. Judgment-call line — writer: `judgmentcalls.py`
`- STEP-n (<rung>|driver|gate) <iso>: <text, newlines collapsed>` appended to
`DEFINED_JUDGMENT_CALLS.md` or `UNDEFINED_JUDGMENT_CALLS.md`.

## S16. `next` output (JSON when `--json`, else the same fields as labelled lines)
```
{ "action": "spawn"|"driver-step"|"pause"|"ended"|"refused",
  "step": STEP, "attempt": int, "kind": ..., "rung": str|null, "read_only": bool,
  "agent_definition": "shackles-max-gate" | null,
  "prompt_file": abs path, "result_file": abs path,
  "owner_text": str | null,               # for pause/ended: shown verbatim to the owner
  "reason": str | null }                  # for refused
```

## S17. `doctor` report (JSON with `--json`, else grouped lines)
`{"errors": [ {"area": str, "item": str, "detail": str} ], "warnings": [...], "rendered": {"<prompt name>": {"tokens": int, "unresolved": [str]}}}`.
Areas: `spec-files`, `config`, `roster`, `steps`, `prose`, `agent-defs`, `owner-log`, `git`, `hooks`.
