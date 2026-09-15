# 03 — The owner's words, control decisions, round state, history, attempts, limits

Parent: [`../SPEC.md`](../SPEC.md). Six modules under `harness/src/`. These hold what the
runner *knows*: what the owner said (verbatim), what the owner decided (as data the driver
classified), where the round is, what happened, and whether a limit has been hit. None of
them spawns anything or touches git; `state.py` writes one JSON file and nothing else.

---

## ownerlog.py — the owner's words, verbatim

**Owns:** the hook writer for `harness/OWNER.log`; slicing the log into a round's own
`OWNER.log`; verifying that a quote is a verbatim substring of an owner entry.
**Depends on:** `paths`. **Depended on by:** `control` (verification), `round` (slice
refresh), `doctor` (presence), the `hook` CLI command.

Log format: one JSON object per line: `{"ts": "<ISO-8601 UTC>", "session": "<id or ''>",
"text": "<the prompt exactly>"}`. Nothing is ever rewritten; the file only grows.

```python
class OwnerLogError(HarnessError): ...

@dataclass(frozen=True)
class Entry:
    line_no: int; ts: str; session: str; text: str

def root_log(roots: Roots) -> Path                      # HARNESS_ROOT/OWNER.log
def append_from_hook(roots: Roots, hook_json: str) -> Entry
    # Parses the UserPromptSubmit payload (keys used: "prompt", "session_id"; unknown shapes
    # are stored with text = the whole payload so nothing is lost); appends; returns the entry.
def read(path: Path) -> list[Entry]                     # tolerant: a malformed line becomes an Entry with text = raw line
def exists_and_nonempty(roots: Roots) -> bool
def slice_since(roots: Roots, first_line_no: int) -> list[Entry]
def refresh_round_slice(roots: Roots, round_log: Path, first_line_no: int) -> int
    # Copies every root entry from first_line_no on that is not yet in round_log (by line_no),
    # appending; returns the number added. Never removes.
def starting_line(roots: Roots) -> int
    # The line number of the last entry in the root log at the moment `start` runs: the round's
    # slice begins with the message that triggered the round (JC-16); 1 if the log is empty
    # (start refuses in that case anyway).
def verify_quote(entries: Iterable[Entry], quote: str) -> Entry | None
    # The most recent entry whose text contains `quote` verbatim after normalising only line
    # endings and trailing whitespace; None if no entry does. No other normalisation (JC-17).
```

---

## control.py — owner decisions as data

**Owns:** the closed vocabulary of things the owner can decide, how each is validated,
and how a decision is recorded. The runner never interprets prose: the *driver* classifies
the owner's words into a kind, hands the verbatim quote along, and this module only checks
the quote exists in the log and the kind's parameters are well-formed.
**Depends on:** `paths`, `steps`, `ownerlog`. **Depended on by:** `round`, `plumbing`
(to list the kinds in driver instructions), the `owner` CLI command.

```python
class ControlError(HarnessError): ...

Kind = Literal["approve", "delegate", "delegate-through", "override", "answer",
               "abandon", "hard-stop-multiple", "note", "accept-spec"]

KINDS: dict[Kind, str]      # kind -> one-line meaning + exact CLI form, rendered into driver instructions

@dataclass(frozen=True)
class Decision:
    kind: Kind
    quote: str                          # verbatim owner words the driver handed over
    log_line: int                       # the OWNER.log entry the quote was found in
    ts: str
    through_step: str | None = None     # delegate-through
    skip_steps: tuple[str, ...] = ()    # override
    skip_gates: tuple[str, ...] = ()    # override (gate names, e.g. "PLAN-TO-SPEC-GATE")
    question: int | None = None         # answer: the question number
    value: float | None = None          # hard-stop-multiple
    reason: str | None = None           # abandon (free text, taken from the quote by the driver)

def validate(kind: Kind, *, through_step: str | None, skip_steps: Iterable[str],
             skip_gates: Iterable[str], question: int | None, value: float | None) -> list[str]
    # Structural checks only: known step/gate names; CHAT-TO-PLAN and LANDING never skippable;
    # a non-overridable step named -> error; value > 0; question >= 1. Returns problems.
def make(kind: Kind, quote: str, entries: Iterable[Entry], **params) -> Decision
    # Runs validate; verifies the quote with ownerlog.verify_quote; raises ControlError
    # ("quote not found in OWNER.log" or the validation problems).
def approval_mode(decisions: Iterable[Decision]) -> tuple[str, str | None]
    # ("none" | "approve" | "delegate", through_step) from the latest approve/delegate decision.
def effective_overrides(decisions: Iterable[Decision]) -> tuple[set[str], set[str]]   # (steps, gates), union
def hard_stop_multiple(decisions: Iterable[Decision], default: float) -> float         # latest override or default
```

---

## state.py — STATE.json, the runner's only state

**Owns:** the schema of `STATE.json`, loading/saving it atomically, and the small
transition helpers that keep it consistent. Every other module receives a `State` value
and returns changes; only `round.py` calls `save`. **Depends on:** `paths`, `config`
(for round paths). **Depended on by:** `round`, `limits`, `ledger`, `findings`,
`attempts`, `localyaml`, `history`.

Schema (JSON, keys in this order; full example in file 08):

