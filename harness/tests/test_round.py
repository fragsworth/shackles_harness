"""One round in a single checkout (--no-branch), driven in-process with the stub."""
import json
import os
import re

import pytest

import fixtures
import stub_agent
from fixtures import PLAN, Repo
from shackles import pipeline

ALL_GATES = {g: 1 for g in pipeline.llm_gates()}


def repo(tmp_path, **kw):
    return Repo(tmp_path, **kw)


def test_start_validates_before_any_git_write(tmp_path):
    r = repo(tmp_path)
    head = r.head()
    res = r.start(plan=dict(PLAN, quote_usd=0))
    assert res.code == 2 and "quote_usd" in res.json["error"]
    assert r.head() == head and r.dirty() == "" and not os.path.exists(r.folder())
    res = r.start(plan=dict(PLAN, approval={"mode": "approved", "overrides": ["LANDING"]}))
    assert res.code == 2 and "LANDING cannot be overridden" in res.json["error"]


def test_start_refuses_spec_drift_unless_accepted(tmp_path):
    r = repo(tmp_path)
    r.append("harness/locked_prose/COMMON-OVERVIEW.txt", "an owner edit\n")
    r.git("commit", "-q", "-am", "prose edit")
    res = r.start()
    assert res.code == 3 and "spec drift" in res.json["error"] and "COMMON-OVERVIEW" in res.json["error"]
    res = r.start(extra=["--accept-spec"])
    assert res.code == 0
    assert r.run("spec", "status").json["clean"]


def test_start_requires_approval_words_when_the_gate_is_enabled(tmp_path):
    r = repo(tmp_path, gates={"CHAT-TO-PLAN-GATE": 1})
    res = r.start()
    assert res.code == 2 and "approval is required" in res.json["error"]
    assert r.start(extra=["--delegate"]).code == 2, "--delegate overrides the mode, not the owner's word (R3-m9)"
    r.owner("hello, thinking", at="2025-12-31T23:00:00Z")
    r.owner("please do it: approve the plan", at="2026-01-01T01:00:00Z")
    plan = dict(PLAN, approval={"mode": "approved", "words": "something else"})
    res = r.start(plan=plan)
    assert res.code == 2 and "not found in the owner log" in res.json["error"]
    res = r.start(plan=dict(plan, approval={"mode": "approved", "words": "thinking"}))
    assert res.code == 2, "a line before presented_at does not count"
    res = r.start(plan=plan, extra=["--unverified"])
    assert res.code == 0 and "unverified" in r.read("harness/archives/rounds/0001/HISTORY.md")
    assert any("unverified" in w for w in res.json["warnings"]), "start prints its flags, not only HISTORY"
    r2 = repo(tmp_path / "b", gates={"CHAT-TO-PLAN-GATE": 1})
    r2.owner("approve the plan", at="2026-01-01T01:00:00Z")
    assert r2.start(plan=dict(PLAN, approval={"mode": "approved", "words": "approve the plan"})).code == 0
    st = r2.state()
    assert st["approval"]["mode"] == "approved" and st["approval"]["words"] == "approve the plan"


def test_start_creates_the_round_folder_state_and_ledger(tmp_path):
    r = repo(tmp_path)
    res = r.start()
    assert res.code == 0
    out = res.json
    assert set(out) >= {"round", "id", "folder", "branch", "worktree", "runner", "record_hint", "warnings"}
    assert out["id"] == "0001" and out["folder"] == "archives/rounds/0001" and os.path.isabs(out["worktree"]) and out["warnings"] == []
    folder = "harness/archives/rounds/0001"
    for name in ("PLAN.json", "STATE.json", "HISTORY.md", "PROMPTS/.keep", "RESULTS/.keep", "FINDINGS/.keep",
                 "DEFINED_JUDGMENT_CALLS.md", "UNDEFINED_JUDGMENT_CALLS.md"):
        assert r.exists(f"{folder}/{name}"), name
    assert r.read(f"{folder}/DEFINED_JUDGMENT_CALLS.md").startswith("# DEFINED JUDGMENT CALLS, round 0001")
    st = r.state()
    assert st["status"] == "active" and st["step"] == "CHAT-TO-PLAN-GATE" and st["attempts"] == {"CHAT-TO-PLAN": 1}
    assert st["base_commit"] == st["prose_commit"] and st["mode"] == "no-branch" and st["budget_usd"] == 100.0
    assert st["approval"] == {"mode": "approved", "source": "gate-disabled"}
    assert r.json(f"{folder}/PLAN.json")["round"] == 1
    sources = [e["source"] for e in st["spend"]["entries"]]
    assert sources == ["agent-estimate", "driver", "owner"]
    assert st["spend"]["driver_usd"] == 1.0 and st["spend"]["owner_usd"] > 0
    assert r.log()[0] == "round 0001: start" and r.dirty() == ""


