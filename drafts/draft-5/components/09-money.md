# 09 — Money (`tokens.py`, `pricing.py`, `ledger.py`)

**Purpose.** Turn text sizes into tokens, tokens into dollars, and events into a bill
that records what happened. `tokens.py` and `pricing.py` are pure functions over
numbers and strings; `ledger.py` gathers inputs (from git diffs and STATE) and writes
S10 into STATE through `state.py`.

**Owns.** The one token estimate; every price formula in `project.yaml`'s comments;
attempt costing (measured or estimated, floored at `spawnCost`); the hard-stop checks;
the project's `remaining`.

**Depends on.** 04 (`Config`, `Roster`), 07 (`changes_between`, `show_bytes`,
`ls_tree_files` for the living diff), 08 (`state.py` to store the ledger).

**Depended on by.** 10 (record bills each attempt; CLEANUP books the round; LANDING
asks for the projection), 05 (`project.remaining`), 03 (`ledger` command).

---

## `tokens.py`

- `estimate_tokens(byte_count: int, token_bytes: int) -> int` — `ceil(bytes /
  tokenBytes)`; 0 for 0 bytes; raises `ValueError` if `token_bytes <= 0`.
- `tokens_of_text(text: str, token_bytes: int) -> int` — UTF-8 byte count → estimate.
- `tokens_of_file(path: Path, token_bytes: int) -> int` — size on disk → estimate.
- `count_test_functions(path: Path) -> int` — by extension (JC-20): `.py` → lines
  matching `^\s*(async\s+)?def\s+test_\w*\s*\(`; `.js/.ts/.jsx/.tsx/.mjs` → occurrences
  of `^\s*(it|test)\s*\(`; anything else → 0. Reads the file as UTF-8 with
  `errors="replace"`.
