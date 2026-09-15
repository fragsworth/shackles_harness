# 08 — State, results, findings (`state.py`, `results.py`, `findings.py`, `judgmentcalls.py`, `history.py`)

**Purpose.** The round's memory and the mechanical reading of what agents said. These
modules hold shapes and transitions; none of them decides the next step, runs git, or
prices anything.

**Owns.** `STATE.json` load/save and its small transitions; parsing and normalizing
result files (S7); the findings lifecycle (S8); the judgment-call files (S15);
`HISTORY.md` (S14).

**Depends on.** 04 (`Paths`, `round_file`), 05 (`steps.step` for names only).

**Depended on by.** 10 (engine), 09 (ledger writes into `STATE.ledger` through
`state.py`), 03 (`status`), 11 (doctor reads STATE for the paused-round check).

---

## `state.py`

`class State` — a mutable dataclass mirroring S1 exactly; nested dataclasses
`Attempt`, `Pause`, `Flag`, `Limits`, `Landing`, `StepRecord`. Every write goes through
`save`, which also bumps `updated_at`.

- `new_state(round_id, folder, branch, base_commit, now) -> State` — status `claimed`,
  all steps `pending`, `mode = checkpoints`, empty everything.
- `load(path: Path) -> State` — raises `StateError` on missing file, bad JSON, or
  `schema != 1` (the message names the file).
- `save(state, path: Path, now) -> None` — atomic (write temp + rename), keys sorted,
  2-space indent, trailing newline.
- `open_attempt(state, step, kind, rung, prompt_rel, result_rel, now) -> Attempt` —
  appends an `issued` attempt with `n = len(attempts)+1`, sets `current`, increments
  `limits.attempts_total`. Raises `StateError` if `current` is already set.
- `close_attempt(state, outcome, usage, cost_usd, notes, now) -> Attempt` — marks the
  current attempt `recorded`/`rejected`/`accepted` per outcome, clears `current`.
- `set_pause(state, kind, step, detail, log_index, now)`, `clear_pause(state) ->
  Pause | None`.
- `set_step_status(state, step, status, now)`; `mark_skipped(state, step)`.
- `add_flags(state, texts: list[str], step, attempt)`; `unshown_flags(state) ->
  list[Flag]`; `mark_flags_shown(state)`.
- `record_owner_word(state, verb, quote, args, log_index, now)`.
- `next_pending_step(state, order: list[str]) -> str | None` — first step whose status
  is `pending`.
- `view_for_prose(state, plan_text: str, worktree: Path) -> dict` — the flat dict
  `prose.round_values` consumes (id, folder, base_commit, plan (with answers and
  overrides), budget, spend, remaining, owner_words, step, attempt).

Errors: `StateError(Exception)`.

## `results.py`

`class ProducerResult`, `class GateResult` — frozen dataclasses of S7 with defaults
for optional lists; `raw: dict` kept for HISTORY.

