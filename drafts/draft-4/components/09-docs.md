# 09 — Documentation files

Seven documents. `INDEX.md` and `README.md` sit at the harness root (uncharged; editable only by CLEANUP). The five under `docs/` are living (charged per token; editable by the steps whose declared paths include `docs/`). Every document describes what the code does; when they disagree, the code is right and the document is fixed (the owner's rule in AGENTS.md: agents follow the prompt and log undefined judgment calls when the docs conflict with it).

For each file: purpose, audience, required sections, and what other components rely on it.

## 9.1 `harness/INDEX.md` — routing

**Audience:** any agent inside the harness ("grep INDEX.md for routing"). **Relied on by:** AGENTS.md's first line; CLEANUP's declared paths.

One line per entry, grep-friendly, formatted `path — purpose (owner component)`: every file and directory at the harness root, every module in `src/shackles/`, every command, every doc, every test-support module, the archive layout, the generated/ignored files. Ends with three routing hints: "rules → docs/PROCESS.md", "formats → docs/FORMATS.md", "how it hangs together → docs/ARCHITECTURE.md". No prose paragraphs.

## 9.2 `harness/README.md` — what it is and how to run it

**Audience:** the owner and a new developer. Sections: What this is (three sentences; the vision quoted from `project.yaml` is not copied — it is referenced); Prerequisites (Python ≥ 3.11, git with a remote, Claude Code with the Agent tool, the `claude` CLI on PATH for helpers/probes); Setup (`pip install -e ".[test]"`, `python src/run.py doctor`, open Claude Code in `harness/`, type one message so `OWNER.log` exists); A round in brief (the ten-line loop from SPEC.md §2); Commands (one line each, pointing to PROCESS.md); Testing (`pytest`; `SHACKLES_LIVE=1 pytest -m live` for probes); Accepting spec changes (`spec-drift`, `accept-spec`); Where the record is (`archives/rounds/NNNN/`).

## 9.3 `harness/docs/PROCESS.md` — the rules

**Audience:** every agent (the prompt says "read docs/PROCESS.md for the rules"); the driver especially. **Relied on by:** prompts (they reference sections by name), the CHAT-TO-PLAN driver template.

Required sections, in order:
1. **Roles** — owner, driver, producer, gate, runner; who may do what (only the runner commits/pushes/contacts the owner; producers edit only their worktree within declared paths plus the round folder; spec files are never edited by agents; owner words in locked prose are not literal descriptions of enforced software until approved).
2. **The step table** — the eleven steps in order, kind, gate, artifact, declared paths, mechanical checks (generated from `steps.py` by hand-copying; a test checks the table in this doc matches `steps.STEPS`, see [10] `test_docs_consistency.py`).
3. **The driver loop** — `start`, then `next`/`record`; what each `next` kind means and what the driver does (spawn `shackles-<rung>` read-write or `shackles-<rung>-gate` read-only with the prompt file verbatim; save the final message verbatim; `record` with `--tokens` when known); the CHAT-TO-PLAN special case (the driver is the producer); checkpoints (stop, summarize from the summary file, wait).
4. **Owner decisions** — the runner's decision kinds and options; the rule that the driver passes owner words verbatim as `--quote` and never paraphrases; that the vocabulary the owner uses is defined in the locked prose and only the driver interprets it; that no round proceeds with unanswered questions; how questions are numbered.
5. **Final messages** — pointer to FORMATS.md; the three producer statuses and two gate verdicts; "exactly one JSON object".
6. **Judgment calls** — the definitions (quoted from AGENTS.md by reference), the tool invocation, gates report in the message.
7. **Findings** — lifecycle: open → fixed/disputed → upheld/withdrawn → settled; the verdict wins; blocking follows the verdict; unresolved findings block acceptance; repeats of withdrawn findings are dropped with a note; flags reach the owner at the next pause.
8. **Mechanical checks and strays** — what runs at record per step; strays are reverted, not failed; the frozen tests; suite moves are done by the runner.
9. **Pauses and limits** — every pause kind, what unblocks it, the limits and their counters, `raise-limit`, `maxRoundAttempts` restarts.
10. **Landing, sync, abandon** — merge main into the branch, conflict attempts on the conflicted files judged against the auto-merged tree, fast-forward main, post-landing commits synced back (bounded), abandon = record-only landing.
11. **Money** — what is booked and when (bills what happened), the living charge in the owner's words (by reference to project.yaml's comment), budgets are targets not gates, hard stops.
12. **Spec drift** — the baseline, the failing test, refusal to start, mid-round pause, `accept-spec`.
13. **Self-hosting hazard** — the runner executing is the driver checkout's `main` copy; a round that changes `src/shackles` takes effect after landing; keep `STATE.json` backward compatible; the judgment tool and `spawn` are invoked through the driver checkout's `run.py`.
14. **Changing the step table** — the consumer list from `steps.consumers()`.

## 9.4 `harness/docs/ARCHITECTURE.md` — how it hangs together

**Audience:** implementers and gates judging structural changes. Sections: the one-page diagram (SPEC.md §2 reproduced); module map with owns/depends/depended-on for every module (a condensed copy of components 02–08); the dependency direction rule; data flow of one attempt (next → prompt → agent → result → record → checks → findings → ledger → fence); git model (main, round branch, worktree, automerge ref, fence, CAS); the testing strategy (fake spec, stub agent, probes) and why prose rewrites fail only the drift test; invariants list (runner-only side effects; one reader per spec file; no prose parsing; every command one JSON; estimated tokens formula; state atomic + fenced).

## 9.5 `harness/docs/FORMATS.md` — formats

**Audience:** agents writing artifacts and final messages; the runner's tests. Content: [00] contracts §0.1, §0.3–§0.14 rendered for agents, each as a heading the prompts can name (`## PLAN.json`, `## AGENTS-PLAN.json`, `## SPEC.json`, `## SUITE.json`, `## POSTMORTEM.md`, `## Final message (producer)`, `## Final message (gate)`, `## FINDINGS file`, `## STATE.json`, `## HISTORY.md`, `## OWNER.log`, `## Judgment-call files`, `## next output`, `## local.yaml`, `## spec.baseline.json`). A test ([10] `test_docs_consistency.py`) asserts these headings exist so prompts never point at a missing section.

## 9.6 `harness/docs/TODO.md` — carry-forward

Seeded content: a header explaining it is edited by POSTMORTEM (charged at `postMortemFileCostPerToken`) and read by CHAT-TO-PLAN ("suggest the highest-impact open TODOs"); entries as `- [ ] <text> (round NNNN)`; initial entries: "upstream mechanics (`allowUpstream`)", "owner attention pricing placeholders in project.yaml", "measured usage from the Agent tool when it becomes available".

## 9.7 `harness/docs/CLARIFICATIONS.md` — carry-forward

Seeded content: a header explaining it holds questions only the owner can settle, each with the plan(s) and exact owner words that gave rise to it and any agent judgment call found (the POSTMORTEM prose's option 2); entry template: `### <title> (round NNNN)` / Plan / Owner words / Judgment calls / Question. Initially the template only.
