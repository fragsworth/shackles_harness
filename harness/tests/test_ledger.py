import copy
import os

import fixtures
from shackles import config as configmod
from shackles import gitops, ledger, pipeline, procs


def cfg_with(**over):
    data = copy.deepcopy(configmod.DEFAULTS)
    data.update(over)
    return configmod.Config(os.path.join(over.pop("_root", "r"), "harness"), data, {}, [], fixtures.ROSTER)


def test_shares_defaults_and_equal_split():
    cfg = cfg_with()
    work, gates = ledger.shares(cfg, None, [], lambda g: g in ("PLAN-AGENTS-GATE", "SPEC-TO-TESTS-GATE"))
    assert work["CHAT-TO-PLAN"] == 0.05 and work["PLAN-AGENTS"] == 0.03
    rest = [p for p in pipeline.producers() if p not in ("CHAT-TO-PLAN", "PLAN-AGENTS")]
    assert all(abs(work[p] - 0.92 / len(rest)) < 1e-9 for p in rest) and abs(sum(work.values()) - 1) < 1e-9
    assert gates == {"PLAN-AGENTS": 0.03, "SPEC-TO-TESTS": 0.97}
    work, gates = ledger.shares(cfg, None, ["CLEANUP", "POSTMORTEM"], lambda g: False)
    assert "CLEANUP" not in work and gates == {}
    plan = {"shares": {"work": {"PLAN-AGENTS": 0.5}, "gates": {"PLAN-AGENTS": 1.0}}}
    work, gates = ledger.shares(cfg, plan, [], lambda g: g == "PLAN-AGENTS-GATE")
    assert work["PLAN-AGENTS"] == 0.5 and gates == {"PLAN-AGENTS": 1.0}


def test_step_budgets_caps_and_retry_cost():
    cfg = cfg_with()
    work, gates = ledger.shares(cfg, None, [], lambda g: g == "PLAN-AGENTS-GATE")
    assert abs(ledger.step_budget(cfg, 100, "PLAN-AGENTS", work, gates) - 100 * 0.7 * 0.03) < 1e-9
    assert abs(ledger.step_budget(cfg, 100, "PLAN-AGENTS-GATE", work, gates) - 100 * 0.3 * 0.03) < 1e-9
    assert ledger.step_budget(cfg, 100, "LANDING", work, gates) == 0
    assert ledger.budget_cap(cfg, 0.1) == 1.0 and ledger.budget_cap(cfg, 10) == 60
    assert ledger.retry_cost(cfg, 5.0, fixtures.ROSTER["max"]) == 5.0 + 0.21 + 1.0


def test_agent_cost_precedence_and_floors():
    cfg = cfg_with()
    rung = fixtures.ROSTER["max"]
    assert ledger.agent_cost(cfg, rung, cost=2.5)[0:2] == (2.5, "agent-cli")
    assert ledger.agent_cost(cfg, rung, cost=0.01)[0] == 0.21
    usd, source, note = ledger.agent_cost(cfg, rung, tokens=1_000_000, spawns=2)
    assert source == "agent-tokens" and abs(usd - (0.2 * 50 + 0.8 * 10 + 2 * 0.21)) < 1e-9 and "2 spawns" in note
    assert ledger.agent_cost(cfg, rung, tokens=10)[0] == 0.21
    usd, source, note = ledger.agent_cost(cfg, rung, estimate=7.0)
    assert (usd, source) == (7.0, "agent-estimate") and "estimate" in note
    assert ledger.agent_cost(cfg, rung, estimate=0.0)[0] == 0.21