def test_action_shape_prompt_commit_and_record_command(tmp_path):
    r = repo(tmp_path)
    r.start()
    res = r.next()
    assert res.code == 0
    a = res.json
    assert a["kind"] == "producer" and a["step"] == "PLAN-AGENTS" and a["attempt"] == 1
    for key in ("prompt_file", "result_file", "artifact", "worktree", "runner"):
        assert os.path.isabs(a[key]), key
    assert a["agent"] == "max" and a["agent_type"] == "shackles-producer-max" and a["model_alias"] == "fable" and a["effort"] == "max"
    assert a["fallback_agent_type"] == "general-purpose" and a["rungs"] == {"max": "fable", "high": "fable", "medium": "opus", "low": "sonnet"}
    assert a["task"] == f"Your instructions are the entire content of {a['prompt_file']}. Read it now and follow it exactly; " \
                        "your final message must be exactly the JSON object it specifies and nothing else."
    assert not any(w.startswith("agent_type") for w in a["warnings"]), "the runner cannot see the session's agent list, so it never guesses"
    assert a["record_command"].endswith(f"record --step PLAN-AGENTS --attempt 1 --result {a['result_file']}")
    assert a["budget_usd"] > 0 and a["budget_cap_usd"] >= a["budget_usd"] and a["tools"] == "all"
    assert os.path.exists(a["prompt_file"]) and r.log()[0] == "round 0001: PLAN-AGENTS attempt 1 prompt" and r.dirty() == ""
    st = r.state()
    assert st["attempt_pending"]["step"] == "PLAN-AGENTS" and st["step_starts"]["PLAN-AGENTS"] == r.head().replace(r.head(), st["step_starts"]["PLAN-AGENTS"])
    assert st["attempts"]["CHAT-TO-PLAN-GATE"] == 1, "the mechanical gate counts an attempt (R3-m3)"
    assert "CHAT-TO-PLAN-GATE passed mechanically (PLAN.json valid; approval: approved None from gate-disabled)" in r.read("harness/archives/rounds/0001/HISTORY.md")
    again = r.next()
    assert again.json["prompt_file"] == a["prompt_file"] and r.log()[0] == "round 0001: PLAN-AGENTS attempt 1 prompt"
    s = repo(tmp_path / "with space")
    s.start()
    a = s.next().json
    assert f' --root "{s.root}" record ' in a["record_command"] and a["record_command"].endswith(f'--result "{a["result_file"]}"')


def test_prompts_render_from_prose_commit_and_config_live(tmp_path):
    r = repo(tmp_path)
    r.start()
    r.append("harness/locked_prose/COMMON-PROJECT.txt", "PROSE-EDITED-MID-ROUND\n")
    r.git("commit", "-q", "-am", "mid-round prose edit")
    res = r.next()
    text = open(res.json["prompt_file"], encoding="utf-8").read()
    assert "PROSE-EDITED-MID-ROUND" not in text
    assert r.state()["spec_edits"] == []
    r.act(res.json)
    project = r.read("harness/project.yaml").replace("PLAN-TO-SPEC-GATE: 0", "PLAN-TO-SPEC-GATE: 1")
    r.write("harness/project.yaml", project)
    r.git("commit", "-q", "-am", "flip a gate live")
    res = r.play(until="PLAN-TO-SPEC-GATE")
    assert res.json["step"] == "PLAN-TO-SPEC-GATE" and res.json["kind"] == "gate" and res.json["tools"] == "read-only"