- `count_test_functions_in_text(text: str, suffix: str) -> int` — the same, for blobs
  at a git ref (the ledger's "before" side).
- `summary_section_bytes(markdown: str) -> int` — bytes of the first `# Summary`/`##
  Summary` heading (case-insensitive) through the line before the next heading of the
  same or higher level; 0 when absent (S6).

## `pricing.py` (all pure; every rate argument comes from `Config`/`Rung`)

- `file_price(tokens: int, cfg: Config) -> float` — `livingFileCostPerToken × min(tokens,
  cap) + livingFileCostPerTokenOverCap × max(0, tokens − cap)` with `cap =
  livingFileTokenCap`; without base cost.
- `living_file_delta(before_tokens: int | None, after_tokens: int | None, renamed: bool,
  cfg) -> float` — `None` = absent. New file: `file_price(after) + livingFileBaseCost`;
  deleted: `−file_price(before) − livingFileBaseCost`; modified or renamed:
  `file_price(after) − file_price(before)` (a rename costs nothing beyond its token
  delta; JC-45).
- `test_delta(joined: int, left: int, cfg) -> float` — `(joined − left) × testBaseCost`.
- `carry_forward_delta(before_tokens, after_tokens, cfg) -> float` — `(after − before) ×
  postMortemFileCostPerToken`; no base cost, no cap (JC-18).
- `archive_charges(plan_tokens, spec_tokens, summary_tokens, cfg) -> dict` —
  `{"plan": plan_tokens × planCostPerToken, "spec": spec_tokens × specCostPerToken,
  "postmortem_summary": summary_tokens × postMortemCostPerSummaryToken}` (JC-19).
- `usage_price(usage: dict, rung: Rung) -> float` — `(in × input + out × output +
  cache_read × cacheRead + cache_write × cacheWrite) / 1e6`.
- `estimate_usage(prompt_tokens: int, roster: Roster) -> dict` — `{"in":
  prompt_tokens, "out": ceil(prompt_tokens × estOutputFraction), "cache_read": 0,
  "cache_write": 0, "measured": False}` (JC-17).
- `attempt_cost(usage: dict, rung: Rung) -> float` — `max(rung.spawnCost,
  usage_price(usage, rung))`.
- `pool(quote_usd: float, cfg, kind: "work"|"gates") -> float` — `quote × workFraction`
  or `× gatesFraction`.
- `step_budget(quote_usd, share: float, cfg, kind) -> float` — `pool × share`.
- `hard_stop_round(quote_usd, multiple: float) -> float`;
  `hard_stop_attempt(step_budget_usd, cfg) -> float` — `× hardStopBudgetMultipleIndividual`.
- `time_context(elapsed_hours: float, cfg) -> float` — `× lostValuePerHour` (JC-29).

## `ledger.py`

- `bill_attempt(state, attempt_n_step: tuple[str,int], rung: Rung, usage: dict | None,
  prompt_tokens: int, roster) -> float` — chooses measured usage when given (every
  token column present) else `estimate_usage`; computes `attempt_cost`; appends to
  `ledger.attempts`; updates `total_usd`; returns the cost. Driver attempts (kind
  `driver`) have no rung and cost 0 here; the driver is billed per step below.
- `bill_driver_step(state, step, roster) -> float` — appends `{step, driverUsdPerStep}`
  once per accepted step (JC-48).
- `spent(state) -> float`; `remaining_round(state) -> float` (`quote − spent`, or 0
  before a quote exists).
- `living_change(repo: Path, base: str, target: str, cfg) -> LivingChange` — walks
  `changes_between` restricted to `livingSourcePaths`, excluding the carry-forward
  files; per file computes before/after tokens (`show_bytes` at `base`, file size at
  `target` via `show_bytes` too — both are refs), renames, and per-test counts for
  files under `testPaths` (functions before vs after; files under `testsArchive` are
  outside living paths and never counted). Returns per-file rows, tests joined/left,
  and the total.
- `carry_forward_change(repo, base, target, cfg) -> list[dict]` — the two files
  `docs/TODO.md`, `docs/CLARIFICATIONS.md` (the code lists them by their step-table
  symbol `carry-forward`, resolved through 04) priced with `carry_forward_delta`.
- `book_round(state, repo, cfg, roster, plan_path, spec_paths: list[Path],
  postmortem_path: Path | None) -> None` — at CLEANUP: `living_change(main_before,
  cleanup_commit)`, carry-forward, `archive_charges` from the archived files' token
  counts, `time_context`, `total_usd`. Idempotent (recomputes and replaces).
- `projected_living(state, repo, cfg) -> float` — `living_change(main_before or
  base_commit, HEAD).usd`; used by the hard stop before landing.
- `over_hard_stop(state, cfg, projected_living_usd: float) -> str | None` — the reason
  text when `spent + projected > hard_stop_round(quote, state.hard_stop_multiple or
  cfg.hardStopBudgetMultiple)`, else `None`.
- `over_individual_stop(cost_usd, step_budget_usd, cfg) -> bool`.
- `project_remaining(paths, cfg, rounds_dir: Path, current_state: State | None) ->
  float` — `budget − Σ total_usd of every `STATE.json` under `archives/rounds/*` with
  `status == ended` − current spend` (JC-36). Unreadable STATE files are skipped with
  a warning list available via `project_remaining_report`.
- `format_bill(state, cfg) -> str` — the owner-facing bill (per attempt, per step
  driver charge, living rows, carry-forward, archive, time context, total); the same
  text is appended to HISTORY at round end and printed by `run.py ledger`.

## Invariants
- No planned share is ever added to a total; shares only produce budgets shown in
  prompts and the individual hard stop.
- The living charge is computed from refs (`main_before` → cleanup commit), so work
  created and removed inside the round can never appear in it, and a shrinking tree
  yields a negative total (credit).
- `book_round` may be re-run safely; re-running replaces the living/archive sections.
- All rounding happens only when writing (4 decimals); arithmetic is on floats.

## Covered by
`tests/test_tokens.py`, `tests/test_pricing.py`, `tests/test_ledger.py`.
