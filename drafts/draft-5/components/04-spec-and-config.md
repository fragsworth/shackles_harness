# 04 — Spec files & config (`paths.py`, `specfiles.py`, `config.py`, `agentsmd.py`, `localyaml.py`)

**Purpose.** Find the repository, read the owner's files into typed values, guard them
against unreviewed change, and derive the machine-local facts. Nothing in this
component knows about rounds, git branches, prompts or money.

**Owns.** Path resolution; the spec-file list and baseline; the config schema (known
keys, types, defaults); the roster schema; AGENTS.md section extraction; `local.yaml`.

**Depends on.** Standard library, PyYAML. `localyaml.py` shells out to `git` for the
remote name and URL (read-only).

**Depended on by.** Every other `src` component (all take a `Paths` and a `Config`).

Common types (in `config.py`): `Config`, `Roster`, `Rung` (frozen dataclasses);
in `paths.py`: `Paths`. All functions here are pure given the file system.

---

## `paths.py`

`class Paths` (frozen): `repo_root: Path`, `spec_yaml: Path`, `harness_root: Path`,
`worktrees_dir: Path` (`repo_root/.worktrees`), `owner_log: Path` (`harness_root/OWNER.log`),
`local_yaml: Path`, `index_md: Path`, `claude_dir: Path`, `agents_dir: Path`,
`baseline_dir: Path` (`harness_root/<archivesPath>/spec-baseline`).

- `find_paths(start: Path | None = None) -> Paths` — walk up from `start` (default: the
  directory of `run.py`) to the first directory containing `spec.yaml`; the harness root
  is the directory containing `project.yaml` beneath it that also contains `src/run.py`
  (JC-01). Raises `PathsError` if either is not found.
- `paths_for_worktree(base: Paths, worktree: Path) -> Paths` — the same layout rooted at
  a worktree checkout. Pure.
- `round_folder(paths: Paths, cfg_round_folder: str, round_id: str) -> Path` — substitutes
  `NNNN` in `roundPaths.folder`; raises `PathsError` when the pattern lacks `NNNN`.
- `round_file(paths: Paths, cfg: "Config", round_id: str, key: str) -> Path` — resolves a
  dotted `roundPaths` key (`artifacts.plan`, `runner.state`, `attempts.prompts`,
  `testsArchive`, `judgmentCalls.defined`) against the round folder.
- `living_paths(paths: Paths, cfg: "Config") -> list[Path]`, `test_paths(...)`,
  `prose_dir(...)`, `archives_dir(...)`, `rounds_dir(...)` — thin resolvers.
- `is_under(path: Path, roots: list[Path]) -> bool` — path containment, symlink-free.

Errors: `PathsError(Exception)`.

## `specfiles.py`

- `list_spec_files(spec_yaml: Path) -> list[Path]` — parses `spec.yaml: files`, expands
  globs relative to `spec.yaml`, sorted, deduplicated, existing files only; a listed
  non-glob path that does not exist is still returned (so drift can report "missing").
  Raises `SpecListError` if `files` is absent or not a list of strings.
- `hash_file(path: Path) -> tuple[str, int]` — sha256 hex and byte count.
- `read_manifest(baseline_dir: Path) -> Manifest | None` — S11; `None` when no baseline.
- `write_baseline(spec_yaml: Path, baseline_dir: Path, now: datetime) -> Manifest` —
  snapshots every listed file into `files/` (creating directories, deleting stale
  snapshots) and writes `MANIFEST.json`.
- `drift(spec_yaml: Path, baseline_dir: Path) -> DriftReport` — `DriftReport(changed:
  list[FileDrift], missing: list[str], unbaselined: list[str], no_baseline: bool)`;
  `FileDrift(path, unified_diff: str)` where the diff is against the snapshot (text) or
  the phrase `binary differs`. Pure; never raises on missing files.
- `format_drift(report: DriftReport) -> str` — the human text the guard test and `start`
  print: one header per file, its diff, and the sentence `run 'python3 src/run.py
  accept-spec' after review`.

Errors: `SpecListError(Exception)`.

## `config.py`

