# 04 — Configuration and the spec-file guard: `config.py`, `specfiles.py`, `localstate.py`, `tokens.py`

## `src/config.py` — `project.yaml` and `subAgents.yaml` as objects

**Owns:** the schema of both files: every known key, its type, whether it is required,
its default (if any), and an example value used by fixtures and by `doctor`'s sample
render. Also cross-validation between the two files. **Depends on:** `errors`,
`pyyaml`. **Depended on by:** `commands`, `steps`, `context`, `ledger`, `paths`,
`doctor`, `prompts`, `landing`, `pauses`, `recording`, `next_action`, `suite`,
`agentdefs`, `fixture_spec` (tests).

Rule: **unknown keys refuse** (`ConfigError`), at every nesting level; a value of the
wrong type refuses; a missing required key refuses; a missing optional key takes its
default and is reported by `defaulted_keys()`. Comments in the YAML are not data.

### Types

- `KeySpec` (frozen dataclass): `path: str` (dotted, e.g. `roundPaths.artifacts.plan`),
  `type: str` (`str|int|float|number|bool01|list[str]|map[str,number]|map[str,bool01]`),
  `required: bool`, `default: Any`, `example: Any`, `description: str`.
- `PROJECT_KEYS: tuple[KeySpec, ...]` — one entry per key of today's `project.yaml`
  (`vision`, `currency`, `budget`, `hardStopBudgetMultiple`,
  `hardStopBudgetMultipleIndividual`, `lostValuePerHour`, `livingFileTokenCap`,
  `livingFileCostPerToken`, `livingFileCostPerTokenOverCap`, `livingFileBaseCost`,
  `testBaseCost`, `tokenBytes`, `postMortemFileCostPerToken`,
  `postMortemCostPerSummaryToken`, `planCostPerToken`, `specCostPerToken`,
  `maxRefactorOverhead`, `defaultShares.work`, `defaultShares.gates`, `gatesFraction`,
  `workFraction`, `steps`, `allowUpstream`, `livingSourcePaths`, `lockedProsePath`,
  `archivesPath`, `roundPaths.folder`, `roundPaths.artifacts.*` (plan, agentsPlan,
  spec, specProse, suite, postmortem), `roundPaths.runner.*` (state, history,
  ownerLog), `roundPaths.attempts.*` (prompts, results, findings),
  `roundPaths.testsArchive`, `roundPaths.judgmentCalls.*` (defined, undefined),
  `maxSimultaneousSubAgentsPerRound`, `maxRoundAttempts`, `maxTurnsPerGate`,
  `maxTurnsPerRun`, `maxRunWallClockHours`, `verifyTimeoutSeconds`, `subAgentsFile`,
  `defaultAgent`, `gateAgent`, `systemTestAgent`, `maxAgent`) — all required — plus the
  **defaulted keys** the code needs but the owner has not (yet) written [JC-18]:
  `testPaths: list[str] = ["tests/"]`, `carryForwardFiles: list[str] = ["docs/TODO.md",
  "docs/CLARIFICATIONS.md"]`, `promptWarnTokens: int = 40000`, `ownerLogPath: str =
  "OWNER.log"`, `verifyCommand: list[str] = ["python", "-m", "pytest", "-q",
  "-p", "no:cacheprovider"]`.
- `RoundPathsConfig` (dataclass): the `roundPaths` subtree as typed fields
  (`folder`, `artifacts: dict[str,str]`, `runner: dict[str,str]`, `attempts:
  dict[str,str]`, `tests_archive`, `judgment_calls: dict[str,str]`).
- `ProjectConfig` (dataclass): one typed attribute per key above (snake_case names,
  e.g. `living_file_token_cap`), `steps: dict[str, int]` in file order,
  `default_shares_work: dict[str, float]`, `default_shares_gates: dict[str, float]`,
  `round_paths: RoundPathsConfig`, `source_path: Path`, `raw: dict`.
  Methods: `defaulted_keys() -> list[str]`; `gate_setting(step: str) -> int` (0 when
  absent); `is_test_path(rel: str) -> bool`; `is_living_path(rel: str) -> bool`;
  `living_non_test_paths() -> list[str]`; `value_at(dotted: str) -> Any` (raises
  `KeyError`; used by templates for `project.*`).
- `AgentSpec` (dataclass): `rung`, `name`, `model`, `effort`, `input_usd_per_mtok`,
  `output_usd_per_mtok`, `cache_read_usd_per_mtok`, `cache_write_usd_per_mtok`,
  `spawn_cost`, `price_source: str | None`, `price_date: str | None`.
- `AgentsConfig` (dataclass): `est_output_fraction: float`, `driver_usd_per_step:
  float`, `agents: dict[str, AgentSpec]` in file order, `source_path: Path`.
  Methods: `ladder() -> list[str]` (rungs in file order; first is the highest [JC-19]);
  `rank(rung) -> int` (0 = highest; raises `KeyError`); `at_or_below(rung, ceiling)
  -> bool`; `get(rung) -> AgentSpec` (raises `ConfigError("UNKNOWN_RUNG")`).

### Functions

- `load_project(path: Path) -> ProjectConfig` — parses YAML, validates against
  `PROJECT_KEYS`, fills defaults, runs `validate_project`. Raises `ConfigError` with
  the dotted key in `details`.
- `load_agents(path: Path) -> AgentsConfig` — same for `subAgents.yaml` (known
  top-level keys: `estOutputFraction`, `driverUsdPerStep`, `agents`; known agent keys as
  in `AgentSpec`, `priceSource`/`priceDate` optional). Raises `ConfigError`.
