# 07 — Money and limits: `charges.py`, `ledger.py`, `budget.py`, `limits.py`

`charges.py` is pure arithmetic over file contents (no I/O). `ledger.py` books entries into `STATE.json` — what happened, never what was planned. `budget.py` turns plans into per-attempt targets. `limits.py` decides pauses.

All money is in `project.yaml` `currency` units (rendered as "USD" today) as floats rounded to cents on output only.

## 7.1 `src/shackles/charges.py`

**Owns:** the living-charge rules from the `project.yaml` comment block, token estimation, test base costs, archive charges, carry-file charges. **Depends on:** nothing but `suite.test_names` (pure) and `errors`. **Depended on by:** `ledger`, `landing` (projection), `prompts` (prompt-size tokens), `doctor` (prompt sizes), tests.

- `@dataclass(frozen=True) class Prices`: `token_bytes: int`, `cost_per_token: float`, `cost_per_token_over_cap: float`, `token_cap: int`, `file_base: float`, `test_base: float`, `carry_cost_per_token: float`, `plan_cost_per_token: float`, `spec_cost_per_token: float`, `postmortem_summary_cost_per_token: float`; `Prices.from_config(cfg: Config) -> Prices`.
- `estimate_tokens(n_bytes: int, token_bytes: int) -> int` — `ceil(n_bytes / token_bytes)`; `token_bytes <= 0` → `ConfigError`. The single estimator used everywhere.
- `file_price(tokens: int, p: Prices) -> float` — `cost_per_token × min(tokens, cap) + cost_per_token_over_cap × max(0, tokens − cap)`; excludes the base cost.
- `@dataclass class FileDelta`: `path: str`, `before_tokens: int | None`, `after_tokens: int | None`, `renamed_from: str | None`, `carry: bool`, `usd: float`, `kind: "new"|"removed"|"changed"|"renamed"|"unchanged"`.
- `@dataclass class ChargeBreakdown`: `files: list[FileDelta]`, `tests_added: list[str]`, `tests_removed: list[str]`, `tests_usd: float`, `files_usd: float`, `carry_usd: float`, `total: float`; `to_json()`.
- `living_charge(before: Mapping[str, bytes], after: Mapping[str, bytes], *, renames: Mapping[str, str], living_paths: list[str], test_paths: list[str], carry_files: list[str], p: Prices) -> ChargeBreakdown` — for every path under `living_paths` in either tree: pair renamed files (`renames`: new → old) as one delta with no base cost; new file → `file_base + file_price(after)`; removed → `−(file_base + file_price(before))`; changed → `file_price(after) − file_price(before)`; carry files (`carry=True`) → `carry_cost_per_token × (after_tokens − before_tokens)` with no base cost and no cap (JC-53); tests: `test_names(after) − test_names(before)` by bare name → `+test_base` each, the reverse → `−test_base` each (moves are neutral by construction). Files outside `living_paths` are ignored even if passed.
- `archive_charges(*, plan_bytes: int, spec_bytes: int, postmortem_summary_bytes: int, p: Prices) -> dict[str, float]` — `{"plan", "spec", "postmortem_summary", "total"}` at their per-token prices; frozen, never refunded.
- `summary_bytes(postmortem_md: str) -> int` — bytes of the Summary section (via `artifacts.validate_postmortem` semantics, re-implemented here as a pure function on text to keep the module pure).
- `usage_usd(rung: Rung, *, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float` — price at the rung's per-MTok rates.
- `estimate_usage(rung: Rung, *, prompt_tokens: int, est_output_fraction: float) -> dict` — `input = prompt_tokens`, `total = input / (1 − f)`, `output = total − input`; returns the token dict (JC-54).
- `apply_spawn_floor(usd: float, rung: Rung) -> float` — `max(usd, rung.spawn_cost_usd)`.

## 7.2 `src/shackles/ledger.py`

**Owns:** booking entries into `STATE.ledger`, round and project totals, remaining. **Depends on:** `state`, `charges`, `config`, `suite`, `gitops` (tree contents at round end, through an injected reader), `artifacts`, `paths`. **Depended on by:** `commands/record`, `commands/owner`, `commands/status`, `commands/spawn`, `prompts` (`round.spend`, `round.remaining`, `project.remaining`), `landing` (round total for the hard stop), `limits`.

