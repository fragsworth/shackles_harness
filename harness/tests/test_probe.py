"""probe and sandbox with the stub; the defect fixtures; the generated agent definitions."""
import json
import os

import pytest

import fixtures
import stub_agent
from fixtures import Repo
from shackles import agentdefs, config as configmod, pipeline, probe, procs

REPO_ROOT = fixtures.REPO_ROOT


def test_every_defect_fixture_loads():
    dirs = probe.defect_dirs()
    assert set(dirs) == set(pipeline.llm_gates())
    for gate in dirs:
        folder, expect = probe.load_defect(gate)
        assert expect["verdict"] == "FAIL" and expect["quote_contains"] and expect["files"]
        for rel, source in expect["files"].items():
            assert os.path.exists(os.path.join(folder, source)), (gate, source)
            assert not os.path.isabs(rel)


@pytest.mark.slow
def test_probe_manual_positions_a_gate_with_a_planted_defect(tmp_path):
    r = Repo(tmp_path)
    folder = str(tmp_path / "probe")
    res = r.run("probe", "--step", "PLAN-TO-SPEC-GATE", "--seed", "defect", "--manual", "--dir", folder)
    assert res.code == 0, res
    out = res.json
    assert out["action"]["step"] == "PLAN-TO-SPEC-GATE" and out["action"]["kind"] == "gate" and out["expect"]["verdict"] == "FAIL"
    assert "dashboard" in procs.read_text(os.path.join(out["action"]["worktree"], "harness", "archives", "rounds", "0001", "SPEC.md"))
    prompt = procs.read_text(out["action"]["prompt_file"])
    assert "STEP: PLAN-TO-SPEC-GATE" in prompt
    result = out["action"]["result_file"]
    procs.write_text(result, json.dumps({"verdict": "FAIL", "findings": [{"id": "F1", "quote": "web dashboard", "reason": "beyond the plan", "suggestion": "drop it", "blocking": True}]}))
    res = r.run("probe", "--check", result, "--dir", out["dir"])
    card = res.json
    assert card["contract_valid"] and card["schema_valid"] and card["verdict_as_expected"] and card["quote_contains_planted"]
    procs.write_text(result, json.dumps({"verdict": "PASS", "findings": []}))
    card = r.run("probe", "--check", result, "--dir", out["dir"]).json
    assert card["verdict_as_expected"] is False and card["quote_contains_planted"] is False


@pytest.mark.slow
def test_probe_runs_the_stub_headlessly_for_a_producer(tmp_path):
    r = Repo(tmp_path, config={"agentCommand": fixtures.stub_command()})
    res = r.run("probe", "--step", "SPEC-TO-IMPLEMENTATION", "--seed", "clean", "--dir", str(tmp_path / "p"))
    assert res.code == 0, res
    card = res.json["scorecard"]
    assert card["schema_valid"] and card["status"] == "DONE" and card["paths_confined"] and card["cost"] == 0.01
    res = r.run("probe", "--changed")
    assert res.json["steps"] == []


@pytest.mark.slow
def test_sandbox_builds_and_a_stub_round_finishes_there(tmp_path):
    r = Repo(tmp_path)
    r.append("harness/docs/TODO.md", "- TODO-MARKER: an item the sandbox planner must see\n")
    r.write(".claude/settings.json", '{"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "py -3.13 harness/src/owner_log_hook.py"}]}]}}\n')
    target = str(tmp_path / "sb")
    res = r.run("sandbox", "--dir", target)
    assert res.code == 0, res
    repo = res.json["repo"]
    assert os.path.isdir(res.json["origin"]) and os.path.exists(os.path.join(repo, "src", "toy", "text.py"))
    assert "TODO-MARKER" in procs.read_text(os.path.join(repo, "harness", "docs", "TODO.md")), "the copied carry-forward files survive the toy"
    assert "def shout" in res.json["toy"]["src/toy/text.py"] and "tests/toy/test_text.py" in res.json["toy"], "the JSON says what the toy already holds"
    assert os.path.exists(os.path.join(repo, ".claude", "settings.json")), "the owner-log hook is copied with the agent definitions"
    from shackles import gitops
    assert gitops.git(repo, "config", "--get", "core.longpaths") == "true" and gitops.git(res.json["origin"], "config", "--get", "core.longpaths") == "true"
    sb = Repo.__new__(Repo)
    sb.tmp, sb.root, sb.explicit_root = target, repo, repo
    sb.scratch = os.path.join(target, "scratch")
    os.makedirs(sb.scratch)
    sb.stub_log = os.path.join(target, "stub.log")
    sb.origin = fixtures.Origin(res.json["origin"])
    fixtures.local_yaml(repo, {"agentCommand": fixtures.stub_command()})
    start = sb.start(no_branch=False, extra=["--delegate"])
    assert start.code == 0, start
    v = sb.view(start.json["worktree"])
    assert v.run("config").json["sources"]["agentCommand"] == "local.yaml", "start copies local.yaml into the worktree"
    res = v.run("run", "--until", "done", env={"STUB_ARCHIVE": "1"})
    assert res.code == 0 and res.json["kind"] == "done" and res.json["main_synced"], res
    assert sb.origin.sha("main") == v.head()


def test_agent_definitions_match_the_roster(tmp_path):
    cfg = configmod.load(REPO_ROOT)
    assert agentdefs.drift(cfg, REPO_ROOT) == []
    files = agentdefs.expected(cfg)
    assert set(files) == {f"shackles-{k}-{r}.md" for k in ("producer", "gate") for r in cfg.agents}
    for rung, entry in cfg.agents.items():
        gate = files[f"shackles-gate-{rung}.md"]
        head = gate.split("---")[1]
        assert f"model: {cfg.model_alias(entry['model'])}" in head and f"effort: {entry['effort']}" in head and "tools: Read, Grep, Glob" in head
        producer = files[f"shackles-producer-{rung}.md"].split("---")[1]
        assert "disallowedTools: Bash(git commit:*)" in producer and "tools:" not in producer.replace("disallowedTools:", "")
    r = Repo(tmp_path)
    res = r.run("agents")
    assert res.code == 3 and res.json["drift"]
    res = r.run("agents", "--write")
    assert res.code == 0 and len(res.json["written"]) == 8 and r.run("agents").code == 0
