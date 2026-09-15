# 07 — The round engine and the command line

Parent: [`../SPEC.md`](../SPEC.md). Two modules under `harness/src/`. `round.py` is the
sequencer: it owns the order in which the other modules are called for `start`, `next`,
`record`, `owner`, `resume`, `abandon`. `run.py` is the dispatcher the driver and the hooks
invoke; it owns argument parsing, exit codes and output shape, nothing else.

---

## round.py — the sequencer

**Owns:** the round lifecycle. **Depends on:** every module in files 01–06.
**Depended on by:** `run.py` only. It is deliberately the *only* module that calls
`state.save`, `gitops.commit` for round commits, and `push_cas`.

Fence rule: every public function below that changes `State` ends with
`save → add_all(round folder) → commit → push_cas(round branch, expected = last known
remote sha)`; a `PushRejected` marks nothing and raises `LockLost` (exit 4). The last known
remote sha is kept in `State.round.pushed_sha`.

```python
class RoundError(HarnessError): ...
class LockLost(RoundError): ...       # code 4
class Refused(RoundError): ...        # code 2 (start/owner) or 3 (record); .reasons: list[str]

@dataclass(frozen=True)
class Next:                           # what `next` tells the driver; serialised as JSON
    action: Literal["spawn", "self", "chat", "done"]
    attempt: str | None; step: str | None; role: str | None
    agent_definition: str | None; rung: str | None; read_only: bool
    cwd: str | None; prompt_file: str | None; end_prompt_file: str | None; result_file: str | None
    budget_usd: float | None; max_helpers: int
    reason: str | None                # chat: checkpoint | approval | questions | blocked | limit | hard-stop | conflict | sync-conflict | drift | round-end
    warnings: tuple[str, ...]         # e.g. prompt size
    flags: tuple[str, ...]; questions: tuple[dict, ...]; bill: dict | None; postmortem_summary: str | None

def start(roots: Roots, cfg: Config, *, now: datetime) -> State
    # Refuses (exit 2) when any holds, listing all: speclock drift/missing; steps.lint errors; config.unknown;
    # agentdefs.stale; no OWNER.log entries; no remote or mainBranch missing on it; another round is
    # not complete/abandoned in .worktrees; doctor.run(offline=True) has errors.
    # Then: fetch; round_id = 1 + max(ids in archives/rounds on remote main ∪ remote round/* branches);
    # branch round/NNNN at remote main; worktree.create; State.new (log_first_line = ownerlog.starting_line);
    # write round folder skeleton (STATE.json, HISTORY.md, empty PROMPTS/ RESULTS/ FINDINGS/ tests-archive/
    # with .gitkeep, empty judgment-call files with a one-line header, OWNER.log slice);
    # commit; push_cas(expected=None) — the claim; on PushRejected: remove worktree and branch, retry with
    # id+1 once, then LockLost. localyaml.write. Returns the state.

def next(roots: Roots, cfg: Config, *, now: datetime) -> Next
    # 0. Load state; ownerlog.refresh_round_slice; if paused -> Next(chat, reason=pause.reason ...) (no state change
    #    except the flags shown are marked shown when the chat prompt is produced).
    # 1. limits.check_before_next -> pause(limit) and return chat.
    # 2. If open_attempt exists -> return the same spawn/self (idempotent; the driver may have crashed).
    # 3. step = state.next_pending(); if None -> finish() and return done.
    # 4. Skipped by override -> mark skipped, HISTORY, loop to 3.
    # 5. kind checkpoint: if approval mode is delegate and (through_step is None or index(step) <= index(through_step))
    #    -> mark skipped ("delegated"), loop; else pause(checkpoint) and return chat with the rendered CHECKPOINT prose.
    # 6. kind runner (LANDING): landing.begin; clean -> finish landing, mark accepted, loop; conflict -> open attempt LANDING-n.
    # 7. kind producer: if the step's last producer attempt is accepted by its gate (or gate off/overridden) -> mark accepted,
    #    book_driver_step, loop. If a producer attempt is DONE and awaits a gate -> open the gate attempt. Else open a
    #    producer attempt: render prompt (render.strict; unresolved -> Refused), write PROMPTS files, set open_attempt,
    #    counters.turns += 1, save, commit, push (fence), return spawn (or self for driver-performed steps).
    # CHAT-TO-PLAN acceptance additionally requires an approve/delegate decision *after* its last DONE record
    # and (if gated) after the PASS; until then `next` returns chat with reason approval (JC-34).

def record(roots: Roots, cfg: Config, attempt: str, *, usage: Usage | None, now: datetime) -> dict
    # Refuses (exit 3, reasons listed, attempt kept open, refused += 1, cost booked; JC-36) when: attempt != open_attempt;
    # result file missing or no JSON; shape problems; validate_* problems; worktree.triage refusals; verify problems.
    # Producer path: triage + revert strays (noted) -> apply_responses -> verify.for_step -> append result's
    # judgment_calls to the round files (gate results too) -> ledger.book_attempt -> commit worktree changes
    # (declared paths + round folder) -> update step counters -> status DONE: if gate applies, next gate attempt
    # pending; else step accepted. NEEDS-OWNER: questions appended (numbered from the round's count), pause(questions).
    # BLOCKED: pause(blocked). flags appended. limits.hard_stop_attempt -> pause(hard-stop).
    # Special producer steps at DONE: TESTS-TO-SUITE -> suite.check_decisions + suite.archive + verify suite again;
    # CLEANUP -> finish(); LANDING-n -> landing.judge_resolution then landing.finish.
    # Gate path: findings.reconcile -> write FINDINGS file -> PASS: step accepted (flags from non-blocking) ;
    # FAIL: gate_rejections += 1; limits.gate_turns -> pause(limit) else the next producer attempt is pending.
    # Always: HISTORY entry, save, commit, push (fence). Returns {"accepted": bool, "reasons": [...], "next_hint": str}.

def owner(roots: Roots, cfg: Config, kind: Kind, quote: str, **params) -> State
    # control.make (verifies the quote in the refreshed round slice) -> append decision -> effects:
    # approve/delegate/delegate-through: set mode; if paused for approval/checkpoint -> resume.
    # answer: attach quote to question n (unknown n -> Refused); when every open question has an answer and paused
    # for questions -> resume (the step's next attempt is pending with answers in its prompt).
    # override: extend skip sets (validated); abandon: abandon(); hard-stop-multiple: set; if paused for hard-stop -> resume.
    # note: HISTORY only. accept-spec: speclock.accept (allowed while no round is active only).
    # Every effect: HISTORY event, save, commit, push (fence).

def resume(roots: Roots, cfg: Config, *, force_restart: bool = False) -> State
    # Clears a pause of kind blocked/limit/hard-stop/conflict/sync-conflict after the owner intervened by hand;
    # counts a restart (limits.restarts -> pause again unless force_restart). Checkpoint/approval/questions
    # pauses resume through `owner` instead and refuse here.

def abandon(roots: Roots, cfg: Config, reason: str) -> dict
    # phase abandoned; bill = attempts + driver + archive charges (no living charge); sync only the round folder
    # to main (sync.sync_to_main(only_prefixes=[round folder])); worktree removed; branch kept on the remote.

def finish(roots: Roots, cfg: Config, state: State) -> dict
    # After CLEANUP is recorded: living = ledger.living_charge(main_before, tip); archive = ledger.archive_charges;
    # bill = make_bill; phase complete; save; commit; push; sync.sync_to_main; sync.update_control_checkout;
    # worktree.remove; localyaml.write; returns the bill (JC-35).

def judgment(roots: Roots, cfg: Config, worktree: Path, kind: str, text: str) -> Path
    # Appends "- [<open attempt>] <text>" to the defined/undefined file in the worktree's round folder; no commit
    # (the producer's record commits it). Refuses when no attempt is open.
def status(roots: Roots, cfg: Config) -> dict
```

