# 03 — Runner CLI (`src/run.py`, `shackles/cli.py`, `shackles/output.py`)

**Purpose.** The command surface the driver, the hooks, the owner and CI use. `run.py`
is a three-line entry; `cli.py` parses arguments, builds the context, calls one engine
or tool function, and maps outcomes to exit codes; `output.py` renders every piece of
text a human or the driver reads. No decisions live here.

**Owns.** Command names and flags; exit codes; the `--json` mode; all owner/driver
facing wording ("contacts the owner" in AGENTS.md's sense: the runner produces the
text, the driver relays it verbatim).

**Depends on.** 10 (engine), 11 (doctor/index), 06 (hooks, agentdefs, ownerlog),
04 (paths, config, specfiles, localyaml), 08 (`judgmentcalls`, `state`), 09 (`ledger`).

**Depended on by.** Nothing in `src`. The hooks in `.claude/settings.json`, CI, the
driver, the stub agent (tests) and the probes invoke it.

---

## `src/run.py`
Module docstring (one line, for INDEX.md), `sys.path` insertion of its own directory,
`sys.exit(shackles.cli.main(sys.argv[1:]))`. The runner always executes from the driver's checkout, even when acting on a worktree (JC-49).

## `cli.py`

- `main(argv: list[str]) -> int` — `argparse` with sub-commands below; builds `Ctx`
  (`round_start.Ctx`) lazily per command; catches the documented exceptions
  (`StartRefused`, `NoActiveRound`, `FenceLost`, `QuoteNotFound`, `PlanQuestionsOpen`,
  `OverrideRefused`, `VerbNotAllowed`, `ConfigError`, `PathsError`, `StateError`,
  `UnresolvedTokenError`, `GitError`) and prints them through `output.error`; any
  other exception propagates (a bug should be loud).
- `build_ctx(paths_start: Path | None) -> Ctx` — `find_paths`, `load_config`,
  `load_roster`, `load_prose`, `now = datetime.utcnow`, `run_py`.

Commands (exit code 0 unless stated; `--json` available on all that print structures):

| Command | Args | Does | Exit |
|---|---|---|---|
| `setup` | — | `agentdefs.write_all`, `localyaml.write_local`, create `OWNER.log` marker if absent, create the baseline if none exists (first install only; otherwise untouched), ensure `.gitignore` entries at the repo root. Prints what it wrote and "restart your Claude Code session". | 0 |
| `doctor` | `--offline`, `--strict`, `--json` | `doctor.run_doctor`; prints S17. | `doctor.exit_code` |
| `accept-spec` | `--yes` | Prints the drift (`format_drift`); without `--yes` asks `accept? [y/N]` on a TTY (refuses when not a TTY); then `write_baseline` and `localyaml` refresh. Refused while a round is not ended and paused on nothing (a round in flight): message "accept between rounds". | 2 when refused |
| `start` | `--json` | `round_start.start`, then `next_action`; prints S16. | 2 on `StartRefused` |
| `next` | `--round NNNN`, `--json` | `open_round`, `next_action`; prints S16. | 0; 3 when `refused` (fence lost) |
| `record` | `--round`, `--tokens-in N --tokens-out N --cache-read N --cache-write N` (all or none), `--seconds S` | `round_record.record`; prints the outcome, notes, and the same S16 the next `next` would print. | 0; 1 on malformed/mechanical rejection (informational: the driver should call `next`) |
| `owner` | `<verb>` `--quote TEXT` `[--through STEP] [--steps A,B] [--gates A,B] [--number N] [--multiple X]` | `round_owner.owner_verb`; prints the owner text. | 2 on `QuoteNotFound`/`VerbNotAllowed`/`OverrideRefused`/`PlanQuestionsOpen` |
| `jc` | `--round --step --attempt --kind --text` | `judgmentcalls.append_line` into the round folder of the worktree. Never fails on content. | 0 |
| `status` | `--json` | STATE summary: id, status, step, attempt, pause, spend/quote, flags, worktree, stale worktrees, fence sha vs remote. | 0 |
| `ledger` | `--round NNNN` | `ledger.format_bill` of the given or current round. | 0 |
| `verify` | `--round`, `--select PATH…` | `verify.run` in the round worktree (or the checkout when no round); prints output. | 0/1 by result |
| `index` | `--check` | `index.regenerate`; with `--check` only reports staleness. | `--check`: 1 when stale |
| `hook` | `prompt` \| `session-start` | `hooks.hook_prompt` / `hook_session_start` with stdin JSON. | 0 always |
| `render` | `--step STEP --kind producer|gate|checkpoint|conflict` | Offline render (placeholder round) printed to stdout; for authoring prose. | 0; 1 with unresolved tokens |

`--round` defaults to the single active round. Every command that changes STATE ends
with the fence; a `FenceLost` prints the pause text and exits 3.

## `output.py`

Every function returns a `str`; `cli.py` prints.
- `next_action_text(action: NextAction) -> str` — labelled lines: `ACTION`, `STEP`,
  `ATTEMPT`, `KIND`, `AGENT` (definition name), `READ-ONLY`, `PROMPT`, `RESULT`, then
  the driver instruction sentence for the action: spawn → "Give the prompt file
  verbatim to a fresh sub-agent `<definition>`; save its final message to RESULT; then
  run `record` with the usage you observed."; driver-step → "This step is yours: follow
  the prompt file, write the artifact, then `record`."; pause → the `owner_text`
  verbatim under `FOR THE OWNER:`; ended → the bill.
- `record_text(outcome: RecordOutcome) -> str`.
- `owner_text(text: str) -> str` — wraps in `FOR THE OWNER:` … `END`.
- `bill_text(state, cfg) -> str` — delegates to `ledger.format_bill`.
- `status_text(...)`, `doctor_text(report)`, `drift_text(report)`, `error(exc) -> str`
  (one line: the class name and message; for `StartRefused` one line per reason).
- `json_dump(obj) -> str` — stable JSON for `--json` (dataclasses → dicts).

## Invariants
- `cli.py` contains no branching on STATE beyond choosing the command; all decisions are
  in 10/11.
- Output for the driver is deterministic and label-based so the driver can read it
  without parsing prose; `--json` gives the same fields.
- Nothing is printed to stdout by any other module (they return strings); stderr is
  reserved for `error`.

## Covered by
`tests/test_cli.py`.
