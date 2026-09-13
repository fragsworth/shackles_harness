"""Budgets, prices, the living charge and the spend buckets."""
import math
import re

from . import gitops, pipeline, procs

SOURCES = ("agent-cli", "agent-tokens", "agent-estimate", "driver", "owner", "living")


def shares(cfg, agents_plan, overrides, gate_runs):
    """(work {step: share}, gates {producer: share}): explicit shares, then an equal split of the remainder."""
    producers = [p for p in pipeline.producers() if p not in overrides]
    gated = [pipeline.producer_of(g) for g in pipeline.llm_gates() if gate_runs(g)]
    planned = (agents_plan or {}).get("shares") or {}
    defaults = cfg.get("defaultShares") or {}

    def fill(explicit, keys):
        explicit = explicit if isinstance(explicit, dict) else {}
        out = {k: float(explicit[k]) for k in keys if isinstance(explicit.get(k), (int, float))}
        rest = [k for k in keys if k not in out]
        remaining = max(0.0, 1.0 - sum(out.values()))
        for k in rest:
            out[k] = remaining / len(rest)
        return out
    return fill(planned.get("work") or defaults.get("work"), producers), fill(planned.get("gates") or defaults.get("gates"), gated)


def step_budget(cfg, budget_usd, name, work, gates):
    s = pipeline.step(name)
    if s.kind in ("gate", "approval"):
        return budget_usd * cfg["gatesFraction"] * gates.get(pipeline.producer_of(name), 0.0)
    return budget_usd * cfg["workFraction"] * work.get(name, 0.0)


def budget_cap(cfg, budget):
    return max(float(cfg["minRunUsd"]), budget * cfg["hardStopBudgetMultiple"])


def retry_cost(cfg, producer_budget, rung):
    return producer_budget + float(rung.get("spawnCost", 0)) + float(cfg["driverUsdPerStep"])


def price_tokens(cfg, rung, tokens):
    f = float(cfg["estOutputFraction"])
    return tokens * (f * float(rung.get("outputUsdPerMTok", 0)) + (1 - f) * float(rung.get("inputUsdPerMTok", 0))) / 1e6


def agent_cost(cfg, rung, cost=None, tokens=None, spawns=0, estimate=0.0):
    """(usd, source, note): --cost, else --tokens priced by the rung, else the step budget as an estimate."""
    spawn = float(rung.get("spawnCost", 0))
    if cost is not None:
        return max(float(cost), spawn), "agent-cli", ""
    if tokens is not None:
        return max(price_tokens(cfg, rung, tokens) + spawn * spawns, spawn), "agent-tokens", f"{tokens} tokens, {spawns} spawns"
    return max(float(estimate), spawn), "agent-estimate", "no cost reported; the step budget is booked as an estimate"


def owner_checkpoint_cost(cfg):
    return float(cfg["costToWaitForOwner"]) + float(cfg["ownerHourlyRate"]) * float(cfg["ownerMinutesPerCheckpoint"]) / 60.0


def word_cost(cfg, key, text):
    return float(cfg[key]) * procs.words(text or "")


def entry(step, attempt, usd, source, note=""):
    return {"at": procs.now(), "step": step, "attempt": attempt, "usd": round(float(usd), 4), "source": source, "note": note}


def append(state, step, attempt, usd, source, note=""):
    spend = state["spend"]
    spend["entries"].append(entry(step, attempt, usd, source, note))
    buckets = {"agent_usd": 0.0, "driver_usd": 0.0, "owner_usd": 0.0, "living_usd": 0.0}
    for e in spend["entries"]:
        key = "agent_usd" if e["source"].startswith("agent") else e["source"] + "_usd"
        buckets[key] += e["usd"]
    for k, v in buckets.items():
        spend[k] = round(v, 4)
    return spend["entries"][-1]


def time_cost(cfg, state, at=None):
    end = state.get("landed_at") or state.get("abandoned_at") or at or procs.now()
    return max(0.0, procs.hours_between(state["created_at"], end)) * float(cfg["lostValuePerHour"])


def totals(cfg, state, at=None):
    spend = state["spend"]
    t = round(time_cost(cfg, state, at), 4)
    total = round(spend["agent_usd"] + spend["driver_usd"] + spend["owner_usd"] + spend["living_usd"] + t, 4)
    return {"agent_usd": spend["agent_usd"], "driver_usd": spend["driver_usd"], "owner_usd": spend["owner_usd"],
            "living_usd": spend["living_usd"], "time_usd": t, "total_usd": total, "quote_usd": state["budget_usd"]}


def hard_stop(cfg, state):
    return totals(cfg, state)["total_usd"] > float(cfg["hardStopBudgetMultiple"]) * float(state["budget_usd"])


def _tokens(cfg, size):
    return math.ceil(size / max(int(cfg["tokenBytes"]), 1)) if size else 0


def _price(cfg, tokens):
    cap = int(cfg["livingFileTokenCap"])
    return min(tokens, cap) * float(cfg["livingFileCostPerToken"]) + max(tokens - cap, 0) * float(cfg["livingFileCostPerTokenOverCap"])


def living_charge(cfg, root, base, head="HEAD", test_paths=()):
    """(usd, detail rows) for every living file that differs between base and head."""
    living = [cfg.repo_rel(p) for p in cfg.living_paths()]
    tests = [cfg.repo_rel(p) for p in test_paths]
    pattern = re.compile(cfg["testFunctionPattern"], re.M)
    if not living:
        return 0.0, []
    out = gitops.git(root, "diff", "--name-status", "--no-renames", base, head, "--", *living, check=False)
    rows, total = [], 0.0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0][0], procs.posix(parts[-1])
        if "__pycache__" in path or path.endswith(".pyc"):
            continue
        before = gitops.blob_size(root, base, path) if status != "A" else None
        after = gitops.blob_size(root, head, path) if status != "D" else None
        usd = _price(cfg, _tokens(cfg, after or 0)) - _price(cfg, _tokens(cfg, before or 0))
        if status == "A":
            usd += float(cfg["livingFileBaseCost"])
        elif status == "D":
            usd -= float(cfg["livingFileBaseCost"])
        new_tests = 0
        if any(procs.under(path, t) for t in tests) and status != "D":
            after_text = gitops.show(root, head, path) or ""
            before_text = (gitops.show(root, base, path) or "") if status != "A" else ""
            new_tests = len(pattern.findall(after_text)) - len(pattern.findall(before_text))
            usd += float(cfg["testBaseCost"]) * new_tests
        rows.append({"path": path, "status": status, "before": before or 0, "after": after or 0, "new_tests": new_tests, "usd": round(usd, 4)})
        total += usd
    return round(total, 4), rows
