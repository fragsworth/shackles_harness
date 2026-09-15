# 31 — src/shackles/config/ (the settings surface)

Parent: `30-src.md`. Owns every read of the owner's spec files and of the
generated `local.yaml`, path resolution, the drift baseline, and the record of
which keys were read and which were defaulted. Depends on: filesystem, PyYAML,
`git/repo.py` (only `spec_files.py`, for the drift diff). Depended on by:
every other component.

```
config/
  __init__.py       re-exports load_settings(); nothing else
  spec_files.py     spec.yaml: the file list, hashing, baseline, drift
  project.py        project.yaml -> Settings; defaults; used-key tracking
  roster.py         subAgents.yaml -> Roster (rungs, prices, ladder)
  local.py          local.yaml read/write
  paths.py          harness root discovery; round-folder path resolution
```

## spec_files.py

Data: `SpecFile(path: Path, rel: str, sha256: str)`; `Baseline(acceptedAt:
str, acceptedCommit: str, files: list[SpecFile])`; `Drift(changed: list[str],
added: list[str], missing: list[str], diff: str)`.

- `locate_spec_yaml(start: Path) -> Path` — walks up from `start` to find
  `spec.yaml`; raises `RefusedError` when none.
- `list_spec_files(spec_yaml: Path) -> list[SpecFile]` — reads the `files:`
  list, expands `*` globs relative to `spec.yaml`, hashes each file. Refuses on
  a non-list, on a pattern that matches nothing (a listed file that does not
  exist is itself drift, not a crash) `[JC-01]`.
- `read_baseline(path: Path) -> Baseline | None` — parses
  `archives/spec-baseline.yaml`; `None` when absent.
- `write_baseline(path: Path, files: list[SpecFile], commit: str) -> Baseline`.
- `compute_drift(current: list[SpecFile], baseline: Baseline | None, repo: Repo) -> Drift | None`
  — `None` when identical; otherwise names changed, added and missing paths and
  builds the diff text via `repo.diff(baseline.acceptedCommit, paths)` for
  tracked files and a full listing for untracked. A missing baseline is drift
  with every file "added".
- `spec_file_set(spec_yaml: Path) -> frozenset[str]` — the relative paths, for
  the mechanical checks' immutability rule (`36-src-checks.md`).

## project.py

Data: `Settings` (frozen dataclass) with one typed field per key the harness
uses, each read by name from `project.yaml`, plus `defaulted: frozenset[str]`
and `unknown: frozenset[str]`, and a nested `StepSwitch(name: str, value: int)`
list for `steps`. Fields (types): `vision: str`, `currency: str`, `budget:
float`, `hardStopBudgetMultiple: float`, `hardStopBudgetMultipleIndividual:
float`, `lostValuePerHour: float`, `livingFileTokenCap: int`,
`livingFileCostPerToken: float`, `livingFileCostPerTokenOverCap: float`,
`livingFileBaseCost: float`, `testBaseCost: float`, `tokenBytes: int`,
`postMortemFileCostPerToken: float`, `postMortemCostPerSummaryToken: float`,
`planCostPerToken: float`, `specCostPerToken: float`, `maxRefactorOverhead:
float`, `defaultShares: dict[str, dict[str, float]]` (`work`, `gates`),
`gatesFraction: float`, `workFraction: float`, `steps: list[StepSwitch]`
(order preserved), `allowUpstream: int`, `livingSourcePaths: list[str]`,
`lockedProsePath: str`, `archivesPath: str`, `roundPaths: RoundPaths` (a
nested dataclass mirroring the YAML: `folder`, `artifacts: dict`, `runner:
dict`, `attempts: dict`, `testsArchive`, `judgmentCalls: dict`),
`maxSimultaneousSubAgentsPerRound: int`, `maxRoundAttempts: int`,
`maxTurnsPerGate: int`, `maxTurnsPerRun: int`, `maxRunWallClockHours: float`,
`verifyTimeoutSeconds: int`, `subAgentsFile: str`, `defaultAgent: str`,
`gateAgent: str`, `systemTestAgent: str`, `maxAgent: str`, and the defaulted
keys of `SPEC.md` §7 (`testPaths`, `carryForwardFiles`, `verifyCommand`,
`collectCommand`, `promptWarnTokens`, `mainBranch`, `remoteName`,
`syncAttempts`, `stepEndDelivery`, `quoteMatch`).

