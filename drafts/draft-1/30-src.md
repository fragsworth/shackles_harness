# 30 — harness/src/ (the runner)

Parent: `SPEC.md` §3 and §5. Living code, charged per token. One script and one
package. Each subpackage is a component with its own file (31–41); this file is
the map and the rules they all follow.

```
harness/src/
  run.py                      entry script: puts src/ on sys.path, calls shackles.cli.main(argv)
  shackles/
    __init__.py               version string only
    cli.py                    argv parsing; one subparser per command; dispatch; exit codes
    errors.py                 the exception types every component raises
    config/                   31  settings surface: spec files, project, roster, local, paths
    steps/                    32  the step table as code; lint against the spec data
    prompts/                  33  tokens, rendering, plumbing text, AGENTS.md sections
    round/                    34  STATE.json, HISTORY.md, owner log slice, judgment calls, artifacts, results, findings, owner verbs
    git/                      35  git wrapper, lease, worktrees, landing merge, bounded sync
    checks/                   36  mechanical checks at record, verification, suite moves
    ledger/                   37  token estimate, pricing, living charge, agent costs, round ledger, hard stops
    quote/                    38  budget pools and shares, per-attempt budgets, run limits
    agents/                   39  agent definitions per rung, hook install, owner-log hook handler
    engine/                   40  the advance decision, attempt lifecycle, landing, booking, pause messages
    commands/                 41  one module per CLI verb
```

## run.py

- Purpose: the only file AGENTS.md names (`src/run.py`). Ten lines: resolve its
  own directory, insert it into `sys.path`, `from shackles.cli import main`,
  `sys.exit(main(sys.argv[1:]))`. Nothing else, so that it is never load-bearing.

## cli.py

- `main(argv: list[str]) -> int` — builds the parser from
  `commands.REGISTRY` (each command module exposes `NAME`, `add_arguments(parser)`,
  `run(args) -> Outcome`), runs the chosen command, prints the outcome's JSON to
  stdout and its human lines to stderr, maps `Outcome.status` to an exit code:
  0 ok, 2 refused, 1 crash. Catches `ShacklesError` subclasses and turns them
  into a refused outcome with `reason`; any other exception is a crash with the
  traceback on stderr.
- `Outcome` (dataclass): `status: "ok"|"refused"`, `json: dict`, `lines:
  list[str]`. Defined here because it is the CLI's own shape; commands return
  it.

## errors.py

Each component raises these and nothing else crosses component boundaries as an
exception:

| class | raised when | carries |
|---|---|---|
| `ShacklesError(Exception)` | base | `reason: str`, `details: dict` |
| `RefusedError` | a command refuses to act (drift, no log, open round, unknown input) | `reason`, `details` |
| `DriftError(RefusedError)` | spec files differ from the baseline | `changed: list[str]`, `diff: str` |
| `LintError(RefusedError)` | step table vs spec data mismatch, unknown key, unresolved token | `problems: list[str]` |
| `LeaseLostError(RefusedError)` | a fence push was rejected | `branch`, `expected`, `actual` |
| `ContractError(ShacklesError)` | a JSON final message or artifact fails its schema | `path`, `problems` |
| `QuoteNotFoundError(RefusedError)` | an owner quote is not in the round's log slice | `quote` |
| `GitError(ShacklesError)` | a git command failed | `argv`, `stderr`, `code` |
| `VerifyError(ShacklesError)` | verification could not run (not test failure) | `output` |

Rules shared by every module under `shackles/`:

- **Read settings only through `config/`.** No module opens `project.yaml`,
  `subAgents.yaml`, `spec.yaml` or `local.yaml` itself.
- **Write the round folder only through `round/`.** No module opens
  `STATE.json` or `HISTORY.md` itself; `engine/` asks `round/state.py` to
  transition and `round/history.py` to append.
- **Run git only through `git/repo.py`**, tests only through `checks/verify.py`.
- **Parse nothing but JSON and YAML.** Owner words are compared as verbatim
  substrings; prose files are substituted, never interpreted.
- **Everything the driver must act on is one JSON object on stdout**, shaped as
  in `70-contracts.md`.
- **Pure functions first.** Pricing, shares, rendering, finding rules,
  transitions are pure and unit-tested without a repo; only `git/`, `checks/`,
  `agents/hooks.py`, `config/local.py` and the commands touch the filesystem.
