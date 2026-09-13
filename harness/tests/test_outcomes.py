"""Every routing row: verdicts, disputes, questions, upstream, blocked, limits, infra, recovery."""
import json
import os

import pytest

import stub_agent
from fixtures import PLAN, Repo
from shackles import pipeline

ALL_GATES = {g: 1 for g in pipeline.llm_gates()}
FOLDER = "harness/archives/rounds/0001"


def history(r):
    return r.read(f"{FOLDER}/HISTORY.md")


def test_fail_reenters_with_findings_then_passes(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    res = r.play(until="PLAN-AGENTS:2", modes={"PLAN-AGENTS-GATE:1": "fail"})
    assert res.json["step"] == "PLAN-AGENTS" and res.json["attempt"] == 2
    st = r.state()
    assert st["failures"]["PLAN-AGENTS"] == 1 and st["findings_ledger"]["F1"]["status"] == "open"
    text = open(res.json["prompt_file"], encoding="utf-8").read()
    assert '"id": "F1"' in text.replace('"id":"F1"', '"id": "F1"') and stub_agent.FAIL_REASON in text
    assert r.json(f"{FOLDER}/FINDINGS/PLAN-AGENTS-GATE-1.json")["verdict"] == "FAIL"
    res = r.play(until="PLAN-TO-SPEC")
    assert res.json["step"] == "PLAN-TO-SPEC"
    st = r.state()
    assert st["findings_ledger"]["F1"]["status"] == "fixed" and st["findings_ledger"]["F1"]["resolution"]["status"] == "fixed"
    gate_prompt = r.read(f"{FOLDER}/PROMPTS/PLAN-AGENTS-GATE-2.txt")
    assert "Ids continue from F2" in gate_prompt and '"status":"fixed"' in gate_prompt


def test_dispute_upheld_twice_is_settled(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES, config={"maxFailuresBeforeStop": 6})
    r.start()
    modes = {"PLAN-AGENTS-GATE:1": "fail", "PLAN-AGENTS:2": "dispute", "PLAN-AGENTS-GATE:2": "uphold",
             "PLAN-AGENTS:3": "dispute", "PLAN-AGENTS-GATE:3": "uphold", "PLAN-AGENTS:4": "dispute"}
    res = r.play(until="PLAN-AGENTS:4", modes=modes)
    assert res.json["step"] == "PLAN-AGENTS" and res.json["attempt"] == 4
    e = r.state()["findings_ledger"]["F1"]
    assert e["upholds"] == 2 and e["status"] == "settled" and e["ruling"]["status"] == "upheld"
    res = r.play(until="PLAN-AGENTS-GATE:4", modes=modes)
    assert res.json["step"] == "PLAN-AGENTS-GATE"
    assert "dispute of F1 ignored: settled" in history(r)
    assert r.state()["findings_ledger"]["F1"]["status"] == "settled"
    prompt = open(res.json["prompt_file"], encoding="utf-8").read()
    assert '"status":"settled"' in prompt
    assert r.state()["failures"]["PLAN-AGENTS"] == 3


def test_withdrawn_finding_is_never_reraised(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    modes = {"PLAN-AGENTS-GATE:1": "fail", "PLAN-AGENTS:2": "dispute", "PLAN-AGENTS-GATE:2": "withdraw"}
    res = r.play(until="PLAN-TO-SPEC", modes=modes)
    assert res.json["step"] == "PLAN-TO-SPEC"
    assert r.state()["findings_ledger"]["F1"]["status"] == "withdrawn"
    r2 = Repo(tmp_path / "b", gates=ALL_GATES)
    r2.start()
    modes = {"PLAN-AGENTS-GATE:1": "fail", "PLAN-AGENTS:2": "dispute", "PLAN-AGENTS-GATE:2": "withdraw",
             "PLAN-TO-SPEC-GATE:1": "fail"}
    res = r2.play(until="PLAN-TO-SPEC:2", modes=modes)
    assert res.json["step"] == "PLAN-TO-SPEC"
    assert "re-raises a withdrawn finding; dropped" in history(r2)
    assert r2.json(f"{FOLDER}/FINDINGS/PLAN-TO-SPEC-GATE-1.json")["findings"] == []


def test_nonblocking_and_deferred_findings_are_carried_to_the_postmortem(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    modes = {"PLAN-AGENTS-GATE:1": "pass_nb", "PLAN-TO-SPEC-GATE:1": "fail", "PLAN-TO-SPEC:2": "deferred"}
    res = r.play(until="SPEC-TO-TESTS", modes=modes)
    if res.json.get("kind") == "checkpoint":
        r.owner_cmd("approve", "ok")
        res = r.play(until="SPEC-TO-TESTS", modes=modes)
    assert res.json["step"] == "SPEC-TO-TESTS"
    carried = r.state()["carried"]
    assert any(c["quote"] == stub_agent.NB_QUOTE for c in carried) and any(c["source"] == "deferred" for c in carried)
    prompt = open(res.json["prompt_file"], encoding="utf-8").read()
    assert stub_agent.NB_QUOTE in prompt and '"source":"deferred"' in prompt
    assert r.state()["findings_ledger"]["F2"]["status"] == "deferred"


def test_needs_owner_with_the_gate_enabled(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start(extra=["--delegate"])
    res = r.play(modes={"PLAN-AGENTS:1": "needs_owner", "PLAN-AGENTS-GATE:1": "q_uphold"})
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "question" and res.json["checkpoint"]["step"] == "PLAN-AGENTS"
    assert stub_agent.QUESTION in res.json["message"]
    res = r.run("answer", "--text", "use blue", "--quote", "use blue")
    assert res.code == 0
    res = r.play(until="PLAN-AGENTS:2")
    assert res.json["attempt"] == 2
    ledger = r.state()["findings_ledger"]
    o1 = [e for k, e in ledger.items() if k.startswith("O1")]
    assert o1 and o1[0]["source"] == "owner" and o1[0]["quote"] == "use blue"
    assert "use blue" in open(res.json["prompt_file"], encoding="utf-8").read()
    r2 = Repo(tmp_path / "b", gates=ALL_GATES)
    r2.start()
    res = r2.play(until="PLAN-TO-SPEC", modes={"PLAN-AGENTS:1": "needs_owner", "PLAN-AGENTS-GATE:1": "q_withdraw"})
    assert res.json["step"] == "PLAN-TO-SPEC"
    carried = r2.state()["carried"]
    assert carried and carried[0]["id"] == "Q1" and stub_agent.ANSWER in carried[0]["suggestion"]
    assert "withdrew the producer's question" in r2.read(f"{FOLDER}/DEFINED_JUDGMENT_CALLS.md")
    gate_prompt = r2.read(f"{FOLDER}/PROMPTS/PLAN-AGENTS-GATE-1.txt")
    assert stub_agent.QUESTION in gate_prompt and stub_agent.ASSUMPTION in gate_prompt


def test_needs_owner_with_the_gate_disabled(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.play(modes={"PLAN-AGENTS:1": "needs_owner"})
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "question"
    assert r.run("approve", "--quote", "go ahead").code == 0
    res = r.play(until="PLAN-AGENTS:2")
    assert res.json["attempt"] == 2 and "proceed on your stated assumption" in open(res.json["prompt_file"], encoding="utf-8").read()
    d = Repo(tmp_path / "d")
    d.start(extra=["--delegate"])
    res = d.play(until="PLAN-TO-SPEC", modes={"PLAN-AGENTS:1": "needs_owner"})
    assert res.json["step"] == "PLAN-TO-SPEC"
    undefined = d.read(f"{FOLDER}/UNDEFINED_JUDGMENT_CALLS.md")
    assert "PLAN-AGENTS attempt 1 assumed: " + stub_agent.ASSUMPTION in undefined and d.state()["judgment_calls"]["undefined"] == 1
    assert d.run("status").json["undefined_tail"][0].startswith("- PLAN-AGENTS attempt 1 assumed")


def test_upstream_to_each_earlier_producer_and_to_the_plan(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True)
    frozen = r.state()["tests_frozen_at"]
    assert frozen
    res = r.act(res.json, "upstream", env={"STUB_TARGET": "SPEC-TO-TESTS"})
    assert res.code == 0
    st = r.state()
    assert st["step"] == "SPEC-TO-TESTS" and st["round_retries"] == 1 and st["tests_frozen_at"] is None
    assert "SPEC-TO-TESTS-GATE" not in st["step_commits"] and "SPEC-TO-TESTS" not in st["step_commits"]
    assert st["attempts"]["SPEC-TO-TESTS"] == 1 and st["attempts"]["SPEC-TO-IMPLEMENTATION"] == 1, "attempt numbers never restart"
    u1 = [e for k, e in st["findings_ledger"].items() if k.startswith("U1")]
    assert u1 and u1[0]["step"] == "SPEC-TO-TESTS" and stub_agent.UPSTREAM_NOTES in u1[0]["quote"]
    res = r.next()
    assert res.json["step"] == "SPEC-TO-TESTS" and res.json["attempt"] == 2
    assert stub_agent.UPSTREAM_NOTES in open(res.json["prompt_file"], encoding="utf-8").read()
    res = r.act(res.json, "upstream", env={"STUB_TARGET": "PLAN-AGENTS"})
    assert r.state()["step"] == "PLAN-AGENTS" and r.state()["round_retries"] == 2
    res = r.play(until="PLAN-AGENTS:2")
    res = r.act(res.json, "upstream", env={"STUB_TARGET": "CHAT-TO-PLAN"})
    assert res.code == 10 and res.json["checkpoint"]["kind"] == "upstream-plan"
    assert r.run("approve", "--quote", "ok").code == 2, "the plan must change first"
    plan = r.json(f"{FOLDER}/PLAN.json")
    plan["summary"] = "PLAN-SUMMARY-MARKER: revised"
    r.write(f"{FOLDER}/PLAN.json", json.dumps(plan, indent=2))
    res = r.run("approve", "--quote", "approved the revised plan")
    assert res.code == 0 and r.state()["step"] == "CHAT-TO-PLAN-GATE" and r.state()["attempts"]["CHAT-TO-PLAN"] == 2
    res = r.next()
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "round-limit"
    assert r.run("approve", "--quote", "keep going").code == 0
    res = r.next()
    assert res.json["step"] == "PLAN-AGENTS" and res.json["attempt"] == 3
    res = r.act(res.json, "upstream", env={"STUB_TARGET": "POSTMORTEM"})
    assert res.code == 0 and r.state()["step"] == "PLAN-AGENTS" and r.state()["failures"]["PLAN-AGENTS"] == 1
    assert "S1" in json.dumps(r.json(f"{FOLDER}/FINDINGS/PLAN-AGENTS-3.mechanical.json"))


def test_blocked_checkpoint_and_answer(tmp_path):
    r = Repo(tmp_path)
    r.start(extra=["--delegate"])
    res = r.play(modes={"PLAN-TO-SPEC:1": "blocked"})
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "blocked" and stub_agent.BLOCKED_NOTES in res.json["message"]
    assert r.state()["failures"]["PLAN-TO-SPEC"] == 1
    assert r.run("answer", "--text", "only whisper", "--quote", "only whisper").code == 0
    res = r.next()
    assert res.json["step"] == "PLAN-TO-SPEC" and res.json["attempt"] == 2 and "only whisper" in open(res.json["prompt_file"], encoding="utf-8").read()


def test_failure_limit_and_approve_resets(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES, config={"maxFailuresBeforeStop": 2})
    r.start()
    res = r.play(modes={"PLAN-AGENTS-GATE": "fail"})
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "failure-limit"
    assert r.state()["failures"]["PLAN-AGENTS"] == 2
    assert r.run("approve", "--quote", "try again").code == 0
    assert r.state()["failures"]["PLAN-AGENTS"] == 0 and r.state()["status"] == "active"
    res = r.play(until="PLAN-TO-SPEC", modes={"PLAN-AGENTS-GATE:3": "pass"})
    assert res.json["step"] == "PLAN-TO-SPEC"


def test_hard_stop_raised_once(tmp_path):
    r = Repo(tmp_path, config={"hardStopBudgetMultiple": 1})
    r.start(extra=["--budget", "1"])
    res = r.play()
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "hard-stop"
    assert r.state()["hard_stop_raised"] is True
    assert r.run("approve", "--quote", "spend more").code == 0
    res = r.play()
    assert res.json.get("checkpoint", {}).get("kind") != "hard-stop"


def test_infra_path_garbage_then_checkpoint(tmp_path):
    r = Repo(tmp_path, config={"infraRetries": 2})
    r.start()
    a = r.next().json
    res = r.act(a, "garbage", cost=0.5)
    assert res.code == 2 and res.json["kind"] == "invalid"
    st = r.state()
    assert st["infra_errors"]["PLAN-AGENTS"] == 1 and st["attempts"].get("PLAN-AGENTS", 0) == 0 and st["attempt_pending"]["infra"] == 1
    assert any(e["usd"] == 0.5 and e["source"] == "agent-cli" for e in st["spend"]["entries"])
    assert r.exists(f"{FOLDER}/RESULTS/PLAN-AGENTS-1.raw-1.txt") and r.dirty() == ""
    again = r.next().json
    assert again["step"] == "PLAN-AGENTS" and again["attempt"] == 1 and again["prompt_file"] == a["prompt_file"]
    res = r.act(again, "garbage")
    assert res.code == 10 and res.json["checkpoint"]["kind"] == "infra"
    assert r.run("approve", "--quote", "retry").code == 0
    res = r.next()
    assert res.json["step"] == "PLAN-AGENTS" and res.json["attempt"] == 1
    assert r.act(res.json, "fence").code == 0 and r.state()["attempts"]["PLAN-AGENTS"] == 1
    res = r.next()
    assert r.act(res.json, "prose_wrapped").code == 0


def test_m0_agent_commit_is_soft_reset(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    res = r.act(a, "commit")
    assert res.code == 0
    assert "M0: HEAD moved" in history(r) and "STUB-AGENT-COMMIT" not in r.log()
    assert r.exists(f"{FOLDER}/AGENTS-PLAN.json") and r.state()["step"] == "PLAN-AGENTS-GATE"


def test_g1_gate_that_writes_is_discarded(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    res = r.play(until="PLAN-AGENTS-GATE")
    res = r.act(res.json, "dirty")
    assert res.code == 2 and "G1" in res.json["errors"][0]
    assert not r.exists("gate-wrote-this.txt") and r.dirty() == "" and r.state()["infra_errors"]["PLAN-AGENTS-GATE"] == 1
    assert r.next().json["step"] == "PLAN-AGENTS-GATE"


def test_dirty_tree_recovery_is_scoped_and_counted(tmp_path):
    r = Repo(tmp_path)
    r.start()
    r.play(until="PLAN-TO-SPEC")
    r.write("harness/junk.txt", "stray")
    r.write("src/toy/junk.py", "stray")
    r.write("outside.txt", "survives")
    r.write("harness/AGENTS.md", r.read("harness/AGENTS.md") + "edited\n")
    res = r.next()
    assert res.code == 2 and "uncommitted work" in res.json["error"] or res.code == 0
    res = r.next("--discard")
    assert res.code == 0
    assert not r.exists("harness/junk.txt") and not r.exists("src/toy/junk.py") and r.exists("outside.txt")
    assert "edited" not in r.read("harness/AGENTS.md")
    assert r.state()["infra_errors"]["PLAN-TO-SPEC"] >= 1


def test_pending_work_refused_without_discard(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    stub_agent.perform(a["prompt_file"], "pass", {})
    res = r.next()
    assert res.code == 2 and "record it, or next --discard" in res.json["error"]
    assert r.exists(f"{FOLDER}/AGENTS-PLAN.json")
    res = r.next("--discard")
    assert res.code == 0 and not r.exists(f"{FOLDER}/AGENTS-PLAN.json") and res.json["attempt"] == 1


def test_out_of_band_plan_and_spec_edits(tmp_path):
    r = Repo(tmp_path)
    r.start()
    r.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True)
    r.append(f"{FOLDER}/SPEC.md", "\nowner edit\n")
    r.git("commit", "-q", "-am", "owner edits the spec")
    res = r.next()
    st = r.state()
    assert res.json["step"] == "SPEC-TO-TESTS" and res.json["attempt"] == 2 and st["round_retries"] == 1 and st["tests_frozen_at"] is None
    assert "SPEC changed out of band" in history(r)
    plan = r.json(f"{FOLDER}/PLAN.json")
    plan["scope"].append("more")
    r.write(f"{FOLDER}/PLAN.json", json.dumps(plan, indent=2))
    r.git("commit", "-q", "-am", "owner edits the plan")
    res = r.next()
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "approval"
    assert r.state()["round_retries"] == 2 and r.state()["approval"] is None
    assert r.run("approve", "--quote", "approved again").code == 0
    res = r.next()
    assert res.json["step"] == "PLAN-AGENTS" and res.json["attempt"] == 2


def test_in_round_spec_edit_is_flagged_and_checkpointed_even_when_delegated(tmp_path):
    r = Repo(tmp_path)
    r.start(extra=["--delegate"])
    res = r.play(modes={"PLAN-TO-SPEC:1": "edit_spec"})
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "spec-edit" and res.json["checkpoint"]["step"] == "LANDING"
    st = r.state()
    assert st["spec_edits"] == ["harness/locked_prose/COMMON-OVERVIEW.txt"]
    assert "SPEC EDIT harness/locked_prose/COMMON-OVERVIEW.txt" in history(r) and "+STUB-SPEC-EDIT" in history(r)
    assert "STUB-SPEC-EDIT" in res.json["message"]
    assert r.run("approve", "--quote", "accept the prose edit").code == 0
    assert r.run("spec", "status").json["clean"]
    res = r.play()
    assert res.json["kind"] == "done" and r.state()["landed_at"]


def test_crash_recovery(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    r.git("reset", "-q", "--soft", "HEAD~1")
    r.git("reset", "-q")
    res = r.next()
    assert res.code == 0 and res.json["prompt_file"] == a["prompt_file"] and r.log()[0] == "round 0001: PLAN-AGENTS attempt 1 prompt"
    message = stub_agent.perform(a["prompt_file"], "pass", {})
    open(a["result_file"], "w", encoding="utf-8").write(message)
    res = r.record("PLAN-AGENTS", 1, message)
    assert res.code == 0 and r.state()["attempts"]["PLAN-AGENTS"] == 1