- `DEFAULTS: dict[str, object]` — the code defaults of `SPEC.md` §7, and only
  those; a key with no default that is missing from the file is a `LintError`.
- `load_project(path: Path) -> Settings` — parses YAML; coerces types; records
  `defaulted` (keys taken from `DEFAULTS`) and `unknown` (top-level keys in the
  file the code does not read); raises `LintError` on type errors, on
  `gatesFraction + workFraction != 1` (tolerance 1e-9), on a `steps` entry
  whose value is not 0 or 1, on an empty `livingSourcePaths`. Unknown keys are
  not an error here (doctor and lint report them; `start` refuses via
  `steps/lint.py`, which is where "unknown inputs refuse to start" lives).
- `render_value(settings: Settings, key: str) -> str` — the text form used by
  prompt tokens: lists joined by `, `, floats without trailing zeros, ints as
  is; raises `KeyError` for a key that is not a field (the renderer turns that
  into an unresolved token).
- `commented_keys(path: Path) -> list[str]` — top-level keys that appear only
  inside comments (`# ownerHourlyRate: 10`); doctor lists them as "placeholders
  seen, ignored" so the owner knows they are not read `[JC-04]`.

## roster.py

Data: `Rung(key: str, name: str, model: str, effort: str, inputUsdPerMTok:
float, outputUsdPerMTok: float, cacheReadUsdPerMTok: float,
cacheWriteUsdPerMTok: float, spawnCost: float, priceSource: str, priceDate:
str, rank: int)`; `Roster(rungs: dict[str, Rung], ladder: list[str],
estOutputFraction: float, driverUsdPerStep: float, sha256: str)`.

- `load_roster(path: Path) -> Roster` — `ladder` is the key order in the file,
  first is highest (`rank` 0) `[JC-06]`; refuses on a missing price field, on
  a non-positive `estOutputFraction`, on duplicate keys.
- `resolve_rung(roster: Roster, key: str, ceiling: str) -> Rung` — the rung by
  key, capped at the ceiling: a key above `ceiling` on the ladder resolves to
  the ceiling and the caller records a note; an unknown key raises
  `LintError`.
- `check_defaults(roster: Roster, settings: Settings) -> list[str]` —
  problems: `defaultAgent`, `gateAgent`, `systemTestAgent`, `maxAgent` not in
  the roster.

## local.py

Data: `Local` dataclass mirroring the `local.yaml` keys of `20-harness-root.md`.

- `read_local(path: Path) -> Local | None`.
- `write_local(path: Path, local: Local) -> None` — atomic write (temp file +
  rename).
- `fresh_local(paths: Paths, roster_hash: str, hooks_hash: str, python: str) -> Local`.

## paths.py

Data: `Paths(repoRoot: Path, harnessRoot: Path, specYaml: Path, projectYaml:
Path, subAgentsYaml: Path, agentsMd: Path, lockedProse: Path, archives: Path,
baseline: Path, ledgerMd: Path, localYaml: Path, ownerLog: Path, worktrees:
Path, verifyScratch: Path, claudeDir: Path)`; `RoundFolder(id: str, folder:
Path, plus one `Path` per `roundPaths` key: `plan`, `agentsPlan`, `spec`,
`specProse`, `suite`, `postmortem`, `state`, `history`, `ownerLog`, `prompts`,
`results`, `findings`, `testsArchive`, `definedCalls`, `undefinedCalls`)`.

- `discover(start: Path) -> Paths` — finds `spec.yaml` upward; the harness root
  is the parent of the listed `AGENTS.md` (`harness/`); raises `RefusedError`
  if the listed files do not share one such parent `[JC-07]`.
- `round_folder(paths: Paths, settings: Settings, round_id: str, base: Path | None = None) -> RoundFolder`
  — substitutes the literal `NNNN` in `roundPaths.folder`, joins each
  `roundPaths` entry; `base` lets a caller point at a worktree instead of the
  harness root.
- `format_round_id(n: int) -> str` — four digits, zero padded; wider when
  needed.
- `is_under(rel: str, roots: list[str]) -> bool` — path prefix test used by
  the checks and the ledger for `livingSourcePaths`, `testPaths`, the round
  folder.

## `__init__.py`

- `load_settings(start: Path | None = None) -> tuple[Paths, Settings, Roster]`
  — the one call everything else uses; discovers paths, loads project and
  roster, runs `roster.check_defaults` and raises `LintError` on problems.