- `book_attempt(rs: RoundState, rec: AttemptRecord, rung: Rung | None, *, usage: dict | None, tokens_total: int | None, prompt_tokens: int, roster: AgentRoster, now: ts) -> LedgerEntry` — precedence: `usage` (measured: full token dict) → `tokens_total` (measured total, split by `est_output_fraction`) → estimated from `prompt_tokens`. Price at the rung; apply the spawn floor; `source` = `measured` or `estimated`; driver attempts (CHAT-TO-PLAN, no rung) book `0` from usage and rely on the driver overhead entry. Detail keeps the tokens and rates used.
- `book_driver_step(rs, step: str, roster, now) -> LedgerEntry` — `driverUsdPerStep` once per step at its first accepted attempt or skip (`kind: "driver"`).
- `book_helper(rs, attempt: str, rung, usage: dict, now) -> LedgerEntry` — from `spawn`, always measured.
- `book_round_end(rs, *, before: Mapping[str, bytes], after: Mapping[str, bytes], renames, cfg: Config, plan_bytes, spec_bytes, postmortem_md: str | None, now) -> list[LedgerEntry]` — at CLEANUP's accepted record (or abandon): a `living` entry with the `ChargeBreakdown` as detail (only if landed), an `archive` entry with `archive_charges`, and a `carry` entry (the carry-file portion, split out so it is visible as "never stops the round"). `before` = tree at `landing.main_before`; `after` = the branch tree after the cleanup commit. Living charges may be negative.
- `round_total(rs) -> float`, `round_remaining(rs) -> float` (quote − total), `attempt_spend(rs, attempt_id) -> float`.
- `project_spent(roots: Roots, rp_factory) -> float` — Σ `ledger.total_usd` over every `archives/rounds/*/STATE.json` in the driver checkout, plus the active round's total; `project_remaining(cfg, roots, rs) -> float` = `budget − project_spent`.
- `elapsed_context_usd(rs, cfg, now) -> float` — `lostValuePerHour × active hours`; shown by `status` and the checkpoint summary, **not** booked (JC-55).
- Every booking appends a `HISTORY` "RUNNER charges booked" entry through the calling command.

## 7.3 `src/shackles/budget.py`

**Owns:** the mapping from plan and config to an attempt's target budget and rung. **Depends on:** `config`, `state`, `steps`. **Depended on by:** `prompts`, `limits`, `plumbing`.

- `share_for(rs: RoundState, cfg: Config, step: Step, *, gate: bool) -> float` — CHAT-TO-PLAN and PLAN-AGENTS (and any step before `AGENTS-PLAN.json` exists) from `defaultShares.work.<STEP>` / `defaultShares.gates.<STEP>` (missing → 0 with a warning); others from `rs.agents_plan`; a step missing from the plan → 0 with a warning.
- `attempt_budget_usd(rs, cfg, step, *, gate) -> float` — `share × quote` ("each retry is budgeted at the step's share again", so retries get the same number).
- `rung_for(rs, roster: AgentRoster, step: Step, *, gate: bool) -> Rung` — from `agents_plan` when present and within the ceiling, else `defaultAgent` / `gateAgent`; the conflict attempt uses `defaultAgent`.
- `helpers_for(rs, step) -> list[dict]` — the planned helpers for the prompt.
- `individual_cap_usd(rs, cfg, step, gate) -> float` — `attempt_budget × effective(hardStopBudgetMultipleIndividual)`.

## 7.4 `src/shackles/limits.py`

**Owns:** every rule that turns counters or money into a pause, and the effective value of a limit after `raise-limit`. **Depends on:** `state`, `config`, `ledger`, `budget`, `steps`. **Depended on by:** `commands/next_`, `commands/record`, `commands/owner`, `landing`, `decisions`.

- `effective(rs: RoundState, cfg: Config, key: str) -> float` — `limit_overrides[key]` if present else `cfg.get(key)`.
- `before_attempt(rs, cfg, now: ts) -> Pause | None` — `counters.turns >= maxTurnsPerRun` → `Pause("limit", "maxTurnsPerRun")`; `active_seconds(now) / 3600 >= maxRunWallClockHours` → `Pause("limit", "maxRunWallClockHours")` (active time only, paused time excluded, JC-56).
- `after_record(rs, cfg, rec: AttemptRecord, step: Step, *, gate: bool) -> Pause | None` — attempt spend `> individual_cap_usd` → `Pause("hard-stop", "hardStopBudgetMultipleIndividual")`; `round_total > effective(hardStopBudgetMultiple) × quote` → `Pause("hard-stop", "hardStopBudgetMultiple")`; rejections of the step `>= maxTurnsPerGate` after a rejection → `Pause("limit", "maxTurnsPerGate")` (mechanical rejections count too, JC-57).
- `rejections_exhausted(rs, cfg, step) -> bool`.
- `restarts_exhausted(rs, cfg) -> bool` — `counters.restarts >= effective(maxRoundAttempts)`.
- `@dataclass class Pause`: `kind`, `limit`, `reason` (a sentence with the numbers); `describe(rs, cfg, now) -> dict` — every limit with its effective value, current counter and headroom (for `status` and the pause summary).

The post-landing steps never stop the round for money: `after_record` skips the round-total hard stop once `landing.landed` is set (carry-file and cleanup charges "never stop the round if over budget"); the entries are still booked.
