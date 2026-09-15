# 37 — src/shackles/ledger/ (bills what happened)

Parent: `30-src.md`. Owns the one token estimate, all pricing rules from
`project.yaml`'s comments, the living charge on a round's net change, agent
costs from usage, the round ledger kept inside `STATE.json`, the hard stops,
and the project's remaining budget. Everything is pure except the two
functions that read trees through `git/repo.py`. Depends on: `config/`,
`git/repo.py`. Depended on by: `engine/` (per-attempt billing, booking, hard
stops), `prompts/` (numbers rendered into prompts, through the engine's
views), `commands/status.py`.

```
ledger/
  tokens.py        bytes -> tokens; test-function counting
  pricing.py       file price, test cost, archive costs
  living.py        the net living charge between two trees
  agent_costs.py   usage -> USD for a rung; the estimate fallback
  ledger.py        entries, booking, totals, hard stops, project remaining, LEDGER.md line
```

## tokens.py

- `estimate_tokens(byte_len: int, token_bytes: int) -> int` — `ceil(bytes /
  tokenBytes)`; the only place text size becomes tokens; every caller (prompt
  warning, pricing, archive costs) uses it.
- `estimate_text(text: str | bytes, token_bytes) -> int` — UTF-8 length then
  the above.
- `count_tests(content: bytes, path: str) -> list[str]` — names of test
  functions: for `.py` files, every `def test_[A-Za-z0-9_]*(` at any indent
  (class methods count) `[JC-05]`; other extensions return `[]`.
- `is_test_file(rel: str, test_paths: list[str]) -> bool`.

## pricing.py

- `file_price(tokens: int, exists: bool, s: Settings) -> float` — `0` when the
  file does not exist; otherwise `livingFileBaseCost + livingFileCostPerToken
  * min(tokens, cap) + livingFileCostPerTokenOverCap * max(0, tokens - cap)`
  with `cap = livingFileTokenCap`.
- `carry_forward_price(tokens: int, exists: bool, s) -> float` —
  `postMortemFileCostPerToken * tokens` (no base, no cap) for files in
  `carryForwardFiles` `[JC-20]`.
- `test_delta_cost(before: int, after: int, s) -> float` — `testBaseCost *
  (after - before)`; negative is a refund; moves between files net to zero
  because the count is a suite-wide total.
- `archive_costs(plan_tokens: int, spec_tokens: int, summary_tokens: int, s) -> ArchiveCosts`
  — `planCostPerToken * plan_tokens`, `specCostPerToken * spec_tokens`
  (SPEC.json plus SPEC.md `[JC-21]`), `postMortemCostPerSummaryToken *
  summary_tokens` (the `## Summary` section of POSTMORTEM.md, up to the next
  `## ` heading), each a field plus `total`.

## living.py

Data: `FileCharge(path: str, oldPath: str | None, tokensBefore: int,
tokensAfter: int, usdBefore: float, usdAfter: float, delta: float, kind:
living|carryForward)`; `LivingCharge(files: list[FileCharge], testsBefore:
int, testsAfter: int, testUsd: float, fileUsd: float, total: float)`.

- `charge_between(repo, before_ref: str, after_ref: str, s: Settings) -> LivingCharge`
  — `diff_names` between the two trees with rename detection; keeps only
  paths under `livingSourcePaths` (`config.paths.is_under`); for each change
  prices the old and new content (`show_file`) with `file_price`, or
  `carry_forward_price` for carry-forward files; a rename with unchanged
  content charges nothing (same tokens both sides, same existence); a rename
  with changes charges only the token difference (the base cost is not
  re-charged: `exists` is true on both sides). Test functions are counted
  suite-wide at both refs over `testPaths` files (the round's `tests-archive/`
  is under `archives/`, never counted). Work created and removed inside the
  round never appears because only the two end trees are compared.
- `projected(repo, base_ref, head_ref, s) -> LivingCharge` — the same
  computation used before landing for the hard stop (`main` before landing vs
  the round branch head); it is a projection because POSTMORTEM and CLEANUP
  have not run.

## agent_costs.py

Data: `Usage(inputTokens: int, outputTokens: int, cacheReadTokens: int,
cacheWriteTokens: int, source: measured|split|estimated)`; `AttemptCost(usd:
float, spawnUsd: float, usage: Usage, rung: str)`.

- `usage_from_total(total_tokens: int, est_output_fraction: float) -> Usage`
  — `source = split`: output = round(total * fraction), input = the rest, no
  cache figures.
- `usage_from_sizes(prompt_bytes: int, result_bytes: int, s, roster) -> Usage`
  — `source = estimated`: input from the prompt size, output from the result
  size, then output raised to at least `estOutputFraction` of the sum `[JC-23]`.
- `cost(usage: Usage, rung: Rung) -> AttemptCost` — per-MTok prices times
  tokens plus `spawnCost`.
- `driver_overhead(roster) -> float` — `driverUsdPerStep`, booked once per
  step at acceptance or skip-by-limit `[JC-24]`.

## ledger.py

Data: `Entry(at, kind: attempt|driver|living|archive|note, attempt|None, step,
usd, usage|None, source, note)`; `Booked(livingUsd, testUsd, archiveUsd,
agentsUsd, driverUsd, total, at, mainBefore, treeAfter)`.

- `add_entry(state: RoundState, entry: Entry) -> RoundState` — appends and
  updates `ledger.total`.
- `round_spend(state) -> float` — sum of entries (agents, driver, and, once
  booked, living and archive).
- `book(state, living: LivingCharge, archive: ArchiveCosts, now, main_before, tree_after) -> RoundState`
  — writes `ledger.booked` and the living/archive entries; refuses if already
  booked. "Booked once, at cleanup."
- `hard_stop_round(state, s) -> bool` — `round_spend > hardStopBudgetMultiple
  * quote`; before landing the engine passes `round_spend + projected living`.
- `hard_stop_attempt(cost: float, budget: float, s) -> bool` — `cost >
  hardStopBudgetMultipleIndividual * budget`.
- `project_spent(paths, s) -> float` — sum of `ledger.total` over every
  `archives/rounds/*/STATE.json` on disk (the runner's worktree of `main` or
  the harness root), plus the open round's current spend; `project.remaining`
  = `budget - project_spent`.
- `ledger_line(state) -> str` — the `LEDGER.md` row of `25-archives.md`;
  `append_ledger_md(path, line)` is its only writer.
- `time_cost_note(state, s, now) -> str` — elapsed hours times
  `lostValuePerHour`, shown in status and HISTORY as context, never booked
  `[JC-25]`.