---

## run.py — the command line

**Owns:** subcommands, argument parsing, exit codes, stdout shape, `sys.path` setup.
**Depends on:** `round`, `doctor`, `agentdefs`, `speclock`, `ownerlog`, `verify`,
`ledger`, `localyaml`. **Depended on by:** the driver (by hand), hooks, CI, tests.

Every command accepts `--json` (default on for `next`, `record`, `status`, `owner`,
`judgment`), `--harness <path>` (override root discovery) and `--now <ISO>` (tests).
Exit codes: 0 ok · 1 usage/config/internal error · 2 refused to start or act · 3 record
refused · 4 lock lost (someone else moved the round branch).

| Command | Arguments | Does |
|---|---|---|
| `doctor` | `[--offline] [--show STEP/ROLE] [--write-index]` | `doctor.run`; prints report; exit 1 on errors |
| `agents` | | `agentdefs.write`; prints files written and "restart your session" |
| `index` | | `doctor.write_index` |
| `accept-spec` | `--quote TEXT` | `control.make("accept-spec")` against the root log (no round needed), then `speclock.accept`; refuses while a round is active |
| `start` | | `round.start`; prints round id, worktree, branch |
| `next` | | `round.next`; prints `Next` as JSON |
| `record` | `ATTEMPT [--result FILE] [--usage JSON]` | copies `--result` to the attempt's result file when given, then `round.record` |
| `owner` | `--kind KIND --quote TEXT [--through STEP] [--skip-step S]* [--skip-gate G]* [--question N] [--value X]` | `round.owner` |
| `resume` | `[--force-restart]` | `round.resume` |
| `abandon` | `--quote TEXT` | `round.owner("abandon")` (alias) |
| `judgment` | `--worktree PATH --kind defined\|undefined --text TEXT` | `round.judgment` |
| `verify` | `[--worktree PATH] [--step STEP]` | `verify.for_step` on demand, no commit; for producers to self-check |
| `status` | | `round.status` |
| `bill` | `[--round NNNN]` | prints a round's bill from its STATE.json |
| `sync` | | `sync.update_control_checkout` (and `sync_to_main` for a complete round whose sync was refused) |
| `hook` | `prompt \| session-start` | `ownerlog.append_from_hook(stdin)` / `doctor` subset printed to stdout; always exit 0 |

`main(argv) -> int` builds the parser, dispatches, catches `HarnessError` → prints
`{"error": str, "code": n}` (or text) and returns `e.code`; any other exception → 1 with
the traceback to stderr.
