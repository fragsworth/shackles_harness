# Judgment calls made while writing PLAN.md

Rule applied, from the owner's prompt to the coordinating session: DEFINED when the choice follows from the spec.yaml files at 20ed0df, the prompt, and the conversation; UNDEFINED when the choice needed the code, the derived docs or the tests. Retiring a piece of existing code is UNDEFINED by construction, since the files alone never name it. One line per call; the plan cites them by number. A builder who finds a sentence of the owner's that two readings still fit stops and asks; it does not add to this list on its own.

## DEFINED

- D1. subAgents.yaml is guarded like project.yaml: read live, never edited in a round, listed by spec.yaml. Basis: the owner's statement; spec.yaml lists it, spelling aside.
- D2. An agent's edit to a guarded file is reverted at record with a finding; provisional acceptance and the spec-edit checkpoint go. Basis: AGENTS.md invariant; the earlier accepted assumption.
- D3. A key the code never reads refuses start; an owner-editable key the file lacks takes its default and doctor names it. Basis: SPEC.md lines 9, 18, 23.
- D4. local.yaml holds only machine facts the runner writes itself; anything else there refuses start. Basis: SPEC.md 23 with 9.
- D5. The step table mirrors the steps block: names, order, one gate per producer named STEP-GATE, checkpoints as rows; lint refuses a mismatch. Basis: project.yaml steps; SPEC.md 9 and 25.
- D6. CHECKPOINT-1 reviews the spec, CHECKPOINT-2 the diff before landing; delegation skips both; the checkpoint message carries CHECKPOINT-OVERVIEW. Basis: row positions; SPEC.md 10; the prose file.
- D7. LANDING is runner-only, no agent and no gate. Basis: the "no gate" comment; AGENTS.md "only the runner commits, pushes".
- D8. CLEANUP is an agent step after POSTMORTEM, no gate, writes under the living paths and the round folder, tests no longer frozen, verify and suite must stay green, commits land by the bounded sync. Basis: CLEANUP-OVERVIEW; "the tree as cleanup leaves it"; SPEC.md 14.
- D9. The CHAT-TO-PLAN flag can only add an LLM gate, whose prose does not exist, so it is inert; the owner's word is always required to start. Basis: "some steps have no gate"; the words table; SPEC.md 19.
- D10. The gates token lists the gates in step order with on or off, derived from steps. Basis: COMMON-PROJECT line 8; accepted earlier.
- D11. Every price is per token, token = ceil(bytes / tokenBytes), the per-word keys go. Basis: project.yaml.
- D12. Living charge booked once at cleanup: main before landing versus the tree after cleanup; renames free; test base cost per net new test function in files under testPaths; archived tests free. Basis: the living block.
- D13. Plan, spec and postmortem Summary tokens booked at cleanup, never refunded: PLAN.json, SPEC.json with SPEC.md, the Summary section of POSTMORTEM.md; carry-forward deltas at postMortemFileCostPerToken instead of the living rate. Basis: project.yaml prices and the POSTMORTEM paragraph.
- D14. The quote includes the planner's living estimate; the work and gate fractions split the quote minus that estimate. Basis: "part of the quote: the planner estimates it"; "Enforced distribution of budget".
- D15. Hard stop: spend plus projected living charge against multiple times quote, before every agent run and before landing; approval needs a new multiple, which re-arms it; post-landing bookings never pause. Basis: the hardStop comment; the POSTMORTEM paragraph.
- D16. hardStopBudgetMultipleIndividual times the step budget caps one run where the runner can cap it; a recorded run over it pauses. Basis: "like above, applied to a single agent and its own budget".
- D17. Owner time and elapsed time are shown, never booked. Basis: "for context"; placeholders commented out.
- D18. driverUsdPerStep and the planning share enter the quote and the retry cost shown to gates, and are not booked. Basis: "should be considered in budgets"; "bills what happened and not what was planned". The other reading, book it as an estimate of a real cost, is defensible; listed as unsettled.
- D19. An off gate's share is unspent; the producer's budget is unchanged. Basis: "A gate that is off does not incur a charge."
- D20. maxRefactorOverhead and defaultShares are printed, not enforced; gatesFraction plus workFraction must sum to one. Basis: the Advisory and Enforced headings.
- D21. maxTurnsPerGate counts rejections of one producer by its gate and by the mechanical checks; reaching it pauses. Basis: "turns (rejections) per gate"; SPEC.md 12 makes the mechanical checks a rejection. Listed as unsettled.
- D22. maxTurnsPerRun and maxRunWallClockHours are enforced where the runner runs the agent, printed otherwise; hitting one pauses the round. Basis: the heading "Limits before pausing a round".
- D23. maxAgent is a ceiling on the roster ladder in roster order; defaultAgent the default for work; a plan naming a higher rung is refused. Basis: project.yaml; subAgents.yaml "rungs on a capability ladder".
- D24. A question always pauses; the ruling field, the silent settle and the assumption field go; the answer returns as a finding; at a question the runner accepts only an answer and the driver turns the owner's words into one. Basis: COMMON-OVERVIEW; SPEC.md 10; the words table; the owner's ruling in chat.
- D25. Start refuses without an owner log; a quote the log lacks is refused. Basis: SPEC.md 19.
- D26. Every checkpoint message and the final report list the flagged items. Basis: SPEC.md 22 "reaches the owner at the next pause".
- D27. An omitted resolution leaves the finding open and rejects the attempt. Basis: SPEC.md 22 "an unresolved finding blocks the step's acceptance".
- D28. One recorder: a runner subcommand appending one line, newlines collapsed, tagged with step and attempt; the process block names it; gates keep the final-message route. Basis: AGENTS.md; roundPaths "one short line"; the conversation.
- D29. COMMON-STEP-END is a second turn to the same sub-agent after its work; the message after it is recorded. Basis: "produced at the end of every step"; the owner's "reminder at the end of every process".
- D30. `{{ agents.X }}` renders the AGENTS.md section whose heading matches X, upper-cased with spaces as underscores. Basis: the token in COMMON-STEP-END.
- D31. allowUpstream 0 removes UPSTREAM from the contract; a wrong earlier artifact is a NEEDS-OWNER question. Basis: the TODO comment; COMMON-OVERVIEW line 4.
- D32. `vision` replaces the `shackles` default. Basis: project.yaml and COMMON-PROJECT.
- D33. Six slices in dependency order, doctor clean and suite green after each; one builder, a reviewer twice, then a sandbox round. Basis: the owner's request for a nice refactor; the earlier plan-for-the-plan.
- D34. The plan states behaviour, not module layout; the naming rule stands in for design. Basis: the owner's request for a high-level plan.