def test_record_guards_refuse_and_change_nothing(tmp_path):
    r = repo(tmp_path)
    r.start()
    a = r.next().json
    head = r.head()
    msg = stub_agent.perform(a["prompt_file"], "pass", {})
    r.git("checkout", "-q", "--", ".")
    r.git("clean", "-fdq", "--", "harness")
    assert r.record("PLAN-TO-SPEC", 1, msg).code == 2
    assert r.record("PLAN-AGENTS", 2, msg).code == 2
    assert r.head() == head and r.state()["attempts"] == {"CHAT-TO-PLAN": 1, "CHAT-TO-PLAN-GATE": 1}
    rec = r.act(a)
    assert rec.code == 0
    replay = r.record("PLAN-AGENTS", 1, msg)
    assert replay.code == 2 and "error" in replay.json
    assert r.state()["attempts"]["PLAN-AGENTS"] == 1


def test_record_agent_names_the_rung_that_ran(tmp_path):
    r = repo(tmp_path)
    r.start()
    a = r.next().json
    stub_agent.perform(a["prompt_file"], "pass", {})
    msg = {"status": "DONE", "notes": "ran on the low rung's model"}
    res = r.record("PLAN-AGENTS", 1, msg, cost=None, extra=["--tokens", "1000000", "--agent", "nope"])
    assert res.code == 2 and "not a roster key" in res.json["error"] and r.state()["attempts"] == {"CHAT-TO-PLAN": 1, "CHAT-TO-PLAN-GATE": 1}
    res = r.record("PLAN-AGENTS", 1, msg, cost=None, extra=["--tokens", "1000000", "--agent", "low"])
    assert res.code == 0
    e = [e for e in r.state()["spend"]["entries"] if e["source"] == "agent-tokens"][-1]
    assert e["usd"] == 0.2 * 10 + 0.8 * 2 and "(rung low)" in e["note"], "priced at the rung that ran, not the action's max"
    flag = "PLAN-AGENTS attempt 1: ran on rung low, the action named max"
    assert flag in res.json["warnings"] and f"FLAG (runner): {flag}" in r.read("harness/archives/rounds/0001/HISTORY.md"), "the plan's rung was not honoured (R3-m1)"
    a = r.next().json
    stub_agent.perform(a["prompt_file"], "pass", {})
    res = r.record("PLAN-TO-SPEC", 1, {"status": "DONE", "notes": "ran on the action's own rung"}, cost=None, extra=["--tokens", "1000", "--agent", "max"])
    e = [e for e in r.state()["spend"]["entries"] if e["source"] == "agent-tokens"][-1]
    assert res.code == 0 and "(rung" not in e["note"] and not any("ran on rung" in w for w in res.json["warnings"]), "no note when the rungs agree"


def test_start_agent_forces_the_rung_and_tells_the_planner(tmp_path):
    """start --agent names the rung in every action and in the PLAN-AGENTS prompt, so record --agent is never needed (R4-n7, DRIVER.md)."""
    r = repo(tmp_path)
    r.start(extra=["--agent", "low"])
    a = r.next().json
    assert a["agent"] == "low" and a["model_alias"] == "sonnet"
    assert "the runner runs and prices each at it): low\n" in open(a["prompt_file"], encoding="utf-8").read()
    stub_agent.perform(a["prompt_file"], "pass", {})
    res = r.record("PLAN-AGENTS", 1, {"status": "DONE", "notes": "ran on the forced rung"}, cost=None, extra=["--tokens", "1000", "--agent", "low"])
    assert res.code == 0 and not any("ran on rung" in w for w in res.json["warnings"])
    assert r.next().json["agent"] == "low", "the forced rung beats the plan's"
    r2 = repo(tmp_path / "free")
    r2.start()
    assert "the runner runs and prices each at it): none\n" in open(r2.next().json["prompt_file"], encoding="utf-8").read()


