# Judgment calls — draft 4

Definition (the owner's): **a judgment call is any choice that lands in the finished work that the author is not confident in making correctly, for any reason.** This log tracks and classifies them; it does not stop them.

## Classification scheme

Every call carries one **cause** and one **reach**.

Cause (why I was not confident):
- `GAP` — the inputs are silent on the point; I had to invent.
- `AMBIG` — the inputs say something, but two readings are reasonable.
- `TENSION` — two input statements pull in different directions and I picked a reconciliation.
- `TOOL` — depends on facts about external tooling (git, Claude Code, pytest, YAML) I could not verify here.
- `TASTE` — a design preference among workable options.

Reach (how much of the design changes if the call is reversed):
- `local` — one function or file changes.
- `component` — one component changes, its neighbours keep their contracts.
- `system` — a contract between components changes.

Each entry: **ID · cause/reach · spec section** — the choice; what I chose; alternatives; why not confident.

---

## Contracts ([00])

**JC-01 · GAP/component · 00 §0.4** — Driver-facing summary files (`PROMPTS/PAUSE-k.txt`, `PROMPTS/CHECKPOINT-i-n.txt`) are not among the owner's `roundPaths`. Chose: write them under the owner's `prompts` folder, since they are rendered prompts for the driver. Alternatives: a new round-folder file name (adds an unlisted setting); stdout only (loses the record). Not confident because the owner says the spec files are the whole settings surface, and these names are code constants.

**JC-02 · GAP/system · 00 §0.3** — Attempt id scheme `STEP-n` / `STEP-GATE-n`, with FINDINGS keyed by the producer attempt judged (`FINDINGS/STEP-n.json`) rather than by the gate attempt. The owner's `roundPaths` comment says "STEP-attempt.json, the gate's verdict" for FINDINGS, which supports keying by the judged attempt; but a gate whose message is INVALID re-runs as `STEP-GATE-(m+1)` still judging attempt n, so FINDINGS is written only once per producer attempt. Alternative: key FINDINGS by gate attempt id.

**JC-03 · GAP/system · 00 §0.5** — Ledger, questions, findings, flags and decisions all live inside `STATE.json` rather than in separate files, because the owner names `STATE.json` "the runner's only state" and lists no ledger file. Alternative: `LEDGER.json` per round (cleaner to read, but an unlisted file name). `HISTORY.md` carries the human-readable copy of the same events.

**JC-04 · GAP/component · 00 §0.6** — Gate messages use `status: PASS|FAIL` and cannot answer NEEDS-OWNER/BLOCKED; a gate that cannot judge (e.g. "too large to review") is instructed by the owner's prose to FAIL, so no third state is needed. Alternative: allow gates NEEDS-OWNER. Not confident because COMMON-OVERVIEW's three statuses might have been meant for gates too.

**JC-05 · GAP/system · 00 §0.7** — Concrete JSON shapes for `PLAN.json`, `AGENTS-PLAN.json`, `SPEC.json`, `SUITE.json` are invented; the owner names the files and their readers (machine-read vs owner-read) but not their fields. Fields were chosen to give the mechanical checks something deterministic to check (quote, question options, shares, rungs, helpers, non-goals, refactor shares, test decisions). Reach is system-wide because prompts, checks and stub agents all produce/consume them.

**JC-06 · AMBIG/local · 00 §0.3** — Question numbering is made global per round by the runner (the driver relays the runner's numbers). The prose says "one numbered list per turn", which could mean per-turn local numbers. Global numbers make `--question N` unambiguous across pauses.

**JC-07 · TASTE/local · 00 §0.1** — Every command emits one JSON object on stdout with `--human` as an opt-in renderer, and exit codes 0/1/2/3/4. Alternative: human text by default with `--json`. JSON-first because the driver is an agent that must parse results reliably.

**JC-08 · GAP/component · 00 §0.13** — `local.yaml` content: detected environment facts (remote, main branch, claude command, python), the effective config with defaults applied, defaulted-key list, agent-definition list and drift status. The owner only says it is generated and holds no user input. Alternative: make it purely a doctor report and have commands re-detect everything each run; chose to let `gitops`/`invoke` read `git.*` and `claude.command` from it so detection is done once and visible.

## Root and tooling ([01])

**JC-09 · TASTE/component · 01 §1.1** — Language and dependencies: Python 3.11+, PyYAML and pytest only. `run.py` is named by the owner, so Python is given; PyYAML is chosen over a hand-written YAML subset parser because the owner edits `project.yaml` freely (inline lists, comments, quoted strings) and a subset parser would be a hidden constraint on that freedom.

**JC-10 · TOOL/local · 01 §1.2** — Worktrees live at `harness/.worktrees/round-NNNN/` (inside the repository, gitignored) rather than beside the repository. Git permits nested worktrees when ignored; keeping them under the harness root keeps every runner-created path under one directory. Alternative: `<repo>/../<name>.worktrees/`.

**JC-11 · TOOL/local · 01 §1.3** — The hook is registered as a `UserPromptSubmit` hook in a committed `harness/.claude/settings.json` invoking `src/hooks/owner_log.py`. I could not verify here the exact hook names, stdin payload keys, or whether `$CLAUDE_PROJECT_DIR` is set; the script tolerates missing keys and locates the harness from its own path. Reversal changes only the hook script and this file.

**JC-12 · GAP/local · 01 §1.6** — CI exists (GitHub Actions) and runs doctor offline plus the non-live suite. The owner never mentions CI. Included because the drift test is only meaningful if something runs it outside the round; harmless if unused.

**JC-13 · TENSION/component · 01 §1.9** — `INDEX.md` and `README.md` sit at the harness root, outside living paths, so no producer can edit them; yet AGENTS.md routes agents to `INDEX.md`, which must track structure. Chose: CLEANUP alone may edit those two files (uncharged). Alternatives: move them under `docs/` (contradicts AGENTS.md's "grep INDEX.md" at root); let every step edit them (weakens the path policy).

## Runner CLI ([02])

**JC-14 · AMBIG/local · 02 §start** — `allowUpstream: 1` refuses to start ("upstream mechanics not implemented") instead of being ignored. The owner's TODO says the mechanics are not implemented; refusing is the explicit, robust reading, but it means flipping the key stops all rounds until code exists. Alternative: warn and ignore.

**JC-15 · GAP/component · 02 §accept-spec** — Acceptance of spec drift is a runner command that requires either an owner quote verified against OWNER.log or an explicit `--by-owner` flag (for a human at a terminal), and it commits the new baseline on main directly. The owner says drift fails a test "until the change is reviewed and accepted" without saying by whom or how. Alternatives: acceptance by editing the baseline by hand; acceptance only inside a round.

**JC-16 · GAP/component · 02 §record** — Order of operations at record (drift → parse → checks → findings → questions/flags → ledger → moves → settle → limits → round end → history/commit/fence) is my sequencing. The owner fixes only that checks run at record on the uncommitted diff and that strays are reverted, not failed.

**JC-17 · GAP/local · 02 §next** — LANDING is executed inside `next` (it needs no agent unless a conflict occurs) rather than through a `record` of a runner-performed attempt. Alternative: a dedicated `land` command; rejected because the driver loop stays `next`/`record` only.

## Spec files and config ([03])

**JC-18 · GAP/component · 03 §3.3** — `testPaths` is registered as a defaulted key (`["tests/"]`). The living-charge comment in `project.yaml` refers to "the spec's testPaths" but no such key exists in the file; the owner also says doctor "names defaulted config keys", so a registered default that doctor reports is the mechanism that fits. Alternative: derive tests from `livingSourcePaths` entries containing "test" (fragile).

**JC-19 · GAP/local · 03 §3.3** — `promptSizeWarnTokens` (default 40000) is registered as the second and last defaulted key, because the living-charge comment mentions "the prompt-size warning" but no threshold exists in the file. Alternative: a code constant that the owner cannot change without a code edit; a registered default keeps the settings surface honest (doctor names it; the owner may add it).

**JC-20 · AMBIG/local · 03 §3.3** — The rung ladder order is the file order of `subAgents.yaml` (`max` first = highest); `maxAgent` is a ceiling by that order. The comment "Keys are rungs on a capability ladder" implies an order but does not say which; file order is the only one in the file. Alternative: order by price.

**JC-21 · TASTE/local · 03 §3.3** — Unregistered keys present in the spec files are errors (doctor error → start refuses), not warnings, because the owner states every setting "is used for something". This makes uncommenting an owner placeholder refuse starts until code consumes it. Alternative: warning only.

**JC-22 · AMBIG/local · 03 §3.3** — `gatesFraction + workFraction` must equal 1 (config error otherwise) per "Enforced distribution of budget (sum to 1)". The alternative reading, that shares within each group sum to 1, is applied to AGENTS-PLAN validation instead ([05]).

**JC-23 · GAP/local · 03 §3.2** — The drift diff comes from `git show <accepted_commit>:<path>` against the working file; without git it degrades to a hash-mismatch notice. Alternative: store full copies of accepted spec files beside the baseline (self-contained diff, but duplicates the owner's files in the tree).

## Steps, prose, prompts ([04])

**JC-24 · AMBIG/component · 04 §4.1** — Which steps `override` may skip: any step or gate except CHAT-TO-PLAN ("the plan itself cannot be skipped"), the checkpoints (governed by delegation and the `steps` flags), LANDING and CLEANUP (skipping them is abandonment or an unbooked round). The owner's text allows "steps or gates" generally. Alternative: allow all but CHAT-TO-PLAN.

**JC-25 · GAP/local · 04 §4.1** — The carry-forward files are the code constants `docs/TODO.md` and `docs/CLARIFICATIONS.md`, taken from the living-charge comment and POSTMORTEM prose; they are not settings in `project.yaml`. Alternative: register them as defaulted keys (would add to doctor's "defaulted" list every run).

**JC-26 · AMBIG/local · 04 §4.2** — `{{ project.gates }}` renders every gate-capable step in table order with `(on)`/`(off)`, plus `(off, no prose)` when the gate prose file is absent. "Gates, in order:" could also mean only the enabled ones. Listing all keeps the prompt informative when gates are off (agents keep the same standards).

**JC-27 · TOOL/local · 04 §4.3** — The judgment-call tool and `spawn` are rendered as the driver checkout's absolute `src/run.py` with `--root <worktree harness root>`, not the worktree's own `src/run.py`, so a round that edits the runner cannot break its own tooling mid-attempt. Alternative: use the worktree's runner (tests the new code sooner but risks a broken tool).

**JC-28 · GAP/component · 04 §4.3** — `{{ plumbing.GATE-PROSE }}` for a step whose gate prose file is absent renders a fixed sentence ("No gate prose is defined for this step.") instead of being an unresolved token; a gate flag of 1 on such a step refuses to start. CHAT-TO-PLAN is the live case (no `CHAT-TO-PLAN-GATE.txt` exists). Alternative: treat the absent file as an unresolved token (would make the current spec files fail doctor).

**JC-29 · GAP/component · 04 §4.4** — `{{ round.plan }}` renders the plan's `text` followed by every owner answer of the round ("Owner answers: #n: quote"), including mid-round answers, so later prompts carry what the owner decided without a separate namespace. Alternative: render only the approved plan and put answers into PROCESS-INSTRUCTIONS (but plumbing is meant to be mechanical steps only).

**JC-30 · TOOL/component · 04 §4.5** — Agent definitions use frontmatter keys `name`, `description`, `model`, `effort`, `tools`, with gates restricted to `Read, Grep, Glob`. I could not verify that Claude Code honours `effort` in agent frontmatter; the owner asserts the Agent tool takes effort only from a definition loaded at session start, so this is the mechanism that fits. Keys are kept in one table for a cheap change.

**JC-31 · AMBIG/component · 04 §4.4** — `COMMON-STEP-END` ("produced at the end of every step where an agent has done work") is appended as the final section of every producer and gate prompt, rather than sent as a second message after the agent finishes. Sub-agents spawned by the Agent tool cannot reliably receive a second message; placing it last in the prompt is the closest mechanical equivalent. Alternative: have the driver resume the sub-agent with it (tool support uncertain).

**JC-32 · AMBIG/local · 04 §4.5** — AGENTS.md says "Your system prompt names your step, your inputs, where to write your artifact, and the JSON your final message must be." Since definitions are static per rung, the step-specific content is carried by the rendered prompt (user message) and the definition body only says "your instruction is the message you receive". Alternative: per-attempt agent definitions (impossible: they load at session start).

**JC-33 · GAP/local · 04 §4.1** — LANDING conflict attempts have no owner prose (no `LANDING-*.txt` exists), so their prompt is the plumbing `conflict.txt` template plus the COMMON-* prose it names (COMMON-PROJECT, COMMON-ROUND, COMMON-OVERVIEW) and the step-end. If the owner later adds `LANDING-OVERVIEW.txt`, the step table entry's `overview_prose` should be pointed at it; doctor reports an unused prose file until then.

## Round state and records ([05])

**JC-34 · AMBIG/component · 05 §5.1** — `maxRoundAttempts` ("maximum attempts at restarting a round after minor issues") is read as: the number of resumes after a *limit-type* pause (limit, mechanical, hard-stop, sync); checkpoint and question pauses do not count. Beyond it, `resume` refuses until `raise-limit maxRoundAttempts` or `abandon`. Alternatives: count every resume; count `start` retries of the CAS claim.

**JC-35 · GAP/local · 05 §5.1** — The "active round" is discovered by scanning `harness/.worktrees/round-*/…/STATE.json` for the newest non-ended state; the driver checkout on main holds no round pointer. Alternative: a pointer file at the harness root (another generated file to keep in sync).

**JC-36 · TASTE/local · 05 §5.3** — Final-message parsing tolerates a single fenced ```json block and surrounding whitespace, otherwise requires a bare JSON object. Strictness is what the owner wants ("the runner parses it"), but fenced JSON is a very common agent habit and rejecting it would burn attempts on formatting.

**JC-37 · AMBIG/component · 05 §5.4** — AGENTS-PLAN share validation: Σ work shares ≤ `workFraction` and Σ enabled-gate shares ≤ `gatesFraction` (small tolerance) are errors; being *under* by more than 0.05, or under a `defaultShares` advisory minimum, is a warning. "Enforced distribution" could also mean exact equality; ≤ was chosen because off gates "do not incur a charge" makes exact sums impossible when gates are off.

**JC-38 · AMBIG/local · 05 §5.4** — "Carry the plan's non-goals in the spec" is checked advisorily (case-insensitive substring of each plan non-goal in the spec's non-goals) and passed to the gate as a warning, not enforced, because agents may legitimately reword. Refactor-cap overrun is likewise advisory ("Advisory fraction").

**JC-39 · GAP/local · 05 §5.5** — A disputed finding the gate fails to rule on counts as upheld and is marked `missing: true` in FINDINGS. The prose orders the gate to rule; silence had to map to something, and "upheld" keeps the producer's obligation alive rather than silently withdrawing. Alternative: treat silence as withdrawn; or mechanically reject the gate message.

**JC-40 · GAP/local · 05 §5.7** — Quote verification: whitespace-normalized substring match against owner prompts logged since the round's `slice_from` (previous round's end). Alternatives: exact match (too brittle for the driver's copying), any entry ever (lets stale words approve a new round).

**JC-41 · GAP/component · 05 §5.8** — Answering the last open question of a `needs-owner` pause clears the pause automatically (the step retries with a new attempt on the next `next`), without a separate `resume`. For `blocked` pauses an explicit `resume` is still required after at least one answer, since narrowing is a conversation. Alternative: always require `resume`.

**JC-42 · GAP/component · 05 §5.8** — The decision vocabulary (`approve, delegate, delegate-through, override, answer, abandon, revise, resume, raise-limit`) extends the owner's list with `revise`, `resume` and `raise-limit`, which the prose implies (plan changes before approval; continuing after pauses; "owner requesting a temporary, specific new multiple") but does not name.

## Git, checks, landing ([06])

**JC-43 · TOOL/component · 06 §6.1** — The CAS claim is `git push --force-with-lease=refs/heads/<branch>:` with an empty expected value (the ref must not exist on the remote), retried with the next id up to 3 times. I believe this is the documented semantics of an empty lease value; if a git version rejects it, the fallback is a plain push of a new branch (rejected when it exists). A remote is required; without one `start` refuses ("git is the only lock").

**JC-44 · TOOL/component · 06 §6.1** — "Judged against git's auto-merged tree": the runner snapshots the working tree as git left it after a conflicted merge (a commit object made with `commit-tree` from a temporary index, kept under `refs/shackles/automerge/`), and the conflict attempt's diff is measured against that snapshot. Exact plumbing commands are left to the implementer; the contract is "a ref whose tree is the auto-merge with markers".

**JC-45 · AMBIG/local · 06 §6.4** — The hard stop before landing compares `round spend so far + projected living charge` (main-before-landing vs the branch tree, living paths only, carry files priced normally at this point) with `hardStopBudgetMultiple × quote`. Archive charges (plan/spec/postmortem) are not projected. Alternative: include archive charges in the projection.

**JC-46 · GAP/local · 06 §6.4** — If the merged tree fails the suite after a *clean* merge (semantic conflict), the round pauses with kind `mechanical` rather than opening an agent attempt, because no file is "conflicted" for the attempt to be scoped to. Alternative: open a conflict attempt on the files main changed.

**JC-47 · GAP/local · 06 §6.4** — Conflicts during the post-landing sync reuse the LANDING conflict machinery and attempt ids (`LANDING-n`), with HISTORY noting "sync conflict", because attempt ids must be `STEP-attempt` and no other step fits. Alternative: `CLEANUP-n` ids.

**JC-48 · GAP/component · 06 §6.4** — `abandon` performs a record-only landing: living paths are restored from the base commit on the round branch and the branch (now main + round folder) is synced into main, so the round's record and ledger reach main. The owner says only "the round ends without landing". Alternative: leave the record on the remote branch only (then `project.remaining` would not see abandoned rounds' spend).

**JC-49 · GAP/local · 06 §6.4** — `SYNC_BOUND = 3` iterations for the bounded sync and landing fast-forward retries is a code constant, not a setting; the owner only says "bounded".

**JC-50 · GAP/local · 06 §6.2** — Mechanical checks per step (tests collect / new tests exist for SPEC-TO-TESTS; suite passes for SPEC-TO-IMPLEMENTATION, POSTMORTEM, CLEANUP and the merged tree; suite consistency for TESTS-TO-SUITE; artifact schemas) are my list. The owner names only the mechanism (run at record on the uncommitted diff; strays reverted). Running the suite after POSTMORTEM/CLEANUP was chosen because they edit living files after landing.

**JC-51 · AMBIG/local · 06 §6.2** — SPEC-TO-IMPLEMENTATION's declared paths exclude `testPaths` ("frozen tests"); any test edit by the implementer is a stray and reverted. The prose says "until the frozen tests pass", which supports it, but an implementer may legitimately need a test fixture file; that becomes a NEEDS-OWNER or a flag.

**JC-52 · TASTE/local · 06 §6.3** — A "test" is any `test*` function at module level or in a `Test*` class of a `.py` file under `testPaths`, found by `ast`. Pytest's collection rules are broader (configurable patterns); `ast` keeps counting deterministic and offline.

## Money and limits ([07])

**JC-53 · AMBIG/local · 07 §7.1** — Carry-forward files (`docs/TODO.md`, `docs/CLARIFICATIONS.md`) are priced at `postMortemFileCostPerToken` per token of delta with no base cost and no cap, in place of the normal living rates, whenever they change in a round (not only when POSTMORTEM edits them). The comment says "special case for postmortem carry-forward files"; whether the special rate applies to edits by other steps is not stated.

**JC-54 · AMBIG/local · 07 §7.1** — `estOutputFraction` is read as the output share of *total* tokens (`output = f × total`), so an estimate from a known prompt size is `total = input / (1 − f)`. Alternative: `output = f × input`. The difference is small at f = 0.2 and both are estimates.

**JC-55 · AMBIG/local · 07 §7.2** — `lostValuePerHour` is shown as context (status, checkpoint summary) and never booked in the ledger, following "globally lost budget per hour of time, for context". Alternative: book it as a separate ledger kind that does not count toward hard stops.

**JC-56 · AMBIG/local · 07 §7.4** — `maxRunWallClockHours` counts active time only (intervals between resume and pause), otherwise a round paused overnight at a checkpoint would re-pause immediately on resume. "Wall clock" could mean literal elapsed time.

**JC-57 · AMBIG/local · 07 §7.4** — Mechanical rejections count toward `maxTurnsPerGate` together with FAIL verdicts ("maximum turns (rejections) per gate"), and the same counter bounds ungated steps and conflict attempts. Alternative: a separate limit for mechanical rejections (no such key exists).

**JC-58 · AMBIG/local · 07 §7.2** — The driver's own cost is booked as `driverUsdPerStep` once per step (at first accepted attempt or skip), and driver attempts (CHAT-TO-PLAN) book no agent usage. Alternative: bill the driver per `next`/`record` call.

**JC-59 · AMBIG/local · 07 §7.2** — Measured usage precedence: full usage dict from `--usage-json` → total tokens from `--tokens` split by `estOutputFraction` → estimate from prompt size; each entry records its `source`. The Agent tool exposes at most a total token count to the driver, so the middle rung is what the driver will usually have.

## Doctor, invoke, hook ([08])

**JC-60 · GAP/local · 08 §8.1** — Doctor warns when `priceDate` in `subAgents.yaml` is older than 90 days. The owner records the date and source but says nothing about staleness; a warning costs nothing and the number is a code constant.

**JC-61 · TOOL/component · 08 §8.2** — `CliInvoker` runs the Claude Code CLI headless with `--agent <generated definition>` and JSON output to obtain measured usage. I could not verify the current flag names or the JSON envelope's usage keys; they are isolated in `CLI_ARGS` and a small parser. If the CLI cannot select an agent definition, the fallback is `--model` from the rung plus an effort environment setting, and the definitions still serve the Agent tool.

**JC-62 · GAP/component · 08 §8.2** — `maxSimultaneousSubAgentsPerRound` is enforced for helpers spawned through `run.py spawn` (lock-file slots) and validated in AGENTS-PLAN; sub-agents the driver spawns via the Agent tool are always one at a time because `next` hands out one attempt at a time. The owner's intent for this setting (driver concurrency vs helper concurrency) is not stated; both readings are covered.

**JC-63 · TASTE/local · 08 §8.3** — The hook never exits non-zero and never prints, logging an error line instead when the payload is unparsable, so a hook bug can never block the owner's chat. Alternative: fail loudly (a blocked prompt would be very visible but hostile).

**JC-64 · GAP/component · 08 §8.2** — Helpers exist at all: producers may spawn helper agents through the runner (`spawn`) so the roster's "sub-agents" in PLAN-AGENTS mean something and their usage is billed as measured. Claude Code sub-agents cannot themselves use the Agent tool (as I understand it), so a runner-mediated CLI spawn is the only path that keeps billing inside the ledger. Alternative: no helpers; AGENTS-PLAN's helper field ignored.

## Tests ([10])

**JC-65 · TENSION/component · 10 (intro)** — Which tests may read the real tree: only the drift test, the agent-definition freshness test, the registered-key surface test (project.yaml/subAgents.yaml keys, not prose) and the docs-consistency tests. No test opens the real locked prose, so "a prose rewrite fails only the drift test" holds; a roster edit fails drift plus the freshness test (acceptable: `accept-spec` regenerates the definitions).

**JC-66 · GAP/component · 10 §10.2** — The fake spec copies the real `src/` into the temp harness (not a symlink) so worktree attempts and the verify step exercise a real package; the runner under test is still the real one invoked with `--root`. Alternative: a minimal dummy `src/` (faster, but the judgment tool and verify would run against nothing real).

**JC-67 · TASTE/local · 10 §10.5** — The bounded-sync exhaustion test monkeypatches `fast_forward_main` to return False rather than racing a background pusher; the race is what the code handles, but a deterministic test is preferred in the permanent suite.

**JC-68 · GAP/local · 10 §10.6** — Probe assertions are structural (verdict, that a finding's quote contains the planted phrase) and never on wording; a probe that fails because a real model behaves differently is information about the prose, which is the owner's domain, so probes are opt-in and never in CI.

**JC-69 · GAP/local · 10 §10.5** — `test_steps.py::test_step_names_unique_and_order_fixed` writes the eleven step names a second time on purpose, so a change to the fixed table cannot pass silently through the generated fake spec (which is derived from the table itself).

## Whole-system calls (SPEC.md §1–§3)

**JC-70 · AMBIG/system · SPEC.md §1, §3** — The harness root is `harness/` (the directory holding `project.yaml`), the git repository root is its parent (where `spec.yaml` lives), and the driver's chat session runs with `harness/` as its working directory. AGENTS.md's relative paths (`src/run.py`, `docs/PROCESS.md`, `INDEX.md`) and `spec.yaml`'s `harness/…` entries only fit together this way, but nothing says it outright.

**JC-71 · AMBIG/system · SPEC.md §1** — The project the harness develops is itself: `livingSourcePaths` are the harness's own `src/`, `docs/`, `tests/`, and producers edit the runner's code in rounds. The vision says the harness "is intended to work with general software development" and "is still in early development"; the living paths say self-hosting for now. Alternative: a separate target project path (no setting exists for one).

**JC-72 · GAP/system · SPEC.md §2, 06 §6.1** — One git worktree per round on the round branch; attempts run sequentially in it; each attempt's work is the uncommitted diff at record and is committed then, whether or not the attempt is accepted (a rejected attempt's edits remain as the base for the retry). Alternatives: one worktree per attempt (isolates retries but loses partial progress); discard rejected diffs.

**JC-73 · AMBIG/local · SPEC.md §2** — Steps run strictly one at a time in table order; SPEC-TO-TESTS and SPEC-TO-IMPLEMENTATION are not run in parallel although both derive from the spec alone. The prose says "the tests, then the code"; parallelism would also complicate the single-worktree model.

**JC-74 · GAP/component · 02 §start** — The round is claimed (CAS push) at `start`, before planning, and `start` takes no owner quote; the plan, questions and approval happen inside the round (status `planning` → `awaiting-owner` → `running`). Alternative: plan outside any round and claim at approval (then PLAN.json has no round folder to live in).

**JC-75 · TASTE/local · 01 §1.4** — Generated agent definitions are committed (with a freshness test) rather than gitignored and generated at doctor time, so a fresh clone has them at the very first session start. Alternative: gitignore them and require `doctor` before the first session.

**JC-76 · AMBIG/local · 00 §0.7** — `PLAN.json` is JSON with a `text` field holding the plain-English plan, because `roundPaths.artifacts.plan` names a `.json` file while the prose says "the plan needs to read as plain English". The charge `planCostPerToken` applies to the whole file's tokens.

**JC-77 · GAP/local · 05 §5.5** — A mechanically rejected producer attempt (invalid message, missing artifact, failing suite, unresolved findings) is retried without a gate turn; the gate only ever judges attempts that passed the mechanical checks. Alternative: send every attempt to the gate with the mechanical notes.

**JC-78 · GAP/local · 07 §7.2** — `project.remaining` is computed from the `STATE.json` ledgers of rounds present under `archives/rounds/` in the driver checkout on main (plus the active round), not from remote branches; rounds are landed or record-landed there by JC-48, so nothing is missed once a round ends.

**JC-79 · GAP/local · 05 §5.7** — The round's `OWNER.log` slice starts at the previous round's `ended_at` (or the beginning of the log), so the planning conversation that precedes `start` is included in the record, and stale words from an earlier round cannot verify a quote.

**JC-80 · GAP/local · 05 §5.5** — Gates read `FINDINGS/` files (which embed the producer's `resolutions`) and never `RESULTS/` files, to honour "never the producer's transcript" even for the final message; the producer's summary text is therefore not shown to the gate.
