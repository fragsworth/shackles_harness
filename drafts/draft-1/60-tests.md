# 60 — harness/tests/ (the permanent suite)

Parent: `SPEC.md` §3. Living, charged per token and per test function. Five
suites plus the stub agent that drives the mechanics suite. `pytest
harness/tests` from the repo root runs everything but the live probes.

```
harness/tests/
  conftest.py       shared fixtures: tmp repo with a bare remote, generated spec, stub driver
  stub/             61  the stub agent: scripted behaviors for every role, and the driver loop
  unit/             62  one file per src module; pure functions, no repo unless noted
  mechanics/        63  whole rounds on temp repos with the generated one-line spec and the stub
  lint/             64  the real spec files vs the code: table, tokens, keys, INDEX, docs
  drift/            64  the spec-files guard
  live/             65  probes with real agents and planted defects (marker `live`)
```

Rules the whole suite follows:

- **Mechanics never read the real prose.** They build a spec set with
  `stub/spec_factory.py` where every prose file is one line, so a rewrite of
  `locked_prose/` fails only `drift/test_spec_files_guard.py`.
- **Lint and drift read the real spec files** (found via `spec.yaml` upward
  from the test file), because their job is to check the code against them.
- **No network.** The "remote" is a bare repository in a temp directory.
- **No real agents outside `live/`.** The stub plays every role.
- **A test asserts one behavior** and is named for it; one file per module or
  per mechanic.

## conftest.py

Fixtures (function scope unless stated):

- `real_paths` (session) — `config.paths.discover` from the test file's
  location: the real repo, for lint and drift.
- `tmp_repo` — a temp directory with a bare `origin`, a clone with identity
  configured, one commit on `main`; returns `RepoHandle(clone: Path, bare:
  Path, repo: Repo)`.
- `generated_spec` — `spec_factory.make_spec(tmp_repo.clone, **overrides)`:
  writes `spec.yaml`, `SPEC.md`, `harness/AGENTS.md`, `harness/project.yaml`,
  `harness/subAgents.yaml`, `harness/locked_prose/*.txt` (one line each),
  the living folders with a tiny passing test, `docs/` carry-forward files,
  commits and pushes; accepts overrides for any `project.yaml` key and for
  the set of prose stems. Runs `accept-spec` so drift is clean.
- `owner_log` — creates `harness/OWNER.log` with entries from a list of
  strings; returns an appender.
- `stub_driver` — `stub.driver.StubDriver(generated_spec, behaviors)`; runs
  rounds to completion or to a pause.
- `settings_min` — an in-memory `Settings` from a minimal dict, for unit
  tests that need numbers.