```
schema: 1
round: {id, folder, branch, worktree, base_commit, started_at, phase, pushed_sha}   # pushed_sha: last remote tip this runner pushed (the lease for the next fence)
   phase: "planning" | "active" | "paused" | "landing" | "post-landing" | "complete" | "abandoned"
pause: {reason, since, detail} | null
   reason: "checkpoint" | "approval" | "questions" | "blocked" | "limit" | "drift" | "conflict" | "sync-conflict" | "hard-stop"
owner: {decisions: [Decision...], log_first_line, mode, through_step, skip_steps, skip_gates, hard_stop_multiple}
steps: {STEP: {status, producer_attempts, gate_attempts, gate_rejections, accepted_attempt, note}}
   status: "pending" | "active" | "accepted" | "skipped" | "failed"
open_attempt: {name, step, role, agent_definition, rung, started_at, budget_usd, prompt_file, result_file, prompt_tokens} | null
attempts: [ {name, step, role, rung, started_at, recorded_at, status, usd, measured, refused: int, summary} ... ]
findings: {STEP: [Finding...]}            # see file 05; kept per step
questions: [ {n, attempt, text, options, answer_quote|null} ]
flags: [ {text, attempt, shown: bool} ]
counters: {turns, restarts, active_seconds}
landing: {main_before, merge_commit, conflicted_files, landed_at} | null
bill: {...} | null                         # see file 06; filled at cleanup or abandon
```

```python
class StateError(HarnessError): ...

@dataclass
class State:                                 # mutable in memory; mirrors the schema one-to-one
    ...                                      # fields as above, plain dataclasses for nested records
    def step(self, name: str) -> StepState
    def next_pending(self) -> str | None     # first step whose status is pending, in table order
    def is_paused(self) -> bool

def path_for(roots: Roots, cfg: Config, round_id: str) -> Path       # <worktree or root>/<roundPaths.folder>/STATE.json
def new(cfg: Config, round_id: str, branch: str, worktree: str, base_commit: str, log_first_line: int) -> State
def load(path: Path) -> State                # raises StateError on schema mismatch (with the found version)
def save(state: State, path: Path) -> None   # write temp + rename; JSON with indent 1, sorted nested keys off (order as schema)
def pause(state: State, reason: str, detail: str = "") -> None
def resume(state: State) -> None             # clears pause; increments counters.restarts when the reason was blocked/limit/hard-stop (JC-18)
def find_round_folders(roots: Roots, cfg: Config) -> list[Path]   # every archives/rounds/NNNN on disk
```

---

## history.py — HISTORY.md, append-only

**Owns:** the format of one history entry and appending it. **Depends on:** `paths`.
**Depended on by:** `round`, `landing`, `sync`, `ledger` (bill entry).

Entry format:

```
## <ISO ts>  <attempt or event>  <status>  $<usd>
<one-line summary>
- verdict: PASS/FAIL (n findings, m blocking)          (gate records only)
- reverted strays: <paths>                              (when any)
- note: <free text from the runner>                     (zero or more)
```

```python
def append(history_path: Path, *, title: str, status: str, usd: float | None,
           summary: str, notes: Iterable[str] = ()) -> None
def event(history_path: Path, name: str, detail: str) -> None     # owner decisions, pauses, landing, sync
```

---

## attempts.py — naming and files of an attempt

**Owns:** attempt names and the three files each one has. **Depends on:** `paths`,
`config`, `state`. **Depended on by:** `round`, `plumbing`, `findings`.

Names: producer `<STEP>-<n>`; gate `<STEP>-GATE-<n>` where `n` is the producer attempt it
judges (a re-run of the same gate after a refused record reuses the name and bumps
`refused`); landing conflict `LANDING-<n>`; driver-performed `CHAT-TO-PLAN-<n>`.

```python
@dataclass(frozen=True)
class Files:
    prompt: Path; end_prompt: Path; result: Path; findings: Path | None    # findings only for gates: FINDINGS/<STEP>-<n>.json

def next_producer_name(state: State, step: str) -> str
def gate_name_for(producer_attempt: str) -> str          # "PLAN-TO-SPEC-2" -> "PLAN-TO-SPEC-GATE-2"
def producer_of(gate_attempt: str) -> str
def files_for(round_folder: Path, cfg: Config, attempt: str, role: str) -> Files
def is_gate(attempt: str) -> bool
```

---

## limits.py — every bound in one place

**Owns:** deciding whether a bound has been reached and naming which. Pure functions over
`State` + `Config`; no side effects. **Depends on:** `config`, `state`. **Depended on
by:** `round` (before `next`, after `record`), `landing` (hard stop before landing).

```python
@dataclass(frozen=True)
class Hit:
    kind: Literal["gate-turns", "run-turns", "wall-clock", "restarts", "hard-stop-round", "hard-stop-attempt"]
    detail: str          # "PLAN-TO-SPEC: 3 rejections (max 3)"

def gate_turns(state: State, cfg: Config, step: str) -> Hit | None     # rejections > maxTurnsPerGate is impossible; == max -> Hit
def run_turns(state: State, cfg: Config) -> Hit | None                 # counters.turns >= maxTurnsPerRun
def wall_clock(state: State, cfg: Config, now: datetime) -> Hit | None # active seconds (paused time excluded, JC-19) > hours*3600
def restarts(state: State, cfg: Config) -> Hit | None                  # counters.restarts > maxRoundAttempts
def hard_stop_round(spend: float, projected_living: float, quote: float, multiple: float) -> Hit | None
def hard_stop_attempt(attempt_usd: float, budget_usd: float | None, multiple: float) -> Hit | None   # None when no budget
def check_before_next(state: State, cfg: Config, now: datetime) -> Hit | None    # run-turns, wall-clock, restarts, in that order
```

A `Hit` always pauses the round with reason `limit` (or `hard-stop`), never ends it; the
owner may resume (counted as a restart), abandon, or raise a multiple.
