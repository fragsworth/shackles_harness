# 12 — Docs (`docs/PROCESS.md`, `docs/ARCHITECTURE.md`, `docs/TODO.md`, `docs/CLARIFICATIONS.md`)

**Purpose.** The living prose. `PROCESS.md` is what AGENTS.md sends every agent to read
for the rules; `ARCHITECTURE.md` is the maintainer's map; `TODO.md` and
`CLARIFICATIONS.md` are the carry-forward files POSTMORTEM writes and CHAT-TO-PLAN reads.
All four are under `docs/`, hence living and token-charged: they are written dense (JC-40).

**Owns.** The wording of the rules for agents (which must agree with the code, never the
reverse: when they disagree the code is what is true and the doc is fixed).

**Depends on.** Nothing at run time. Content mirrors 05 (step table), 15 (schemas),
10 (what record checks), 09 (prices are *not* repeated; they are rendered into prompts
from `project.yaml`).

**Depended on by.** Agents (by reading). `steps.py` input symbols `todo` and
`clarifications` point at the two carry-forward files; `mechanical.allowed_roots`
resolves `carry-forward` to them. The engine reads neither file's content.

---

## `docs/PROCESS.md` (target ≤ 2,500 tokens)
Sections, in order, each a short list:
1. **Roles** — owner, driver, runner, producers, gates, the conflict resolver; who may
   write where (worktree, declared paths, round folder; gates nothing).
2. **The driver loop** — `start` → repeat (`next` → act → `record`) → owner verbs on
   pauses → `next` … until `ended`. The exact wording that each `next` action expects
   from the driver (from 03 `output.py`). How to report usage on `record`.
3. **Final messages** — the two JSON shapes (S7) copied verbatim; the three producer
   endings and what each causes; PASS/FAIL and the fact that the verdict wins.
4. **Findings** — ids, `fixed`/`disputed`, rulings, "upheld twice is settled",
   withdrawn repeats are dropped, unresolved findings block acceptance.
5. **Judgment calls** — the `jc` command (producers) and the `judgment_calls` field
   (gates); the two files; that COMMON-STEP-END will ask again at the end.
6. **Mechanical checks at record** — strays reverted (list of what counts), spec files
   untouched, per-step checks (from 10 `mechanical.py`), verify timeout.
7. **Owner words** — the verbs, and that the driver passes verbatim quotes; that the
   runner only checks presence in OWNER.log after the pause began.
8. **Money in one paragraph** — what is billed when (attempt, driver per step, living
   at cleanup, archives), that shares are targets, and the two hard stops.
9. **Paths** — the round folder layout (from `project.yaml: roundPaths`) and where
   worktrees are.

## `docs/ARCHITECTURE.md` (target ≤ 2,000 tokens)
1. The component list of this spec's §4 (one line each, with the module names).
2. The dependency direction rule and the "no load-bearing file" rule.
3. The git model (claim, fence, worktree, land, sync) in ten lines.
4. The spec guard and why mechanics tests use a generated spec tree.
5. The step table (copied from `steps.py` by hand; a test asserts the names match).
6. Where to add things: a new config key (schema in 04 + a use + doctor sees it), a
   new mechanical check (10 `mechanical.py` + a stub behavior + a test), a new owner
   verb (10 `round_owner.py` + CLI + PROCESS.md §7).

## `docs/TODO.md`
Header line explaining the format, then one bullet per item:
`- [ ] (round NNNN) <resolution proposed by POSTMORTEM> — <trace: component, plan line, owner words>`.
CHAT-TO-PLAN reads it to "suggest the highest-impact open TODOs"; items the owner
accepts are copied into `PLAN.json: accepted_todos` and ticked (`[x]`) by CLEANUP of
the round that lands them. Starts with the header only.

## `docs/CLARIFICATIONS.md`
Header line, then one section per open clarification:
`## C-<round>-<n>: <one-line question>` followed by `Plan:` (quoted plan text),
`Owner words:` (verbatim), `Judgment calls:` (ids/lines if found), `Options:` (lettered,
so the driver can ask them as decisions). CHAT-TO-PLAN presents open ones to the owner
when relevant; a resolved clarification is removed by the round that resolves it.
Starts with the header only.

## Invariants
- No number from `project.yaml` is repeated in these files (prices, limits, fractions);
  they say "see the rendered prompt" instead, so an owner edit cannot desync them.
- `PROCESS.md` §3 and `ARCHITECTURE.md` §5 are checked by tests against code
  (`tests/test_docs.py`): the JSON shapes parse and match S7's required keys; the step
  names listed equal `steps.order()`.

## Covered by
`tests/test_docs.py`.
