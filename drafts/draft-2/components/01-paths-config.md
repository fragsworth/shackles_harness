# 01 — Roots, configuration, the step table, the spec guard

Parent: [`../SPEC.md`](../SPEC.md). Five modules under `harness/src/`. Each owns one
question and answers it with plain data; none of them touches git, prompts or money.

Conventions used in every module file (01–07): signatures are Python; `Path` is
`pathlib.Path`; "raises" lists the exception types a caller may catch; every module defines
its own exception class derived from `HarnessError` (defined in `paths.py`, the one shared
base class, chosen because every module already imports `paths`). Every public function is
pure or says what it writes.

---

## paths.py — where things are

**Owns:** root discovery, conversion between harness-relative and repo-relative paths,
the fixed names of generated files. **Depends on:** nothing in `src/`.
**Depended on by:** every other module.

```python
class HarnessError(Exception): ...            # base for all runner errors; .code: int exit code (default 1)
class PathsError(HarnessError): ...

@dataclass(frozen=True)
class Roots:
    harness: Path          # HARNESS_ROOT, absolute
    repo: Path             # REPO_ROOT, absolute
    spec_index: Path       # the spec.yaml found (absolute)
    prefix: Path           # harness relative to repo, e.g. Path("harness"); Path(".") if equal

def discover(start: Path | None = None) -> Roots
    # Walk up from `start` (default: this file's directory) to the first dir holding project.yaml;
    # find REPO_ROOT with git; find spec.yaml (harness dir, then parents up to repo root).
    # raises PathsError when no project.yaml, no git repo, or no spec.yaml is found.

def to_repo(roots: Roots, harness_rel: str | Path) -> Path      # "src/x.py" -> "harness/src/x.py"
def to_harness(roots: Roots, repo_rel: str | Path) -> Path | None   # inverse; None if outside HARNESS_ROOT
def under(path: Path, prefixes: Iterable[Path]) -> bool          # path is inside any prefix (both relative to the same root)

# Fixed generated-file names, one place, no magic strings elsewhere:
LOCAL_YAML = "local.yaml"; OWNER_LOG = "OWNER.log"; INDEX_MD = "INDEX.md"
BASELINE_DIR = "spec-baseline"; BASELINE_MANIFEST = "MANIFEST.json"
WORKTREES_DIR = ".worktrees"; AGENT_DEF_PREFIX = "shackles-"
```

---

## config.py — the owner's settings, validated

**Owns:** loading `project.yaml` and `subAgents.yaml` into typed objects; the registry of
required keys, their types, and the *defaulted* keys (keys the runner needs that the owner
may omit); reporting unknown keys. **Depends on:** `paths`. **Depended on by:** almost
everything, but only through the `Config` value; no one imports the YAML layout.

```python
class ConfigError(HarnessError): ...

@dataclass(frozen=True)
class Agent:            # one rung of subAgents.yaml
    rung: str; name: str; model: str; effort: str
    input_usd_per_mtok: float; output_usd_per_mtok: float
    cache_read_usd_per_mtok: float; cache_write_usd_per_mtok: float
    spawn_cost_usd: float; price_source: str; price_date: str

@dataclass(frozen=True)
class Roster:
    ladder: tuple[str, ...]            # rung keys in file order; index 0 is the highest rung
    agents: dict[str, Agent]
    est_output_fraction: float
    driver_usd_per_step: float
    def rank(self, rung: str) -> int   # 0 = highest; raises ConfigError for unknown rung
    def at_or_below(self, ceiling: str) -> tuple[str, ...]

@dataclass(frozen=True)
class RoundPaths:       # project.yaml roundPaths, verbatim strings, folder pattern with "NNNN"
    folder: str; artifacts: dict[str, str]; runner: dict[str, str]
    attempts: dict[str, str]; tests_archive: str; judgment_calls: dict[str, str]

@dataclass(frozen=True)
class Config:
    raw: dict                                   # project.yaml as loaded (read-only use only)
    vision: str; currency: str; budget: float
    hard_stop_multiple: float; hard_stop_multiple_individual: float; lost_value_per_hour: float
    living_file_token_cap: int; living_file_cost_per_token: float; living_file_cost_per_token_over_cap: float
    living_file_base_cost: float; test_base_cost: float; token_bytes: int
    post_mortem_file_cost_per_token: float; post_mortem_cost_per_summary_token: float
    plan_cost_per_token: float; spec_cost_per_token: float
    max_refactor_overhead: float
    default_shares: dict[str, dict[str, float]]  # {"work": {STEP: f}, "gates": {STEP: f}}
    gates_fraction: float; work_fraction: float
    steps: dict[str, int]                        # name -> 0/1 as written, in file order
    allow_upstream: int
    living_source_paths: tuple[str, ...]; locked_prose_path: str; archives_path: str
    round_paths: RoundPaths
    max_simultaneous_sub_agents_per_round: int
    max_round_attempts: int; max_turns_per_gate: int; max_turns_per_run: int
    max_run_wall_clock_hours: float; verify_timeout_seconds: int
    sub_agents_file: str; default_agent: str; gate_agent: str; system_test_agent: str; max_agent: str
    # defaulted keys (see DEFAULTS):
    test_paths: tuple[str, ...]; main_branch: str; remote: str; prompt_warn_tokens: int
    roster: Roster
    defaulted: tuple[str, ...]                   # which DEFAULTS were applied (owner did not set them)
    unknown: tuple[str, ...]                     # keys present in project.yaml the runner does not use

DEFAULTS: dict[str, object] = {
    "testPaths": ["tests/"],       # where test functions are counted and where verify runs (JC-07)
    "mainBranch": "main",
    "remote": "origin",
    "promptWarnTokens": 30000,     # prompt-size warning threshold, in estimated tokens
}
REQUIRED: dict[str, type | tuple[type, ...]]     # every other key above, with its expected type

def load(roots: Roots) -> Config
    # Parses both YAML files, applies DEFAULTS, validates REQUIRED presence and types,
    # validates: fractions in [0,1]; gatesFraction + workFraction == 1 (±1e-6);
    # steps values are 0/1/true/false; every *Agent key names a rung; maxAgent is a rung;
    # every path setting ends with "/"; roundPaths.folder contains "NNNN"; tokenBytes >= 1;
    # allowUpstream == 0 (1 is "not implemented", refused).
    # raises ConfigError with every problem listed (not just the first).

def sub_agents_path(roots: Roots, cfg_raw: dict) -> Path      # HARNESS_ROOT / subAgentsFile
def unknown_keys(raw: dict) -> list[str]                       # top-level keys not in REQUIRED or DEFAULTS
def project_view(cfg: Config) -> dict[str, str]
    # Every project.yaml key rendered for {{ project.KEY }}: scalars as str, lists as JSON,
    # dicts as compact JSON; derived keys are added by render.py, not here.
```

