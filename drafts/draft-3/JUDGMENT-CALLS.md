# Judgment calls — part 1 (JC-01 … JC-35)

Definition used (the owner's): a judgment call is any choice that lands in the finished
work that I am not confident in making correctly, for any reason. Part 2 is in
`JUDGMENT-CALLS-2.md` (JC-36 … JC-71). Spec files reference calls inline as `[JC-nn]`;
the `Affects` field names the spec file and section either way.

## Classification scheme

Each call carries three labels:

- **Kind** — why the choice was not forced:
  `GAP` the owner's files are silent · `AMBIGUITY` they admit more than one reading ·
  `CONFLICT` two owner statements pull apart · `TOOLING` behaviour of an external tool
  (Claude Code, git, pytest, GitHub) that the files cannot settle.
- **Weight** — how much moves if the owner overrules it:
  `light` local to one section · `structural` ripples across components ·
  `owner-facing` changes what the owner sees or must do.
- **D/U** — per the owner's AGENTS.md: `D` (defined) decided from the spec files alone;
  `U` (undefined) needed knowledge from outside them.

Format: **JC-nn** (Kind · Weight · D/U) · *Choice* · *Chose* · *Alternatives* · *Why
unsure* · *Affects*.

## Calls

**JC-01** (GAP · light · D) · Whether the repository root carries a README. · A one-
paragraph pointer README, content fixed so it cannot go stale. · None; a longer guide
at the root. · The owner lists no root files beyond the spec files; "everything else is
derived" allows it but does not ask for it. · `01-repo-layout.md`, `16-docs.md`.

**JC-02** (TOOLING · light · U) · Whether to ship CI. · A minimal GitHub Actions
workflow running the suite (drift test included), marked optional. · No CI; a
provider-neutral script only. · The hosting platform is not stated anywhere in the
spec files. · `01`, `20-tooling-ci.md`.

**JC-03** (TOOLING · light · U) · How Claude Code gets to read the owner's `AGENTS.md`.
· `install` writes a `CLAUDE.md` containing `@AGENTS.md`, never overwriting one that
exists. · A symlink; asking the owner to configure it; duplicating the text. · Claude
Code's import syntax and Windows symlink support are outside the spec files. · `01`,
`15 install`, `20`.

**JC-04** (AMBIGUITY · structural · D) · What the "hashed baseline" stores so the failing
test can show a diff. · Hashes in `local.yaml` (authority) plus accepted copies under
`archives/spec-baseline/` (for diffs). · Hashes only (no diff possible); a git commit
sha as baseline (`git diff` against it; breaks on history rewrites); copies only. ·
The owner says "hashed baseline" and "failing test with diff" in one line; hashes
alone cannot diff. · `01`, `04 specfiles`, `19 test_spec_drift`.

**JC-05** (GAP · owner-facing · D) · How many rounds may be active at once. · One:
`start` refuses while any `round/*` branch is non-terminal (or unreadable). · Any
number, selected with `--round`. · "A CAS push claims a round" suggests one claim; the
files never say. · `02 §3`, `08 rounds.active`.

**JC-06** (AMBIGUITY · light · D) · What to do with `allowUpstream`. · Read it, require
`0`, refuse to start otherwise. · Ignore it; implement upstream sends. · The comment
says "TODO: Implement upstream mechanics"; the settings rule says every key is used. ·
`02 §3`, `04 config.validate_project`.

**JC-07** (GAP · light · D) · CHAT-TO-PLAN has no gate prose file but is in the gated
table. · Treat the gate prose as optional; if the owner turns the gate on without a
file, lint refuses to start. · Treat CHAT-TO-PLAN as never gated; synthesize a gate
prompt from COMMON-GATE. · `steps: CHAT-TO-PLAN: 0` with "0 = gate off" implies a gate
could exist; no file exists. · `02 §4`, `05 table`.

**JC-08** (AMBIGUITY · structural · D) · The meaning of shares in an agents plan and
what "enforced distribution" enforces. · Shares are fractions of the quote; work
shares must sum to `workFraction`; on-gate shares at most `gatesFraction`; off gates
cost nothing; `defaultShares` are warnings. · Shares as fractions of the work/gate
sub-budgets; enforcing minima; enforcing an exact gate sum. · "Enforced distribution
(sum to 1)" and "advisory minimum per-stage budgets" leave the unit of a share open. ·
`02 §4 PLAN-AGENTS`, `07 AGENTS-PLAN`.

**JC-09** (GAP · light · D) · What happens to round tests when TESTS-TO-SUITE is
overridden. · Nothing moves; every round test joins the suite. · Archive all;
refuse the override. · The override mechanism is described only in one prose line. ·
`02 §4 TESTS-TO-SUITE`.

**JC-10** (GAP · structural · U) · Which runner code runs after landing, given the
harness edits its own `src/`. · `next` fast-forwards the main checkout after a
successful landing, so POSTMORTEM/CLEANUP run under the landed runner. · Keep the old
runner until the round ends; never auto-pull. · Self-hosting is implied by
`livingSourcePaths` containing `src/` but never discussed. · `02 §4 LANDING`, `12
landing.land`.

**JC-11** (AMBIGUITY · light · D) · How the carry-forward files are priced. · Always at
`postMortemFileCostPerToken` on their net change, no cap, no base cost. · Standard
rates before POSTMORTEM and the special rate only for POSTMORTEM's edits (not
separable in a net-change ledger). · The comment "special case for postmortem carry-
forward files" does not say whether other steps' edits get the rate. · `02 §4
POSTMORTEM`, `13 ledger.carry_forward_price`.

**JC-12** (AMBIGUITY · owner-facing · D) · Which steps an `override` may skip. ·
Any step or gate except CHAT-TO-PLAN, LANDING and CLEANUP. · Allow LANDING/CLEANUP
skips (equivalent to abandoning or never booking); allow only gates. · "The plan
itself cannot be skipped" is the only stated exception. · `02 §5`, `05
parse_overrides`.

**JC-13** (AMBIGUITY · structural · D) · What "verifies quotes against the log" means
mechanically. · Whitespace-normalised substring of any log entry (local log or the
round's committed slice); no keyword check at all. · Exact byte match; requiring the
decision keyword inside the quote. · "Verbatim" versus chat clients re-wrapping text;
a keyword check would tie the runner to prose wording. · `02 §5`, `14
ownerlog.verify`.

**JC-14** (AMBIGUITY · structural · D) · What a "run" is for `maxTurnsPerRun` and
`maxRunWallClockHours`. · A run is the unattended stretch between owner pauses; turns
are `next` calls; both limits pause and `resume` starts a new run. · A run is one
agent attempt (unenforceable by the runner); a run is the whole round including waits.
· The keys are listed under "limits before pausing a round" with no definition. · `02
§6`, `10 pauses.check_run_limits`.

**JC-15** (AMBIGUITY · owner-facing · D) · What `maxRoundAttempts` ("attempts at
restarting a round after minor issues") bounds. · Resumes: each `resume` is a
restart; past the cap it refuses unless `--extend`. · Bound invalid-result re-runs
only; bound landing loops only. · One number, several plausible "restarts". · `02 §6`,
`10 pauses.resume`.

**JC-16** (GAP · light · D) · What bounds the "bounded sync" and the landing merge
loop. · `maxRoundAttempts` iterations for each. · A code constant; a new config key
(forbidden: settings live in the spec files). · The owner says "bounded" without a
number. · `02 §7`, `12 landing`.

**JC-17** (AMBIGUITY · structural · D) · How the runner detects that a gate finding
"repeats a withdrawn one". · Equality of whitespace-normalised `quote` fields within
the step. · Text similarity; asking the gate to mark repeats; comparing `text`. · The
runner cannot judge prose; quote equality is the only mechanical reading. · `02 §8`,
`11 findings.apply_gate`.

**JC-18** (CONFLICT · structural · D) · Keys the code needs that `project.yaml` lacks
(`testPaths`, `carryForwardFiles`, `promptWarnTokens`, `ownerLogPath`,
`verifyCommand`). · Defaulted keys in the config schema, reported by `doctor` as
"defaulted config keys"; the owner may add them to `project.yaml`. · Hard-code them;
refuse to start without them. · "Every setting the owner may edit appears in these
files" versus the comments naming `testPaths` and the carry-forward files without keys;
`doctor … defaulted config keys` suggests defaults are expected. · `04 config`.

**JC-19** (AMBIGUITY · light · D) · The order of the rung ladder. · File order, first
key highest (matches `maxAgent: max` being first). · Order by price; an explicit
`rank` key. · "Keys are rungs on a capability ladder" does not state direction. · `04
AgentsConfig.ladder`.

**JC-20** (GAP · light · D) · How lists and mappings render inside prompts. ·
Comma-space joined; mappings as `key: value` pairs. · YAML/JSON dumps. · The prose
renders `{{ project.livingSourcePaths }}` inline in a sentence. · `04
config.render_value`.

**JC-21** (AMBIGUITY · light · D) · What `{{ round.plan }}` shows. · The plan's `text`
followed by the numbered questions with the owner's answers and quotes. · The whole
`PLAN.json`; only `text`. · "Approved plan:" could mean either. · `06 context`, `07
plan_as_text`.

**JC-22** (AMBIGUITY · light · D) · What `{{ project.gates }}` ("Gates, in order")
lists. · Every gate-capable step in table order with `on/off`. · Only the on gates;
all steps. · Agents are told to behave as if gates were on, so showing off gates
seemed useful. · `06 context.gates_text`.

**JC-23** (AMBIGUITY · light · U) · Whether COMMON-STEP-END is a second message. ·
The tail of the one prompt per attempt. · A follow-up message through the Agent
tool's resume feature. · The prose calls it "a message produced at the end of every
step"; one-prompt attempts keep `doctor` and tests exact; resume support is outside
the files. · `06 prompts layout`.

**JC-24** (GAP · light · D) · How nested plumbing tokens inside a gate-prose preview
render. · Masked as `[gate process instructions omitted]`. · Render the gate's real
instructions; leave the token. · Rendering the gate's instructions inside a producer
prompt would be misleading. · `06 prompts.gate_prose_preview`.

**JC-25** (GAP · light · D) · The LANDING conflict prompt has no prose file. · Built
from `COMMON-PROJECT/ROUND/OVERVIEW` when present plus plumbing; a `LANDING-
OVERVIEW.txt` is used if the owner adds one. · A hard-coded full prompt; refuse to
land on conflict. · No LANDING prose exists; the settings surface rule discourages
harness-owned text. · `06 prompts.landing_prompt_body`.

**JC-26** (GAP · light · D) · The prompt-size warning threshold. · A defaulted key
`promptWarnTokens = 40000`. · A constant; no warning. · The comment mentions the
warning but no number. · `06 size_warning`, `04`.

**JC-27** (GAP · light · D) · How gates see a code diff. · Inline when small,
otherwise a companion `PROMPTS/<STEP>-<n>.diff` file. · Always a file; no diff, gate
reads the worktree. · "One file per STEP-attempt" in PROMPTS is slightly bent by the
companion file. · `06 prompts.write_prompt`.

**JC-28** (GAP · light · D) · How to find the JSON in an agent's final message. ·
Last ```json fence, else the last balanced object. · First object; require the whole
message to be JSON. · Agents often wrap JSON in prose. · `07 extract_json`.

