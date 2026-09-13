# DRIVER

How a chat session drives one round on this machine; every command is `py -3.13 harness/src/run.py ...` from the repository root unless a worktree is named, and carries `--root <repo>` whenever the shell's cwd may be another repository (a sandbox): without it the runner acts on the nearest ancestor of the cwd that holds `spec.yaml`.

## Before a round

Run `doctor` and read its warnings; errors block `start`.
Run `render --step CHAT-TO-PLAN --raw` and follow that prompt: it names the inputs (history, TODO.md, CLARIFICATIONS.md, the last postmortems) and the plan contract.
Converse with the owner, write `harness/DRAFT-PLAN.json` (schema PLAN), and set `presented_at` when you show the plan.
Interpreting the owner's words is your judgment call: `approve`/`approved` means approved with checkpoints, `delegate`/`delegated` means no review checkpoints, `delegate through STEP` skips reviews up to STEP, `override` plus names skips those steps.
Fill `approval` (`mode`, `through`, `overrides`, `words` verbatim) and run the `start --plan ...` command the CHAT-TO-PLAN prompt prints, which names the runner, `--root` and the draft absolutely (`--delegate [--through STEP]` sets delegation from the command line).
A worktree round starts from `origin/<mainBranch>`: a gate flip or any other spec edit is committed, accepted with `spec accept` and pushed before `start`, which refuses otherwise; `harness/local.yaml` is copied into the worktree.
`start` prints `worktree` and `runner`: from then on drive the round with that worktree's runner, `py -3.13 <worktree>/harness/src/run.py --root <worktree> ...`.

## The loop

Run `next`; exit 0 prints an action, exit 10 prints a checkpoint, `done` ends the round.
For an action, spawn one fresh sub-agent with the Agent tool: `subagent_type` = the action's `agent_type` (`shackles-producer-<rung>` or `shackles-gate-<rung>`), `model` = `model_alias`, no worktree isolation, and the task text `contract.WRAPPER` with `prompt_file` filled in: "Your instructions are the entire content of <prompt_file>. Read it now and follow it exactly; your final message must be exactly the JSON object it specifies and nothing else."
Agent definitions register only at session start and only from the session's own project directory (`<project>/.claude/agents/`): a session started in a parent folder has none, and one written mid-session is "not found", so run `agents --write` and commit before the session that drives the round.
The action's `warnings` carry an `agent_type` line when the command ran from a folder without the definition, which is the usual sign that the session has no such type.
When the definition type is unavailable, spawn `subagent_type: general-purpose` with `model: <model_alias>`; effort then inherits the session's setting (a `general-purpose` sub-agent spawned with `model: fable` from a max-effort session reported `claude-fable-5-1` at `max`).
Save the sub-agent's final message to `result_file` exactly as returned, then run the action's `record_command`, adding `--tokens N` when the tool reported a token total (else the step budget is booked as an estimate).
Never do a gate's job, never edit an artifact or a result, never commit or push; the runner does.
`record` exit 2 with kind `invalid` means the message was not the JSON the prompt asked for: run `next` again, which reprints the same attempt, and spawn again.
Exit 10 from `next` or `record`: relay `message` to the owner verbatim and stop; when the owner speaks, run the matching command with their exact words in `--quote` (the commands are listed in the message).
`push rejected` from `record` means another runner owns the round: stop and report.
A crash mid-command is resumed by rerunning `next`; unrecorded work of a pending attempt is refused until you `record` it or run `next --discard`, so always `record` before another `next`.

## After

On `done`, run `git pull --ff-only` in the main checkout; `main_synced: false` means the tail commits arrive with the next landing.
Before `abandon`, confirm with the owner in chat; quote their words.

## Headless

`run --until checkpoint|step|done` runs the loop with `agentCommand` (the installed `claude.exe`, resolved from `SHACKLES_CLAUDE`, `claudePath` in `harness/local.yaml`, PATH, then `%APPDATA%`), exact costs from the CLI envelope, and the tool flags per kind.
`doctor --probe-cli` makes one capped call on the low rung and must succeed before relying on headless mode.
