# TESTING

Run the suite from the repository root with `py -3.13 -m pytest`; `-m "not slow"` skips the origin and worktree tests; the `real` marker is never run by default.

## Suite map

`test_config.py`, `test_render.py`, `test_pipeline.py`, `test_schemas.py`, `test_ledger.py`, `test_owner.py`: units, no round.
`test_round.py`, `test_outcomes.py`, `test_checks.py`, `test_cli.py`: one round in a single checkout (`--no-branch`) driven in-process with the stub.
`test_concurrency.py` (slow): claims, the fence, landing against a moving main, conflicts and `sync_main` on a local bare origin with Python update hooks.
`test_headless.py`, `test_probe.py`: the headless loop, probe, sandbox and the agent definitions, with the stub standing in for `claude.exe`.
`test_spec_baseline.py` and `test_spec_structure.py` are the only tests that read the owner's files: drift, structure, and that every prompt renders.
`test_docs.py`: INDEX aliases resolve, every command and config key is documented, the agent definitions match the roster.

## Fixtures

`fixtures.write_spec` generates the minimal fixture spec: a `project.yaml` from `DEFAULTS` with living paths at the toy project, a four-rung roster, and one prose file per step holding only the includes and tokens the real files use.
`fixtures.Repo` builds a throwaway repository with that spec, the toy project (`src/toy/text.py` already holds `shout(text)`, which upper-cases, and `tests/toy/test_text.py` asserts `shout('hi') == 'HI'`; a plan that "adds" `shout` changes it), a copy of the runner and an accepted baseline; `add_origin`, `clone` and `view` add a bare origin, another machine and a worktree view.
`stub_agent.py` is the fake agent: it parses the contract lines, writes canned artifacts from `fixtures/canned/`, and answers per `STUB_MODE` or `STUB_SCRIPT`; its agents plan chooses rungs by kind and weights the work shares (the clean seed of PLAN-AGENTS-GATE) unless `STUB_RUNG` forces one rung.
Stub modes: producers `pass noop dispute deferred needs_owner upstream blocked garbage fence prose_wrapped commit stray touch_tests break rewrite_judgment edit_spec big slow resolve bad_artifact replay`; gates `pass pass_nb fail uphold withdraw q_uphold q_withdraw judgment inconsistent dirty garbage fence`.
`Repo.play(until, modes, env, auto_review)` drives next, stub and record in-process to a step; a full stub round takes about ten seconds and the whole suite about six and a half minutes on this machine, most of it git subprocesses.

## Baseline procedure

When a spec file changes, `test_spec_baseline.py` fails with the diff and the instruction: run `doctor`, `render --step` for the affected steps, reconcile `pipeline.py` for a step or key change and `config.DEFAULTS` for a config key change, then `spec accept --note "<what you reviewed>"` in the same commit.
`spec_waivers.json` lists tokens the real prose may leave unresolved with the reason; it is empty.

## Real-agent ladder

Level 0, free: this suite; every checkpoint, override, cap, dispute, upstream, conflict, race and fence with the stub.
Level 1, cents to dollars per run: `probe --step S [--seed clean|defect] [--agent RUNG] [--manual]` builds a temp repo with the real prose played to just before S, prints the action, runs one real agent (or you spawn it with `--manual`), and `probe --check RESULT_FILE --dir DIR` scores contract validity, schema validity, path confinement, the expected verdict and whether the planted text was quoted; `--changed` probes the steps whose prose drifted.
Planted defects live in `tests/fixtures/defects/<GATE>/` with `expect.json`; a clean artifact must PASS and a planted defect must FAIL with the planted text quoted.
Level 2, tens of dollars per pass: `sandbox --dir D` builds a temp clone with a local bare origin (`core.longpaths` on), the agent definitions, the hook settings and the toy project, and its JSON prints the toy's files; run a real round there with `run --until done` (gates off, `--delegate`), then with gates on (in `D/repo`: set the flags in `harness/project.yaml`, `spec accept --note "gates on"`, commit, `git push origin main`, then `start`), then answering checkpoints.
Level 3: the owner's tiny task on the real repository; copy its RESULTS/ and artifacts into `tests/fixtures/replays/` for the stub's `replay` mode.
Expected costs at today's prices: Level 1 about $0.5 to $3 per run, the full matrix about $10 to $40; Level 2 about $10 to $40 per pass.
