# 09 — Documentation under `harness/docs/`

Parent: [`../SPEC.md`](../SPEC.md). Five files. `docs/` is a living path: every token is
charged, so each file is dense, and each says only what no code comment can. Two are
carry-forward files edited by rounds (TODO, CLARIFICATIONS); three describe the rules
and are kept true by tests in `tests/test_docs.py` (file 10).

The owner's rule from the monorepo world applies here too and is stated at the top of
`PROCESS.md`: the code is the authority; when a doc and the code disagree, fix the doc.

---

## docs/PROCESS.md — the rules of a round

Target size: under 2,500 tokens. Sections, in order:

1. **What a round is.** One paragraph: a round turns the owner's request into landed
   code through a fixed list of steps, each performed by one fresh agent from a prompt
   the runner renders from the owner's locked prose; the runner alone commits, pushes and
   talks to the owner (through the driver).
2. **Roles.** Owner; driver (the agent in the owner's chat: runs `run.py`, performs
   CHAT-TO-PLAN and checkpoints itself, spawns every other agent, relays owner words as
   verbatim quotes); producer; gate (read-only); helper sub-agents (spawned by a
   producer, bounded by AGENTS-PLAN and `maxSimultaneousSubAgentsPerRound`).
3. **The step table.** A table generated from `steps.TABLE`: name, kind, performer, gate
   possible, what it may edit, verification, artifacts. `tests/test_docs.py` regenerates
   it and asserts equality, so the doc cannot drift from the code.
4. **The driver loop.** The exact loop, also quoted in `README.md`:
   ```
   python3 src/run.py start
   loop:
     N = python3 src/run.py next
     spawn: give N.prompt_file verbatim to a fresh sub-agent of type N.agent_definition
            with cwd N.cwd; if the tool allows a follow-up, send N.end_prompt_file; save
            the final message to N.result_file; python3 src/run.py record N.attempt [--usage ...]
     self:  read N.prompt_file and do it yourself; write PLAN.json; save your result JSON; record
     chat:  read N.prompt_file; talk to the owner; hand every decision over with
            python3 src/run.py owner --kind K --quote "<exact owner words>" ...
     done:  present N.bill, N.flags and N.postmortem_summary; stop
   ```
5. **Owner words the runner accepts.** The `control.KINDS` table, generated: kind,
   meaning, CLI form. States plainly that the driver classifies and the runner only
   verifies the quote exists in `OWNER.log`.
6. **Pauses.** The reasons (`checkpoint`, `approval`, `questions`, `blocked`, `limit`,
   `hard-stop`, `conflict`, `sync-conflict`, `drift`) and what ends each one. Delegation
   skips only checkpoints.
7. **Final messages.** Producer and gate JSON, from `results.schema_text`, generated.
8. **Findings.** The state diagram from file 05 in prose: respond to every open finding;
   disputes are ruled on; upheld twice is settled; PASS turns non-blocking findings into
   owner flags; repeats of withdrawn findings are dropped with a note; nothing closes in
   silence.
9. **Path discipline.** Declared paths, the round folder, strays reverted and noted,
   refusals, the spec files never touched, frozen tests.
10. **Judgment calls.** The two kinds (quoting AGENTS.md by reference, not copy), the
    tool command, gates report in the final message.
11. **Limits.** Each `max*` key and what happens when hit (pause; resume counts as a restart).
12. **Git.** Round branch, worktree, fence pushes, claim by CAS push, landing, conflict
    attempt, post-landing sync, abandon lands the round folder only.

---

## docs/MONEY.md — how dollars are computed

Target size: under 1,200 tokens. Sections: token estimate (one formula); attempt cost
(measured vs estimated, spawn cost, driver per step); the quote and shares (enforced caps,
advisory minima, retries budgeted at the share again); hard stops (round multiple with
projected living charge before landing; individual multiple per attempt); the living
charge (the five-step algorithm from file 06, verbatim); archive charges (plan, spec,
postmortem summary; frozen, never refunded); the bill and `project.remaining`. Every
number is a config key name, never a value, so the doc survives price edits.

`tests/test_docs.py` checks that every config key named in this file exists in
`config.REQUIRED` or `config.DEFAULTS`.

---

## docs/TESTING.md — how the harness tests itself

Target size: under 900 tokens. Sections: the generated one-line spec (`tests/specgen.py`)
and why mechanics tests never read the owner's prose; the stub agent and its behaviour
names (generated list from `stub_agent.BEHAVIOURS`, checked by test); the drive loop
helper; live probes (`SHACKLES_LIVE=1`, the `claude -p` wrapper, planted defects, cost
warning); the drift test and `accept-spec`; how to add a test (naming, where fixtures
live, the `live` marker).

---

## docs/TODO.md — carry-forward, open work

Format, one item per line so lines can be quoted and removed cheaply:

```
- [ ] R0007 P2: <one-line proposal> (from POSTMORTEM issue 1; plan: "quoted plan words")
```
`R` = round that added it; `P` = priority 1–3 (1 highest). CHAT-TO-PLAN suggests the
highest-impact open items and moves accepted ones into the plan (`todos_accepted`) and
marks them `[x]` at CLEANUP of the round that delivers them. Removing a line is a refund.

---

## docs/CLARIFICATIONS.md — carry-forward, for the owner

```
- [ ] R0007 C1: <the question> — plan: "<plan words>" — owner: "<exact owner words>" — judgment call: <attempt> "<line>" (if any)
```
The owner answers by editing the line or in chat; the driver moves resolved items out at
the next CHAT-TO-PLAN (into the plan's assumptions or `docs/TODO.md`) and deletes them.
