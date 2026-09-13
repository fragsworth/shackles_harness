# shackles_harness

A loop-engineered software development harness that restricts agents to judgment calls inside a carefully monitored process.
A round runs plan, spec, tests, implementation, suite selection, cleanup, landing and postmortem; a deterministic runner does every mechanical step and fresh agents do only the judgment ones.

## Quick start

`py -3.13 harness/src/run.py doctor` checks this machine.
`py -3.13 harness/src/run.py render --step CHAT-TO-PLAN --raw` shows the planning prompt; `harness/docs/DRIVER.md` is the driving loop.
`py -3.13 harness/src/run.py start --plan harness/DRAFT-PLAN.json` starts a round; `next` and `record` drive it; `run --until done` drives it headlessly.

## Layout

`harness/AGENTS.md` is the agents' entry point and `harness/INDEX.md` routes; `harness/docs/PROCESS.md` holds the rules.
The files `spec.yaml` lists are the owner's; `harness/archives/spec-baseline.json` guards them.

## Tests

`py -3.13 -m pytest` from this folder runs the whole suite (a few minutes, no network, no agent spend).
`harness/docs/TESTING.md` describes the four levels: the stub suite (free), single-step probes (cents to dollars), a sandbox round (tens of dollars), the real repository.
