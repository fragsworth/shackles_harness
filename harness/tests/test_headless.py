"""The headless loop (run) with the stub standing in for claude."""
import json
import os
import sys

import fixtures
from fixtures import Repo
from shackles import config as configmod

FOLDER = "harness/archives/rounds/0001"


def claude_like_command():
    return [sys.executable, fixtures.STUB] + configmod.DEFAULTS["agentCommand"][1:]


def test_run_until_step_invokes_the_agent_like_the_cli(tmp_path):
    r = Repo(tmp_path, gates={"PLAN-AGENTS-GATE": 1}, config={"agentCommand": claude_like_command()})
    r.start()
    env = {"STUB_LOG": r.stub_log, "GH_TOKEN": "secret", "STUB_MODE": "pass"}
    res = r.run("run", "--until", "step", env=env)
    assert res.code == 0 and res.json["kind"] == "recorded" and res.json["step"] == "PLAN-AGENTS"
    calls = [json.loads(l) for l in open(r.stub_log, encoding="utf-8") if l.strip()]
    argv = calls[0]["argv"]
    assert "--print" in argv and argv[argv.index("--output-format") + 1] == "json" and "--max-turns" not in argv
    assert argv[argv.index("--model") + 1] == "claude-fable-5-1" and argv[argv.index("--effort") + 1] == "max"
    assert argv[argv.index("--json-schema") + 1].startswith('{"type":"object"')
    i = argv.index("--disallowedTools")
    assert argv[i + 1] == "Bash(git commit:*)" and argv.index("--permission-mode") > i and argv[-1] == configmod.DEFAULTS["agentTask"]
    assert calls[0]["cwd"].lower() == os.path.join(r.root, "harness").lower()
    assert "SHACKLES_SUBAGENT" in calls[0]["env_keys"] and "GH_TOKEN" not in calls[0]["env_keys"]
    assert r.exists(f"{FOLDER}/RESULTS/PLAN-AGENTS-1.meta.json") and r.json(f"{FOLDER}/RESULTS/PLAN-AGENTS-1.meta.json")["num_turns"] == 2
    assert any(e["source"] == "agent-cli" and e["usd"] >= 0.01 for e in r.state()["spend"]["entries"])
    res = r.run("run", "--until", "step", env=env)
    assert res.json["step"] == "PLAN-AGENTS-GATE"
    argv = [json.loads(l) for l in open(r.stub_log, encoding="utf-8") if l.strip()][1]["argv"]
    assert argv[argv.index("--tools") + 1:argv.index("--tools") + 4] == ["Read", "Grep", "Glob"]


def test_run_until_done_and_fenced_results(tmp_path):
    r = Repo(tmp_path)
    r.start(extra=["--delegate"])
    res = r.run("run", "--until", "done", env={"STUB_MODE": "fence", "STUB_NO_STRUCTURED": "1", "STUB_ARCHIVE": "1"})
    assert res.code == 0 and res.json["kind"] == "done" and res.json["status"] == "finished", res
    assert r.state()["landed_at"] and r.exists(f"{FOLDER}/tests-archive/test_scratch.py")


def test_run_stops_at_a_checkpoint(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.run("run", "--until", "done")
    assert res.code == 10 and res.json["checkpoint"]["kind"] == "review"


def test_garbage_and_nonzero_exit_are_infra_errors_then_a_checkpoint(tmp_path):
    r = Repo(tmp_path, config={"infraRetries": 2})
    r.start()
    res = r.run("run", "--until", "step", env={"STUB_MODE": "garbage"})
    assert res.code == 10 and res.json["checkpoint"]["kind"] == "infra"
    st = r.state()
    assert st["infra_errors"]["PLAN-AGENTS"] == 2 and st["attempts"].get("PLAN-AGENTS", 0) == 0
    assert r.exists(f"{FOLDER}/RESULTS/PLAN-AGENTS-1.raw-1.txt") and r.exists(f"{FOLDER}/RESULTS/PLAN-AGENTS-1.raw-2.txt")
    r2 = Repo(tmp_path / "b", config={"infraRetries": 1})
    r2.start()
    res = r2.run("run", "--until", "step", env={"STUB_EXIT": "3"})
    assert res.code == 10 and "headless agent error: exit 3" in r2.read(f"{FOLDER}/HISTORY.md")


def test_slow_agent_is_killed_at_the_wall_clock(tmp_path):
    r = Repo(tmp_path, config={"infraRetries": 1, "maxRunWallClockHours": 0.0005})
    r.start()
    import time
    t0 = time.time()
    res = r.run("run", "--until", "step", env={"STUB_MODE": "slow", "STUB_SLEEP": "30"})
    assert time.time() - t0 < 20
    assert res.code == 10 and res.json["checkpoint"]["kind"] == "infra" and "timed out" in res.json["message"]