def assert_round_files(r, gates_on):
    st = r.state()
    folder = "harness/archives/rounds/0001"
    for name in pipeline.NAMES:
        s = pipeline.step(name)
        if s.kind in ("producer", "code"):
            assert st["attempts"][name] == 1 and name in st["step_commits"], name
            assert r.exists(f"{folder}/PROMPTS/{name}-1.txt") and r.exists(f"{folder}/RESULTS/{name}-1.json"), name
        if s.kind == "gate":
            assert r.exists(f"{folder}/FINDINGS/{name}-1.json"), name
            verdict = r.json(f"{folder}/FINDINGS/{name}-1.json")
            if gates_on:
                assert verdict["source"] == "gate" and r.exists(f"{folder}/PROMPTS/{name}-1.txt")
                if pipeline.step(pipeline.producer_of(name)).kind == "code":
                    diff = r.read(f"{folder}/PROMPTS/{name}-1.diff")
                    assert diff.startswith("diff --git") and "archives/rounds" not in diff, "the gate's diff holds the artifact, not the round folder"
            else:
                assert verdict["source"] == "disabled" and not r.exists(f"{folder}/PROMPTS/{name}-1.txt")
    assert st["status"] == "finished" and st["landed_at"] and st["tests_frozen_at"]
    assert r.exists("src/toy/text.py") and "whisper" in r.read("src/toy/text.py")
    assert r.exists(f"{folder}/tests-archive/test_scratch.py") and not r.exists("tests/toy/test_scratch.py")
    assert "round/0001-landed" in r.tags()
    rows = [json.loads(l) for l in r.read("harness/archives/rounds/index.jsonl").splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["id"] == 1 and rows[0]["outcome"] == "landed" and rows[0]["spend"]["living_usd"] > 0
    assert st["judgment_calls"]["defined"] >= 7 and st["judgment_calls"]["undefined"] == 0
    assert len([e for e in st["spend"]["entries"] if e["source"] == "living"]) == 1
    assert "## round 0001" in r.read("harness/docs/TODO.md")
    assert r.run("status").json["living_preview_usd"] is None, "once landed, the booked living_usd is the figure"


def drive(r, modes=None, env=None, quotes=("approve",)):
    """Play to done, answering every review checkpoint with approve; returns the checkpoints seen."""
    seen = []
    for _ in range(12):
        res = r.play(modes=modes, env=env)
        if res.json.get("kind") == "done":
            return seen, res
        assert res.json.get("kind") == "checkpoint", res
        seen.append((res.json["checkpoint"]["kind"], res.json["checkpoint"]["step"]))
        assert r.owner_cmd("approve", "approve").code == 0
    raise AssertionError("did not finish")


def test_full_round_every_gate_enabled(tmp_path):
    r = repo(tmp_path, gates=ALL_GATES)
    r.start()
    seen, res = drive(r, env={"STUB_ARCHIVE": "1", "STUB_JUDGMENT": "1,0"})
    assert seen == [("review", "PLAN-TO-SPEC-GATE"), ("review", "CLEANUP")]
    assert res.json["main_synced"] is True and res.json["status"] == "finished"
    assert_round_files(r, gates_on=True)
    assert r.dirty() == ""
    h = r.read("harness/archives/rounds/0001/HISTORY.md")
    assert h.index("PLAN-TO-SPEC-GATE attempt 1: PASS") < h.index("CHECKPOINT review at PLAN-TO-SPEC-GATE") < h.index("RESUME approve"), "R3-n5"


def test_gate_prompt_retry_cost_uses_the_producers_rung(tmp_path):
    """The producer's prompt and its gate's name the same retry cost: the producer's budget plus the producer's spawnCost (R3-n6)."""
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    res = r.play(until="PLAN-TO-SPEC", env={"STUB_RUNG": "low"})
    assert res.json["agent"] == "low"
    producer_prompt = open(res.json["prompt_file"], encoding="utf-8").read()
    res = r.play(until="PLAN-TO-SPEC-GATE")
    assert res.json["agent"] == "max", "the gate runs on another rung than its producer"
    cost = re.search(r"Retry cost ([0-9.]+)\.", producer_prompt).group(1)
    assert f"A FAIL costs ${cost} (the producer's retry)" in open(res.json["prompt_file"], encoding="utf-8").read()


def test_full_round_every_gate_disabled_and_delegation(tmp_path):
    r = repo(tmp_path)
    r.start()
    seen, res = drive(r, env={"STUB_ARCHIVE": "1", "STUB_JUDGMENT": "1,0"})
    assert seen == [("review", "PLAN-TO-SPEC-GATE"), ("review", "CLEANUP")]
    assert_round_files(r, gates_on=False)
    d = repo(tmp_path / "delegated")
    d.start(extra=["--delegate"])
    seen, res = drive(d, env={"STUB_ARCHIVE": "1"})
    assert seen == [] and res.json["kind"] == "done"
    assert "review checkpoint after PLAN-TO-SPEC-GATE skipped (delegated)" in d.read("harness/archives/rounds/0001/HISTORY.md")
    t = repo(tmp_path / "through")
    t.start(extra=["--delegate", "--through", "PLAN-TO-SPEC-GATE"])
    seen, res = drive(t, env={"STUB_ARCHIVE": "1"})
    assert seen == [("review", "CLEANUP")]


def test_delegation_from_the_plan(tmp_path):
    """The plan's approval alone delegates; an empty or null `through` means every review is skipped (test-A 3.1)."""
    for name, through in (("empty", ""), ("null", None)):
        p = repo(tmp_path / name)
        assert p.start(plan=dict(PLAN, approval={"mode": "delegated", "through": through, "overrides": [], "words": "delegate"})).code == 0
        assert p.state()["approval"]["mode"] == "delegated"
        seen, res = drive(p, env={"STUB_ARCHIVE": "1"})
        assert seen == [] and res.json["kind"] == "done", name
        assert "review checkpoint after CLEANUP skipped (delegated)" in p.read("harness/archives/rounds/0001/HISTORY.md")
    q = repo(tmp_path / "step")
    assert q.start(plan=dict(PLAN, approval={"mode": "delegated", "through": "NOPE"})).code == 2
    for through in ("PLAN-TO-SPEC-GATE", "PLAN-TO-SPEC"):  # the gate's name or the producer's, the natural thing for an owner to say (R3-M1)
        q = repo(tmp_path / through)
        assert q.start(plan=dict(PLAN, approval={"mode": "delegated", "through": through, "words": f"delegate through {through}"})).code == 0
        seen, res = drive(q, env={"STUB_ARCHIVE": "1"})
        assert seen == [("review", "CLEANUP")], through
    p = repo(tmp_path / "earlier")
    assert p.start(plan=dict(PLAN, approval={"mode": "delegated", "through": "PLAN-AGENTS", "words": "delegate through PLAN-AGENTS"})).code == 0
    seen, res = drive(p, env={"STUB_ARCHIVE": "1"})
    assert seen == [("review", "PLAN-TO-SPEC-GATE"), ("review", "CLEANUP")], "a through before the spec skips no review"


def test_delegate_at_a_checkpoint(tmp_path):
    r = repo(tmp_path)
    r.start()
    res = r.play()
    assert res.json["checkpoint"]["kind"] == "review" and res.json["checkpoint"]["step"] == "PLAN-TO-SPEC-GATE"
    res = r.run("delegate", "--through", "NOPE", "--quote", "delegate through nope")
    assert res.code == 2 and "unknown step NOPE" in res.json["error"] and r.state()["status"] == "checkpoint"
    res = r.run("delegate", "--quote", "delegate")
    assert res.code == 0 and r.state()["approval"]["mode"] == "delegated" and r.state()["approval"]["through"] is None
    seen, res = drive(r, env={"STUB_ARCHIVE": "1"})
    assert seen == [] and res.json["kind"] == "done", "delegating at the first review skips the later one"


def test_overrides(tmp_path):
    r = repo(tmp_path)
    plan = dict(PLAN, approval={"mode": "approved", "overrides": ["PLAN-AGENTS", "TESTS-TO-SUITE", "CLEANUP"]})
    r.start(plan=plan)
    seen, res = drive(r, env={"STUB_ARCHIVE": "1"})
    assert seen == [("review", "PLAN-TO-SPEC-GATE"), ("review", "CLEANUP")]
    st = r.state()
    assert "PLAN-AGENTS" not in st["attempts"] and "TESTS-TO-SUITE" not in st["attempts"] and "CLEANUP" not in st["attempts"]
    assert r.exists("tests/toy/test_scratch.py"), "TESTS-TO-SUITE overridden keeps every test"
    assert not r.exists("harness/archives/rounds/0001/AGENTS-PLAN.json")
    assert r.json("harness/archives/rounds/0001/FINDINGS/PLAN-AGENTS-GATE-1.json")["source"] == "override"
    assert st["status"] == "finished"
    r2 = repo(tmp_path / "b")
    r2.start()
    res = r2.run("override", "--steps", "LANDING", "--quote", "skip it")
    assert res.code == 2 and "cannot be overridden" in res.json["error"]
    res = r2.run("override", "--steps", "POSTMORTEM", "--quote", "skip the postmortem")
    assert res.code == 0 and r2.state()["overrides"] == ["POSTMORTEM"]
    seen, res = drive(r2)
    assert r2.state()["status"] == "finished" and "POSTMORTEM" not in r2.state()["attempts"]
    assert res.json["landed_at"]


def test_status_spend_and_check_are_read_only(tmp_path):
    r = repo(tmp_path)
    r.start()
    res = r.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True)
    head = r.head()
    status = r.run("status").json
    assert status["step"] == "SPEC-TO-IMPLEMENTATION" and status["attempt_pending"]["attempt"] == 1 and "undefined_file" in status
    assert status["living_preview_usd"] > 0, "before landing: the charge the diff from base_commit would book"
    spend = r.run("spend").json
    assert spend["total_usd"] > 0 and spend["quote_usd"] == 100.0
    check = r.run("check")
    assert check.code == 3 and check.json["findings"][0]["id"] == "M3"
    assert r.head() == head and r.dirty() == ""
    assert r.run("spend", "--project").json["rounds"][0]["id"] == 1


