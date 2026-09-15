# 03 — Spec files and configuration: `paths.py`, `specfiles.py`, `config.py`, `localcfg.py`

These four modules are the only readers of the owner's YAML files and the only place that knows where things are on disk. Everything else asks them.

## 3.1 `src/shackles/paths.py`

**Owns:** locating the harness root, the repository root and `spec.yaml`; resolving round-folder paths from `roundPaths`. **Depends on:** `errors` only (no config import; `RoundPaths` is given the `roundPaths` mapping as a plain dict). **Depended on by:** every other module.

- `@dataclass(frozen=True) class Roots`: `harness: Path` (dir containing `project.yaml`), `repo: Path` (`git rev-parse --show-toplevel` equivalent found by walking up to a `.git` entry), `spec_yaml: Path` (first `spec.yaml` found walking up from `harness`), `spec_dir: Path` (its parent), `src: Path`, `runner: Path` (`src/run.py`).
  - `Roots.discover(start: Path) -> Roots` — raises `ConfigError` when no `project.yaml` or no `spec.yaml` is found upward.
  - `Roots.for_worktree(self, worktree_root: Path) -> Roots` — the same layout inside a worktree (harness = `worktree_root / self.harness.relative_to(self.repo)`).
- `class RoundPaths`: built from `RoundPaths(round_paths: dict, round_id: str, harness: Path)`.
  - `folder(self) -> Path` — `roundPaths.folder` with the `N…N` placeholder replaced by the padded id; raises `ConfigError` if the pattern has no run of `N`.
  - `artifact(self, key: str) -> Path`, `runner_file(self, key: str) -> Path`, `attempt_dir(self, key: str) -> Path`, `judgment_file(self, kind: str) -> Path`, `tests_archive(self) -> Path` — each looks the name up in the mapping; unknown key → `ConfigError("roundPaths.<group>.<key> missing")`.
  - `prompt_file(self, attempt_id: str) -> Path`, `result_file(self, attempt_id: str) -> Path`, `findings_file(self, judged_attempt_id: str) -> Path`, `pause_file(self, k: int) -> Path`, `checkpoint_file(self, step: str, n: int) -> Path`.
  - `relative(self, p: Path) -> str` — path relative to the harness root, forward slashes (used in prompts and history).
- `pad_round_id(n: int, pattern: str) -> str`, `round_id_width(pattern: str) -> int`, `is_under(path: Path, roots: Iterable[str]) -> bool` (prefix test on normalized relative paths; `"src/"` matches `src/x.py` but not `srcx`).

## 3.2 `src/shackles/specfiles.py`

**Owns:** the list of spec files, their hashing, the committed baseline, drift detection and the drift diff. **Depends on:** `paths`, `errors`; uses `gitops.show_file` through an injected callable for the diff (so tests can pass a fake). **Depended on by:** `commands/start`, `commands/record`, `commands/next_`, `commands/spec_drift`, `commands/accept_spec`, `doctor`, `tests/test_spec_drift.py`.

- `list_spec_files(roots: Roots) -> list[str]` — parse `spec.yaml` (`files:` list), expand globs (`harness/locked_prose/*` → sorted matches), return paths relative to `spec_dir`; `spec.yaml` itself is included only if listed (it is). Raises `ConfigError` on a malformed list or an entry that resolves to nothing (a glob with no matches is allowed and reported as empty).
- `hash_file(p: Path) -> str` — `sha256:<hex>` of bytes.
- `current_hashes(roots: Roots) -> dict[str, str]`.
- `@dataclass class Baseline`: `files: dict[str, str]`, `accepted_commit: str | None`, `accepted_at: ts`, `accepted_by: str`, `note: str`; `load(path: Path) -> Baseline` (`ConfigError` on a missing or malformed file; a missing baseline is drift of everything), `save(self, path: Path) -> None`.
- `@dataclass class Drift`: `changed: list[str]`, `added: list[str]`, `removed: list[str]`; `empty -> bool`.
- `drift(roots: Roots, baseline: Baseline) -> Drift` — set/hash comparison, no git.
- `drift_diff(roots: Roots, baseline: Baseline, d: Drift, show: Callable[[str, str], str | None]) -> str` — unified diff per changed file between `show(accepted_commit, path)` and the working file; when `show` returns `None` (no git, no commit) the diff section says "(baseline content unavailable; hash mismatch only)". Added/removed files are listed with full content / a note.
- `accept(roots: Roots, path: Path, *, commit: str | None, by: str, note: str, now: ts) -> Baseline` — write the new baseline from current hashes.
- `is_spec_file(rel_repo_path: str, roots: Roots, files: list[str]) -> bool` — used by `checks` to revert any attempt edit to a spec file.

