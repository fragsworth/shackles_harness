# harness/

You are inside the development harness.
grep `INDEX.md` for routing, read `docs/PROCESS.md` for the rules.

## ADVICE.
* Your system prompt names your step, your inputs, where to write your artifact, and the JSON your final message must be. Follow it; the runner parses it.
* If you are the driver (the agent that runs `run.py next` and spawns others): each `next` gives you a prompt file; give it verbatim to a fresh sub-agent (read-only for gates), save its final message to the result file, then `record`.
* `src/`, `docs/`, and `tests/` are living: every token you add is charged, every token you remove is refunded. Be dense, not clever.

## INVARIANTS.
* Only the runner (`src/run.py`) commits, pushes, and contacts the owner. Producers edit only inside their worktree and only within their step's declared paths plus the round folder.
* Files listed by `spec.yaml` may only change given exact text written by the owner.
* {{ plumbing.PROCESS-INSTRUCTIONS }} refers to the mechanical steps agents must follow given their current task. These steps never require judgment calls.

## DEFINED AND UNDEFINED JUDGMENT CALLS
* A judgment call is any choice that lands in your finished work that someone later, human or agent, may reasonably want to inspect. The intent here is to track and classify judgment calls, not to stop them.
* A DEFINED JUDGMENT CALL is one you can make given only the information in your task, AGENTS.md and locked_prose/*, needing nothing else, which is expected and logged.
* Any judgment call made by including information outside the files above is an UNDEFINED JUDGMENT CALL.
* A blanket DEFINED ask such as "do what is sensible" only defines how you choose, not the line between the definitions: when the task, spec, plan, code, tests, or docs conflict or falls silent on something that impacts behavior, the judgment call is UNDEFINED even though the prose told you to be sensible.
* If you ever feel like you are making an UNDEFINED JUDGMENT CALL, append a small record with context inside your round's UNDEFINED_JUDGMENT_CALLS.md file and proceed with what is most sensible. Record DEFINED JUDGMENT CALLS the same way in DEFINED_JUDGMENT_CALLS.md.
