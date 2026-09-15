# 25 — harness/archives/ (the record)

Parent: `SPEC.md` §3. `archivesPath` in `project.yaml` (currently
`archives/`). Committed, never charged per token, left alone by convention once
a round is complete. Three kinds of content live here; each is written by
exactly one module.

```
harness/archives/
  spec-baseline.yaml      accepted hashes of the spec files   (config/spec_files.py)
  LEDGER.md               one line per round, appended at booking (ledger/ledger.py)
  rounds/
    NNNN/                 one folder per round; layout below   (round/*, engine/*)
```

## spec-baseline.yaml (written by `run.py accept-spec`; read by the drift test and `start`)

```
acceptedAt: <UTC ISO>
acceptedCommit: <sha of HEAD when accepted>
specYaml: spec.yaml                       # path relative to repo root
files:
  - path: spec.yaml
    sha256: ...
  - path: harness/locked_prose/COMMON-GATE.txt
    sha256: ...
```

One entry per file the glob patterns in `spec.yaml` expand to at acceptance.
A file listed here but missing now, or present now but not listed, is drift
just like a changed hash. The diff shown on drift is `git diff
<acceptedCommit> -- <changed paths>` for tracked files, and a full listing for
untracked ones (`31-src-config.md`, `spec_files.py`) `[JC-01]`. Not per round,
not user input: it lives in `archives/` because the record is the natural home
for "what was accepted when" and because `archives/` is free of living charge.

## LEDGER.md (append-only; human record; not state)

One line per round, written at booking (CLEANUP) or at abandon:
`| NNNN | landed|abandoned | quote | agents | driver | living | archive | total | ended <UTC> |`.
The numbers are copied from that round's `STATE.json.ledger`; `STATE.json` is
the source of truth for `project.remaining`, this file is for eyes.

## rounds/NNNN/ (the round folder; `roundPaths` in project.yaml)

Every name comes from `project.yaml`'s `roundPaths`; the code never hard-codes
`PLAN.json` or `PROMPTS/`, it reads the key (`config/paths.py`). With the
current values:

| file | writer | when | frozen after |
|---|---|---|---|
| `STATE.json` | runner (`round/state.py`) | every state change | round end |
| `HISTORY.md` | runner (`round/history.py`) | every attempt, verdict, owner command, landing, booking | round end |
| `OWNER.log` | runner (`round/owner_log.py`) | at start and refreshed at every `owner` command | round end |
| `PLAN.json` | driver (CHAT-TO-PLAN) | before approval | approval |
| `AGENTS-PLAN.json` | PLAN-AGENTS producer | its attempt | step accepted |
| `SPEC.json`, `SPEC.md` | PLAN-TO-SPEC producer | its attempt | step accepted |
| `SUITE.json` | TESTS-TO-SUITE producer | its attempt | step accepted |
| `POSTMORTEM.md` | POSTMORTEM producer | its attempt | step accepted |
| `PROMPTS/<attempt>.txt` | runner (`engine/attempts.py`) | at `next` | immediately |
| `RESULTS/<attempt>.json` | driver (saves the final message) | at `record` | at `record` |
| `FINDINGS/<attempt>.json` | runner (`round/findings.py`) from the gate's result | at gate `record` | immediately |
| `tests-archive/` | runner (`checks/suite_moves.py`) | TESTS-TO-SUITE accepted | round end |
| `DEFINED_JUDGMENT_CALLS.md`, `UNDEFINED_JUDGMENT_CALLS.md` | any agent via `run.py judgment`; runner for gates | any time in an attempt | append-only |

Attempt ids: `<STEP>-<n>` for producer attempts, `<STEP>-GATE-<n>` for gate
attempts, `LANDING-<n>` for conflict attempts, `CHECKPOINT-1-<n>` for
checkpoint prompts to the driver, `n` starting at 1 per step. `FINDINGS/` is
keyed by the producer attempt the verdict judges, so `FINDINGS/PLAN-AGENTS-2.json`
is the gate's verdict on `PLAN-AGENTS-2`; the gate's own raw final message is
`RESULTS/PLAN-AGENTS-GATE-2.json`.

Round id `NNNN`: four digits, zero-padded, one more than the largest existing
id among `archives/rounds/*` on `main` and `round/*` branches on the remote
(`git/lease.py`). The folder path template `archives/rounds/NNNN/` is taken
from `roundPaths.folder` with the literal `NNNN` replaced.

What lands where: the whole round folder lands on `main` with the round. An
abandoned round lands only its round folder (so the ledger stays complete) and
keeps its `round/NNNN` branch as the record of the discarded work `[JC-22]`.
