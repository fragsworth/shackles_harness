# 16 — Documentation files: `docs/`, `INDEX.md`, root `README.md`

All of `docs/` is living (charged per token): every file is dense, plain English,
and each has a stated audience. Owner-facing files quote no locked prose (the prose
changes often; the docs describe mechanics only). A test (`test_docs.py`, file 18)
checks that every `docs/*.md` starts with a level-1 heading and an `Audience:` line,
that every CLI command in `commands.register` is mentioned in `OWNER-GUIDE.md` or
`PROCESS.md`, and that `SCHEMAS.md` names every field `schemas.describe` mentions.

## `docs/PROCESS.md` — the rules for agents inside the harness
Audience: any agent spawned by the driver; the driver itself. AGENTS.md sends every
agent here ("read docs/PROCESS.md for the rules").
Sections: (1) Where you are — the worktree, the branch, the round folder, what the
runner owns. (2) Your prompt — its layout (file 06), the plumbing headings and what
each tells you. (3) What you may change — declared paths, the round folder rule
(artifacts and the two trails only), frozen tests, strays are reverted not punished,
spec files are never yours. (4) Your final message — the exact producer and gate JSON
(from `schemas.describe`), the three statuses, when to use each, what happens next
for each. (5) Findings — how prior findings arrive, `fixed`/`disputed`, settled after
two upholds, that silence is invalid. (6) Judgment calls — the `jc` command, the two
kinds as AGENTS.md defines them, gates report in the message. (7) Limits — budget,
turns, sub-agents, verify timeout, and that the runner enforces only what it can
measure. (8) The driver's loop — `next` → spawn with the prompt file verbatim (gate:
the `-gate` definition) → save the final message → `record`; the decision flags for
CHAT-TO-PLAN and checkpoints; relay runner messages verbatim; never paraphrase an
owner word into a quote.

## `docs/OWNER-GUIDE.md` — for the owner
Audience: the owner. Sections: (1) Install — requirements (git with an `origin`,
Python 3.11+, `pip install pyyaml pytest`), `run.py install`, restart the session,
`run.py doctor`. (2) Starting a round — what to say, that the driver runs `start`
with your words, the plan and its questions. (3) The words that count — a pointer
to `locked_prose/CHAT-TO-PLAN-OVERVIEW.txt` (not quoted). (4) Checkpoints and pauses
— what a pause message contains, `resume`/`abandon`, hard-stop overrides. (5) Editing
the spec files — the drift test, `spec status|diff|accept`, that `start` refuses
drift, that the step list is fixed in code. (6) Where things are — round folders,
HISTORY.md, the ledger command, INDEX.md. (7) Several machines — the round branch,
worktrees, fences, OWNER.log per machine. (8) Recovering — a failed sync, an orphan
branch, `prune`.

## `docs/ARCHITECTURE.md` — how the code realises the owner's architecture features
Audience: agents changing `src/`. One section per feature sentence of the owner's
SPEC.md (git lock; driver interprets/runner verifies; step table as code; delegation;
spec guard; mechanical checks and strays; landing conflict attempt; bounded sync;
verdict wins; generated one-line spec for tests; stub agent and probes; doctor; prompt
hook and OWNER.log; generated agent definitions; ledger bills what happened; nothing
closes in silence; settings surface), each naming the modules and functions that
implement it. Plus the module dependency table (owns / depends on / depended on by)
copied from this spec's per-module sections, and the invariants that tests enforce.

## `docs/PROMPTS.md` — prompt assembly
Audience: agents and the owner editing prose. The layout, the five namespaces and
their keys (`project.<any config key>`, `project.remaining`, `project.gates`,
`round.id|folder|base_commit|plan|budget|spend|remaining`, `agents.<SECTION>`,
`prose.<STEM>`, `plumbing.PROCESS-INSTRUCTIONS|GATE-PROSE`), recursion and cycle
rules, what happens when a token is unknown (doctor lists; `next` refuses), how the
plumbing block is appended when a prose file omits its token, the size warning.

## `docs/SCHEMAS.md` — the JSON formats
Audience: agents. The six artifact/message shapes from file 07 with field tables
(required, type, meaning), plus STATE.json's top-level fields for the curious, with a
note that it is the runner's and never edited by hand.

## `docs/LEDGER.md` — the pricing math
Audience: the owner and planning agents. Attempt cost (measured vs estimated), the
living charge with a worked example (a 12,000-token file grown by 500 tokens, a new
file, a removed test), archive charges, carry-forward pricing, the hard stops and
when they are checked, what is informational (`lostValuePerHour`, `budget`).

## `docs/TESTING.md` — running and writing tests
Audience: agents in SPEC-TO-TESTS and SPEC-TO-IMPLEMENTATION. `python -m pytest` from
the harness root; the generated fixture spec and why tests never read the real prose;
the stub agent behaviours table (file 17) and how to add one; the fake driver; git
fixtures; the drift and lint tests and what to do when they fail; probes (`-m probe`,
`SHACKLES_PROBES=1`, cost warning).

## `docs/TODO.md` and `docs/CLARIFICATIONS.md` — carry-forward files
Audience: the owner and CHAT-TO-PLAN/POSTMORTEM. Each starts with a level-1 heading
and a one-line format note; entries are `- [round NNNN] <text>` bullets. TODO.md holds
proposed resolutions POSTMORTEM adds and CHAT-TO-PLAN offers; CLARIFICATIONS.md
holds questions with the plan and the exact owner words that raised them. Both are
priced at `postMortemFileCostPerToken`.

## `INDEX.md` (harness root, generated)
See file 15. Free (outside living paths).

## `README.md` (repository root, derived)
One paragraph: this repository is the shackles harness; `spec.yaml` lists the owner's
spec files; `harness/` is the harness; start with `harness/docs/OWNER-GUIDE.md`; run
`python src/run.py doctor` from `harness/`. No other content, so it never goes stale.