Rules:
- `steps` is loaded verbatim (order kept); *interpreting* it is `steps.py`'s job.
- Unknown keys are not an error here; `doctor` warns and `start` refuses (see JC-08).
- `subAgents.yaml` `agents:` order is the ladder; `maxAgent` must be a rung; rungs above
  `maxAgent` remain loaded (for pricing history) but are not selectable (JC-09).

---

## steps.py — the fixed step table, in code

**Owns:** the ordered list of steps, each step's kind, performer, artifact names, declared
path classes (JC-11), verification mode and prose file names; the lint of `project.yaml steps`
against that table. **Depends on:** `paths`, `config`. **Depended on by:** `round`,
`plumbing`, `doctor`, `worktree`, `verify`, `quote`, `suite`.

```python
class StepsError(HarnessError): ...

Kind = Literal["producer", "checkpoint", "runner"]
Performer = Literal["driver", "subagent", "runner"]
Verify = Literal["none", "collect", "suite"]
PathClass = Literal["round_folder", "test_paths", "living_non_test", "living_all",
                    "carry_forward", "conflicted_files"]

@dataclass(frozen=True)
class Step:
    name: str; kind: Kind; performer: Performer
    has_gate: bool                       # a gate *can* exist (owner turns it on/off in project.yaml)
    artifacts: tuple[str, ...]           # roundPaths.artifacts keys produced, e.g. ("spec", "specProse")
    inputs: tuple[str, ...]              # artifact keys / carry-forward names read (for process instructions)
    declared: tuple[PathClass, ...]      # what the producer may edit; round_folder is always included
    verify: Verify
    overview_prose: str | None           # "PLAN-TO-SPEC-OVERVIEW"; None for runner-only steps
    gate_prose: str | None               # "PLAN-TO-SPEC-GATE"; None when has_gate is False
    overridable: bool                    # may the owner "override" (skip) it this round

TABLE: tuple[Step, ...] = (
  Step("CHAT-TO-PLAN",          "producer", "driver",   True,  ("plan",),              (),                                     ("round_folder",),                     "none",    "CHAT-TO-PLAN-OVERVIEW",           "CHAT-TO-PLAN-GATE"?, False),
  Step("PLAN-AGENTS",           "producer", "subagent", True,  ("agentsPlan",),        ("plan",),                              ("round_folder",),                     "none",    "PLAN-AGENTS-OVERVIEW",            "PLAN-AGENTS-GATE",           True),
  Step("PLAN-TO-SPEC",          "producer", "subagent", True,  ("spec","specProse"),   ("plan","agentsPlan"),                  ("round_folder",),                     "none",    "PLAN-TO-SPEC-OVERVIEW",           "PLAN-TO-SPEC-GATE",          True),
  Step("CHECKPOINT-1",          "checkpoint","driver",  False, (),                     (),                                     (),                                    "none",    "CHECKPOINT-OVERVIEW",             None,                         True),
  Step("SPEC-TO-TESTS",         "producer", "subagent", True,  (),                     ("plan","spec","specProse"),            ("test_paths","round_folder"),         "collect", "SPEC-TO-TESTS-OVERVIEW",          "SPEC-TO-TESTS-GATE",         True),
  Step("SPEC-TO-IMPLEMENTATION","producer", "subagent", True,  (),                     ("plan","spec","specProse"),            ("living_non_test","round_folder"),    "suite",   "SPEC-TO-IMPLEMENTATION-OVERVIEW", "SPEC-TO-IMPLEMENTATION-GATE",True),
  Step("TESTS-TO-SUITE",        "producer", "subagent", True,  ("suite",),             ("spec","specProse"),                   ("test_paths","round_folder"),         "suite",   "TESTS-TO-SUITE-OVERVIEW",         "TESTS-TO-SUITE-GATE",        True),
  Step("CHECKPOINT-2",          "checkpoint","driver",  False, (),                     (),                                     (),                                    "none",    "CHECKPOINT-OVERVIEW",             None,                         True),
  Step("LANDING",               "runner",   "runner",   False, (),                     (),                                     ("conflicted_files","round_folder"),   "suite",   None,                              None,                         False),
  Step("POSTMORTEM",            "producer", "subagent", True,  ("postmortem",),        ("plan","spec","specProse","suite"),    ("carry_forward","round_folder"),      "collect", "POSTMORTEM-OVERVIEW",             "POSTMORTEM-GATE",            True),
  Step("CLEANUP",               "producer", "subagent", False, (),                     (),                                     ("living_all","round_folder"),         "suite",   "CLEANUP-OVERVIEW",                None,                         True),
)
```

