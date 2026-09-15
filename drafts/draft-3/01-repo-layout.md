# 01 — Repository layout

Root first. Every path is listed once with its owner: **owner** (a `spec.yaml` file,
never edited by agents), **living** (under `livingSourcePaths`, charged per token),
**generated** (written by the runner, committed), **local** (gitignored), **record**
(archives, free, left alone once a round ends), **derived** (hand-maintained, free).
Judgment calls are tagged `[JC-nn]` and explained in `JUDGMENT-CALLS.md`.

```
<repo root>/                          the git repository; remote `origin` is required
  spec.yaml                           owner   list of the spec files (paths relative to it)
  SPEC.md                             owner   what the harness must do
  README.md                           derived one paragraph: where things are, how to start   [JC-01]
  .gitignore                          derived see 20-tooling-ci.md
  .github/workflows/ci.yml            derived runs the suite on push; optional               [JC-02]
  .worktrees/                         local   one git worktree per active round: round-NNNN/
  harness/                            THE HARNESS ROOT: everything below is relative to it
    AGENTS.md                         owner   the agents' standing instructions
    project.yaml                      owner   settings, prices, step table, paths, limits
    subAgents.yaml                    owner   the rung ladder with models and prices
    locked_prose/                     owner   one .txt per step overview / gate / common fragment
    CLAUDE.md                         generated one line `@AGENTS.md` so Claude Code loads AGENTS.md [JC-03]
    INDEX.md                          generated one line per file: path — purpose (`run.py index`)
    local.yaml                        generated spec baseline hashes + hashes of generated files
    OWNER.log                         local   JSONL of the owner's chat prompts, written by the hook
    pyproject.toml                    derived deps (pyyaml, pytest), pytest config, probe marker
    .claude/
      settings.json                   generated the UserPromptSubmit hook (owner log)
      agents/<rung>.md                generated one agent definition per rung
      agents/<rung>-gate.md           generated read-only twin of each rung, for gates
    src/                              living  the runner
      run.py                          CLI entry: argparse, dispatch, exit codes           (03)
      commands.py                     thin glue from parsed args to domain calls          (03)
      errors.py                       the exception hierarchy and exit-code mapping       (03)
      paths.py                        root discovery, RoundPaths, worktree location       (03)
      config.py                       project.yaml + subAgents.yaml models, defaults      (04)
      specfiles.py                    spec.yaml listing, hashing, baseline, drift, diff   (04)
      localstate.py                   local.yaml read/write                               (04)
      tokens.py                       the single token estimate                           (04)
      steps.py                        the step table and its lint                         (05)
      prose.py                        locked_prose loading, AGENTS.md sections            (05)
      templates.py                    `{{ ns.KEY }}` rendering engine                     (06)
      context.py                      builds the namespaces project/round/agents/prose    (06)
      prompts.py                      prompt assembly, plumbing text, size warning        (06)
      schemas.py                      artifact/result/findings validation, JSON extract   (07)
      state.py                        STATE.json model, load/save, transitions            (08)
      history.py                      HISTORY.md appender                                 (08)
      rounds.py                       round discovery, claiming, scaffolding, abandon     (08)
      gitops.py                       git plumbing: CAS push, lease, worktrees, merges    (09)
      next_action.py                  computes and prepares the next action               (10)
      recording.py                    the `record` flow                                   (10)
      pauses.py                       limits, pause/resume/abandon, owner messages        (10)
      findings.py                     findings lifecycle: rulings, settled, repeats, flags (11)
      checks.py                       mechanical checks on the attempt's diff, strays     (11)
      verify.py                       runs the suite with a timeout                       (11)
      landing.py                      landing, conflict attempt, bounded post-landing sync (12)
      suite.py                        round test enumeration (ast), SUITE.json application (12)
      ledger.py                       all prices, attempt costs, living and archive charges (13)
      ownerlog.py                     OWNER.log model, quote verification, round slice     (14)
      hooks/owner_log_hook.py         the hook script: stdin JSON → OWNER.log line         (14)
      judgment_calls.py               the `jc` tool and ingestion from final messages      (14)
      agentdefs.py                    generates .claude/agents and .claude/settings.json   (14)
      install.py                      generates every derivative, writes local.yaml        (15)
      doctor.py                       offline diagnosis: lint, render, drift, staleness    (15)
      index.py                        INDEX.md generation and check                        (15)
    docs/                             living
      PROCESS.md                      the rules for agents inside the harness              (16)
      OWNER-GUIDE.md                  how the owner installs, starts, steers, accepts      (16)
      ARCHITECTURE.md                 how the code realises each architecture feature      (16)
      PROMPTS.md                      prompt assembly and the token namespaces             (16)
      SCHEMAS.md                      the JSON formats, for agents and humans              (16)
      LEDGER.md                       the pricing math with worked examples                (16)
      TESTING.md                      running tests, stub behaviours, probes               (16)
      TODO.md                         carry-forward: accepted TODOs, edited by POSTMORTEM   (16)
      CLARIFICATIONS.md               carry-forward: questions for the owner, by POSTMORTEM (16)
    tests/                            living
      conftest.py                     fixtures: temp repo + origin, generated spec, stub    (17)
      fixture_spec.py                 generates the one-line-per-file spec                  (17)
      stub_agent.py                   scripted agent behaviours                             (17)
      fake_driver.py                  drives next/stub/record loops in tests                (17)
      gitfixtures.py                  bare origin, clones, commits, helpers                 (17)
      test_*.py                       unit and flow tests                                  (18, 19)
      test_spec_drift.py              THE drift test: real spec files vs baseline           (19)
      test_spec_lint.py               real spec files pass the step-table lint              (19)
      probes/                         opt-in live agent probes, marker `probe`              (19)
    archives/                         record
      spec-baseline/                  accepted copies of the spec files, for diffs         [JC-04]
      rounds/NNNN/                    one folder per round, layout from project.yaml roundPaths
        PLAN.json AGENTS-PLAN.json SPEC.json SPEC.md SUITE.json POSTMORTEM.md
        STATE.json HISTORY.md OWNER.log
        PROMPTS/ RESULTS/ FINDINGS/ tests-archive/
        DEFINED_JUDGMENT_CALLS.md UNDEFINED_JUDGMENT_CALLS.md
```