## 3.3 `src/shackles/config.py`

**Owns:** loading and validating `project.yaml` and `subAgents.yaml`; the key registry (every key the code consumes, its type, whether it is required or defaulted); the agent roster and rung ladder; derived values used by prompts (`remaining` is *not* derived here — it needs the ledger; see [07] `ledger.project_remaining`). **Depends on:** `paths`, `errors`, PyYAML. **Depended on by:** almost everything.

### Registry
- `@dataclass(frozen=True) class Key`: `path: str` (dotted; `*` matches one map level, e.g. `steps.*`, `agents.*.model`, `defaultShares.work.*`), `type: str` (`int|number|str|bool|list[str]|map|fraction`), `required: bool`, `default: object | None`, `used_by: str` (module name, informational), `doc: str`.
- `PROJECT_KEYS: tuple[Key, ...]` — one entry per key in `project.yaml` as it stands (vision, currency, budget, hardStopBudgetMultiple, hardStopBudgetMultipleIndividual, lostValuePerHour, livingFileTokenCap, livingFileCostPerToken, livingFileCostPerTokenOverCap, livingFileBaseCost, testBaseCost, tokenBytes, postMortemFileCostPerToken, postMortemCostPerSummaryToken, planCostPerToken, specCostPerToken, maxRefactorOverhead, defaultShares.work.*, defaultShares.gates.*, gatesFraction, workFraction, steps.*, allowUpstream, livingSourcePaths, lockedProsePath, archivesPath, roundPaths.folder, roundPaths.artifacts.*, roundPaths.runner.*, roundPaths.attempts.*, roundPaths.testsArchive, roundPaths.judgmentCalls.*, maxSimultaneousSubAgentsPerRound, maxRoundAttempts, maxTurnsPerGate, maxTurnsPerRun, maxRunWallClockHours, verifyTimeoutSeconds, subAgentsFile, defaultAgent, gateAgent, systemTestAgent, maxAgent) — all `required`, no default — plus the registered defaulted keys: `testPaths` (default `["tests/"]`, JC-18), `promptSizeWarnTokens` (default 40000, JC-19). Commented-out owner placeholders (`ownerHourlyRate`, `costToWaitForOwner`) are *not* registered: if the owner uncomments one it is reported as unused until code consumes it.
- `SUBAGENTS_KEYS: tuple[Key, ...]` — `estOutputFraction`, `driverUsdPerStep`, `agents.*.{name, model, effort, inputUsdPerMTok, outputUsdPerMTok, cacheReadUsdPerMTok, cacheWriteUsdPerMTok, spawnCost, priceSource, priceDate}`, all required.

