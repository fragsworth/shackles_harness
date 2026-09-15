# 02 — Prompts: prose, rendering, plumbing, AGENTS.md sections, agent definitions, doctor

Parent: [`../SPEC.md`](../SPEC.md). Six modules under `harness/src/`. Together they turn
the owner's locked prose into the exact text an agent receives, and check offline that this
can be done for every step. None of them touches git or money; `plumbing` reads state
values it is *given*, never `STATE.json` itself.

## Template language (shared by all six)

A token is `{{ ns.KEY }}` — two braces, optional spaces, a namespace, a dot, a key of
`[A-Za-z0-9_-]+`, two braces. Namespaces:

| ns | KEY resolves to | Supplied by |
|---|---|---|
| `prose` | the rendered content of `locked_prose/KEY.txt` (recursive; cycles are errors) | `prose.py` |
| `project` | `config.project_view()` plus derived `remaining` and `gates` | `render.py` |
| `round` | `id`, `folder`, `base_commit`, `plan`, `budget`, `spend`, `remaining` | `render.RoundView` |
| `plumbing` | `PROCESS-INSTRUCTIONS`, `GATE-PROSE` | `plumbing.py` |
| `agents` | a section of `AGENTS.md` by normalised heading | `agentsmd.py` |

An unknown namespace, unknown key, or missing prose file is an **unresolved token**; the
renderer collects them all instead of stopping at the first. Tokens never expand to text
that is re-scanned for tokens except in the `prose` namespace (so owner words rendered
through `round.plan` cannot inject tokens).

---

## prose.py — the locked prose, as files

**Owns:** reading `locked_prose/`, listing what exists, finding tokens in text.
**Depends on:** `paths`, `config` (for `lockedProsePath`). **Depended on by:** `render`,
`plumbing`, `doctor`.

```python
class ProseError(HarnessError): ...

TOKEN_RE: re.Pattern      # the token grammar above; groups "ns" and "key"

@dataclass(frozen=True)
class Token:
    ns: str; key: str; span: tuple[int, int]; raw: str

def prose_dir(roots: Roots, cfg: Config) -> Path
def available(roots: Roots, cfg: Config) -> dict[str, Path]      # name (without .txt) -> path
def read(roots: Roots, cfg: Config, name: str) -> str            # raises ProseError if missing
def tokens_in(text: str) -> list[Token]
def inventory(roots: Roots, cfg: Config) -> dict[str, list[Token]]   # every file -> its tokens (unrendered)
def classify_names(names: Iterable[str]) -> dict[str, list[str]]
    # {"overview": [...step names...], "gate": [...], "common": [...], "unknown": [...]}
    # by suffix: "-OVERVIEW", "-GATE", prefix "COMMON-"; "unknown" is anything else.
```

---

## agentsmd.py — sections of AGENTS.md

**Owns:** splitting the owner's `AGENTS.md` into sections addressable as `agents.KEY`.
**Depends on:** `paths`. **Depended on by:** `render`, `doctor`.

Normalisation of a heading to a key: strip leading `#`s and surrounding whitespace, drop
trailing punctuation, uppercase, replace runs of non-alphanumerics with `_`. So
`## DEFINED AND UNDEFINED JUDGMENT CALLS` → `DEFINED_AND_UNDEFINED_JUDGMENT_CALLS`. A section
is the heading line plus everything up to the next heading of the same or higher level.

```python
class AgentsMdError(HarnessError): ...
def path(roots: Roots) -> Path                          # HARNESS_ROOT/AGENTS.md
def sections(text: str) -> dict[str, str]              # key -> section text (heading included)
def section(roots: Roots, key: str) -> str             # raises AgentsMdError when absent
def keys(roots: Roots) -> list[str]
```

---

## render.py — turning templates into text

**Owns:** resolving tokens against the five namespaces; the `RoundView` value; unresolved
token reporting; the prompt-size estimate. **Depends on:** `paths`, `config`, `prose`,
`agentsmd`, `tokens` (file 06, for size). **Depended on by:** `plumbing` (for GATE-PROSE),
`round` (to write prompt files), `doctor`.