- `read_result(path: Path, kind: "driver"|"producer"|"conflict"|"gate") ->
  ProducerResult | GateResult` — raises `MalformedResult(reason)` when: file missing or
  empty; not a JSON object (a leading/trailing code fence ```` ```json ```` around one
  object is tolerated and stripped, JC-52); `status` missing or not in the allowed set
  for the kind; gate without `verdict` in `{PASS, FAIL}`; list fields not lists of the
  right item shape; `resolutions[].resolution` not in `{fixed, disputed}`;
  `rulings[].ruling` not in `{upheld, withdrawn}`; `judgment_calls[].kind` not in
  `{defined, undefined}`.
- `normalize_gate(result: GateResult) -> GateResult` — **the verdict wins**: with `PASS`
  every finding's `blocking` becomes `False`; with `FAIL` and no blocking finding, every
  finding becomes `blocking=True`; with `FAIL` and no findings at all raises
  `MalformedResult("FAIL without findings")` (JC-30).
- `missing_resolutions(result: ProducerResult, handed_ids: list[str]) -> list[str]` —
  ids the producer was given but did not resolve (only when `status == DONE`).
- `to_history_json(result) -> str` — pretty JSON of `raw`.

Errors: `MalformedResult(Exception)` with `.reason`.

## `findings.py`

Operates on `list[Finding]` (S8.finding) for one step, kept in `STATE.findings[step]`
and mirrored to `FINDINGS/STEP-n.json` per gate attempt.

- `next_id(existing: list[Finding]) -> str` — `F<n>`.
- `apply_rulings(findings, rulings: list, gate_attempt: int, now) -> list[str]` —
  notes. `withdrawn` → status `withdrawn`; `upheld` → `upheld_count += 1`, status
  `upheld`, or `settled` when the count reaches 2 ("upheld twice is settled"); an
  unknown id or a ruling on a `withdrawn`/`closed` finding is ignored with a note.
- `apply_resolutions(findings, resolutions: list, producer_attempt: int, now) ->
  list[str]` — `fixed` → status `fixed`; `disputed` → status `disputed` unless the
  finding is `settled` (then note `dispute of settled F3 ignored; still open`).
- `add_new(findings, new: list[dict], gate_attempt: int, now) -> tuple[list[Finding],
  list[dict]]` — assigns ids; a new finding whose `normalize(quote)` equals the quote
  of a `withdrawn` finding is dropped and returned in the second list (JC-31).
- `apply_verdict(findings, verdict, now) -> None` — `PASS` → every status not
  `withdrawn` becomes `closed`; `FAIL` → `fixed` findings not re-raised stay `fixed`
  (the gate did not confirm; they are re-handed), `upheld`/`settled`/`open` stay.
- `handed_to_producer(findings) -> list[Finding]` — statuses `open`, `upheld`,
  `settled`, `fixed` (fixed ones are re-handed so the producer confirms them).
- `blocks_acceptance(findings) -> bool` — any status in `{open, disputed, upheld,
  settled}` ("an unresolved finding blocks the step's acceptance"; after a PASS this is
  always false because `apply_verdict` closed them — the verdict wins).
- `render_for_prompt(findings, include_history: bool) -> str` — verbatim, one block per
  finding: id, status, quote, issue, suggestion, upheld count.
- `write_findings_file(path, step, gate_attempt, verdict, findings, dropped) -> None`.

## `judgmentcalls.py`

- `append_line(path: Path, step: str, n: int, who: str, text: str, now) -> None` — S15;
  newlines in `text` collapsed to spaces; creates the file with a one-line header
  `# <kind> judgment calls, one per line` when absent.
- `append_from_result(round_folder: Path, cfg_keys, step, n, who, calls: list[dict],
  now) -> int` — routes each `{kind, text}` to the defined or undefined file; returns
  the count.
- `counts(round_folder, cfg_keys) -> tuple[int, int]` — lines (excluding the header) in
  each file; used by pause summaries.
- `jc_command(run_py: Path, round_id: str, step: str, n: int) -> str` — the exact
  command line rendered into process instructions:
  `python3 <run_py> jc --round NNNN --step STEP --attempt n --kind <defined|undefined> --text "<one line>"`.

## `history.py`

- `append_attempt(path: Path, attempt: Attempt, result_json: str | None, spend_usd:
  float, notes: list[str], now) -> None` — S14.
- `append_note(path: Path, title: str, lines: list[str], now) -> None` — for owner
  verbs, pauses, landing events, dropped repeats, strays, limits.
- `append_round_end(path, reason, ledger_text: str, now) -> None`.

Never read by the runner; append-only; created on first use.

## Invariants
- `STATE.json` is the only file the engine reads to decide anything; HISTORY, prompts,
  results and findings files are records.
- `results.py` never raises on unknown extra keys; it raises on any shape it cannot act
  on. It never inspects the natural-language fields (JC-51).
- A finding's `quote` is stored verbatim; `normalize` is used only to compare.
- Every transition in `findings.py` appends to the finding's `history`.

## Covered by
`tests/test_state.py`, `tests/test_results.py`, `tests/test_findings.py`,
`tests/test_judgmentcalls.py`, `tests/test_history.py`.