### Loading
- `load_yaml(p: Path) -> dict` — PyYAML safe load; `ConfigError` on parse error or non-mapping root.
- `@dataclass class Config`: `values: dict` (raw), `effective: dict` (defaults applied), `defaulted: list[str]`, `unused: list[str]`, `source: Path`.
  - `Config.load(roots: Roots) -> Config` — read `project.yaml`, apply registry: type-check every registered key present (`ConfigError` naming the key and expected type), fill defaults, collect `defaulted` and `unused` (present but unregistered; wildcard-matched keys count as registered). Cross-checks: `gatesFraction + workFraction == 1 ± 1e-9`; `livingSourcePaths` non-empty and each ends with `/`; `roundPaths.folder` contains an `N` run; every `steps.*` and `defaultShares.*.*` value is `0` or `1` / a fraction respectively. Does **not** check step names (that is `steps.lint`, [04]).
  - `get(self, path: str) -> object` — effective value by dotted path; `KeyError`-free: raises `ConfigError` for unregistered paths (a programming error surfaced loudly).
  - `step_gate_on(self, step: str) -> bool`, `checkpoint_on(self, step: str) -> bool` — read `steps.<name>` as 0/1.
  - `living_paths(self) -> list[str]`, `test_paths(self) -> list[str]` (each test path must lie under a living path; else `ConfigError`), `round_paths(self) -> dict`.
  - `prose_values(self) -> dict[str, str]` — every scalar/list effective key rendered for `{{ project.* }}`: scalars as-is, lists comma-joined, plus `gates` (see [04] §4.2 for its text). `remaining` is supplied by the caller (prompts) because it needs the ledger.
- `@dataclass class Rung`: `key: str`, `name: str`, `model: str`, `effort: str`, `input_usd_per_mtok: float`, `output_usd_per_mtok: float`, `cache_read_usd_per_mtok: float`, `cache_write_usd_per_mtok: float`, `spawn_cost_usd: float`, `price_source: str`, `price_date: str`, `rank: int` (0 = highest, file order).
- `@dataclass class AgentRoster`: `rungs: dict[str, Rung]` (ordered), `est_output_fraction: float`, `driver_usd_per_step: float`, `default_agent: str`, `gate_agent: str`, `system_test_agent: str`, `max_agent: str`.
  - `AgentRoster.load(roots: Roots, cfg: Config) -> AgentRoster` — file named by `cfg.get("subAgentsFile")` relative to the harness root; validates with `SUBAGENTS_KEYS`; every rung referenced by `defaultAgent/gateAgent/systemTestAgent/maxAgent` must exist (`ConfigError`).
  - `rung(self, key: str) -> Rung` (`ConfigError` unknown), `within_ceiling(self, key: str) -> bool` (rank ≤ rank of `max_agent`), `ladder(self) -> list[str]`, `table_text(self) -> str` (one line per rung: key, name, model, effort, prices — rendered into PLAN-AGENTS prompts).
- `registered_paths(keys: tuple[Key, ...]) -> list[str]`, `match_key(path: str, keys) -> Key | None`, `walk(values: dict) -> Iterator[tuple[str, object]]` (dotted leaf paths).

Errors: all `ConfigError` with `detail` naming the key.

## 3.4 `src/shackles/localcfg.py`

**Owns:** `local.yaml` ([00] §0.13): detection of environment facts and (re)generation. **Depends on:** `paths`, `errors`; takes detection callables from `gitops`/`invoke` by injection (`detect(roots, cfg, probes: EnvProbes)`), so it does not import them. **Depended on by:** `doctor`, `commands/start`, `gitops` (reads `git.*`), `invoke` (reads `claude.command`).

- `@dataclass class EnvProbes`: `git_remote: Callable[[], tuple[str, str] | None]` (name, url), `git_main_branch: Callable[[str], str]`, `claude_version: Callable[[str], str | None]`, `python: Callable[[], tuple[str, str]]`.
- `@dataclass class LocalConfig`: the fields of [00] §0.13; `load(p: Path) -> LocalConfig | None` (None when absent; `ConfigError` when unparsable), `save(self, p: Path) -> None`, `git_remote -> str` (default `origin`), `main_branch -> str` (default `main`), `claude_command -> str` (default `claude`).
- `generate(roots: Roots, cfg: Config, roster: AgentRoster, probes: EnvProbes, *, baseline_drift: bool, agent_defs: list[str], owner_log_entries: int, now: ts) -> LocalConfig` — pure assembly from arguments.
- `ensure(roots, cfg, roster, probes, ...) -> LocalConfig` — load if present, else generate and save.

Nothing in `local.yaml` is ever read as a *setting*; a command that needs a value it lacks re-detects rather than failing.