def test_owner_charges_time_and_hard_stop():
    cfg = cfg_with(ownerMinutesPerCheckpoint=30, lostValuePerHour=2)
    assert ledger.owner_checkpoint_cost(cfg) == 5 + 10 * 0.5
    assert ledger.word_cost(cfg, "planCostPerWord", "one two  three\nfour") == 0.4
    state = {"created_at": "2026-01-01T00:00:00Z", "landed_at": "2026-01-01T03:00:00Z", "budget_usd": 10,
             "spend": {"entries": [], "agent_usd": 0, "driver_usd": 0, "owner_usd": 0, "living_usd": 0}}
    ledger.append(state, "PLAN-AGENTS", 1, 3.5, "agent-cli")
    ledger.append(state, "PLAN-AGENTS", 1, 1.0, "driver")
    ledger.append(state, "LANDING", 1, 2.0, "living")
    t = ledger.totals(cfg, state)
    assert t["agent_usd"] == 3.5 and t["driver_usd"] == 1.0 and t["living_usd"] == 2.0 and t["time_usd"] == 6.0 and t["total_usd"] == 12.5
    assert not ledger.hard_stop(cfg, state)
    state["budget_usd"] = 2
    assert ledger.hard_stop(cfg, state)


def mini_repo(tmp_path):
    root = str(tmp_path / "repo")
    os.makedirs(os.path.join(root, "harness"))
    for rel, text in (("src/a.py", "x = 1\n"), ("tests/test_a.py", "def test_one():\n    pass\n"), ("harness/docs/d.md", "doc\n"), ("other.txt", "free\n")):
        procs.write_text(os.path.join(root, *rel.split("/")), text)
    gitops.git(root, "init", "-q", "-b", "main")
    gitops.git(root, "add", "-A")
    gitops.git(root, "commit", "-q", "-m", "base")
    cfg = cfg_with(_root=root, livingSourcePaths=["../src/", "../tests/", "docs/"], livingFileTokenCap=5, livingFileCostPerToken=1.0,
                   livingFileCostPerTokenOverCap=2.0, livingFileBaseCost=10, testBaseCost=3, tokenBytes=4)
    return root, cfg


def test_living_charge_cases(tmp_path):
    root, cfg = mini_repo(tmp_path)
    base = gitops.head(root)
    procs.write_text(os.path.join(root, "src", "a.py"), "x = 1\n" + "y" * 30 + "\n")          # 6 -> 37 bytes: 2 -> 10 tokens
    procs.write_text(os.path.join(root, "src", "new.py"), "z\n")                                # added: 1 token + base
    os.remove(os.path.join(root, "harness", "docs", "d.md"))                                     # deleted: 1 token refunded, base refunded
    procs.write_text(os.path.join(root, "tests", "test_a.py"), "def test_one():\n    pass\n\n\ndef test_two():\n    pass\n")
    procs.write_text(os.path.join(root, "other.txt"), "free but changed\n")
    gitops.git(root, "add", "-A")
    gitops.git(root, "commit", "-q", "-m", "round")
    usd, rows = ledger.living_charge(cfg, root, base, "HEAD", test_paths=["../tests/"])
    by = {r["path"]: r for r in rows}
    assert by["src/a.py"]["usd"] == (5 * 1.0 + 5 * 2.0) - 2 * 1.0
    assert by["src/new.py"]["usd"] == 1.0 + 10
    assert by["harness/docs/d.md"]["usd"] == -(1.0 + 10)
    assert by["tests/test_a.py"]["new_tests"] == 1 and by["tests/test_a.py"]["usd"] == (5 + 8 * 2.0) - (5 + 2 * 2.0) + 3
    assert "other.txt" not in by
    assert abs(usd - sum(r["usd"] for r in rows)) < 1e-9


def test_living_charge_ignores_pycache_and_is_zero_without_changes(tmp_path):
    root, cfg = mini_repo(tmp_path)
    base = gitops.head(root)
    procs.write_text(os.path.join(root, "src", "__pycache__", "a.pyc"), "bytes")
    gitops.git(root, "add", "-A")
    gitops.git(root, "commit", "-q", "-m", "cache")
    assert ledger.living_charge(cfg, root, base, "HEAD") == (0.0, [])