The `CHAT-TO-PLAN` gate prose name is `"CHAT-TO-PLAN-GATE"` even though no such file exists
today: the owner's table lists a gate flag for it, so the table allows a gate; when the
prose file is absent and the flag is 0, nothing is rendered; when the flag is 1 and the file
is absent, `doctor` and `start` report "gate on but no prose" and refuse (JC-10). `CLEANUP`
and `LANDING` are "no gate" per the owner's comments, so `has_gate` is False and a flag of 1
is accepted but ignored with a doctor note.

```python
def by_name(name: str) -> Step                 # raises StepsError for unknown names
def names() -> tuple[str, ...]
def index_of(name: str) -> int
def producers() -> tuple[Step, ...]            # kind == "producer"
def gated(cfg: Config) -> tuple[Step, ...]     # steps whose gate is on this round (flag 1 and has_gate)
def checkpoints_on(cfg: Config) -> tuple[str, ...]
def lint(cfg: Config) -> list[str]
    # Problems, empty when clean: owner steps not the same set and order as TABLE ("step list
    # assumed fixed"); flag on a step without a gate (note, not an error); unknown names.
def gate_name(step: Step) -> str               # "PLAN-TO-SPEC-GATE"
def prose_names(cfg_steps_on: bool = True) -> set[str]   # every prose name the table can reference
```

---

## localyaml.py — the generated `local.yaml`

**Owns:** writing `HARNESS_ROOT/local.yaml`, a machine-readable digest with no user input.
**Depends on:** `paths`, `config`, `steps`, `speclock` (status only). **Depended on by:**
`doctor`, `round` (both call `write`); agents read the file.

Contents (all derived): schema version; absolute `harness_root`, `repo_root`, `spec_index`;
`defaults_applied` (key → value); `unknown_keys`; `steps_effective` (name → {kind, gate_on,
checkpoint_on, overridden_this_round}); `gates_in_order`; `agent_definitions` (rung → file);
`baseline_status` (`clean` | `drift` | `missing`); `current_round` (id or null);
`generated_at`.

```python
def build(roots: Roots, cfg: Config, *, state: dict | None = None) -> dict
def write(roots: Roots, cfg: Config, *, state: dict | None = None) -> Path   # atomic replace
```

---

## speclock.py — the spec-file guard

**Owns:** enumerating the spec files from `spec.yaml`, hashing them, comparing to the
accepted snapshot, producing diffs, and accepting a new snapshot. **Depends on:** `paths`.
**Depended on by:** `doctor`, `round.start` (refuses on drift), `tests/test_spec_drift.py`,
`localyaml`.

```python
class SpecLockError(HarnessError): ...

@dataclass(frozen=True)
class SpecFile:
    rel: str            # path relative to the spec index's directory, as listed/globbed
    abs: Path
    sha256: str; size: int

@dataclass(frozen=True)
class Drift:
    changed: tuple[str, ...]; added: tuple[str, ...]; removed: tuple[str, ...]
    def clean(self) -> bool
    def diff_text(self, roots: Roots) -> str     # unified diffs, one per changed/added/removed file

def list_files(roots: Roots) -> tuple[SpecFile, ...]
    # Reads spec.yaml `files:`; expands globs (sorted); raises SpecLockError if a non-glob
    # entry is missing, or if spec.yaml is itself not listed (the owner's own rule).
def baseline_dir(roots: Roots) -> Path
def read_manifest(roots: Roots) -> dict[str, dict] | None       # None when no baseline yet
def compare(roots: Roots) -> Drift
def accept(roots: Roots) -> tuple[SpecFile, ...]
    # Replaces spec-baseline/ atomically (write to a temp dir, swap) with copies + MANIFEST.json.
def status(roots: Roots) -> Literal["clean", "drift", "missing"]
```

The owner quote requirement for `accept` is enforced by the CLI layer (file 07), not here,
so that tests can call `accept` directly.
