# INDEX

One line per topic: `alias, alias -> path`; paths are relative to this folder.

process, rules, checkpoints, disputes, costs, invariants -> docs/PROCESS.md
driving a round, spawning, record, recovery, headless -> docs/DRIVER.md
tests, fixtures, stub, probes, sandbox, baseline procedure, real-agent ladder -> docs/TESTING.md
config, defaults, layering -> src/shackles/config.py, project.yaml, subAgents.yaml
runner, commands, exit codes -> src/run.py, src/shackles/cli.py, src/shackles/commands.py
steps, pipeline, mechanical check ids -> src/shackles/pipeline.py, src/shackles/checks.py
contracts, result JSON, verdict JSON, process instructions -> src/shackles/plumbing/, src/shackles/contract.py
schemas, artifacts, STATE -> src/shackles/schemas.py
prose, prompts, rendering -> locked_prose/, src/shackles/render.py, src/shackles/prompts.py
rounds, archives, index, state machine -> archives/rounds/, src/shackles/round.py
landing, claim, worktrees, sync_main -> src/shackles/landing.py
costs, budgets, living charge -> src/shackles/ledger.py
owner log, quotes, hook -> src/shackles/owner.py, src/owner_log_hook.py, ../.claude/settings.json
agent definitions, headless agents, claude path -> ../.claude/agents/, src/shackles/agentdefs.py, src/shackles/agents.py
spec files, baseline, drift, acceptance -> ../spec.yaml, archives/spec-baseline.json, archives/spec-changes.jsonl, src/shackles/specguard.py
doctor, environment -> src/shackles/doctor.py
probe, sandbox, defect fixtures -> src/shackles/probe.py, tests/fixtures/defects/
todo, clarifications, carry-forward -> docs/TODO.md, docs/CLARIFICATIONS.md
vision, invariants, judgment calls -> AGENTS.md