## Ownership rules the layout encodes

- The harness root is `harness/` because `spec.yaml` lists `harness/AGENTS.md` and
  `project.yaml`'s `lockedProsePath`, `livingSourcePaths`, `archivesPath`,
  `subAgentsFile` and `roundPaths.folder` are relative to "the harness root". The
  runner finds its root as the parent of `src/` (`paths.harness_root()`), never by
  walking from the current directory, so the main checkout's runner always operates on
  the main checkout and addresses worktrees explicitly.
- `archives/rounds/NNNN/` names are taken from `project.yaml` `roundPaths` at run
  time; the tree above shows today's values. Code refers to them by key (`artifacts.plan`,
  `runner.state`, `attempts.prompts`, ...), never by literal file name.
- `src/`, `docs/`, `tests/` are the default `livingSourcePaths`; if the owner changes
  the list the ledger and the declared write paths follow the config.
- `INDEX.md`, `local.yaml`, `CLAUDE.md`, `.claude/`, `pyproject.toml`, `README.md`
  and `archives/` are outside the living paths and therefore free.
- Nothing under `archives/rounds/` is edited by anyone once a round is `DONE` or
  `ABANDONED` (convention, enforced only by the step write paths).
- Agents run inside `<repo>/.worktrees/round-NNNN/harness/`; the round branch
  `round/NNNN` is checked out there. The main checkout stays on `main`. The worktree
  path is deterministic and machine-local, so it is never stored in STATE.json.

## Files that must exist before the first round

`install` creates the generated files; the harness ships with these hand-written
derived files: `README.md`, `.gitignore`, `pyproject.toml`, all of `docs/` (TODO.md
and CLARIFICATIONS.md start as a heading and an empty list), `INDEX.md` (regenerated by
`install`), and an empty `archives/rounds/`. `OWNER.log` appears when the owner sends
the first chat prompt after installing the hook.
