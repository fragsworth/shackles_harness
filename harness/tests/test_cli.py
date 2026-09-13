"""The CLI contract, through real subprocesses."""
import json
import os
import subprocess
import sys

import fixtures
from fixtures import Repo


def run_py(root, *args, runner=None, cwd=None):
    runner = runner or os.path.join(root, "harness", "src", "run.py")
    proc = subprocess.run([sys.executable, runner] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=cwd or root)
    return proc


def test_help_and_usage_exit_codes(tmp_path):
    r = Repo(tmp_path)
    assert run_py(r.root, "--help").returncode == 0 and "Exit codes" in run_py(r.root, "--help").stdout
    assert run_py(r.root, "nonsense").returncode == 2
    proc = run_py(r.root, "--root", str(tmp_path), "status")
    assert proc.returncode == 2 and "spec.yaml" in json.loads(proc.stdout)["error"]


def test_start_prints_one_json_line_and_root_is_found_from_cwd(tmp_path):
    r = Repo(tmp_path)
    proc = run_py(r.root, "start", "--plan", r.plan_file(), "--no-branch", cwd=os.path.join(r.root, "harness"))
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["round"] == 1 and set(out) >= {"round", "folder", "branch", "worktree", "runner"}
    proc = run_py(r.root, "next")
    assert proc.returncode == 0 and json.loads(proc.stdout.strip())["kind"] == "producer"
    proc = run_py(r.root, "status")
    assert json.loads(proc.stdout.strip())["step"] == "PLAN-AGENTS"


def test_doctor_config_and_render_on_the_fixture(tmp_path):
    r = Repo(tmp_path)
    proc = run_py(r.root, "doctor")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout.strip())
    assert report["errors"] == [] and report["info"]["prompts"]["PLAN-AGENTS"]["unresolved"] == []
    assert any("hook" in w for w in report["warnings"])
    defs = report["info"]["agent_definitions"]
    assert len(defs["drift"]) == 8 and defs["folder"].endswith("agents") and "general-purpose" in defs["note"], "the fixture repo has no definitions: say so"
    proc = run_py(r.root, "config")
    out = json.loads(proc.stdout.strip())
    assert out["sources"]["suiteCommand"] == "project.yaml" and out["sources"]["pushAttempts"] == "default"
    proc = run_py(r.root, "render", "--step", "CLEANUP", "--fixture", "--raw")
    assert proc.returncode == 0 and "STEP: CLEANUP" in proc.stdout
    proc = run_py(r.root, "spec", "status")
    assert proc.returncode == 0 and json.loads(proc.stdout.strip())["clean"]
    assert report["info"]["longpaths"] is True and not any("longpaths" in w for w in report["warnings"])
    if os.name == "nt":
        r.git("config", "core.longpaths", "false")
        report = json.loads(run_py(r.root, "doctor").stdout.strip())
        assert report["info"]["longpaths"] is False and any("core.longpaths" in w for w in report["warnings"])
        r.git("config", "core.longpaths", "true")


def test_runner_skew_warning(tmp_path):
    r = Repo(tmp_path)
    r.start()
    proc = run_py(r.root, "--root", r.root, "next", runner=os.path.join(fixtures.SRC, "run.py"))
    assert proc.returncode == 0
    action = json.loads(proc.stdout.strip())
    assert any(w.startswith("runner_skew") for w in action["warnings"])
    proc = run_py(r.root, "next")
    warnings = json.loads(proc.stdout.strip())["warnings"]
    assert not any(w.startswith("runner_skew") for w in warnings)


def test_checkpoint_exit_code_10_and_message_on_stderr(tmp_path):
    r = Repo(tmp_path)
    r.start()
    proc = run_py(r.root, "next")
    action = json.loads(proc.stdout.strip())
    import stub_agent
    message = stub_agent.perform(action["prompt_file"], "blocked", {})
    open(action["result_file"], "w", encoding="utf-8").write(message)
    proc = run_py(r.root, "record", "--step", action["step"], "--attempt", "1", "--result", action["result_file"], "--cost", "0.5")
    assert proc.returncode == 10 and json.loads(proc.stdout.strip())["kind"] == "checkpoint"
    assert "CHECKPOINT blocked" in proc.stderr
    assert run_py(r.root, "next").returncode == 10
