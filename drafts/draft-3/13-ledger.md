# 13 — The ledger: `ledger.py`

## `src/ledger.py`

**Owns:** every price in the harness and where it is booked: attempt costs (measured
or estimated), the driver overhead, the living charge on the round's net change to
main, the archive charges (plan, spec, postmortem summary), the test base costs,
the informational elapsed-time cost, round totals and the project's remaining budget.
Pure arithmetic over configs, git trees and state; it writes only into
`RoundState.ledger`. **Depends on:** `config`, `tokens`, `gitops` (tree listings and
blobs), `suite` (test counts), `schemas` (postmortem summary extraction), `state`,
`errors`. **Depended on by:** `recording`, `landing` (projected charge), `pauses`
(limits and messages), `context` (`round.spend`, `project.remaining`), `commands`
(`ledger` command), `next_action` (budget in prompts).

The owner's rule: **the ledger bills what happened and not what was planned**;
tokens are estimated as `ceil(bytes / tokenBytes)` everywhere (`tokens.py`).

### Types

- `Usage` (frozen dataclass): `input_tokens: int`, `output_tokens: int`,
  `cache_read_tokens: int = 0`, `cache_write_tokens: int = 0`.
- `AttemptCost` (dataclass): `step`, `attempt`, `kind`, `rung`, `usage: Usage`,
  `measured: bool`, `spawn_cost: float`, `token_cost: float`, `driver_overhead:
  float`, `total: float`.
- `FilePrice` (dataclass): `path`, `tokens: int`, `price: float`, `is_carry_forward:
  bool`.
- `LivingCharge` (dataclass): `before: dict[str, FilePrice]`, `after: dict[str,
  FilePrice]`, `token_delta_usd: float`, `file_base_usd: float` (new files ×
  `livingFileBaseCost` − removed files × it), `carry_forward_usd: float`, `total:
  float`, `changed: list[str]`.
- `ArchiveCharge` (dataclass): `plan_tokens`, `plan_usd`, `spec_tokens`, `spec_usd`,
  `summary_tokens`, `summary_usd`, `summary_found: bool`, `total`.
- `RoundBooking` (dataclass): `living: LivingCharge`, `archive: ArchiveCharge`,
  `test_delta: int`, `test_usd: float`, `elapsed_hours: float`, `elapsed_usd: float`
  (informational, excluded from `total`) [JC-38], `total: float`.

### Prices of an attempt

- `attempt_cost(agents: AgentsConfig, rung: str, usage: Usage | None, prompt_tokens:
  int, first_of_step: bool) -> AttemptCost` — `spawn_cost` = the rung's `spawnCost`;
  when `usage` is given (`measured=True`): `input × inputUsdPerMTok/1e6 + output ×
  outputUsdPerMTok/1e6 + cache_read × cacheReadUsdPerMTok/1e6 + cache_write ×
  cacheWriteUsdPerMTok/1e6`; when `None` (`measured=False`): `input = prompt_tokens`,
  `output = ceil(prompt_tokens × estOutputFraction)`, no cache terms [JC-39];
  `driver_overhead = driverUsdPerStep` when `first_of_step` else 0 [JC-55]. Raises
  `ConfigError("UNKNOWN_RUNG")`.
- `book_attempt(st: RoundState, cost: AttemptCost, now) -> None` — appends a
  `LedgerEntry` (`kind: attempt`) and updates `attempts_total`, `driver_total`,
  `total`.
- `round_total(st) -> float`; `attempt_budget_exceeded(cost, budget, multiple) -> bool`.

### The living charge

- `file_price(tokens: int, cfg: ProjectConfig) -> float` — `min(tokens, cap) ×
  livingFileCostPerToken + max(0, tokens − cap) × livingFileCostPerTokenOverCap`.
- `carry_forward_price(tokens: int, cfg) -> float` — `tokens ×
  postMortemFileCostPerToken` (no cap, no base cost) [JC-11].
- `price_tree(repo: Repo, cfg, ref: str, harness_rel: str) -> dict[str, FilePrice]`
  — `ls_tree(ref, living prefixes)`; tokens from blob sizes; carry-forward files
  priced by `carry_forward_price`, others by `file_price`.
- `living_charge(repo, cfg, before_ref: str, after_ref: str, harness_rel) ->
  LivingCharge` — prices both trees; `token_delta_usd` = Σ(after − before) per path
  over living, non-carry-forward files; `file_base_usd` = (paths only in after − paths
  only in before) × `livingFileBaseCost` — a rename nets to zero and its content, if
  unchanged, to zero; `carry_forward_usd` = Σ(after − before) over carry-forward files;
  `total` = the three summed. May be negative.
- `projected_living_charge(repo, cfg, main_ref, branch_ref, harness_rel) -> float`
  — `living_charge(...).total`, used by `landing` for the hard stop.

### Archive charges and tests

- `archive_charge(cfg, rp: RoundPaths) -> ArchiveCharge` [JC-66] — `planCostPerToken ×
  tokens(PLAN.json)`, `specCostPerToken × (tokens(SPEC.json) + tokens(SPEC.md))`,
  `postMortemCostPerSummaryToken × tokens(Summary section of POSTMORTEM.md)`; when
  no Summary heading exists the whole file is charged and `summary_found=False`
  [JC-29]; missing artifacts (skipped steps) count zero.
- `test_charge(repo, cfg, before_ref, after_ref, harness_rel) -> tuple[int, float]`
  — `(count_after − count_before, delta × testBaseCost)` using `suite.count_tests`;
  moving a test between files changes no count.
- `elapsed(st: RoundState, now) -> tuple[float, float]` — hours from `created_at`
  to `now` and `hours × lostValuePerHour`; informational.

### Booking the round

- `book_round(repo, cfg, st: RoundState, rp: RoundPaths, harness_rel, after_ref:
  str, now) -> RoundBooking` — `before = st.landing.pre_landing_main`
  (`base_commit` when the round never landed, which only happens on abandon — then
  nothing is booked and the function returns zeros with a note), `after` = the commit
  CLEANUP's record produced; computes the three charges; writes `living_charge`,
  `archive_charge`, `test_charge`, `elapsed_hours`, `elapsed_cost` and the new
  `total` (attempts + driver + living + archive + tests) into `st.ledger`; appends one
  `LedgerEntry` per charge. The POSTMORTEM step's carry-forward edits are inside the
  living charge and never trigger a pause (booking happens after the last hard-stop
  check).
- `charges_text(booking: RoundBooking, cfg) -> str` — the block shown to the owner in
  the final message and by the `ledger` command: one line per component, the total,
  the currency from `cfg.currency`.
- `ledger_text(st: RoundState, cfg) -> str` — every entry with step, attempt, rung,
  tokens, measured/estimated, cost; then the totals.

### Project level

- `project_remaining(cfg, all_rounds_spend: float) -> float` — `budget −
  all_rounds_spend`; the sum comes from `context.all_rounds_spend`.
