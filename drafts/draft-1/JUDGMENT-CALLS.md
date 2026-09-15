# Judgment-call log — draft 1

Definition used (the owner's, verbatim): a judgment call is any choice that
lands in your finished work that you are not confident in making correctly
for any reason. This log tracks and classifies them; it does not try to
prevent them.

## Classification scheme

Two axes on every call.

**Basis** (what the call rests on):
- `DEFINED` — decidable from the spec files' text alone; I chose one reading
  of words that are there.
- `UNDEFINED` — the spec files are silent or conflict; I supplied a rule.

**Kind** (what the call is about):
- `reading` — interpreting an owner sentence.
- `mechanism` — how something is done (a platform or git or file mechanic).
- `default` — a number, name or value the owner never gave.
- `scope` — what to include or leave out.

**Risk**: `low` (easy to change later, local), `medium` (touches several
components or prompts), `high` (changes what the owner sees or pays).

Format per entry: id, the choice, what I chose, alternatives, why not
confident, classification, spec sections affected.

---

- **JC-01** Drift semantics for missing files and the diff source. Chose: a
  listed file that no longer exists is drift, not a crash; a glob matching
  nothing refuses; the diff comes from `git diff <acceptedCommit>` plus full
  listings for untracked files. Alternatives: store full snapshots in the
  baseline; treat a missing file as a crash. Not confident: the owner said
  "failing test with diff" without saying against what. `DEFINED /
  mechanism / low`. Sections: `25-archives.md`, `31-src-config.md`.
- **JC-02** What `local.yaml` is. Chose: gitignored, machine-local, derived
  facts only (paths, hashes, owner-log cursor); the spec baseline lives in
  `archives/spec-baseline.yaml` (committed, generated). Alternatives: commit
  `local.yaml` and put the baseline in it; put the baseline under `tests/`.
  Not confident: "local.yaml is generated; and does not contain user input"
  says what it is not, not where the baseline goes. `UNDEFINED / mechanism /
  medium`. Sections: `20-harness-root.md`, `25-archives.md`.
- **JC-03** Defaulted config keys with code defaults. Chose: ten keys
  (`SPEC.md` §7) with code defaults, each named by doctor. Alternatives: no
  defaults (refuse on any missing key); hard-code the values. Not confident:
  "the whole settings surface" argues against code knobs, but the prose
  refers to `testPaths`, which the file lacks, and doctor is required to
  name "defaulted config keys", so defaults must exist. `UNDEFINED / default
  / medium`. Sections: `SPEC.md` §7, `31-src-config.md`.
- **JC-04** Commented placeholder keys (`ownerHourlyRate`,
  `costToWaitForOwner`). Chose: doctor lists them as seen-and-ignored; not
  read. Alternative: ignore silently. Not confident: "each is used for
  something" versus "Ignore for now". `DEFINED / scope / low`. Section:
  `31-src-config.md`.
- **JC-05** What a test is. Chose: a `def test_` function in a `.py` file
  under `testPaths`; other languages count zero. Alternatives: pytest
  collection output; a per-language plugin. Not confident: the harness is
  for "general software development" but the prose says "a test function
  in a file under testPaths" without a language. `DEFINED / default /
  medium`. Sections: `SPEC.md` §6, `37-src-ledger.md`.
- **JC-06** Rung ladder order. Chose: file order in `subAgents.yaml`, first
  is highest. Alternatives: sort by price; an explicit rank key (would be a
  new setting). Not confident: "Keys are rungs on a capability ladder" gives
  no order. `UNDEFINED / default / low`. Section: `31-src-config.md`.
- **JC-07** Where the harness root is. Chose: the parent folder of the
  `AGENTS.md` listed in `spec.yaml` (`harness/`). Alternative: a fixed
  `harness/` name. Not confident: project.yaml says "from the harness root"
  without defining it. `DEFINED / mechanism / low`. Section:
  `31-src-config.md`.
- **JC-08** Which steps `override` may skip and what skipping does. Chose:
  gates, checkpoints, PLAN-AGENTS (defaults apply), TESTS-TO-SUITE (all
  tests join the suite), POSTMORTEM (nothing); never CHAT-TO-PLAN,
  PLAN-TO-SPEC, SPEC-TO-TESTS, SPEC-TO-IMPLEMENTATION, LANDING, CLEANUP.
  Alternatives: allow any step; allow gates only. Not confident: the prose
  says "override + steps or gates: the runner skips them this round; the
  plan itself cannot be skipped", silent on which steps are safe.
  `UNDEFINED / scope / high`. Sections: `32-src-steps.md`, `34-src-round.md`.
- **JC-09** Inputs per step. Chose the table in `32-src-steps.md`
  (implementation reads plan and spec, not the tests' text as an artifact;
  the tests are in the tree). Alternative: every earlier artifact for every
  step. Not confident: prose says each step is built "from the spec alone"
  for tests and code, and CHECKPOINT summarises everything. `DEFINED /
  scope / medium`. Section: `32-src-steps.md`.
- **JC-10** Committing `.claude/agents/` and `.claude/settings.json`. Chose:
  committed, regenerated by `setup`. Alternative: gitignored and generated
  per machine. Not confident: a fresh clone needs them at session start, but
  they are generated files. `UNDEFINED / mechanism / low`. Section:
  `10-repository-root.md`.
- **JC-11** Rendering `{{ project.gates }}`. Chose: every gated step in
  order with `on`/`off` for this round. Alternatives: only gates that are on;
  the bare list of gate names. Not confident: "Gates, in order:" is all the
  prose says, and agents must hold gate standards even when gates are off.
  `DEFINED / reading / low`. Section: `33-src-prompts.md`.
- **JC-12** A prose file without the plumbing token. Chose: append the
  plumbing at the end with a warning. Alternative: refuse to render. Not
  confident: robustness to arbitrary edits argues for appending; "unknown
  inputs refuse to start" argues for refusing. `UNDEFINED / mechanism /
  low`. Section: `33-src-prompts.md`.
- **JC-13** Delivering COMMON-STEP-END. Chose: default `inline` at the end
  of the prompt under "Before your final message"; optional `follow-up`
  mode that re-contacts the same sub-agent. Alternative: follow-up only.
  Not confident: "This message is produced at the end of every step where
  an agent has done work" reads as a second message, but sub-agent
  resumption is a platform feature I cannot verify. `DEFINED / mechanism /
  medium`. Sections: `SPEC.md` §7, `33-src-prompts.md`, `63-tests-mechanics.md`.
- **JC-14** Gate prose shown to producers when the gate is off or absent.
  Chose: always render it, prefixed "gate is off this round; the standard
  still applies"; absent file becomes a fixed sentence. Alternative: omit
  when off. Not confident: "All agents operate on the same standards as if
  the gates ... were on" supports rendering; CHAT-TO-PLAN has no gate file
  yet still uses the token. `DEFINED / reading / low`. Section:
  `33-src-prompts.md`.
- **JC-15** Owner-quote verification rule. Chose: verbatim substring of one
  logged entry, whitespace-normalized by default, latest match wins.
  Alternatives: exact only; whole-entry equality; fuzzy match. Not
  confident: "verifies quotes against it" does not say how strict.
  `UNDEFINED / mechanism / medium`. Section: `34-src-round.md`.
- **JC-16** `{{ round.plan }}` rendering. Chose: a fixed plain-English
  layout of PLAN.json's fields. Alternative: pretty-printed JSON. Not
  confident: "the plan needs to read as plain English" is about the plan,
  not the token. `DEFINED / mechanism / low`. Section: `34-src-round.md`.
- **JC-17** Final-message parsing. Chose: the last JSON object in the
  message, bare or fenced. Alternative: the whole message must be JSON.
  Not confident: "the JSON your final message must be" is strict; models
  often add a sentence. `DEFINED / mechanism / low`. Section: `34-src-round.md`.
- **JC-18** Detecting a repeat of a withdrawn finding without parsing prose.
  Chose: the gate's `repeats` id, or an identical normalized `quote`.
  Alternative: gate-only; textual similarity. Not confident: the owner's
  rule needs a detector and the runner may not parse prose. `UNDEFINED /
  mechanism / medium`. Section: `34-src-round.md`.
- **JC-19** Meaning of `maxRoundAttempts` for resumes. Chose: `resume`
  counts toward it and is refused above it; only abandon or an explicit
  owner override then. Alternative: resumes unlimited. Not confident:
  "maximum attempts at restarting a round after minor issues" fits both
  resumes and mechanical retries (see JC-27). `DEFINED / reading / medium`.
  Section: `34-src-round.md`.
- **JC-20** Carry-forward pricing. Chose: `postMortemFileCostPerToken` per
  token, no base cost, no cap. Alternative: tiered price with the
  postmortem rate below the cap. Not confident: "special case for
  postmortem carry-forward files" gives the rate only. `DEFINED / default /
  low`. Section: `37-src-ledger.md`.
- **JC-21** What `specCostPerToken` prices. Chose: SPEC.json and SPEC.md
  together. Alternative: SPEC.md only (owner-read). Not confident: "for
  specs (stored in round, frozen)". `DEFINED / reading / low`. Section:
  `37-src-ledger.md`.
- **JC-22** What an abandoned round leaves on `main`. Chose: only its round
  folder (so the ledger is complete), work discarded, branch kept.
  Alternatives: nothing on main; everything. Not confident: "the round
  ends without landing" versus "the ledger bills what happened".
  `UNDEFINED / mechanism / medium`. Sections: `25-archives.md`, `40-src-engine.md`.
- **JC-23** Usage when the driver reports no token count. Chose: estimate
  from prompt and result sizes with an output floor of `estOutputFraction`.
  Alternative: refuse to record without `--tokens`. Not confident: the
  Agent tool's reporting is a platform detail. `UNDEFINED / default /
  medium`. Section: `37-src-ledger.md`.
- **JC-24** When `driverUsdPerStep` is booked. Chose: once per step at
  acceptance (or skip by limit). Alternative: per attempt. Not confident:
  the name says per step; the driver's work is per attempt. `DEFINED /
  reading / low`. Section: `37-src-ledger.md`.
- **JC-25** `lostValuePerHour`. Chose: shown as context, never booked.
  Alternative: booked at cleanup. Not confident: "for context" versus
  "globally lost budget". `DEFINED / reading / medium`. Section:
  `37-src-ledger.md`.
- **JC-26** Shares summing above 1. Chose: scale down with a warning.
  Alternative: mechanical retry of PLAN-AGENTS. Not confident: the gate is
  the judge of the plan; the runner should only keep arithmetic sane.
  `UNDEFINED / mechanism / low`. Section: `38-src-quote.md`.
- **JC-27** `maxRoundAttempts` also bounds mechanical retries per step.
  Chose: yes (with JC-19). Alternative: a code constant for retries. Not
  confident: overloading one setting. `DEFINED / reading / medium`.
  Sections: `38-src-quote.md`, `40-src-engine.md`.
- **JC-28** Gate tool set. Chose: `Read, Grep, Glob`. Alternative: add
  `Bash` for running tests. Not confident: "read-only for gates" is clear,
  but a gate judging tests might want to run them. `DEFINED / default /
  low`. Section: `39-src-agents.md`.
- **JC-29** `accept-spec` refuses while a round is open. Chose: refuse.
  Alternative: allow. Not confident: mid-round spec changes would change
  prompts mid-round. `UNDEFINED / scope / low`. Section: `41-src-commands.md`.
- **JC-30** Mechanics tests use tiny limits and prices. Chose: overrides
  in the generated spec. Alternative: real values (slow tests). `UNDEFINED /
  mechanism / low`. Section: `63-tests-mechanics.md`.
- **JC-31** The follow-up step-end action shape (`phase: step-end`).
  Chose: a `SPAWN` for the same attempt with a phase. Alternative: a new
  action kind. `UNDEFINED / mechanism / low`. Sections: `63-tests-mechanics.md`,
  `70-contracts.md`.
- **JC-32** Proving "each setting is used for something". Chose: an
  attribute-access tracker used only under one lint test. Alternative: grep
  `src/` for the key names. Not confident: a tracker adds a wrapper to the
  settings object. `UNDEFINED / mechanism / low`. Section: `64-tests-lint-drift.md`.
- **JC-33** Live probes spawn real agents through the Claude Code CLI
  headless. Alternative: the API directly (would bypass agent definitions
  and effort). Not confident: CLI flags for agents, effort and JSON output
  are platform details I cannot verify. `UNDEFINED / mechanism / medium`.
  Section: `65-tests-live.md`.
- **JC-34** The harness develops itself. Chose: `src/`, `docs/`, `tests/`
  under `harness/` are both the runner's code and the living project.
  Alternative: the runner elsewhere, living paths for a separate project.
  Not confident: AGENTS.md says `src/run.py` is the runner and `src/` is
  living; the vision says "general software development". `DEFINED /
  reading / high`. Sections: `SPEC.md` §1, §3, `30-src.md`.
- **JC-35** Python 3.12 + PyYAML + pytest. Alternatives: any other stack.
  Not confident: the spec files name no language; `run.py` implies Python.
  `DEFINED / default / medium`. Section: `SPEC.md` §6.
- **JC-36** Attempts are serial; `maxSimultaneousSubAgentsPerRound` limits
  a producer's own nested sub-agents. Alternative: parallel attempts. Not
  confident: the step table is linear, and PLAN-AGENTS "choose[s] ...
  sub-agents ... for each step". `DEFINED / reading / medium`. Sections:
  `34-src-round.md`, `38-src-quote.md`.
- **JC-37** CHAT-TO-PLAN is done by the driver itself (`SELF` action), and
  checkpoints likewise. Alternative: a sub-agent for planning. Not
  confident: "You are the runner/driver" and "the only agent that speaks to
  them" settle it, but AGENTS.md says every `next` gives a prompt for a
  sub-agent. `DEFINED / reading / medium`. Sections: `SPEC.md` §4,
  `40-src-engine.md`.
- **JC-38** The round's ledger lives inside `STATE.json`; `LEDGER.md` is a
  human record; `project.remaining` sums every round's `STATE.json`.
  Alternative: a separate ledger file as state. Not confident: "STATE.json
  ... the runner's only state" versus "the ledger". `DEFINED / mechanism /
  medium`. Sections: `25-archives.md`, `37-src-ledger.md`.
- **JC-39** Worktree location `harness/.worktrees/` (gitignored) and a
  persistent runner worktree on the round branch. Alternative: outside the
  repo; no runner worktree (commit from the main checkout). `UNDEFINED /
  mechanism / low`. Sections: `20-harness-root.md`, `35-src-git.md`.
- **JC-40** The runner's own `OWNER.log` slice starts at the machine's
  cursor (entries not yet consumed by any round on this machine) and is
  refreshed at every `owner` command. Alternative: entries since round start
  only (loses the words that led to the plan). `UNDEFINED / mechanism /
  medium`. Sections: `20-harness-root.md`, `34-src-round.md`.
- **JC-41** A landing conflict is "judged against git's auto-merged tree"
  mechanically: only conflicted files may differ, markers must be gone;
  no gate runs (LANDING has none). Alternative: a gate attempt comparing
  trees. `DEFINED / reading / medium`. Sections: `35-src-git.md`,
  `40-src-engine.md`.
- **JC-42** `AGENTS.md` is rendered verbatim at the head of every prompt.
  Alternative: rely on the platform loading it. Not confident: the judgment
  call definition counts AGENTS.md as prompt text; whether Claude Code loads
  it for sub-agents is a platform detail. `DEFINED / mechanism / low`.
  Section: `33-src-prompts.md`.
- **JC-43** Verification per step: COLLECT after SPEC-TO-TESTS, PASS after
  IMPLEMENTATION, TESTS-TO-SUITE, LANDING, CLEANUP; none after planning
  steps and POSTMORTEM. Alternative: PASS everywhere after landing too.
  `UNDEFINED / scope / medium`. Section: `32-src-steps.md`.
- **JC-44** Off gates leave their share unspent rather than redistributing
  it. Alternative: fold it into the work pool. Not confident: "A gate that
  is off does not incur a charge" and "sum to 1". `DEFINED / reading / low`.
  Section: `38-src-quote.md`.
- **JC-45** `hardStopBudgetMultipleIndividual` applies to one attempt's
  cost against that attempt's share budget, checked after record.
  Alternative: per step across attempts. `DEFINED / reading / medium`.
  Sections: `37-src-ledger.md`, `40-src-engine.md`.
- **JC-46** A "run" for `maxTurnsPerRun` and `maxRunWallClockHours` is the
  stretch between a start or resume and the next pause. Alternative: the
  whole round. `UNDEFINED / reading / medium`. Sections: `34-src-round.md`,
  `38-src-quote.md`.
- **JC-47** `allowUpstream: 0` is read and rendered nowhere but validated
  as a known key; upstream mechanics are not designed (the owner marked it
  TODO). `DEFINED / scope / low`. Section: `31-src-config.md`.
- **JC-48** Owner-facing `docs/CONTRACTS.md` duplicates the shapes in code.
  Alternative: generate it from the validators. Not confident: "be dense"
  versus agents needing the shapes in a file they can read. `UNDEFINED /
  scope / low`. Section: `50-docs.md`.
- **JC-49** Repeat-withdrawn dropping and blocking-flag correction are done
  by the runner, not asked of the gate. `DEFINED / reading / low`.
  Section: `34-src-round.md`.
- **JC-50** CI runs everything but live probes; live probes are manual.
  `UNDEFINED / scope / low`. Section: `10-repository-root.md`.
