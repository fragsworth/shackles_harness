# 06 — Money: token estimates, agent pricing, the quote and shares, the ledger

Parent: [`../SPEC.md`](../SPEC.md). Four modules under `harness/src/`. Everything that
turns bytes, usage or plans into dollars lives here. All prices come from `Config`; no
module hard-codes a number. The ledger bills what happened, never what was planned.

---

## tokens.py — the one token estimate

**Owns:** the single estimate `tokens = ceil(bytes / tokenBytes)` used everywhere text
size becomes tokens (prompt-size warning included). **Depends on:** `config`.
**Depended on by:** `render`, `ledger`, `pricing` (estimated usage), `doctor`.

```python
def estimate(text: str | bytes, token_bytes: int) -> int         # ceil(len(bytes)/token_bytes); "" -> 0
def file_tokens(path: Path, token_bytes: int) -> int             # 0 for a missing file
def blob_tokens(blob: bytes | None, token_bytes: int) -> int
```

---

## pricing.py — dollars for an attempt

**Owns:** converting a rung's prices and a usage record (measured or estimated) into USD,
plus the spawn cost. **Depends on:** `config`, `tokens`. **Depended on by:** `ledger`,
`round` (at record), `quote` (for advisory checks), `tests/stub_agent.py` (usage fixtures).

```python
@dataclass(frozen=True)
class Priced:
    usd: float; measured: bool; detail: dict[str, float]     # per-component dollars

def price_usage(agent: Agent, usage: Usage) -> Priced
    # input*in + output*out + cache_read*cr + cache_write*cw (per MTok) + spawn_cost; measured=True
def estimate_usage(agent: Agent, prompt_tokens: int, est_output_fraction: float) -> Priced
    # input = prompt_tokens uncached; output = est_output_fraction * prompt_tokens; + spawn_cost; measured=False
def attempt_cost(agent: Agent, usage: Usage | None, prompt_tokens: int, roster: Roster) -> Priced
    # measured when usage is given and non-zero, else estimated (JC-29)
```

---

## quote.py — the round's budget and its shares

**Owns:** the plan's quote, the enforced and advisory share rules, per-attempt budgets,
and the lint of `AGENTS-PLAN.json`. **Depends on:** `config`, `steps`. **Depended on by:**
`round` (budgets for `next`), `verify` (AGENTS-PLAN parse via `load_agents_plan`),
`plumbing` (budget line), `render` (RoundView.budget).

```python
class QuoteError(HarnessError): ...

@dataclass(frozen=True)
class StepShare: agent: str; sub_agents: int; share: float; notes: str
@dataclass(frozen=True)
class AgentsPlan:
    steps: dict[str, StepShare]; gates: dict[str, StepShare]; refactor_share: float; rationale_md: str

@dataclass(frozen=True)
class Plan:
    plan_md: str; quote_usd: float; scope: tuple[str, ...]; non_goals: tuple[str, ...]; assumptions: tuple[str, ...]
    validation_steps: tuple[str, ...]; questions: tuple[dict, ...]; todos_accepted: tuple[str, ...]
    refactor_fraction: float; living_charge_estimate_usd: float; archive_cost_estimate_usd: float

def load_plan(path: Path) -> Plan                                   # shape only (8.3); QuoteError on shape
def plan_problems(plan: Plan, entries: Iterable[Entry]) -> list[str]  # unanswered questions; answer quotes not in the owner log
def load_agents_plan(path: Path) -> AgentsPlan                       # shape only; QuoteError on shape
def lint_agents_plan(plan: AgentsPlan, cfg: Config) -> tuple[list[str], list[str]]
    # (errors, warnings). Errors (enforced): unknown step/gate; rung unknown or above maxAgent;
    # share < 0; sub_agents > maxSimultaneousSubAgentsPerRound; a share for a gate that is off
    # and > 0; sum(work shares) > workFraction + 0.005; sum(on-gate shares) > gatesFraction + 0.005 (JC-30).
    # Warnings (advisory): a share below defaultShares; refactor_share > maxRefactorOverhead;
    # work or gate pool left more than 10% unallocated.
def default_plan(cfg: Config) -> AgentsPlan
    # Before PLAN-AGENTS exists: defaultShares for CHAT-TO-PLAN and PLAN-AGENTS (work and gate),
    # defaultAgent/gateAgent rungs, no other entries.
def budget_for(plan: AgentsPlan | None, cfg: Config, step: str, role: str, quote: float) -> float | None
    # share * quote for the step or its gate; None when no share is known (JC-31)
def rung_for(plan: AgentsPlan | None, cfg: Config, step: str, role: str) -> str
    # plan's rung, else defaultAgent / gateAgent; landing-conflict uses defaultAgent
def helpers_for(plan: AgentsPlan | None, cfg: Config, step: str) -> int   # min(sub_agents, maxSimultaneousSubAgentsPerRound)
```

