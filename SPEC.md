# shackles spec

## spec.yaml
The files spec.yaml lists are the implied shackles spec: harness/AGENTS.md, project.yaml, subAgents.yaml, the
locked prose, and this file. They say what the harness must do. Everything else in the repository is derived
from them and must survive arbitrary edits to them; a test fails whenever one of them changes until the change
is reviewed and accepted.

## Architecture features the spec files do not imply
- Git is the only lock: a CAS push claims a round, every state change pushes the branch as a fence. [other: inherited]
- The driver interprets owner words and hands the runner verbatim quotes; the runner never parses prose. [non-obvious]
- The step table is code, lint-checked against the spec's data; unknown tokens and keys warn, never crash. [non-obvious]
- Delegation skips only review checkpoints; questions, blocks, limits and spec edits still stop the round. [non-obvious]
- Spec guard: hashed baseline, failing test with diff, start refuses drift, edits checkpoint the owner. [non-obvious]
- Mechanical checks run at record on the attempt's own uncommitted diff; strays are reverted, not failed. [non-obvious]
- A landing conflict becomes one agent attempt on the conflicted files, judged against git's auto-merged tree. [hard]
- Post-landing commits merge back into main through a bounded sync; every plan had orphaned them. [non-obvious]
- The gate's verdict wins and blocking flags follow it, so a reworded cost rule cannot desync the runner. [non-obvious]
- Mechanics tests use a generated one-line-per-file spec, so a prose rewrite fails only the drift test. [non-obvious]
- A stub agent with many scripted behaviors drives every path; real agents run as probes with planted defects. [other]
- doctor renders every prompt offline and names unresolved tokens, unknown steps and defaulted config keys. [other]
- A prompt hook logs the owner's chat to a gitignored OWNER.log; the runner verifies quotes against it. [non-obvious]
- Agent definitions are generated per rung: the Agent tool takes effort only from one loaded at session start. [hard]