```python
class RenderError(HarnessError): ...

@dataclass(frozen=True)
class RoundView:
    id: str; folder: str; base_commit: str; plan: str
    budget: float; spend: float; remaining: float
    def as_map(self) -> dict[str, str]         # money as "12.34", ints as str

@dataclass(frozen=True)
class Context:
    project: dict[str, str]          # config.project_view + "remaining" + "gates"
    round: dict[str, str]            # RoundView.as_map(), or the synthetic view (doctor)
    plumbing: dict[str, str]         # {"PROCESS-INSTRUCTIONS": ..., "GATE-PROSE": ...}
    agents: dict[str, str]           # agentsmd.sections()

@dataclass(frozen=True)
class Rendered:
    text: str
    unresolved: tuple[Token, ...]    # every token that could not be resolved, in order
    used_prose: tuple[str, ...]      # prose files pulled in (for HISTORY and doctor)
    est_tokens: int                  # tokens.estimate(text)

def project_context(cfg: Config, *, remaining: float, gates_line: str) -> dict[str, str]
def gates_line(cfg: Config, overridden_gates: Iterable[str] = ()) -> str
    # "PLAN-AGENTS-GATE, PLAN-TO-SPEC-GATE, ... " in step order for gates that are on and not
    # overridden; gates that are off are listed with "(off)" so agents still see the standard;
    # "none" when no gate exists at all (JC-15).
def render(template: str, ctx: Context, roots: Roots, cfg: Config, *, depth: int = 0) -> Rendered
    # Expands prose.* recursively (max depth 8; deeper is a cycle -> RenderError listing the chain).
def render_prose(name: str, ctx: Context, roots: Roots, cfg: Config) -> Rendered
def strict(rendered: Rendered) -> str          # returns text; raises RenderError naming every unresolved token
def synthetic_round_view() -> RoundView         # "0000", placeholder plan text; used by doctor only
```

---

## plumbing.py — the mechanical instructions

**Owns:** the text of `{{ plumbing.PROCESS-INSTRUCTIONS }}` for every (step, role) and of
`{{ plumbing.GATE-PROSE }}`; the final-message JSON contracts *as shown to agents* (the
schemas themselves live in `results.py`, file 05, and are imported so the two cannot drift).
**Depends on:** `paths`, `config`, `steps`, `results` (schemas + examples), `render`
(only for GATE-PROSE). **Depended on by:** `round`, `doctor`.

Everything here is mechanical: paths, commands, lists, the JSON contract. It contains no
judgment language of its own; the sentence "These steps never require judgment calls" is
a requirement on this module.

```python
Role = Literal["producer", "gate", "driver-plan", "driver-checkpoint", "driver-pause", "landing-conflict"]

@dataclass(frozen=True)
class AttemptFacts:          # everything the instructions need, supplied by round.py
    step: Step; role: Role; attempt: str                 # e.g. "PLAN-TO-SPEC-2"
    round_id: str; round_folder_abs: Path; worktree_abs: Path
    runner_cmd: str                                      # absolute "python3 /.../src/run.py" of the *control* checkout
    declared_paths: tuple[str, ...]                      # concrete harness-relative paths/prefixes
    spec_files: tuple[str, ...]                          # never-touch list, repo-relative
    inputs: tuple[str, ...]                              # files to read, worktree-relative
    artifacts: tuple[str, ...]                           # files to write, worktree-relative
    budget_usd: float | None                             # None = "no specific budget"
    max_helpers: int; helper_rung_ceiling: str
    open_findings: tuple[FindingView, ...]               # from findings.py (file 05)
    owner_answers: tuple[tuple[str, str], ...]           # (question text, verbatim answer quote)
    prior_summary: str | None                            # previous attempt's summary, if a retry
    verify_cmd: str | None; verify_timeout_s: int
    conflicted_files: tuple[str, ...]                    # landing-conflict only
    gate_on: bool; gate_overridden: bool

def process_instructions(f: AttemptFacts) -> str
    # Numbered mechanical list. Sections in order: WHERE (worktree, round folder), MAY EDIT,
    # NEVER EDIT (spec files, frozen tests when applicable), READ (inputs), WRITE (artifacts),
    # PRIOR FINDINGS (each id, state, text, suggestion; "respond to every one in `responses`"),
    # OWNER ANSWERS, HELPERS (max count, ceiling rung, agent-definition names), BUDGET,
    # JUDGMENT CALLS (exact command: `<runner_cmd> judgment --worktree <abs> --kind defined|undefined --text "..."`;
    # gates: "list them in your final message instead"), VERIFY (command + timeout, when applicable),
    # FINAL MESSAGE (schema + one example from results.py), then the rendered COMMON-STEP-END text.
def gate_prose(step: Step, ctx: Context, roots: Roots, cfg: Config, *, on: bool, overridden: bool) -> Rendered
    # The step's gate prose rendered with plumbing.PROCESS-INSTRUCTIONS replaced by a one-line
    # placeholder "(gate process instructions omitted here)" to avoid recursion; prefixed with
    # "This gate is off this round; the standard still applies." when not on or overridden.
def driver_instructions(f: AttemptFacts) -> str
    # For driver roles: the owner-word kinds the runner accepts and their exact CLI forms
    # (from control.py KINDS), what to present (flags, judgment-call files, summary source files),
    # "one numbered list of questions per turn", and where to write PLAN.json / result JSON.
def step_end_text(roots: Roots, ctx: Context, cfg: Config) -> Rendered   # COMMON-STEP-END rendered
```