Schema = a tuple of `Key(name: str, type: str, default: object | MISSING, doc: str)`
for `project.yaml`, and a second for `subAgents.yaml`. Every key in
`project.yaml` as shipped is in the schema without a default. Keys with defaults
(the ones `doctor` names as defaulted, JC-09): `testPaths` (`["tests/"]`),
`verifyCommand` (`["python3", "-m", "pytest", "-q", "tests", "--ignore=tests/probes"]`),
`promptTokenWarning` (`40000`), `gitRemote` (`"origin"`), `mainBranch` (`"main"`).

`class Config` (frozen) — one attribute per schema key (camelCase preserved as-is so
`{{ project.X }}` maps by name), plus `steps: dict[str, int]` (ordered as in file),
`defaultShares: {"work": dict, "gates": dict}`, `roundPaths: RoundPaths` (nested frozen
dataclass mirroring the YAML), `defaulted: tuple[str, ...]`, `unknown: tuple[str, ...]`,
`source: Path`.

`class Rung` (frozen): `key, name, model, effort, inputUsdPerMTok, outputUsdPerMTok,
cacheReadUsdPerMTok, cacheWriteUsdPerMTok, spawnCost, priceSource, priceDate, rank: int`
(0 = first in file = highest). `class Roster` (frozen): `rungs: dict[str, Rung]` (file
order), `estOutputFraction: float`, `driverUsdPerStep: float`, `sha256: str`, `unknown`.

- `load_config(harness_root: Path) -> Config` — reads `project.yaml`; type-checks every
  known key (int/float/str/bool/list[str]/dict); fills defaults; records `defaulted` and
  `unknown` (top level and inside `roundPaths`, `defaultShares`). Raises `ConfigError`
  listing every problem at once (wrong type, missing required key, `steps` not a mapping
  of name→0|1, `gatesFraction + workFraction` not 1 ± 0.001, `livingSourcePaths` empty).
- `load_roster(harness_root: Path, cfg: Config) -> Roster` — reads `cfg.subAgentsFile`;
  every rung needs all price fields; `rank` from order. Raises `ConfigError`.
- `rung_ceiling(roster: Roster, cfg: Config) -> Rung` — `cfg.maxAgent`; error if absent.
- `rung_at_most(roster: Roster, key: str, ceiling: Rung) -> bool`.
- `gates_on(cfg: Config, gated_steps: list[str], overrides: list[str]) -> list[str]` —
  steps whose table value is 1, in table order, minus overrides.
- `project_values(cfg: Config, roster: Roster, remaining_usd: float, gates: list[str])
  -> dict[str, str]` — the `{{ project.* }}` namespace: every scalar config key
  rendered as text, lists rendered `a, b, c`, plus `remaining` and `gates`.
- `config_doc() -> list[Key]` — the schema, for doctor and tests.

Errors: `ConfigError(Exception)` with `.problems: list[str]`.

## `agentsmd.py`

- `sections(agents_md: Path) -> dict[str, str]` — every `## ` heading → its body up to
  the next `## ` or EOF. Key = heading text uppercased, trailing period stripped, runs
  of non-alphanumerics → `_`; e.g. `## DEFINED AND UNDEFINED JUDGMENT CALLS` →
  `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`, `## ADVICE.` → `ADVICE`. Duplicate keys →
  `AgentsMdError`.
- `agents_values(agents_md: Path) -> dict[str, str]` — the `{{ agents.* }}` namespace
  (same as `sections`, plus `ALL` = the whole file).

## `localyaml.py`

- `derive_local(paths: Paths, cfg: Config, roster: Roster) -> dict` — S12 values:
  interpreter path, remote name (`cfg.gitRemote`) and its URL from `git remote get-url`,
  main branch, baseline manifest hash, roster hash, agent-defs hash (06 provides
  `agentdefs.current_hash`; passed in as a callable to avoid a cycle), owner-log path.
- `write_local(paths: Paths, values: dict) -> None` — YAML with a `# generated, do not
  edit` header. `read_local(paths: Paths) -> dict | None` (JC-11).

## Invariants
- `load_config` never returns a partially valid config; it raises with all problems.
- No function here writes anything but `local.yaml` and the baseline directory.
- Only `specfiles.py` reads the real spec-file contents for hashing; `config.py` reads
  only the two YAML files.

## Covered by
`tests/test_paths.py`, `tests/test_specfiles.py`, `tests/test_config.py`,
`tests/test_agentsmd.py`, `tests/test_localyaml.py` (cases in 13-tests.md).