**JC-29** (AMBIGUITY · light · D) · Where the postmortem "summary" ends for pricing. ·
The section under the first `Summary` heading; whole file if absent (noted). · Charge
nothing if absent; charge the whole file always. · The prose asks for the summary
"under the heading Summary" but the heading level is unspecified. · `07
postmortem_summary`, `13 archive_charge`.

**JC-30** (CONFLICT · light · D) · Requiring a non-empty suggestion on blocking
findings. · Required in the schema (invalid otherwise). · Optional with a warning. ·
The rule comes from COMMON-GATE prose ("every finding carries a suggestion"); code must
not depend on prose wording, yet the JSON contract is the harness's own. · `07
validate_findings`.

**JC-31** (GAP · structural · U) · What happens locally after a lease push is rejected.
· Save the local commit to `round/NNNN-orphan-<ts>`, reset to the remote, exit 4. ·
Keep the local branch and refuse further commands; discard silently. · "Every state
change pushes the branch as a fence" says nothing about the loser's local state. · `09
backup_branch`, `10 commit_and_push`.

**JC-32** (AMBIGUITY · light · D) · Whether mechanical (verify) rejections count
against `maxTurnsPerGate`. · Yes: any rejection of a producer consumes a gate turn. ·
A separate counter; unlimited retries. · The key says "turns (rejections) per gate";
a verify failure is a rejection with no gate. · `10 fail_producer`.

**JC-33** (GAP · owner-facing · D) · The round's status when the post-landing sync
fails. · `DONE` with `sync.status = failed` and a manual-merge message. · `PAUSED`
until synced; `ABANDONED`. · The owner only says post-landing commits must not be
orphaned. · `10 finish_round`, `12 landing.sync`.

**JC-34** (AMBIGUITY · light · D) · The concrete "blocking flags follow the verdict"
rule. · FAIL upgrades all non-blocking findings to blocking; PASS downgrades blocking
ones to flags. · FAIL with no blocking finding is invalid; PASS with blocking findings
is invalid. · The owner's sentence gives the principle, not the mechanics. · `11
findings.apply_gate`.

**JC-35** (GAP · light · D) · A clean merge whose suite then fails at landing. · Pause
`LANDING_FAILED` (no agent attempt). · Treat as a conflict attempt on the files both
sides touched. · The owner defines the attempt for textual conflicts only. · `12
landing.land`.
