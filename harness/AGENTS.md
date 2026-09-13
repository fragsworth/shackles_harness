# harness/

You are inside the development harness.
grep `INDEX.md` for routing, read `docs/PROCESS.md` for the rules.

The bullets below are invariants.
* Only the runner (`src/run.py`) commits, pushes, and contacts the owner. Producers edit only inside their worktree and only within their step's declared paths plus the round folder.
* Your system prompt names your step, your inputs, where to write your artifact, and the JSON your final message must be. Follow it exactly; the runner parses it.
* Prose under `locked_prose/` does not change mid-round. `src/`, `docs/`, and `tests/` are living: every token you add is charged, every token you remove is refunded. Be dense, not clever.
* If you are the driver (the agent that runs `run.py next` and spawns others): each `next` gives you a prompt file; give it verbatim to a fresh sub-agent (read-only for gates), save its final message to the result file, then `record`. Never do a gate's job yourself.
* {{ plumbing.PROCESS-INSTRUCTIONS }} refers to the mechanical steps agents must follow given their current task. These steps never require judgment calls.

## JUDGMENT CALLS
* A judgment call is a choice that impacts behavior and that two sensible agents could make differently. AGENTS.md and locked_prose/ may define them; that is a DEFINED JUDGMENT CALL, expected and logged. Any other is an UNDEFINED JUDGMENT CALL.
* If you ever feel like you are making an UNDEFINED JUDGMENT CALL outside of what was defined by AGENTS.md or locked prose, append a small record with context inside your round's UNDEFINED_JUDGMENT_CALLS.md file and proceed with what is most sensible. Record DEFINED JUDGMENT CALLS the same way in DEFINED_JUDGMENT_CALLS.md.
* A blanket ask such as "do what is sensible" defines how you choose, not the line between the two: when the spec, plan, code, tests, or docs conflict or fall silent on something that impacts behavior, the judgment call is UNDEFINED even though the prose told you to be sensible.
