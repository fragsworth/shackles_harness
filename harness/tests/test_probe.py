"""probe and sandbox with the stub; the defect fixtures; the generated agent definitions."""
import contextlib
import io
import json
import os

import pytest
import yaml

import fixtures
import stub_agent
from fixtures import Repo
from shackles import agentdefs, cli, config as configmod, pipeline, probe, procs, specguard

REPO_ROOT = fixtures.REPO_ROOT


def run_cli(root, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["--root", root] + list(argv))
    return fixtures.Result(code, out.getvalue(), err.getvalue())


def test_every_defect_fixture_loads():
    dirs = probe.defect_dirs()
    assert set(dirs) == set(pipeline.llm_gates())
    for gate in dirs:
        folder, expect = probe.load_defect(gate)
        assert expect["verdict"] == "FAIL" and expect["quote_contains"] and expect["files"]
        anchors = expect["quote_contains"] if isinstance(expect["quote_contains"], list) else [expect["quote_contains"]]
        assert anchors and all(isinstance(a, str) and a for a in anchors), "one anchor or a list of them (R5-M4)"
        for rel, source in expect["files"].items():
            assert os.path.exists(os.path.join(folder, source)), (gate, source)
            assert not os.path.isabs(rel)


def test_probe_check_scores_any_listed_anchor_and_finds_its_folder(tmp_path):
    """A FAIL quoting any listed anchor scores true (R5-M4); `--check` finds the probe folder above the result file or refuses, and a folder
    already holding a repo is refused (R5-m8); a defect seed on a producer step is refused before anything is built (R5-n5)."""
    folder = tmp_path / "probe"
    results = folder / "repo" / "harness" / "archives" / "rounds" / "0001" / "RESULTS"
    results.mkdir(parents=True)
    procs.write_json(str(folder / "probe.json"), {"step": "SPEC-TO-TESTS-GATE", "seed": "defect", "root": str(folder / "repo"), "action": {},
                                                   "expect": {"verdict": "FAIL", "quote_contains": ["shout", "whisper"], "files": {}}})
    result = str(results / "SPEC-TO-TESTS-GATE-1.json")

    def check(quote):
        procs.write_text(result, json.dumps({"verdict": "FAIL", "findings": [{"id": "F1", "quote": quote, "reason": "r", "suggestion": "s", "blocking": True}]}))
        return run_cli(REPO_ROOT, "probe", "--check", result)

    for quote in ("def test_shout_again(self):", "Add `whisper(text)` to `src/toy/text.py`"):
        res = check(quote)
        assert res.code == 0 and res.json["verdict_as_expected"] and res.json["quote_contains_planted"], quote
    assert check("The tests under `tests/toy/` cover both functions.").json["quote_contains_planted"] is False
    res = run_cli(REPO_ROOT, "probe", "--check", str(tmp_path / "loose.json"))
    assert res.code == 2 and "--check needs --dir" in res.json["error"]
    res = run_cli(REPO_ROOT, "probe", "--step", "PLAN-TO-SPEC-GATE", "--manual", "--dir", str(folder))
    assert res.code == 2 and "already holds a probe repository" in res.json["error"]
    res = run_cli(REPO_ROOT, "probe", "--step", "SPEC-TO-IMPLEMENTATION", "--seed", "defect", "--manual", "--dir", str(tmp_path / "p"))
    assert res.code == 2 and "only gates have planted defects, not SPEC-TO-IMPLEMENTATION" in res.json["error"] and not os.path.exists(str(tmp_path / "p"))


@pytest.mark.slow
def test_probe_manual_positions_a_gate_with_a_planted_defect(tmp_path):
    r = Repo(tmp_path)
    folder = str(tmp_path / "probe")
    res = r.run("probe", "--step", "PLAN-TO-SPEC-GATE", "--seed", "defect", "--manual", "--dir", folder)
    assert res.code == 0, res
    out = res.json
    assert out["action"]["step"] == "PLAN-TO-SPEC-GATE" and out["action"]["kind"] == "gate" and out["expect"]["verdict"] == "FAIL"
    assert "dashboard" in procs.read_text(os.path.join(out["action"]["worktree"], "harness", "archives", "rounds", "0001", "SPEC.md"))
    project = os.path.join(out["action"]["worktree"], "harness", "project.yaml")  # the owner's comments survive the probe's copy (R4-n8)
    comments = lambda path: sum(1 for l in procs.read_text(path).splitlines() if "#" in l)
    assert comments(project) >= comments(os.path.join(REPO_ROOT, "harness", "project.yaml")) > 0
    probe_cfg = configmod.load(out["action"]["worktree"])
    assert probe_cfg.gate_enabled("PLAN-TO-SPEC-GATE") and not probe_cfg.gate_enabled("CHAT-TO-PLAN-GATE") and probe_cfg["lostValuePerHour"] == 0
    assert probe_cfg["livingSourcePaths"] == ["../src/", "../tests/", "docs/"] and probe_cfg["agentCommand"][1:] == fixtures.stub_command()[1:]
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


def test_set_yaml_keys_replaces_or_appends_and_keeps_comments():
    text = "# top\na: 1  # inline\nb:\n  x: 1\n  # inner\n  y: 2\nc: [1, 2]\n# tail\nd: 4\n"
    out = probe.set_yaml_keys(text, {"c": ["p", "q"], "b": {"z": 3}, "e": [5]})
    assert yaml.safe_load(out) == {"a": 1, "b": {"z": 3}, "c": ["p", "q"], "d": 4, "e": [5]}
    assert "# top" in out and "# inline" in out and "# tail" in out and out.index("# tail") < out.index("e:")


@pytest.mark.slow
def test_sandbox_of_the_real_repository_passes_spec_status_and_doctor(tmp_path):
    """The sandbox copies spec.yaml and every file it lists, wherever they are (SPEC.md is at the root), with the owner's comments."""
    res = run_cli(REPO_ROOT, "sandbox", "--dir", str(tmp_path / "real"))
    assert res.code == 0, res
    repo = res.json["repo"]
    assert specguard.spec_files(repo) == specguard.spec_files(REPO_ROOT) and all(os.path.exists(os.path.join(repo, f)) for f in specguard.spec_files(repo))
    status = run_cli(repo, "spec", "status")
    assert status.code == 0 and status.json["clean"], status
    report = run_cli(repo, "doctor")
    assert report.code == 0 and report.json["errors"] == [], report
    comments = lambda path: sum(1 for l in procs.read_text(path).splitlines() if l.startswith("#"))
    assert comments(os.path.join(repo, "harness", "project.yaml")) >= comments(os.path.join(REPO_ROOT, "harness", "project.yaml")) > 0


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