def test_abandon_from_any_status(tmp_path):
    r = repo(tmp_path)
    r.start()
    r.play(until="PLAN-TO-SPEC")
    res = r.run("abandon", "--reason", "changed my mind", "--quote", "stop")
    assert res.code == 0 and res.json["kind"] == "done" and res.json["status"] == "abandoned"
    st = r.state()
    assert st["status"] == "abandoned" and st["abandoned_at"] and "round/0001-abandoned" in r.tags()
    rows = [json.loads(l) for l in r.read("harness/archives/rounds/index.jsonl").splitlines() if l.strip()]
    assert rows[-1]["outcome"] == "abandoned"
    assert r.next().json["kind"] == "done"
    assert r.run("approve", "--quote", "x").code == 2
    r2 = repo(tmp_path / "b")
    r2.start()
    res = r2.start()
    assert res.code == 0 and res.json["id"] == "0002"
    assert r2.run("status").code == 2, "two unfinished rounds: --round is required"
    assert r2.run("--round", "2", "status").json["round"] == "0002"


def test_render_command_on_a_round_has_no_side_effects(tmp_path):
    r = repo(tmp_path)
    r.start()
    a = r.next().json
    head = r.head()
    res = r.run("render", "--step", "PLAN-AGENTS", "--attempt", "1")
    assert res.code == 0 and res.json["prompt"] == open(a["prompt_file"], encoding="utf-8").read() and res.json["unresolved"] == []
    assert r.head() == head and r.dirty() == ""
    res = r.run("render", "--step", "CHAT-TO-PLAN")
    assert res.code == 0 and "STEP: CHAT-TO-PLAN" in res.json["prompt"] and "# TODO" in res.json["prompt"]
    harness = os.path.join(r.root, "harness")
    assert f'"{harness}/DRAFT-PLAN.json": JSON object with' in res.json["prompt"] and "0000/PLAN.json" not in res.json["prompt"], "one destination for the plan"
    start = f'py -3.13 "{os.path.join(harness, "src", "run.py")}" --root "{r.root}" start --plan "{harness}/DRAFT-PLAN.json"'
    assert start in res.json["prompt"], "the printed start command names the repository it was rendered for"


def test_history_marks_a_note_it_cuts(tmp_path):
    r = repo(tmp_path)
    r.start()
    a = r.next().json
    stub_agent.perform(a["prompt_file"], "pass", {})
    assert r.record("PLAN-AGENTS", 1, {"status": "DONE", "notes": "N" * 2500}).code == 0
    text = r.read("harness/archives/rounds/0001/HISTORY.md")
    assert "N" * 2000 + " [cut at 2000 characters; the whole message is archives/rounds/0001/RESULTS/PLAN-AGENTS-1.json]" in text
    assert "N" * 2001 not in text
