# Judgment-call log for draft-2

Definition used (the owner's, verbatim): *a judgment call is any choice that lands in
your finished work that you are not confident in making correctly for any reason.*
Every entry below is such a choice. Nothing here is a "decision" in the sense of a
requirement; each is a place where a reviewer may reasonably want to overrule me.

## Classification scheme

Each call carries three labels.

**Cause** (why I was not confident):
- `SILENCE` — the inputs say nothing about this; I had to pick something.
- `AMBIGUITY` — the inputs can be read more than one way; I picked one reading.
- `CONFLICT` — two inputs disagree (or an input disagrees with itself); I picked a winner.
- `ENVIRONMENT` — depends on how an external tool (Claude Code, git, pytest, the model API)
  behaves, and I could not verify that here.
- `ENGINEERING` — the inputs allow several sound designs; I picked one on taste.

**Reach**: `LOCAL` (one component) or `CROSS` (several components or the owner-visible surface).

**Confidence**: `LOW` or `MEDIUM` (a `HIGH` confidence choice is not a judgment call).

Each entry: what the choice was, what I chose, alternatives seen, why I was not sure,
and the spec section(s) it affects (file § heading).

---

### JC-01 — Where the harness root and `.claude/` live
- **Choice:** HARNESS_ROOT is the directory containing `project.yaml` (found by walking up from `src/run.py`); REPO_ROOT is the git top level; `.claude/` (hooks, agent definitions) lives at REPO_ROOT; a `harness/CLAUDE.md` symlink to `AGENTS.md` and a two-line root `CLAUDE.md` make Claude Code load the owner's `AGENTS.md`.
- **Alternatives:** put `.claude/` under `harness/`; assume the session cwd is `harness/`; rename nothing and rely on the driver reading `AGENTS.md` by hand.
- **Why unsure:** the inputs never say where the Claude Code session is launched from or which directory Claude Code treats as the project root; hooks resolve `$CLAUDE_PROJECT_DIR`, which I believe is the git root but could not verify here.
- **Labels:** ENVIRONMENT / CROSS / MEDIUM. **Affects:** 00 §0.1, §0.5; 01 §paths.py.

### JC-02 — Generated files kept outside living paths
- **Choice:** `INDEX.md`, `local.yaml`, `spec-baseline/`, `.claude/agents/` live outside `src/`, `docs/`, `tests/` so their tokens are never charged.
- **Alternatives:** put `INDEX.md` in `docs/`; keep the baseline in `archives/`.
- **Why unsure:** `AGENTS.md` says "grep INDEX.md" without a path; the owner may expect it in `docs/`. `archives/` is "left alone once a round is complete" but the baseline changes on acceptance, so I kept it out of `archives/`.
- **Labels:** ENGINEERING / LOCAL / MEDIUM. **Affects:** 00 §0.2, §0.10.

### JC-03 — The round's OWNER.log slice is committed
- **Choice:** the hook's `harness/OWNER.log` is gitignored (required), but the runner copies the round's slice into `archives/rounds/NNNN/OWNER.log`, which is committed with the round.
- **Alternatives:** keep the slice ignored too and verify quotes only against the root log.
- **Why unsure:** `roundPaths.runner.ownerLog` exists and POSTMORTEM needs "the exact owner words", which a sub-agent can only read from the worktree; but committing chat may not be what the owner wants for privacy.
- **Labels:** AMBIGUITY / CROSS / MEDIUM. **Affects:** 00 §0.4; 03 §ownerlog.py.

### JC-04 — Spec baseline stores full copies, not only hashes
- **Choice:** `spec-baseline/` mirrors each spec file byte-for-byte plus a hash manifest.
- **Alternatives:** hashes only (cannot print a diff); store the baseline commit id and diff against git (breaks when the spec files are edited uncommitted).
- **Why unsure:** the owner wrote "hashed baseline" and "failing test with diff"; both are satisfied, but a copy of ~25 KB of owner text lives in the tree twice.
- **Labels:** ENGINEERING / LOCAL / MEDIUM. **Affects:** 00 §0.10; 01 §speclock.py; 10 §test_spec_drift.py.

### JC-05 — CI configuration exists at all
- **Choice:** a small GitHub Actions workflow running doctor and the offline suite.
- **Alternatives:** no CI (the inputs never mention one).
- **Why unsure:** the task statement lists CI among things to cover; the owner's files are silent. It is harmless and reflects "a test fails whenever one of them changes".
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 00 §0.7.

### JC-06 — SessionStart hook checks, never regenerates
- **Choice:** the SessionStart hook only reports whether `.claude/agents/` matches `subAgents.yaml`; generation is the explicit `run.py agents`, after which the session must restart; `start` refuses while definitions are stale.
- **Alternatives:** regenerate in the hook (but the owner says definitions are taken only from what was loaded at session start, so a hook-time regeneration would be invisible to that session and, worse, would make the staleness undetectable).
- **Why unsure:** I cannot verify Claude Code's load order for hooks versus agent definitions.
- **Labels:** ENVIRONMENT / LOCAL / MEDIUM. **Affects:** 00 §0.5; 02 §agentdefs.py; 07 §start.

### JC-07 — `testPaths` is a defaulted config key
- **Choice:** the living-charge commentary refers to "the spec's testPaths", which no owner file defines; I made `testPaths` a runner default (`["tests/"]`) that `doctor` reports as defaulted, so the owner can add it to `project.yaml` and it is then "used for something".
- **Alternatives:** read `testPaths` from the round's `SPEC.json`; hard-code `tests/`; treat the mention as stale and derive tests from `livingSourcePaths`.
- **Why unsure:** it could be a stale reference or a planned key; the round-spec reading is plausible but would let a producer change what gets charged.
- **Labels:** AMBIGUITY / CROSS / MEDIUM. **Affects:** 01 §config.py DEFAULTS; 06 §ledger.py; 05 §suite.py.

### JC-08 — Unknown `project.yaml` keys refuse `start`
- **Choice:** keys the runner does not use are a `doctor` warning and a `start` refusal.
- **Alternatives:** ignore unknown keys silently; warn only.
- **Why unsure:** "each is used for something" is an owner statement about the settings surface; refusing enforces it but makes the harness stricter toward owner edits than "robust to arbitrary changes" may intend. The drift guard already stops the round on any change, so refusing adds little friction.
- **Labels:** CONFLICT / LOCAL / MEDIUM. **Affects:** 01 §config.py; 02 §doctor.py; 07 §start.

### JC-09 — Ladder order is `subAgents.yaml` key order, top first
- **Choice:** rungs are ranked by their order in the file, first = highest; `maxAgent` names the ceiling and rungs listed above it are not selectable.
- **Alternatives:** rank by price; rank by an explicit `level` key (none exists); treat the map as unordered and only check `maxAgent` membership.
- **Why unsure:** "Keys are rungs on a capability ladder" gives no ordering rule; the current file lists `max` first, which matches, but the `high` rung being "Fable 5.1 Low" shows names and keys do not track each other.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 01 §config.py Roster; 06 §quote.py lint.

### JC-10 — A step's gate may be "on" without prose only as an error
- **Choice:** the table allows a `CHAT-TO-PLAN` gate (the owner's table has a flag for it) but there is no `CHAT-TO-PLAN-GATE.txt`; flag 0 + missing file is fine, flag 1 + missing file refuses to start. `LANDING` and `CLEANUP` have no gate regardless of the flag.
- **Alternatives:** treat CHAT-TO-PLAN's flag as ignored like CLEANUP's; synthesise a gate prompt from COMMON-GATE only.
- **Why unsure:** the owner comment says only LANDING and CLEANUP have "no gate", which implies CHAT-TO-PLAN can be gated, yet no prose exists for it.
- **Labels:** CONFLICT / LOCAL / MEDIUM. **Affects:** 01 §steps.py TABLE; 02 §doctor.py.

### JC-11 — Declared path classes per step are fixed in the table
- **Choice:** what a producer may edit is a per-step class in `steps.py` (tests, living non-test, carry-forward files, conflicted files, whole living tree for CLEANUP) plus the round folder; `SPEC.json` does not narrow it further.
- **Alternatives:** let `SPEC.json` declare paths for SPEC-TO-TESTS and SPEC-TO-IMPLEMENTATION; let AGENTS-PLAN declare them.
- **Why unsure:** "their step's declared paths" does not say who declares; a table is mechanical and cannot be gamed by a producer, but is coarser.
- **Labels:** AMBIGUITY / CROSS / MEDIUM. **Affects:** 01 §steps.py; 04 §worktree.py.

### JC-12 — A landing-conflict attempt's prompt is composed, not authored
- **Choice:** no `LANDING-OVERVIEW.txt` exists, so the conflict-resolution attempt gets COMMON-PROJECT + COMMON-ROUND + COMMON-OVERVIEW + process instructions; if the owner later adds `LANDING-OVERVIEW.txt`, it is used instead.
- **Alternatives:** refuse to start when any step lacks prose (breaks every round today); ship a runner-authored overview (would be judgment language outside locked prose).
- **Why unsure:** "A landing conflict becomes one agent attempt" needs a prompt and the owner wrote none.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 02 §plumbing.py; 04 §landing.py.

### JC-13 — `effort:` in agent-definition front matter; read-only twins for gates
- **Choice:** generated definitions carry `model:` and `effort:`; gates use a `-readonly` twin whose `tools:` list has no write or shell tools.
- **Alternatives:** one definition per rung and pass effort another way; restrict gates by prompt only.
- **Why unsure:** I could not verify that Claude Code honours an `effort` front-matter key; the owner asserts the Agent tool takes effort only from definitions loaded at session start, so this is the only place it can go.
- **Labels:** ENVIRONMENT / LOCAL / LOW. **Affects:** 02 §agentdefs.py.

### JC-14 — COMMON-STEP-END delivery
- **Choice:** the rendered COMMON-STEP-END is the last section of every agent prompt and is also written to `PROMPTS/<attempt>-END.txt`; the driver's instructions say to send it as a follow-up turn when its agent tool allows one.
- **Alternatives:** follow-up only (impossible with one-shot sub-agents); prompt-only.
- **Why unsure:** the prose says the message "is produced at the end of every step", which reads as a second message; one-shot sub-agents cannot receive one.
- **Labels:** ENVIRONMENT / LOCAL / MEDIUM. **Affects:** 02 §plumbing.py; 07 §next.

### JC-15 — How `{{ project.gates }}` renders
- **Choice:** all gates in step order; gates that are off or overridden are suffixed "(off)"; "none" if the table has no gates.
- **Alternatives:** list only gates that are on; list every step.
- **Why unsure:** "Gates, in order" is all the prose says; agents are told the standard applies even when gates are off, which argues for showing them.
- **Labels:** AMBIGUITY / LOCAL / MEDIUM. **Affects:** 02 §render.py gates_line.

### JC-16 — Where a round's OWNER.log slice begins
- **Choice:** the slice starts at the last owner entry present when `start` runs (the message that triggered the round) and grows at every runner command until the round ends.
- **Alternatives:** start at `start` time exactly (loses the triggering request); let the driver pass an explicit line number.
- **Why unsure:** "this round's slice of the owner's words" does not define the boundary; the plan chat straddles `start`.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 03 §ownerlog.py starting_line; 07 §start.

### JC-17 — Quote verification is verbatim substring, near-zero normalisation
- **Choice:** a quote must appear verbatim inside one owner entry, after normalising only line endings and trailing whitespace.
- **Alternatives:** case-insensitive or whitespace-collapsed matching; fuzzy matching.
- **Why unsure:** "verifies quotes against it" and "the runner never parses prose" push toward strictness, but a driver that copies with a changed quote character would be refused and must retry with the exact text.
- **Labels:** AMBIGUITY / LOCAL / MEDIUM. **Affects:** 03 §ownerlog.py verify_quote; 03 §control.py.

### JC-18 — What a "restart" is for `maxRoundAttempts`
- **Choice:** a restart is a `resume` after a pause whose reason was `blocked`, `limit` or `hard-stop`; resuming after `checkpoint`, `approval` or `questions` is not a restart. Exceeding `maxRoundAttempts` pauses again with reason `limit` (kind `restarts`), from which only abandon or an owner-raised multiple/explicit resume with `--force-restart` proceeds.
- **Alternatives:** count every pause; count only verify-failure loops; count `next` after any refusal.
- **Why unsure:** "maximum attempts at restarting a round after minor issues" names neither the trigger nor what counts as minor.
- **Labels:** AMBIGUITY / LOCAL / LOW. **Affects:** 03 §state.py resume; 03 §limits.py restarts; 07 §resume.

### JC-19 — Wall clock excludes paused time
- **Choice:** `maxRunWallClockHours` is measured on active time only (pauses waiting for the owner are excluded).
- **Alternatives:** measure from `start` regardless of pauses (a round paused overnight at a checkpoint would then be dead on resume).
- **Why unsure:** "per run" is undefined; the owner's `lostValuePerHour` suggests elapsed time matters, but a limit that fires because the owner slept seems wrong.
- **Labels:** AMBIGUITY / LOCAL / MEDIUM. **Affects:** 03 §limits.py wall_clock; 03 §state.py counters.active_seconds.

### JC-20 — One worktree per round, one open attempt at a time
- **Choice:** a single worktree per round holds the runner's round folder and the producer's edits; `next` hands out one attempt at a time; `maxSimultaneousSubAgentsPerRound` bounds the helper sub-agents a producer may itself spawn inside its attempt.
- **Alternatives:** one worktree per attempt with merges at record (needed only if two attempts could be open at once); a shared checkout with no worktree.
- **Why unsure:** "Producers edit only inside their worktree" could mean one worktree per producer; the step table is strictly sequential, so I could not find a path where two runner-handed attempts overlap.
- **Labels:** AMBIGUITY / CROSS / MEDIUM. **Affects:** 04 §worktree.py; 07 §next; 02 §plumbing HELPERS.

### JC-21 — The carry-forward files are exactly `docs/TODO.md` and `docs/CLARIFICATIONS.md`
- **Choice:** fixed in code (the owner named them in project.yaml comments and prose); POSTMORTEM's declared paths are those two files plus the round folder.
- **Alternatives:** a config key; allow POSTMORTEM to edit all of docs/.
- **Why unsure:** the names appear only in a comment; if the owner renames them the step table must change.
- **Labels:** ENGINEERING / LOCAL / MEDIUM. **Affects:** 04 §worktree.py declared_prefixes; 06 §ledger.py.

### JC-22 — Verify failure on a clean merge pauses instead of spawning an agent
- **Choice:** when the merge is clean but the suite fails on the merged tree, the round pauses with reason `conflict` for the owner; only textual conflicts get the one agent attempt.
- **Alternatives:** treat a red suite after a clean merge as a conflict attempt too.
- **Why unsure:** the owner scoped the agent attempt to "the conflicted files"; a semantic conflict has no such file list.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 04 §landing.py step 4.

### JC-23 — Two attempts at conflict resolution, then pause
- **Choice:** `LANDING-1`, then `LANDING-2`, then pause.
- **Alternatives:** exactly one attempt ("one agent attempt"); use `maxTurnsPerGate`.
- **Why unsure:** "becomes one agent attempt" may mean one at a time or one total; a single transient failure ending the landing seemed too brittle.
- **Labels:** AMBIGUITY / LOCAL / LOW. **Affects:** 04 §landing.py; 07 §record.

### JC-24 — What "bounded" means for the post-landing sync
- **Choice:** at most 3 fetch/merge/push cycles; only round-folder, carry-forward and living paths may differ; conflicts pause the round for the owner, never an agent.
- **Alternatives:** unbounded retry; an agent attempt on sync conflicts like landing.
- **Why unsure:** "bounded sync" names no bound; "every plan had orphaned them" says only that it must exist.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 04 §sync.py.

### JC-25 — Sub-agent questions need not carry lettered options
- **Choice:** the result schema requires ≥ 1 question for NEEDS-OWNER; options are optional; the *driver* is the one instructed (by CHAT-TO-PLAN prose) to present one numbered list of lettered choices per turn and may rephrase.
- **Alternatives:** require ≥ 2 lettered options from every agent.
- **Why unsure:** the lettered-choice rule lives in CHAT-TO-PLAN prose addressed to the driver; imposing it mechanically on every agent would be judgment language the owner did not write for them.
- **Labels:** AMBIGUITY / LOCAL / MEDIUM. **Affects:** 05 §results.py validate_producer.

### JC-26 — Lenient JSON extraction from the final message
- **Choice:** take the last fenced ```json block that parses, else the last balanced top-level object; the driver may save the raw message.
- **Alternatives:** require the file to be pure JSON (the driver would have to trim by hand).
- **Why unsure:** "the runner never parses prose" is about owner words; agents wrap JSON in prose despite instructions, and trimming by the driver is itself an interpretation step.
- **Labels:** ENVIRONMENT / LOCAL / MEDIUM. **Affects:** 05 §results.py extract_json.

### JC-27 — "Blocking flags follow the verdict", concretely
- **Choice:** PASS forces every finding of that gate attempt non-blocking and turns them into owner flags; FAIL with no blocking finding forces them all blocking.
- **Alternatives:** PASS with blocking findings refuses the gate record; FAIL without blocking findings is treated as PASS.
- **Why unsure:** "The gate's verdict wins and blocking flags follow it" fixes precedence but not the exact rewrite; "a flagged item reaches the owner at the next pause" suggested the PASS branch.
- **Labels:** AMBIGUITY / CROSS / MEDIUM. **Affects:** 05 §findings.py reconcile; 03 §state flags.

### JC-28 — Archiving a test means cutting its function by AST span
- **Choice:** the runner cuts each archived test function (with decorators) from its file and appends it to `tests-archive/<same path>`; empty new files are removed; the producer only decides.
- **Alternatives:** per-file decisions only; let the producer move them and the runner just checks.
- **Why unsure:** "moved by the runner" and "a test is a test function" force a function-level mechanical move; shared fixtures and imports the cut function needed are not carried, so an archived file may not run as-is (it is a record, not a suite).
- **Labels:** ENGINEERING / LOCAL / LOW. **Affects:** 05 §suite.py archive.

### JC-29 — Measured usage when the driver supplies it, estimate otherwise
- **Choice:** `record --usage` prices token counts the driver observed; without them the runner estimates from prompt size and `estOutputFraction`; the bill marks each entry measured or estimated. Refused records are booked too.
- **Alternatives:** always estimate; require measured usage.
- **Why unsure:** whether the Agent tool exposes usage to the driver is an environment detail I cannot verify; "bills what happened" argues for measured when available.
- **Labels:** ENVIRONMENT / LOCAL / MEDIUM. **Affects:** 06 §pricing.py; 07 §record.

### JC-30 — Enforced share rule is a cap per pool, not an equality
- **Choice:** work shares must sum to ≤ workFraction and on-gate shares to ≤ gatesFraction; unallocated pool is a warning.
- **Alternatives:** require equality (impossible when every gate is off); scale gate shares to the on gates.
- **Why unsure:** "Enforced distribution of budget (sum to 1). A gate that is off does not incur a charge" cannot both sum to 1 and drop off gates.
- **Labels:** CONFLICT / LOCAL / MEDIUM. **Affects:** 06 §quote.py lint_agents_plan.

### JC-31 — Attempts with no known share have no budget line and no individual hard stop
- **Choice:** before AGENTS-PLAN exists, steps without a `defaultShares` entry (e.g. a CHAT-TO-PLAN gate) get "no specific budget" and the individual hard stop is skipped for them.
- **Alternatives:** invent a share; use the whole quote as the budget.
- **Why unsure:** `defaultShares` covers only three entries; the owner said budgets are targets, so silence seemed better than invention.
- **Labels:** SILENCE / LOCAL / LOW. **Affects:** 06 §quote.py budget_for; 03 §limits.py hard_stop_attempt.

### JC-32 — Carry-forward files priced flat at `postMortemFileCostPerToken`
- **Choice:** docs/TODO.md and docs/CLARIFICATIONS.md deltas are priced at that rate with no cap tiers and no base cost, replacing the living-file price for those two files.
- **Alternatives:** living price plus the special rate; special rate only for POSTMORTEM's own edits (needs per-step attribution the net diff cannot give).
- **Why unsure:** the key's comment says "special case for postmortem carry-forward files" and nothing more.
- **Labels:** AMBIGUITY / LOCAL / MEDIUM. **Affects:** 06 §ledger.py living_charge step 3.

### JC-33 — No project ledger file; bills live in each round's STATE.json
- **Choice:** `project.remaining` is computed by scanning `archives/rounds/*/STATE.json` bills; no shared ledger file exists.
- **Alternatives:** `archives/LEDGER.json` appended per round (a shared file every round edits; sync conflicts).
- **Why unsure:** `roundPaths` lists no bill file; STATE.json is "the runner's only state", which a bill arguably is.
- **Labels:** ENGINEERING / LOCAL / MEDIUM. **Affects:** 06 §ledger.py remaining_project; 08 §STATE.json.

### JC-34 — Order of gate and owner approval for CHAT-TO-PLAN
- **Choice:** the driver records the plan (DONE) → the gate judges it (if on) → then `next` asks for the owner's approve/delegate; the step is accepted only after both.
- **Alternatives:** approval before the gate; approval only (gate ignored for this step).
- **Why unsure:** the prose says the owner approves "a plan and a quote" and the gate judges the planner; nothing fixes the order. Judging first means the owner approves the judged plan.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 07 §round.next; 03 §control.py.

### JC-35 — Abandon lands the round folder only
- **Choice:** on abandon, the round folder is merged into main (so the record and bill survive) while living changes are dropped; the branch stays on the remote.
- **Alternatives:** land nothing (the ledger then cannot see the round); land everything.
- **Why unsure:** "the round ends without landing" says nothing about the record; `project.remaining` needs completed and abandoned bills.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 07 §round.abandon; 04 §sync.py only_prefixes.

### JC-36 — Refused records keep the attempt open and re-run it under the same name
- **Choice:** a refused record does not create a new attempt; `next` hands out the same attempt again (`refused += 1`), the cost is booked, and refusals do not count as gate rejections.
- **Alternatives:** count refusals as attempts; make the driver fix the result file by hand.
- **Why unsure:** the inputs describe accepted and rejected attempts, not malformed ones.
- **Labels:** SILENCE / LOCAL / MEDIUM. **Affects:** 07 §round.record; 03 §attempts.py.

### JC-37 — The stub agent is a scripted Python class, not a fake CLI
- **Choice:** tests drive the runner with an in-process `StubAgent` that edits the worktree and writes result files according to named behaviours, and a `driveloop` that plays the driver.
- **Alternatives:** a fake `claude` executable invoked by the runner (the runner never invokes agents, so there is nothing to fake at that seam).
- **Why unsure:** "A stub agent with many scripted behaviors drives every path" fixes the idea, not the seam; since the driver, not the runner, spawns agents, the only seam is the `next`/`record` contract.
- **Labels:** ENGINEERING / LOCAL / MEDIUM. **Affects:** 10 §stub_agent.py, §driveloop.py.

### JC-38 — The drift test runs against the real checkout, all others against fixtures
- **Choice:** `test_spec_drift.py` is the only test that reads the owner's files; it is skipped only when no `spec.yaml` is reachable from the test file (never in CI).
- **Alternatives:** compare fixtures too; never skip.
- **Why unsure:** a test that inspects the real checkout is unusual and depends on where pytest is run from; the owner's requirement makes it necessary.
- **Labels:** ENGINEERING / LOCAL / MEDIUM. **Affects:** 10 §test_spec_drift.py.

### JC-39 — A word-list check keeps `plumbing.py` mechanical
- **Choice:** `test_plumbing.py` asserts that process instructions contain no "sensible" or "judgment" outside the quoted STEP-END text, as a crude guard for "these steps never require judgment calls".
- **Alternatives:** no such check (it is a heuristic and can be gamed or produce false alarms).
- **Why unsure:** it is weak evidence, but it is cheap and it makes drift toward judgment language visible.
- **Labels:** ENGINEERING / LOCAL / LOW. **Affects:** 10 §test_plumbing.py.

### JC-40 — Live probes call the Claude Code CLI in print mode
- **Choice:** probes spawn real agents through `claude -p --output-format json --model <model>` in a subprocess (command overridable), with no SDK dependency; effort comes from the CLI's defaults for the model, not from the generated definitions.
- **Alternatives:** the Anthropic Python SDK (new dependency, API key handling); require the probes to be run by the driver's Agent tool (not automatable from pytest).
- **Why unsure:** the inputs never say how a test may reach a real agent; the CLI is what the harness already assumes exists, but its flags may change.
- **Labels:** ENVIRONMENT / LOCAL / LOW. **Affects:** 11 §probes/.