## UNDEFINED

- U1. The upstream mechanics stay in code behind allowUpstream rather than being deleted. Needed: the code, to know they exist.
- U2. A run with no cost and no token count books the rung's spawn floor with a flag, not the step budget. Needed: docs/TODO.md and driver experience that the Agent tool may report no tokens.
- U3. The --unverified flag goes from start and the owner commands. Needed: the code, to know it exists; a spec-only build ends the same way.
- U4. Retired list: gates key, checkpointsAfter, maxFailuresBeforeStop, ownerMinutesPerCheckpoint, minRunUsd, the owner bucket, planCostPerWord, specCostPerWord, the plan-share booking at start, needs_owner, settle_question, the assumption field, E1, the spec-edit and upstream-plan checkpoints. Needed: config.DEFAULTS and round.py.
- U5. The generated fixture spec and the stub are extended, not rewritten. Needed: the tests.
- U6. The CAS claim, worktrees, the landing merge attempt, sync_main, the mechanical checks and the render engine are kept as they are. Needed: the code, to judge them aligned with SPEC.md.
- U7. PROCESS.md's config section is generated from the code's key table under a test; the other docs are rewritten by hand in the last slice. Needed: the docs and test_docs.py.
- U8. The recorder is a run.py subcommand rather than a separate script. Needed: cli.py and commands.py.
- U9. Headless step-end uses claude --resume with the envelope's session id. Needed: agents.py and the CLI's flags.
- U10. CLEANUP loses its special INDEX.md write path; only the living paths and the round folder remain. Needed: prompts.py.
- U11. The failure-limit and round-limit checkpoint kinds merge into one limit kind. Needed: round.py's kinds.
