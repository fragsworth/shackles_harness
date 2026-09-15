# 11 — Tests, part 2: units for files 05–07, integration rounds, docs checks, live probes

Parent: [`../SPEC.md`](../SPEC.md). Part 1 (infrastructure, files 01–04) is
[`10-tests-infra-and-units.md`](10-tests-infra-and-units.md). Same conventions: one file
per module, cases listed as *case → assertion*, fixtures from `conftest.py`.

## Unit test files (files 05–07)

**test_results.py** — `extract_json`: pure JSON, fenced block, prose before and after,
two objects (last wins), none → ResultError · `parse_producer` missing status → error listing
it; unknown keys ignored · `validate_producer`: NEEDS-OWNER without questions; BLOCKED without
narrow; response to unknown finding; missing response to an open blocking finding; dispute on
a settled finding; option keys not single letters · `parse_gate`/`validate_gate`: verdict
case-sensitive; disputed finding without ruling; finding lacking suggestion; duplicate ids ·
`example_*` parse back as valid results · `schema_text` names every field.

**test_findings.py** — ids assigned F1, F2 across two gate attempts · resolved then not
re-raised stays resolved · resolved then re-raised reopens with the same id (matched by
normalised quote) · dispute → withdrawn · dispute → upheld once (open, count 1) → upheld
twice (settled) → a third dispute is refused by `apply_responses` · repeat of a withdrawn
quote → dropped with a note naming both ids · PASS with findings → all flagged, blocking
False, note · FAIL with no blocking → all blocking, note · `flags_from` format · `views`
sets `needs_response` only for open blocking/settled · `to_findings_file` shape equals 8.9.

**test_verify.py** — `test_command` for both modes includes `-m "not live"` and every
`testPaths` entry · `run_tests` passing suite ok; failing suite `ok=False` with tail; sleep
past a 1-second timeout → `timed_out` · `artifacts_present` names each missing artifact by
its `roundPaths` name · `artifacts_parse`: bad PLAN.json, AGENTS-PLAN.json, SPEC.json,
SUITE.json, POSTMORTEM.md without Summary → one problem each · `no_markers` finds `<<<<<<<`
· `for_step` DONE runs tests per `step.verify`; NEEDS-OWNER runs none.

**test_suite.py** — `test_functions` finds functions, methods, decorated tests, skips
helpers · `new_this_round` ignores a test moved between files and finds an added one ·
`load_suite_json` shape errors · `check_decisions`: missing test, unknown test, duplicate ·
`archive` cuts a decorated function including decorators, appends to
`tests-archive/tests/test_x.py`, leaves the rest byte-identical, deletes a now-empty file
created this round, keeps a pre-existing file even when empty of tests.

**test_tokens.py** — `estimate("")==0`, 4 bytes → 1, 5 bytes → 2 with `tokenBytes=4`,
multibyte text counts bytes · `file_tokens` missing → 0.

**test_pricing.py** — `price_usage` arithmetic against hand-computed values for the two
generated rungs · `estimate_usage` uses `estOutputFraction` · `attempt_cost` measured when
usage present, estimated otherwise, zero usage → estimated.

**test_quote.py** — `load_plan` shape; `plan_problems` unanswered question and quote not
in log · `load_agents_plan` shape · `lint_agents_plan`: each enforced error one at a time;
each advisory warning; clean plan → no errors · `default_plan` matches `defaultShares` ·
`budget_for` share × quote, None when unknown · `rung_for` fallbacks · `helpers_for` cap.

**test_ledger.py** — `price_tokens` below, at, and above the cap · `living_charge`: new
file (base + tokens); deleted file (refund); grown file; pure rename → 0; rename + edit →
delta only; file outside living paths ignored; carry-forward file priced at the flat rate;
tests joined and left; test moved between files → 0; total negative when the tree shrinks ·
`archive_charges` with and without each file · `summary_section` extracts up to the next
`## ` · `book_attempt`/`book_driver_step`/`round_spend` sums · `make_bill` totals and the
POSTMORTEM never-blocks note · `remaining_project` subtracts complete and abandoned rounds
only.

**test_round.py** (unit level; the integration file below drives whole rounds) — `start`
refusals one at a time: drift, missing baseline, unknown config key, stale agent defs, empty
OWNER.log, no remote, steps lint error, doctor error · `start` picks id = max+1 across
remote round branches and landed folders · second `start` on a claimed id → retries id+1 once
then LockLost · `next` idempotent while an attempt is open · `record` wrong attempt name →
refused · `owner` quote not in log → refused · `judgment` with no open attempt → refused ·
every state change leaves the remote round branch at the local tip (fence) · a foreign push
to the round branch → next state change raises LockLost and writes nothing.

**test_cli.py** — every subcommand parses; `--json` shapes; exit codes 0/1/2/3/4 mapped from
`HarnessError.code` · `record --result FILE` copies into the result file · `hook prompt`
reads stdin and always exits 0 even on a broken payload · `hook session-start` prints the
staleness line · `accept-spec` requires `--quote` and refuses while a round is active ·
`abandon` is an alias of `owner --kind abandon`.

---

## test_integration.py — whole rounds with the stub agent

Every case builds a repo, scripts the stub, runs `driveloop.drive`, and asserts on the
`next` sequence, `STATE.json`, `HISTORY.md`, git and the bill. Gates all on unless said.

1. **Happy path, approve mode** — every step in table order; checkpoints pause twice and
   resume on "approved"; landing fast-forwards main; POSTMORTEM and CLEANUP land through sync;
   worktree removed; `done` carries bill, flags, postmortem summary; `project.remaining`
   reflects the bill; every attempt has PROMPTS/RESULTS files; each gate has a FINDINGS file.
