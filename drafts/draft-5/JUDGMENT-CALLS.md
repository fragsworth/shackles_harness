# Judgment calls — draft 5

Definition used (the owner's): a judgment call is any choice that lands in the
finished work that I am not confident in making correctly, for any reason.

## Classification scheme
Each entry carries three labels.
- **Kind** (the owner's own scheme from AGENTS.md): `DEFINED` — decidable from the spec
  files alone; `UNDEFINED` — needed knowledge outside them (platform behaviour, git,
  Claude Code, taste).
- **Cause**: `A` spec silent · `B` spec ambiguous or two passages pull apart ·
  `C` platform/tooling uncertainty · `D` structure/taste with several workable options ·
  `E` conservative safety choice.
- **Impact** if wrong: `high` (changes what the owner sees or what lands on main),
  `medium` (changes agent behaviour or billing), `low` (local, easy to change).

Format: **JC-nn — title** · Kind/Cause/Impact · *Affects:* spec section(s). Then: the
choice, the alternatives, why unsure.

---

**JC-01 — Repository layout** · DEFINED / D / high · *Affects:* SPEC.md §3, 01, 02, 04 `paths.py`
Chose: repo root holds `spec.yaml`, `SPEC.md`, `harness/`; harness root is `harness/`;
worktrees at `<repo>/.worktrees/round-NNNN`. Alternatives: harness root = repo root
with the spec files inside it; worktrees under `/tmp`. Why unsure: the restart folder
shows `spec.yaml` one level above `harness/`, but that may only be how the notes were
laid out, not the intended repo shape.

**JC-02 — Baseline shape and location** · DEFINED / A / medium · *Affects:* 02, 04 `specfiles.py`, 13 guard
Chose: `archives/spec-baseline/MANIFEST.json` (hashes) plus byte snapshots under
`files/` so the failing test can print a real diff. Alternatives: hashes only (no
diff); a recorded git commit as the baseline (fragile across history rewrites);
baseline at the harness root. Why unsure: the spec says "hashed baseline, failing test
with diff" but not where or how the diff is obtained.

**JC-03 — Language and dependencies** · UNDEFINED / C / medium · *Affects:* 02, 01
Chose: Python ≥ 3.11, PyYAML, pytest; no build step. Alternatives: stdlib-only with a
hand-written YAML subset; another language. Why unsure: AGENTS.md names `src/run.py`
(Python) but nothing fixes the version or the YAML library; the harness is meant to
develop "general software", so a language-neutral verify command matters more than
the runner's own language.

**JC-04 — CHAT-TO-PLAN has no gate** · DEFINED / B / medium · *Affects:* 05 `steps.py`, `plumbing.gate_prose_for`
Chose: the table says no gate (the owner approves the plan); `{{ plumbing.GATE-PROSE }}`
in its prose renders a fixed sentence. Alternatives: require `CHAT-TO-PLAN-GATE.txt`
(would refuse start today); treat the owner's approval text as the gate prose. Why
unsure: the step table lists `CHAT-TO-PLAN: 0` like gated steps and its prose mentions
"the gate that judges you", yet no gate prose file exists.

**JC-05 — LANDING conflict prompt without owner prose** · DEFINED / A / medium · *Affects:* 05 `assemble_prompt`, 10 `landing.py`
Chose: honour `LANDING-OVERVIEW.txt` if the owner adds one; otherwise concatenate the
rendered `COMMON-PROJECT`, `COMMON-ROUND`, `COMMON-OVERVIEW` and the mechanical
instructions. Alternatives: refuse to land on conflict until the owner writes prose;
invent runner text. Why unsure: the conflict attempt is required by SPEC.md but no
prose exists for it, and the runner must not author owner words.

**JC-06 — COMMON-STEP-END is appended to the prompt** · UNDEFINED / C / medium · *Affects:* 05 `assemble_prompt`, SPEC.md §5.4
Chose: append its rendering as the final section of every agent prompt. Alternative:
deliver it as a second message when the sub-agent returns (needs resuming a sub-agent,
which the Agent tool may not support). Why unsure: the prose says "this message is
produced at the end of every step", which reads like a separate message.

**JC-07 — OWNER.log format and quote rule** · DEFINED / A / high · *Affects:* 06 `ownerlog.py`, 10 `round_owner.py`
Chose: JSONL entries with index and timestamp; a quote verifies when its
whitespace-normalized text is a substring of an entry logged after the current pause
began; a log with only marker lines counts as present. Alternatives: plain text log
with exact substring; any entry at any time; require the entry to be the latest. Why
unsure: "verifies quotes against it" fixes neither normalization nor recency.

**JC-08 — Unknown config keys refuse start** · DEFINED / B / medium · *Affects:* 04 `config.py`, 10 `preflight`, 11
Chose: an unknown key in `project.yaml`/`subAgents.yaml` is an error (start refuses,
doctor errors). Alternative: warn only. Why unsure: "robust to arbitrary changes" pulls
toward tolerance; "each [setting] is used for something" pulls toward refusing.

**JC-09 — Five defaulted keys exist** · DEFINED / A / medium · *Affects:* 04 `config.py`, 09, 10 `verify.py`
Chose: `testPaths`, `verifyCommand`, `promptTokenWarning`, `gitRemote`, `mainBranch`
have code defaults and are named by doctor as defaulted. Alternatives: refuse to run
until the owner adds them (violates robustness); hard-code silently (violates the
settings-surface rule). Why unsure: project.yaml mentions "the spec's testPaths" and a
"prompt-size warning" without defining either.

**JC-10 — Agent definitions: two per rung, committed, stamped** · UNDEFINED / C / high · *Affects:* 06 `agentdefs.py`, 02, 01
Chose: `shackles-<rung>-work` and `shackles-<rung>-gate` (read-only tools) generated
from the roster, committed, stamped with the roster hash; `start` refuses when stale;
the session-start hook warns. Alternatives: gitignore them and generate at session
start (too late for the Agent tool); one file per rung with tools decided per call.
Why unsure: exact Agent-tool front-matter behaviour (`effort`, `tools`) is platform
knowledge that may change.

**JC-11 — local.yaml content** · DEFINED / A / low · *Affects:* 04 `localyaml.py`, S12
Chose: derived facts only (paths, remote, hashes, timestamp), gitignored, regenerated
by setup and the session-start hook. Alternative: no local.yaml at all. Why unsure:
the spec only says it is generated and holds no user input.

**JC-12 — A git remote is required** · DEFINED / E / high · *Affects:* 07, 10 `preflight`
Chose: start refuses without a remote; tests use a bare local remote. Alternative: fall
back to local branches as the lock. Why unsure: "git is the only lock" implies a shared
remote, but a solo owner might run without one.

**JC-13 — Claim mechanics** · UNDEFINED / C / high · *Affects:* 07 `claim_round`, 10 `start`
Chose: `--force-with-lease=refs/heads/round/NNNN:` (expect absent) as the CAS; on
rejection recompute the id (3 tries). Alternative: a plain push relying on
non-fast-forward rejection. Why unsure: relies on git's lease semantics for absent refs.

**JC-14 — Mechanical and malformed rejections count toward maxTurnsPerGate** · DEFINED / B / medium · *Affects:* 10 `round_record.py`
Chose: one counter per step (`rejections`) for gate FAILs, mechanical failures and
malformed results. Alternatives: separate counters; unbounded mechanical retries. Why
unsure: the key says "turns (rejections) per gate", which may mean gate verdicts only.

**JC-15 — maxRoundAttempts bounds landing/sync races** · DEFINED / B / medium · *Affects:* 10 `landing.py`, S1 `limits.landing_tries`
Chose: it bounds the fetch-merge-push loop. Alternatives: it bounds `start --restart`
of a failed round; it bounds fence recoveries. Why unsure: "attempts at restarting a
round after minor issues" is open to all three.

**JC-16 — maxTurnsPerRun counts attempts recorded** · DEFINED / B / low · *Affects:* 10 `round_next.py`
Chose: a turn is one attempt (any kind). Alternative: agent-internal turns (not
observable by the runner). Why unsure: "turns" is undefined.

**JC-17 — Usage reporting and estimate** · UNDEFINED / C / medium · *Affects:* 03 `record` flags, 09 `pricing.estimate_usage`
Chose: the driver passes the four token counts it observed as `record` flags; absent,
the runner estimates input = prompt tokens, output = `estOutputFraction` × input, cache
0; cost floored at `spawnCost`. Alternatives: usage inside the result file; always
estimate. Why unsure: what the Agent tool reports to the driver is platform-dependent.

**JC-18 — Carry-forward files always priced at the postmortem rate** · DEFINED / B / medium · *Affects:* 09
Chose: `docs/TODO.md` and `docs/CLARIFICATIONS.md` are excluded from the living charge
and billed at `postMortemFileCostPerToken` × token delta, no base cost, no cap.
Alternative: living rate for non-POSTMORTEM edits plus the special rate only for the
POSTMORTEM attempt's delta. Why unsure: both readings fit the comment.

**JC-19 — Archive charge bases** · DEFINED / A / low · *Affects:* 09 `archive_charges`
Chose: plan = all of `PLAN.json`; spec = `SPEC.json` + `SPEC.md`; postmortem = the
Summary section only. Alternative: plan `text` only; spec prose only. Why unsure: the
prose says "in the plan"/"in the spec" without naming files.

**JC-20 — Counting test functions per language** · UNDEFINED / C / medium · *Affects:* 09 `tokens.count_test_functions`
Chose: regex detectors for Python and JS/TS; other languages count 0. Alternative: a
pluggable detector configured in project.yaml (a new key). Why unsure: the harness
targets general software but the settings surface has no language key.

**JC-21 — Skip effects of overridden steps** · DEFINED / A / high · *Affects:* 05 `skip_effect`, 10 `advance.skip`
Chose: one fixed mechanical consequence per step (default agents plan, plan-is-spec,
no new tests, no code, all tests to suite, skip checkpoint, no postmortem, no cleanup
attempt); LANDING and CLEANUP's runner parts cannot be skipped. Alternative: refuse to
override producer steps. Why unsure: "override + steps or gates: the runner skips them"
gives no consequences.

**JC-22 — Abandoned rounds still land their archive folder** · DEFINED / A / medium · *Affects:* 10 `advance.end`, `landing.sync_archives_only`
Chose: merge only the round folder to main so the record and the id are kept.
Alternative: leave the branch and land nothing. Why unsure: "the round ends without
landing" could mean landing nothing at all.

**JC-23 — Strays in the driver's checkout are reported, never reverted** · DEFINED / E / medium · *Affects:* 10 `mechanical.py`
Chose: only the worktree's diff is reverted; the driver's checkout is inspected at
start only. Alternative: revert there too. Why unsure: the owner's own uncommitted
work lives in that checkout.

**JC-24 — Fast-forward the driver's checkout after a round** · DEFINED / A / low · *Affects:* 07, 10 `advance.end`
Chose: `merge --ff-only` when clean, else a note. Alternative: never touch it.

**JC-25 — INDEX.md is generated and committed** · DEFINED / D / low · *Affects:* 11 `index.py`, 02
Chose: generated from file headers, regenerated at CLEANUP, test-checked for currency.
Alternative: hand-maintained living file. Why unsure: AGENTS.md only says to grep it.

**JC-26 — Answers live in STATE, not in PLAN.json** · DEFINED / D / medium · *Affects:* S1 `answers`, S2, 10 `round_owner.answer`, 05 `round_values`
Chose: the runner stores each verbatim answer quote in `STATE.answers` and renders it
under the plan in `{{ round.plan }}`; the driver's artifact stays untouched.
Alternatives: the runner edits PLAN.json; a separate ANSWERS file in the round folder
(not in `roundPaths`). Why unsure: "STATE.json — the runner's only state" versus the
plan being "what the owner approved" including answers.

**JC-27 — The `continue` verb** · DEFINED / A / high · *Affects:* 10 `round_owner.py`, 03
Chose: one verb clears `needs-owner`, `blocked`, `limit`, `fence`, `landing` pauses,
resets the limit that fired, and carries the quote into the next prompt as owner
words. Alternatives: separate verbs per pause; require a new plan after BLOCKED. Why
unsure: the prose lists verbs only for the plan approval moment; nothing says how an
owner resumes after NEEDS-OWNER or a limit.

**JC-28 — Sub-agent limit is an instruction only** · DEFINED / A / low · *Affects:* 05 `process_instructions`
Chose: `maxSimultaneousSubAgentsPerRound` is rendered into the mechanical
instructions; the runner cannot observe nested spawns. Alternative: drop it from
prompts. Why unsure: no observable enforcement point exists.

**JC-29 — Time cost is context, not billed** · DEFINED / B / low · *Affects:* 09 `time_context`, S10
Chose: elapsed hours × `lostValuePerHour` is shown as a separate line and excluded
from `total_usd`. Alternative: add it to the total. Why unsure: the key's comment says
"for context", while the prose says "Costs, dollars, estimated, not real".

**JC-30 — Gate FAIL with no findings is malformed** · DEFINED / A / medium · *Affects:* 08 `normalize_gate`, 10
Chose: treat as malformed and re-spawn the gate (counted as a rejection). Alternatives:
accept as FAIL with a synthetic finding; treat as PASS. Why unsure: "every finding
carries a suggestion that would prevent the FAIL" implies a FAIL always has findings,
but the runner cannot invent one.

**JC-31 — Repeat detection by normalized quote equality** · DEFINED / A / medium · *Affects:* 08 `findings.add_new`
Chose: a new finding repeats a withdrawn one when their whitespace-normalized quotes
are equal. Alternatives: gate references an id; fuzzy match. Why unsure: exact equality
may miss paraphrased repeats; anything looser is prose parsing.

**JC-32 — Probes through the `claude` CLI, opt-in** · UNDEFINED / C / low · *Affects:* 14
Chose: `claude -p --output-format json --agent <definition>` per prompt, gated by
`SHACKLES_PROBES=1`, never in CI. Alternatives: the Agent SDK; a manual checklist. Why
unsure: CLI flags and JSON envelope are platform details.

**JC-33 — Individual hard stop is checked after the attempt** · DEFINED / A / medium · *Affects:* 10 `round_record` step 3
Chose: compare the attempt's cost with `hardStopBudgetMultipleIndividual × step
budget` at record and pause `limit` if exceeded. Alternative: a pre-spawn ceiling the
driver enforces (not observable). Why unsure: cost is known only after the fact.

**JC-34 — Default agents plan when PLAN-AGENTS is skipped** · DEFINED / A / medium · *Affects:* 10 `advance.skip`, `round_next.build_attempt_spec`
Chose: `defaultAgent` for work, `gateAgent` for gates, `defaultShares` minimums for the
named steps, the remainder split equally. Alternative: refuse to override PLAN-AGENTS.
Why unsure: the keys exist but their use when the step is skipped is unstated.

**JC-35 — Share pools and validation tolerance** · DEFINED / B / medium · *Affects:* 09 `pool`, 10 `validate_agents_plan`, S3
Chose: work shares sum to 1 over the work pool (`workFraction × quote`), gate shares
sum to 1 over the gate pool, ±0.001; off gates must be 0 and their share is unspent.
Alternatives: shares as fractions of the whole quote summing to `workFraction` and
`gatesFraction`; redistribute off-gate shares. Why unsure: "Enforced distribution of
budget (sum to 1)" and "A gate that is off does not incur a charge" leave the pool
arithmetic open.

**JC-36 — project.remaining** · DEFINED / A / low · *Affects:* 09 `project_remaining`
Chose: `budget − Σ total_usd of ended rounds (from their STATE.json on main) − current
spend`. Alternative: a running figure in a separate file. Why unsure: "can become
stale" suggests the owner does not expect precision; the derivation is mine.

**JC-37 — Dirty living paths in the driver's checkout refuse start** · DEFINED / E / medium · *Affects:* 10 `preflight`
Chose: refuse with the list. Alternative: warn and continue (the round branches from
`origin/main`, so the dirt is simply not included). Why unsure: refusing may annoy an
owner mid-edit; continuing may silently orphan their work.

**JC-38 — Checkpoint delivery** · DEFINED / B / medium · *Affects:* 10 `round_next.issue`, `pause_text`
Chose: a checkpoint is a pause whose owner text starts with the rendered
`CHECKPOINT-OVERVIEW`, followed by the runner's summary (spend, judgment-call counts,
flags, last summaries); the driver relays it. Alternative: treat the driver as an
agent attempt of the checkpoint with a result file. Why unsure: the prose addresses
the driver directly, not a spawned agent.

**JC-39 — Step order mismatch refuses start** · DEFINED / E / low · *Affects:* 05 `steps.lint`
Chose: `project.yaml: steps` must list the table's steps in the table's order.
Alternative: accept any order, use the table's. Why unsure: the table "is code", so
order in YAML is informative only; refusing surfaces an edit the owner probably wants
reviewed.

**JC-40 — The docs set** · DEFINED / D / low · *Affects:* 12
Chose: `PROCESS.md`, `ARCHITECTURE.md`, `TODO.md`, `CLARIFICATIONS.md` only.
Alternatives: more files (DECISIONS, LEDGER); fewer. Why unsure: only PROCESS, TODO and
CLARIFICATIONS are named by the owner's files.

**JC-41 — Every state change is a commit and a fence push** · DEFINED / B / medium · *Affects:* 10 `round_start.fence`
Chose: `next`, `record` and every owner verb end in a commit of the round folder and a
lease push. Alternative: fence only at record. Why unsure: "every state change" taken
literally yields many small commits; that is accepted as the cost of the lock.

**JC-42 — `delegate through STEP`** · DEFINED / A / low · *Affects:* 10 `round_owner.delegate`
Chose: checkpoints at or before STEP's table position are skipped; later ones pause.
Alternative: skip every checkpoint until STEP is *accepted*. Why unsure: both fit
"no checkpoints up to and including STEP".

**JC-43 — Inputs are given by path, not inlined** · DEFINED / B / medium · *Affects:* 05 `process_instructions`, AGENTS.md's DEFINED/UNDEFINED rule
Chose: prompts list absolute input paths; only the roster and prices (for PLAN-AGENTS)
and prior findings/resolutions are inlined verbatim. Alternative: inline every
artifact. Why unsure: AGENTS.md makes anything read from a pointed-to file an UNDEFINED
judgment call, which argues for inlining; prompt size argues against.

**JC-44 — Gate read-only enforced by the agent definition's tools** · UNDEFINED / C / medium · *Affects:* 06 `agentdefs`, 10 `mechanical` (gate diff reverted)
Chose: the `-gate` definition lists read-only tools; any gate diff is reverted at
record as a second line of defence. Alternative: rely on prose alone. Why unsure: the
exact tool names and `Bash(git diff:*)` syntax are platform details.

**JC-45 — Renames via git's detection (50%)** · UNDEFINED / C / low · *Affects:* 07 `changes_between`, 09 `living_file_delta`
Chose: `-M --find-renames=50%`; a rename with edits is charged only its token delta.
Alternative: 100% similarity only. Why unsure: threshold choice affects base-cost
billing at the margin.

**JC-46 — What SPEC-TO-TESTS must pass mechanically** · DEFINED / A / medium · *Affects:* 10 `mechanical` (SPEC-TO-TESTS)
Chose: new tests must collect; the pre-existing suite must still pass; new tests may
fail (the implementation does not exist yet). Alternative: require new tests to fail.
Why unsure: the prose says "before it exists", not what the runner should check.

**JC-47 — TESTS-TO-SUITE re-verifies after moving** · DEFINED / E / low · *Affects:* 10 `suite.apply`
Chose: after archiving, the suite must pass; failure becomes a mechanical rejection.
Alternative: trust the move. Why unsure: moving files can break imports.

**JC-48 — driverUsdPerStep billed once per accepted step** · DEFINED / B / low · *Affects:* 09 `bill_driver_step`
Chose: once per step at acceptance (skipped steps 0). Alternatives: per attempt; per
`next`. Why unsure: "per step" could mean each attempt the driver mediates.

**JC-49 — The runner runs from the driver's checkout** · DEFINED / B / medium · *Affects:* 03 `run.py`, 10
Chose: `src/run.py` executes from the driver's checkout while acting on the round's
worktree; the worktree's `src/` is what agents edit and what verify tests. Alternative:
re-exec the worktree's copy. Why unsure: rounds that change the runner itself only
take effect for the next round; that seems right but is not stated.

**JC-50 — The round's OWNER.log slice is refreshed at every verb and at end** · DEFINED / A / low · *Affects:* 10 `round_owner`, `advance.end`
Chose: from the claim index to the current last index, byte-exact copy, overwritten
each time. Alternative: write once at round end. Why unsure: only "this round's slice"
is specified.

**JC-51 — NEEDS-OWNER question format is not enforced** · DEFINED / E / low · *Affects:* 08 `results.py`, 10 `pause_text`
Chose: the runner relays `questions` verbatim; whether they are lettered decisions is
the agent's and the driver's business. Alternative: a mechanical shape check.
Why unsure: enforcing a shape on natural language edges toward parsing prose.

**JC-52 — A fenced JSON final message is tolerated** · UNDEFINED / C / low · *Affects:* 08 `read_result`
Chose: strip one surrounding ```` ```json ```` fence before parsing. Alternative:
strict JSON only. Why unsure: models often fence JSON; strictness would waste attempts.

**JC-53 — Mixed suite/archive decisions split a Python file** · DEFINED / A / low · *Affects:* 10 `suite.split_file`
Chose: archive the whole file and remove the archived functions from the suite copy
(Python only; other languages archive whole and flag the owner). Alternative: refuse
per-function decisions. Why unsure: "choose where each test goes" suggests
per-function choice, but splitting non-Python files needs language knowledge.

**JC-54 — Hook wiring is platform-specific** · UNDEFINED / C / high · *Affects:* 02 `.claude/settings.json`, 06 `hooks.py`
Chose: `UserPromptSubmit` and `SessionStart` hooks invoking `run.py hook …` with
`$CLAUDE_PROJECT_DIR`, reading the hook's stdin JSON (`prompt`, `session_id`).
Alternative: a wrapper script around the chat client; manual logging by the driver
(which the spec forbids: the runner must verify quotes against a hook-written log).
Why unsure: event names, environment variables and stdin fields belong to Claude Code
and may change; if the prompt hook does not fire, no owner word verifies and `start`
refuses, which is the safe failure.
