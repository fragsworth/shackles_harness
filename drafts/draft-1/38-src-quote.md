# 38 — src/shackles/quote/ (budgets, shares, limits)

Parent: `30-src.md`. Owns the arithmetic that turns the approved quote into
pools and per-attempt budgets, and the run-limit checks. Pure. Depends on:
`config/` (fractions, default shares, limits), `steps/` (which steps are work
or gates), `round/state.py` types (read only). Depended on by: `engine/`.

```
quote/
  shares.py   pools, shares, attempt budgets, advisory minimum warnings
  limits.py   turn, gate-turn, wall-clock and mechanical-retry limits
```

## shares.py

Data: `Pools(quote: float, work: float, gates: float)`; `Share(step: str,
role: work|gate, fraction: float, usd: float, source: plan|default|equal)`.

- `pools(quote: float, s: Settings) -> Pools` — `work = workFraction * quote`,
  `gates = gatesFraction * quote`.
- `shares(quote, s, agent_plan: dict | None, gates_on: list[str]) -> list[Share]`
  — for every work step (all non-checkpoint, non-landing steps; LANDING's
  conflict attempt draws on the work pool under `LANDING`) and every gate that
  is on: the fraction from `agent_plan` when present, else from
  `defaultShares`, else an equal split of what the named shares leave in the
  pool. A gate that is off has no share and no charge. Sums above 1 are
  scaled down proportionally with a warning (the gate on PLAN-AGENTS judges
  the plan; the runner only keeps arithmetic sane) `[JC-26]`.
- `attempt_budget(share: Share, s) -> float` — the share's USD; every retry
  is budgeted at the share again (the prose says so), so the budget does not
  shrink with attempts.
- `advisory_warnings(shares, s) -> list[str]` — a work or gate share below
  its `defaultShares` minimum; text for the PLAN-AGENTS gate's inputs and for
  HISTORY.
- `rung_for(step: str, role, s, roster, agent_plan) -> tuple[Rung, str]` —
  the rung from the plan, else `defaultAgent` / `gateAgent`, capped at
  `maxAgent` via `roster.resolve_rung`; second value is a note when capped or
  defaulted.
- `sub_agents_for(step, s, agent_plan) -> int` — the plan's `subAgents`
  capped at `maxSimultaneousSubAgentsPerRound`, default 0.
- `refactor_note(spec_doc: dict, quote, s) -> str | None` — when
  `SPEC.json.refactor.estimatedUsd > maxRefactorOverhead * quote`, a warning
  line (advisory: shown to the gate and in HISTORY, never enforced).

## limits.py

Data: `LimitHit(kind: GATE_TURNS|RUN_TURNS|WALL_CLOCK|MECHANICAL, step, value,
limit, message: str)`.

- `check_before_attempt(state: RoundState, s: Settings, now) -> LimitHit | None`
  — `run.turns + 1 > maxTurnsPerRun`; elapsed hours since `run.startedAt`
  `>= maxRunWallClockHours`.
- `check_gate_turns(state, step, s) -> LimitHit | None` — `gateTurns[step] >
  maxTurnsPerGate` after a FAIL ("maximum turns (rejections) per gate").
- `check_mechanical(state, step, s) -> LimitHit | None` —
  `mechanicalRetries[step] > maxRoundAttempts` `[JC-27]`.
- `message(hit: LimitHit) -> str` — the sentence the driver relays: what was
  hit, the number, what the owner can do (`resume`, `abandon`, a temporary
  override with explicit words).