Quote rules as data (rendered into docs/MONEY.md and checked by `tests/test_docs.py`):
- The quote is `PLAN.json.quote_usd`, fixed at approval; only an owner `hard-stop-multiple`
  decision changes what the hard stop compares against.
- Each retry of a gated step is budgeted at the step's share again (the prose promises
  this to the planner); the per-attempt budget therefore never shrinks with retries.

---

## ledger.py — what the round actually cost

**Owns:** attempt spend accumulation, the driver's per-step charge, the living charge on
the net diff, the frozen archive charges, the round bill, and `project.remaining`.
**Depends on:** `config`, `tokens`, `pricing`, `gitops` (tree reads), `suite`
(test counting), `state`. **Depended on by:** `round` (record, cleanup, abandon),
`landing` (projected charge), `render` (spend/remaining), `status`/`bill` CLI.

Living-charge algorithm (`living_charge`), per the owner's commentary:
1. `changes = diff_names(main_before, tip)` restricted to `livingSourcePaths` (renames
   detected; a pure rename costs 0).
2. For each changed file: `price(tokens) = min(t, cap)·rate + max(t−cap, 0)·rate_over`;
   charge `price(after) − price(before)`; added files `+ livingFileBaseCost`, deleted
   `− livingFileBaseCost`; a rename with content change is priced on the content delta only.
3. Carry-forward files (docs/TODO.md, docs/CLARIFICATIONS.md): `(after − before tokens) ×
   postMortemFileCostPerToken`, no cap tiers, no base cost (JC-32).
4. Tests: `(joined − left) × testBaseCost` where joined/left are `(file, name)` pairs under
   `testPaths` present only after / only before (moves between files are neither).
5. The total may be negative (credit).

```python
@dataclass(frozen=True)
class FileCharge: path: str; before_tokens: int; after_tokens: int; usd: float; kind: Literal["living", "carry-forward", "rename"]
@dataclass(frozen=True)
class LivingCharge:
    files: tuple[FileCharge, ...]; tests_joined: int; tests_left: int; usd: float

def price_tokens(t: int, cfg: Config) -> float
def living_charge(repo: Path, cfg: Config, prefix: Path, main_before: str, tip: str) -> LivingCharge
def archive_charges(round_folder: Path, cfg: Config) -> dict[str, float]
    # {"plan": tokens(PLAN.json)*planCostPerToken, "spec": tokens(SPEC.json)+tokens(SPEC.md) * specCostPerToken,
    #  "postmortem_summary": tokens(Summary section of POSTMORTEM.md)*postMortemCostPerSummaryToken}; missing files -> 0
def summary_section(postmortem_md: str) -> str          # text under the first "## Summary" heading up to the next "## "
def book_attempt(state: State, attempt: str, priced: Priced) -> None
def book_driver_step(state: State, step: str, cfg: Config) -> None      # driverUsdPerStep once per accepted step
def round_spend(state: State) -> float                                  # sum of attempts + driver charges so far
def make_bill(state: State, cfg: Config, living: LivingCharge | None, archive: dict[str, float]) -> dict
    # {"quote", "attempts", "driver", "living", "archive": {...}, "total", "over_quote_by", "note"}; POSTMORTEM's
    # carry-forward charge never blocks (the note says so when the total exceeds the hard stop after landing).
def remaining_project(roots: Roots, cfg: Config, current: State | None) -> float
    # budget − Σ bill.total of every round folder whose STATE.json phase is complete or abandoned − current spend (JC-33)
```