2. **Delegate mode** — no checkpoint pause; a NEEDS-OWNER still pauses; a BLOCKED still pauses.
3. **Delegate through PLAN-TO-SPEC** — CHECKPOINT-1 skipped, CHECKPOINT-2 pauses.
4. **Override** — `--skip-gate SPEC-TO-TESTS-GATE` and `--skip-step POSTMORTEM`: no gate
   attempt for that step, POSTMORTEM marked skipped with the quote; overriding CHAT-TO-PLAN
   refused.
5. **Gate FAIL then PASS** — retry attempt prompt lists the finding with "needs response";
   producer resolves; PASS; findings file states; gate_rejections == 1.
6. **Gate turns limit** — three FAILs → pause `limit` (gate-turns); `resume` counts a restart;
   second restart beyond `maxRoundAttempts` → pause again; `--force-restart` proceeds.
7. **Dispute lifecycle** — dispute → upheld → dispute → upheld → settled; third dispute refused
   at record with the reason text; repeat-of-withdrawn dropped.
8. **Verdict wins** — PASS with findings → flags shown in the next checkpoint prompt file and
   marked shown; FAIL with none blocking → all blocking in FINDINGS.
9. **Strays** — stray edit reverted and HISTORY notes the path; spec-file edit reverted;
   STATE.json edit → record refused; truncated judgment file → refused.
10. **Frozen tests** — SPEC-TO-IMPLEMENTATION editing a test file → reverted; breaking the
    suite → record refused with the tail, same attempt handed out again, `refused == 1`, cost
    booked twice.
11. **Questions** — NEEDS-OWNER from PLAN-TO-SPEC: pause `questions`; `owner --kind answer
    --question 1 --quote "1. b"`; the retry prompt contains the answer verbatim.
12. **Landing conflict** — foreign commit on main touching the same file; conflict attempt
    spawned with declared = that file; `conflict_leave_markers` → judged with a problem →
    `LANDING-2`; `conflict_resolve` → main pushed; a stray in the conflict attempt reverted.
13. **Landing hard stop** — huge living diff → pause `hard-stop` before main is touched;
    `owner --kind hard-stop-multiple --value 50` resumes and lands.
14. **Post-landing sync conflict** — foreign edit to docs/TODO.md after landing → pause
    `sync-conflict`; nothing on main changed; `sync` after manual resolution completes.
15. **TESTS-TO-SUITE** — `suite_split`: archived functions appear under `tests-archive/`,
    absent from the suite, suite still passes, `tests_joined` counts only suite ones;
    `suite_incomplete` → refused.
16. **Ledger** — hand-computed bill for a scripted diff equals `bill.total`; a rename is free;
    a removal credits; measured usage on one attempt appears as `measured: true`.
17. **Abandon** — mid-round `abandon`: phase abandoned, only the round folder on main, branch
    kept on remote, bill without living charge, `remaining_project` subtracts it.
18. **Turn and wall-clock limits** — `maxTurnsPerRun` small → pause; clock advanced past
    `maxRunWallClockHours` while paused → no limit; advanced while active → limit.
19. **Two runners** — a second checkout claims the next id while the first is open; both
    complete; ids differ; neither observed a LockLost.
20. **Prompt hygiene** — every prompt handed out contains no unresolved token and ends with
    the STEP-END text; a prose file edited mid-round (uncommitted in the control checkout)
    does not change prompts (they render from the worktree's committed prose).
21. **CHAT-TO-PLAN order** — plan recorded → gate → `next` says `approval` → "approved" →
    step accepted; unanswered question in PLAN.json → record refused.
22. **Idempotent driver** — calling `next` twice, or `record` after a crash-and-retry, never
    creates a second attempt.

---

## test_docs.py — docs stay true to the code

- `docs/PROCESS.md` contains the step table generated from `steps.TABLE` verbatim.
- `docs/PROCESS.md` and `README.md` contain the driver loop block verbatim (single source:
  a constant in `doctor.py`).
- `docs/PROCESS.md` lists every `control.KINDS` entry and every pause reason.
- `docs/MONEY.md` names only config keys that exist.
- `docs/TESTING.md` lists every `stub_agent.BEHAVIOURS` name.
- `INDEX.md` equals `doctor.index_text()`.
- `harness/CLAUDE.md` is a symlink to `AGENTS.md`.
- No file under `docs/` exceeds its stated token target (targets are constants in the test).

---

## probes/ — live tests with real agents (opt-in)

Skipped unless `SHACKLES_LIVE=1`. Marked `live`. Each probe spawns a real agent of the
`systemTestAgent` rung through `probes/live_agent.py`, a subprocess wrapper around the
Claude Code CLI in print mode (`claude -p --output-format json --model <model>`; command
overridable with `SHACKLES_LIVE_CMD`) (JC-40). Each probe plants one defect and asserts the
agent's *mechanical* behaviour, never its wording:

- **test_probe_gate_catches_planted_defect.py** — a SPEC.json with a contradictory
  sentence; the PLAN-TO-SPEC gate returns FAIL and at least one finding quotes text that
  exists in the artifact.
- **test_probe_gate_rules_on_dispute.py** — a disputed prior finding; the gate result has a
  ruling for it before any new finding.
- **test_probe_producer_json.py** — a producer prompt from the real prose; the final
  message yields a parseable, valid result.
- **test_probe_judgment_tool.py** — the producer is told about the judgment tool; when its
  prompt plants an undefined judgment call (a missing input), a line appears in
  `UNDEFINED_JUDGMENT_CALLS.md` or in the final message's `judgment_calls`.
- **test_probe_stray_discipline.py** — the prompt declares only the round folder; the
  attempt's worktree has no changes outside it (or, if it does, `record` reverts them and
  the round proceeds).

Probes print their cost estimate and are budgeted by `systemTestAgent` prices; they are
never run in CI.
