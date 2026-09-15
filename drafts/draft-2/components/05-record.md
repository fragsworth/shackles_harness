# 05 — Recording an attempt: results, findings, verification, suite selection

Parent: [`../SPEC.md`](../SPEC.md). Four modules under `harness/src/`. `record` is where
an agent's work becomes part of the round: its final message is parsed, its claims are
checked mechanically, the gate's findings are reconciled, and tests are run. These modules
do the checking; `round.py` (file 07) sequences them and commits.

---

## results.py — the final-message contract

**Owns:** the JSON schemas for producer, gate and driver final messages; extracting JSON
from an agent's message text; validation; the examples that `plumbing` shows agents.
**Depends on:** `paths`. **Depended on by:** `round`, `plumbing`, `findings`, `suite`,
`tests/stub_agent.py`.

Producer result (also used for the driver's own CHAT-TO-PLAN and for landing-conflict):

```json
{"status": "DONE | NEEDS-OWNER | BLOCKED",
 "summary": "one paragraph",
 "artifacts": ["archives/rounds/0007/SPEC.json"],
 "responses": [{"finding": "F1", "action": "resolved | disputed", "text": "what changed / why disputed"}],
 "questions": [{"n": 1, "text": "...", "options": {"a": "...", "b": "..."}}],
 "narrow": "what to narrow (BLOCKED only)",
 "flags": ["for the owner at the next pause"],
 "judgment_calls": [{"kind": "defined | undefined", "text": "one line"}],
 "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}}
```

Gate result:

```json
{"verdict": "PASS | FAIL",
 "summary": "one paragraph",
 "rulings": [{"finding": "F1", "ruling": "upheld | withdrawn", "quote": "the text the ruling rests on"}],
 "findings": [{"id": "G1", "blocking": true, "quote": "the artifact text judged", "text": "the problem", "suggestion": "what would prevent the FAIL"}],
 "flags": [], "judgment_calls": []}
```

Rules enforced by `validate_*` (each returns a list of problems; empty = valid):
- `status`/`verdict` must be one of the literals, exactly (uppercase).
- NEEDS-OWNER requires ≥ 1 question with non-empty text; options are optional but, when
  present, keys are single lowercase letters (JC-25). BLOCKED requires `narrow`.
- `responses` must name only open findings (ids from `findings.py`) and every open
  *blocking* finding must have a response; a `disputed` response on a settled finding is a
  problem ("settled: upheld twice").
- Gate: every disputed finding must have a ruling; each finding needs non-empty `quote`,
  `text`, `suggestion`; ids unique within the message.
- Unknown keys are ignored (agents may add commentary fields); missing optional lists are
  empty.

```python
class ResultError(HarnessError): ...

@dataclass(frozen=True) class Question: n: int; text: str; options: dict[str, str]
@dataclass(frozen=True) class Response: finding: str; action: str; text: str
@dataclass(frozen=True) class JudgmentCall: kind: str; text: str
@dataclass(frozen=True) class Usage: input_tokens: int; output_tokens: int; cache_read_tokens: int; cache_write_tokens: int
@dataclass(frozen=True) class ProducerResult: status: str; summary: str; artifacts: tuple[str, ...]; responses: tuple[Response, ...]; questions: tuple[Question, ...]; narrow: str; flags: tuple[str, ...]; judgment_calls: tuple[JudgmentCall, ...]; usage: Usage | None; raw: dict
@dataclass(frozen=True) class RawFinding: id: str; blocking: bool; quote: str; text: str; suggestion: str
@dataclass(frozen=True) class Ruling: finding: str; ruling: str; quote: str
@dataclass(frozen=True) class GateResult: verdict: str; summary: str; rulings: tuple[Ruling, ...]; findings: tuple[RawFinding, ...]; flags: tuple[str, ...]; judgment_calls: tuple[JudgmentCall, ...]; usage: Usage | None; raw: dict

def extract_json(text: str) -> dict
    # The last fenced ```json block that parses as an object; else the last balanced top-level
    # {...} that parses; else ResultError("no JSON object in message") (JC-26).
def read_result_file(path: Path) -> dict            # file may hold the raw message or pure JSON
def parse_producer(d: dict) -> ProducerResult       # shape only; raises ResultError with all shape problems
def parse_gate(d: dict) -> GateResult
def validate_producer(r: ProducerResult, open_findings: Iterable[Finding]) -> list[str]
def validate_gate(r: GateResult, disputed: Iterable[Finding]) -> list[str]
def example_producer(step: str) -> str              # pretty JSON shown in process instructions
def example_gate(step: str) -> str
def schema_text(role: str) -> str                   # human-readable field list for the prompt
```

---

## findings.py — the life of a gate finding

**Owns:** the finding record kept in `STATE.json`, id assignment, reconciliation of a new
gate result against prior findings, the verdict-wins rule, repeat-of-withdrawn dropping,
and the flags that flow to the owner. **Depends on:** `results`, `state`. **Depended on
by:** `round`, `plumbing` (FindingView), `results` (open ids).

States and transitions:

```
open ──(producer: resolved)──> resolved      (closed when the next gate does not re-raise it; re-raised = open again, same id)
open ──(producer: disputed)──> disputed ──(gate: withdrawn)──> withdrawn
                                        └─(gate: upheld)────> open (upheld_count += 1); upheld_count == 2 -> settled (still open, no more disputes)
open, non-blocking, on a PASS ──────────> flagged  (becomes an owner flag; the gate did not block on it)
new finding whose quote equals a withdrawn one's quote ──> dropped (recorded with a note; never shown as open)
```

```python
@dataclass
class Finding:
    id: str                 # "F3", unique within the step across gate attempts
    step: str; raised_in: str          # gate attempt name
    blocking: bool; quote: str; text: str; suggestion: str
    state: Literal["open", "resolved", "disputed", "withdrawn", "settled", "flagged", "dropped"]
    upheld_count: int = 0
    history: list[str]      # "<attempt>: <event>" lines

@dataclass(frozen=True)
class FindingView:          # what plumbing renders for the next agent
    id: str; state: str; blocking: bool; quote: str; text: str; suggestion: str; needs_response: bool

def open_findings(state: State, step: str) -> list[Finding]         # state in (open, disputed, settled)
def apply_responses(state: State, step: str, attempt: str, responses: Iterable[Response]) -> list[str]
    # Marks resolved/disputed; returns problems (unknown id, dispute on settled) — round.py refuses on any.
def reconcile(state: State, step: str, gate_attempt: str, result: GateResult) -> tuple[list[Finding], list[str]]
    # 1. Apply rulings to disputed findings (withdrawn / upheld; second uphold -> settled).
    # 2. For each new RawFinding: assign the next id; if its normalised quote equals a withdrawn
    #    finding's quote -> state dropped + note; else open.
    # 3. Verdict wins: PASS -> every open finding of this gate attempt becomes flagged (blocking
    #    forced False, note "non-blocking by verdict"); FAIL with zero blocking findings ->
    #    all of this attempt's open findings become blocking (note "blocking by verdict") (JC-27).
    # 4. Findings marked resolved that the gate did not re-raise are closed (state stays resolved).
    # Returns (findings as they now stand for the step, notes for HISTORY).
def views(state: State, step: str) -> list[FindingView]
def flags_from(findings: Iterable[Finding]) -> list[str]           # "F3 (PLAN-TO-SPEC, non-blocking): text — suggestion"
def normalise_quote(q: str) -> str                                  # collapse whitespace, strip, casefold
def to_findings_file(gate_attempt: str, result: GateResult, findings: Iterable[Finding], notes: Iterable[str]) -> dict
    # the FINDINGS/<STEP>-<n>.json content: verdict, rulings, findings with final states, notes
```

---

## verify.py — mechanical checks at record

**Owns:** running the test suite (or a collect-only pass) in a worktree with a timeout,
the artifact-presence and artifact-schema checks, the "no conflict markers" check, and
composing all of them into one `Verdict` for a step. **Depends on:** `paths`, `config`,
`steps`, `gitops` (none), `schemas` (file 08 JSON schema checks via `results`/`suite`
loaders). **Depended on by:** `round`, `landing`, the `verify` CLI command.

```python
class VerifyError(HarnessError): ...

@dataclass(frozen=True)
class TestRun:
    mode: Literal["collect", "suite"]; ok: bool; timed_out: bool
    exit_code: int | None; tail: str        # last 60 lines of output
    seconds: float; counts: dict[str, int]  # passed/failed/errors/skipped when parsable

@dataclass(frozen=True)
class Verdict:
    ok: bool
    problems: tuple[str, ...]               # each is a reason the record is refused
    test_run: TestRun | None

def test_command(cfg: Config, mode: str) -> list[str]
    # ["python3", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not live", *cfg.test_paths] (+ "--collect-only" for collect)
def run_tests(worktree: Path, cfg: Config, mode: str) -> TestRun      # subprocess with timeout = verifyTimeoutSeconds
def artifacts_present(worktree: Path, round_folder: str, cfg: Config, step: Step) -> list[str]
def artifacts_parse(worktree: Path, round_folder: str, cfg: Config, step: Step) -> list[str]
    # PLAN.json / AGENTS-PLAN.json / SPEC.json / SUITE.json validated by their loaders (file 08);
    # POSTMORTEM.md must start with a "## Summary" (first heading) section.
def load_spec_json(path: Path) -> dict                   # 8.5 shape check; raises VerifyError listing problems
def load_postmortem(path: Path) -> str                   # returns the text; VerifyError unless the first heading is "## Summary"
def no_markers(worktree: Path, paths: Iterable[str]) -> list[str]
def for_step(worktree: Path, cfg: Config, step: Step, round_folder: str, *, status: str) -> Verdict
    # DONE: presence + parse + tests per step.verify. NEEDS-OWNER/BLOCKED: parse only for artifacts
    # that exist (partial work is kept), no tests.
```

A timed-out or failing suite on a DONE result is a refusal, not a stray: the attempt
keeps its edits in the worktree, the record is refused with the tail, and the driver
re-runs the attempt (same name, `refused += 1`).

---

## suite.py — TESTS-TO-SUITE mechanics

**Owns:** enumerating this round's new test functions, loading `SUITE.json`, moving
archived tests into the round's `tests-archive/` by AST span, and the post-move checks.
**Depends on:** `paths`, `config`, `gitops` (base tree), `tokens` (none). **Depended on
by:** `round` (at record of TESTS-TO-SUITE), `ledger` (test counting helper), `plumbing`
(lists the round's tests for the producer).

```python
class SuiteError(HarnessError): ...

@dataclass(frozen=True)
class TestFn:
    file: str            # harness-relative
    name: str            # function name; methods as "Class.test_x"
    lineno: int; end_lineno: int; decorators_start: int

def test_functions(root: Path, test_paths: Iterable[str]) -> list[TestFn]
    # ast walk of every *.py whose name starts with test_ or ends with _test.py; functions and
    # methods named test*; sorted by (file, lineno).
def test_names_at(repo: Path, rev: str, prefix: Path, test_paths: Iterable[str]) -> set[tuple[str, str]]   # (file, name) at a commit
def new_this_round(repo: Path, base_commit: str, worktree: Path, prefix: Path, cfg: Config) -> list[TestFn]
    # names present in the worktree but absent at base_commit (by (file, name)); a moved test is not new.
@dataclass(frozen=True)
class Decision: file: str; name: str; decision: Literal["suite", "archive"]; reason: str
def load_suite_json(path: Path) -> tuple[list[Decision], list[str]]      # (decisions, flags); raises SuiteError on shape
def check_decisions(decisions: Iterable[Decision], new_tests: Iterable[TestFn]) -> list[str]
    # every new test has exactly one decision; no decision names an unknown test.
def archive(worktree: Path, round_folder: Path, tests_archive_rel: str, decisions: Iterable[Decision]) -> list[str]
    # For each archive decision: cut the function's source (decorators included) from its file,
    # append to tests-archive/<same relative file path>; if the source file then has no test
    # functions and did not exist at base -> delete it. Returns moved "file::name" list (JC-28).
```