The prompt handed to an agent is: rendered overview (or gate) prose, whose
`{{ plumbing.* }}` tokens were filled by this module. When a step has no overview prose
(LANDING conflict), the prompt is `COMMON-PROJECT` + `COMMON-ROUND` + `COMMON-OVERVIEW` +
process instructions (JC-12).

---

## agentdefs.py — generated agent definitions

**Owns:** writing `.claude/agents/shackles-<rung>.md` and `shackles-<rung>-readonly.md` from
`subAgents.yaml`, and checking they are current. **Depends on:** `paths`, `config`.
**Depended on by:** `doctor`, `round.start` (refuses when stale), the `agents` CLI command,
the SessionStart hook.

File format (YAML front matter + one-line body):

```
---
name: shackles-max
description: shackles harness agent, rung max (Fable 5.1 Max). Runs the prompt it is given verbatim.
model: claude-fable-5-1
effort: max
tools: Read, Edit, Write, Grep, Glob, Bash, Agent        # read-only twin: Read, Grep, Glob
---
Follow the prompt you are given exactly. It names your step, inputs, outputs and the JSON your final message must be.
```

```python
class AgentDefsError(HarnessError): ...
def agents_dir(roots: Roots) -> Path                            # REPO_ROOT/.claude/agents
def definition_name(rung: str, *, readonly: bool) -> str        # "shackles-max", "shackles-max-readonly"
def expected(cfg: Config) -> dict[str, str]                     # file name -> exact content
def write(roots: Roots, cfg: Config) -> list[Path]              # writes all; removes stale shackles-* files
def stale(roots: Roots, cfg: Config) -> list[str]               # names whose content differs or is missing
```

The `effort` front-matter key is included because the owner states the Agent tool takes
effort from the loaded definition (JC-13).

---

## doctor.py — offline health report

**Owns:** rendering every prompt offline with a synthetic round, and every static check
the harness can make without git pushes or agents; the `INDEX.md` generator. **Depends
on:** everything above plus `steps`, `speclock`, `agentdefs`, `localyaml`, `gitops`
(read-only queries), `ownerlog` (presence check). **Depended on by:** the CLI, CI, the
SessionStart hook (subset).

```python
Severity = Literal["error", "warning", "note"]

@dataclass(frozen=True)
class Check:
    id: str; severity: Severity; message: str; detail: str = ""

@dataclass(frozen=True)
class Report:
    checks: tuple[Check, ...]
    rendered: dict[str, Rendered]      # "<STEP>/<role>" -> Rendered (for --show)
    def errors(self) -> tuple[Check, ...]
    def to_json(self) -> dict
    def to_text(self) -> str

def run(roots: Roots, *, offline: bool = False) -> Report
def index_text(roots: Roots) -> str        # INDEX.md content: one line per file under src/, docs/, tests/ and root
def write_index(roots: Roots) -> Path
```

Checks performed (id → what, severity):
- `config.load` — config loads; each problem is an error.
- `config.defaulted` — each defaulted key: note naming key and value.
- `config.unknown` — each unknown key: warning ("not used by the runner").
- `steps.lint` — from `steps.lint`: errors.
- `prose.unknown` — prose files that match no step and no COMMON prefix: warning.
- `prose.missing` — a step whose gate is on (or whose overview is required) lacks its file: error.
- `render.<STEP>/<role>` — every step × applicable role rendered with the synthetic round: each unresolved token is an error naming file, token and position; each cycle an error.
- `render.size` — rendered prompt above `promptWarnTokens`: warning with the number.
- `agentsmd.sections` — every `agents.*` token in any prose file resolves: error otherwise.
- `agentdefs.stale` — generated definitions differ from `subAgents.yaml`: error ("run agents, restart the session").
- `speclock.status` — `drift` (error, with per-file summary) or `missing` (error) or clean (note).
- `hooks.settings` — `.claude/settings.json` has both hook commands: error.
- `hooks.ownerlog` — `OWNER.log` exists and its last line parses: warning when absent ("start will refuse").
- `git.remote` — remote configured and `mainBranch` exists on it (skipped when `--offline`): error.
- `git.clean` — control checkout has no changes under spec files: warning.
- `index.current` — `INDEX.md` equals `index_text()`: warning.
- `roster.selectable` — `defaultAgent`, `gateAgent`, `systemTestAgent` are at or below `maxAgent`: error.

Exit status of the CLI command is 1 when any error exists, else 0.

INDEX.md line format: `<harness-relative path> — <purpose>`, purpose taken from the first
line of a module docstring, the first heading of a Markdown file, or the fixed purpose
string for root files (a small table in this module). Sorted by path.
