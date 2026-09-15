# 50 — harness/docs/ (living prose)

Parent: `SPEC.md` §3. Four files. All are living and charged per token, so
each is as short as its job allows. Two are carry-forward files edited by
POSTMORTEM (`carryForwardFiles`); two are references agents are pointed at
by AGENTS.md and by the plumbing. No document here is authoritative over the
code: a lint test keeps the references in sync where that can be checked
mechanically (`64-tests-lint-drift.md`).

```
harness/docs/
  PROCESS.md          the rules: round lifecycle, driver protocol, agent duties, owner verbs
  CONTRACTS.md        the JSON shapes and CLI outputs, as agents and the driver see them
  TODO.md             carry-forward: proposed resolutions for next rounds (POSTMORTEM appends)
  CLARIFICATIONS.md   carry-forward: questions only the owner can settle (POSTMORTEM appends)
```

## PROCESS.md ("read `docs/PROCESS.md` for the rules")

Sections, each a few lines:

1. **The round** — the step list, what each step produces, gates and
   checkpoints, where the record lives (`archives/rounds/NNNN/`).
2. **The driver protocol** — `setup` once; `doctor`; `start`; loop: `next` ->
   act on the action (`SELF`: follow the prompt yourself; `SPAWN`: give the
   prompt file verbatim to a fresh sub-agent of the named agent file, save its
   final message to the result file, run `record <attempt> --tokens N`;
   `OWNER`: relay `message` verbatim, wait, then `owner <verb> --quote`;
   `END`: stop). Never edit living files as the driver except `PLAN.json`
   during CHAT-TO-PLAN. Never commit or push.
3. **Owner words** — the verbs, how the driver interprets and hands over a
   verbatim quote, that the runner checks the quote against the owner log,
   that answers may be anything, that delegation skips only checkpoints.
4. **Producers** — worktree, declared paths, artifact, the judgment-call tool,
   the final JSON, what the runner reverts, what fails a step (nothing
   mechanical fails it; contract problems and failing tests re-spawn it).
5. **Gates** — read-only, what they see, verdict rules (rulings first,
   repeats of withdrawn findings are dropped, the verdict wins, upheld twice
   is settled), that every finding needs a suggestion.
6. **Money** — the quote, shares, the living charge, archive costs, hard
   stops, the ledger bills what happened.
7. **Limits and pauses** — every pause reason and the verbs that continue.
8. **Spec files** — never edited during a round; drift fails a test and
   refuses `start`; `accept-spec` between rounds.

## CONTRACTS.md

The agent- and driver-facing copy of `70-contracts.md`'s shapes: the producer
final message, the gate final message, the driver's results, `PLAN.json`,
`AGENTS-PLAN.json`, `SPEC.json`, `SUITE.json`, the `next` action, the
`record` and `owner` outputs. Each shape is shown once as a JSON template with
one-line field notes. A lint test checks that every field name the validators
in `round/artifacts.py` and `round/results.py` require appears in this file.

## TODO.md and CLARIFICATIONS.md (carry-forward)

Each starts with a two-line header explaining its purpose and the entry
format: `- [NNNN] <text>` for TODO (a proposed resolution and the round that
proposed it); `- [NNNN] <problem> — plan: <quote> — owner words: "<quote>" —
judgment call: <ref or none>` for CLARIFICATIONS. POSTMORTEM appends; CLEANUP
may prune resolved entries; CHAT-TO-PLAN reads TODO.md to suggest the
highest-impact open items. Both are priced at `postMortemFileCostPerToken`
when POSTMORTEM changes them and never stop a round when over budget.
