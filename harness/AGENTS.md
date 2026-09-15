# harness/

You are inside the shackles harness.
grep `INDEX.md` for routing, read `docs/PROCESS.md` for the rules.

## ADVICE.
* Your system prompt names your step, your inputs, where to write your artifact, and the JSON your final message must be. Follow it; the runner parses it.
* If you are the driver (the agent that runs `run.py next` and spawns others): each `next` gives you a prompt file; give it verbatim to a fresh sub-agent (read-only for gates), save its final message to the result file, then `record`.
* `src/`, `docs/`, and `tests/` are living: every token you add is charged, every token you remove is refunded. Be dense, not clever.

## INVARIANTS.
* Only the runner (`src/run.py`) commits, pushes, and contacts the owner. Producers edit only inside their worktree and only within their step's declared paths plus the round folder.
* Files listed by `spec.yaml` are never changed by any agents inside the shackles harness.
* {{ plumbing.PROCESS-INSTRUCTIONS }} refers to the mechanical steps agents must follow given their current task. These steps never require judgment calls.

## DEFINED AND UNDEFINED JUDGMENT CALLS
* A judgment call is any choice that lands in your finished work that someone later, human or agent, is likely to blame you for making incorrectly, rather than the author of your task. The intent here is to track and classify judgment calls, not to stop them.
* A DEFINED JUDGMENT CALL is one you can make from the text of your prompt alone: its instructions, AGENTS.md, and the locked prose rendered into it, with nothing read from any file the prompt points you to. It is expected and logged.
* Any judgment call made by including information outside your prompt is an UNDEFINED JUDGMENT CALL.
* A blanket DEFINED ask such as "do what is sensible" only defines how you choose, not the line between the definitions: when the code, tests, or docs conflict with your prompt or falls silent on something that impacts behavior, the judgment call is UNDEFINED even though the prose told you to be sensible.
* If you ever feel like you are making an UNDEFINED JUDGMENT CALL, record it with the judgment-call tool your process instructions name (gates: in your final message) and proceed with what is most sensible. Record DEFINED JUDGMENT CALLS the same way.