- `validate_project(cfg: ProjectConfig) -> list[str]` — returns warnings; raises
  `ConfigError` on: `gatesFraction + workFraction != 1` (±1e-9); any fraction outside
  [0, 1]; `tokenBytes < 1`; non-positive limits; a `steps` value not 0/1; `roundPaths.folder`
  without `NNNN`; `defaultShares` naming a step absent from `steps`; a `livingSourcePaths`
  entry not ending in `/`; `allowUpstream != 0` (message: upstream mechanics are not
  implemented) [JC-06]. Warnings: `budget` ≤ 0, `testPaths` entry not under
  `livingSourcePaths`, a carry-forward file outside living paths.
- `validate_cross(cfg: ProjectConfig, agents: AgentsConfig) -> None` — `defaultAgent`,
  `gateAgent`, `systemTestAgent`, `maxAgent` exist; `defaultAgent`, `gateAgent`,
  `systemTestAgent` are at or below `maxAgent`. Raises `ConfigError`.
- `example_project_dict(steps: list[str]) -> dict` — a complete dict with example
  values for every key, `steps` built from the given names (all gates 0, checkpoints 1),
  `defaultShares` for the first two steps. Used by `fixture_spec` and `doctor`.
- `example_agents_dict() -> dict` — two rungs (`max`, `low`) with round prices.
- `render_value(value: Any) -> str` — how config values appear in prompts: scalars as
  YAML scalars, lists comma-space joined, mappings as `key: value` pairs comma-space
  joined [JC-20].

## `src/specfiles.py` — the spec-file guard

**Owns:** reading `spec.yaml`, expanding its patterns, hashing, the baseline, drift,
diffs, acceptance. **Depends on:** `localstate`, `errors`, `pyyaml`. **Depended on
by:** `commands` (`spec`), `rounds` (`start` refuses drift), `doctor`,
`test_spec_drift.py`, `install`.

- `SPEC_YAML = "spec.yaml"`; `BASELINE_DIRNAME = "spec-baseline"` (under
  `archivesPath`) [JC-04].
- `load_file_list(spec_yaml: Path) -> list[str]` — the `files:` entries as written.
  Raises `RefusedError("SPEC_YAML")` if the key is missing or not a list of strings.
- `expand_patterns(repo_root: Path, patterns: list[str]) -> list[str]` — posix
  relative paths, sorted, duplicates removed; a pattern may end in `/*` (all regular
  files of that directory, non-recursive); a pattern that matches nothing raises
  `RefusedError("SPEC_FILE_MISSING")`.
- `hash_bytes(data: bytes) -> str` and `hash_file(path: Path) -> str` — sha256 hex.
- `current_hashes(repo_root: Path) -> dict[str, str]` — path → hash for every
  expanded file (`spec.yaml` itself included).
- `DriftReport` (dataclass): `added: list[str]`, `removed: list[str]`, `changed:
  list[str]`, `unchanged: list[str]`; `clean` property; `summary() -> str`.
- `compare(current: dict[str, str], baseline: dict[str, str]) -> DriftReport`.
- `check_drift(repo_root: Path, harness_root: Path) -> DriftReport` — loads
  `local.yaml` via `localstate`, compares; an absent baseline reports every file as
  `added`.
- `assert_no_drift(repo_root: Path, harness_root: Path) -> None` — raises `DriftError`
  with `details["report"]` when not clean.
- `diff_text(repo_root: Path, harness_root: Path, rel: str) -> str` — unified diff
  between the baseline copy (`archives/spec-baseline/<rel>`) and the current file; for
  `added` files the whole file as `+` lines; for `removed`, the copy as `-` lines;
  `(no baseline copy)` when the copy is missing.
- `accept(repo_root: Path, harness_root: Path, archives_dir: Path) -> DriftReport` —
  copies every current spec file into the baseline directory (removing copies of
  removed files), writes the hashes and `spec_accepted_at` into `local.yaml`, returns
  the report that was accepted.
- `baseline_copy_path(archives_dir: Path, rel: str) -> Path`.

## `src/localstate.py` — `local.yaml`

**Owns:** the generated, committed, no-user-input file at the harness root. **Depends
on:** `errors`, `pyyaml`. **Depended on by:** `specfiles`, `agentdefs`, `install`,
`doctor`, `rounds` (staleness checks).

- `LocalState` (dataclass): `spec_baseline: dict[str, str]`, `spec_accepted_at: str |
  None`, `generated: dict[str, str]` (keys: `subAgentsHash`, `agentDefsHash`,
  `settingsHash`, `hookHash`), `installed_at: str | None`, `harness_version: str`.
- `load(path: Path) -> LocalState` — an absent file yields an empty state; malformed
  YAML raises `RefusedError("LOCAL_YAML")`.
- `save(path: Path, state: LocalState) -> None` — writes with a header comment
  `# generated by run.py; do not edit; no user input lives here`.
- `local.yaml` is committed, not gitignored [JC-51].
- `HARNESS_VERSION: str` — a constant bumped by hand when STATE.json's shape changes;
  written into every STATE.json (`state.py`) and `local.yaml`.

## `src/tokens.py` — the one token estimate

**Owns:** the only place bytes become tokens. **Depends on:** nothing. **Depended on
by:** `ledger`, `prompts`, `doctor`, `schemas` (summary size), `history`.

- `estimate(nbytes: int, token_bytes: int) -> int` — `ceil(nbytes / token_bytes)`;
  raises `ValueError` if `token_bytes < 1`.
- `text_tokens(text: str, token_bytes: int) -> int` — UTF-8 byte length, then `estimate`.
- `file_tokens(path: Path, token_bytes: int) -> int` — size on disk; 0 for a missing
  file.
- `blob_tokens(data: bytes, token_bytes: int) -> int`.
