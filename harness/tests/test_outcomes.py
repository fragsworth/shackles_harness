"""Every routing row: verdicts, disputes, questions, upstream, blocked, limits, infra, recovery."""
import json
import os
import sys

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
    res = r.play(until="PLAN-TO-SPEC", modes={"PLAN-AGENTS:2": "prose_wrapped"})
    assert res.json["step"] == "PLAN-TO-SPEC", "prose around a message that carries resolutions is tolerated (R2-M1)"
    st = r.state()
    assert st["findings_ledger"]["F1"]["status"] == "fixed" and st["findings_ledger"]["F1"]["resolution"]["status"] == "fixed"
    assert st["infra_errors"] == {}
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
    r3 = Repo(tmp_path / "c", gates=ALL_GATES)
    r3.start()
    res = r3.play(until="PLAN-TO-SPEC-GATE", modes={"PLAN-AGENTS:1": "needs_owner", "PLAN-AGENTS-GATE:1": "pass"})
    assert res.json["step"] == "PLAN-TO-SPEC-GATE" and r3.state()["pending_question"] is None, "a PASS without a ruling settles the question"
    assert "no ruling on the producer's question; the assumption stands" in history(r3)
    assert "PLAN-AGENTS assumed: " + stub_agent.ASSUMPTION in r3.read(f"{FOLDER}/UNDEFINED_JUDGMENT_CALLS.md")
    assert stub_agent.QUESTION not in open(res.json["prompt_file"], encoding="utf-8").read(), "a later gate is not asked to rule on it"


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
    res = d.play(modes={"PLAN-AGENTS:1": "needs_owner"})
    assert res.code == 10 and res.json["checkpoint"]["kind"] == "question" and res.json["checkpoint"]["step"] == "PLAN-AGENTS", \
        "delegation skips only reviews: with no gate to weigh it, the question stops the round (R5-M1)"
    assert stub_agent.QUESTION in res.json["message"] and stub_agent.ASSUMPTION in res.json["message"]
    assert any(" override --steps " in c for c in res.json["resume"]), "override is offered at a question (R5-m4)"
    assert "assumed" not in d.read(f"{FOLDER}/UNDEFINED_JUDGMENT_CALLS.md") and d.state()["judgment_calls"]["undefined"] == 0, "the runner settles nothing"
    assert "NEEDS-OWNER -> the round pauses for the owner; their answer returns to you as a finding" in d.read(f"{FOLDER}/PROMPTS/PLAN-AGENTS-1.txt")
    assert d.run("status").json["checkpoint"]["kind"] == "question"
    assert d.run("answer", "--text", "use blue", "--quote", "use blue").code == 0
    res = d.play(until="PLAN-AGENTS:2")
    assert res.json["attempt"] == 2 and "use blue" in open(res.json["prompt_file"], encoding="utf-8").read()
    o1 = [e for k, e in d.state()["findings_ledger"].items() if k.startswith("O1")]
    assert o1 and o1[0]["source"] == "owner" and o1[0]["quote"] == "use blue"


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
    h = history(r)
    assert h.index("PLAN-TO-SPEC attempt 1: BLOCKED") < h.index("CHECKPOINT blocked at PLAN-TO-SPEC"), "the attempt entry precedes the checkpoint it raised (R3-n5)"
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
    r2 = Repo(tmp_path / "b", gates=ALL_GATES, config={"maxFailuresBeforeStop": 2})
    r2.start()
    res = r2.play(modes={"PLAN-AGENTS-GATE": "fail"})
    assert res.json["checkpoint"]["kind"] == "failure-limit"
    res = r2.run("override", "--steps", "PLAN-AGENTS-GATE", "--quote", "skip the gate")
    assert res.code == 10 and res.json["kind"] == "checkpoint", "overriding another step keeps the checkpoint; approve follows"
    assert "overrides recorded; the checkpoint at PLAN-AGENTS stands: approve to resume" in res.json["warnings"]
    res = r2.run("override", "--steps", "PLAN-AGENTS", "--quote", "skip the step")
    assert res.code == 0 and res.json["kind"] == "resumed" and res.json["status"] == "active", "overriding the checkpoint's own step resumes"
    res = r2.play(until="PLAN-TO-SPEC")
    assert res.json["step"] == "PLAN-TO-SPEC" and r2.state()["attempts"]["PLAN-AGENTS"] == 2, "no third attempt ran"
    assert r2.json(f"{FOLDER}/FINDINGS/PLAN-AGENTS-GATE-3.json")["source"] == "override"


def test_override_at_a_review_checkpoint_stands_until_approve(tmp_path):
    """A review's own step is already accepted; another override is recorded, the checkpoint reprinted with a note, and approve resumes (R3-m6)."""
    r = Repo(tmp_path)
    r.start()
    res = r.play()
    assert res.json["checkpoint"]["kind"] == "review" and res.json["checkpoint"]["step"] == "PLAN-TO-SPEC-GATE"
    res = r.run("override", "--steps", "PLAN-TO-SPEC-GATE", "--quote", "skip the spec gate")
    assert res.code == 2 and "already accepted" in res.json["error"]
    res = r.run("override", "--steps", "SPEC-TO-TESTS-GATE", "--quote", "skip the tests gate")
    assert res.code == 10 and res.json["kind"] == "checkpoint" and r.state()["status"] == "checkpoint"
    assert "overrides recorded; the checkpoint at PLAN-TO-SPEC-GATE stands: approve to resume" in res.json["warnings"]
    res = r.run("approve", "--quote", "skip the tests gate")
    assert res.code == 0 and res.json["kind"] == "resumed"
    res = r.play(until="SPEC-TO-IMPLEMENTATION")
    assert res.json["step"] == "SPEC-TO-IMPLEMENTATION" and r.json(f"{FOLDER}/FINDINGS/SPEC-TO-TESTS-GATE-1.json")["source"] == "override"


def test_override_settles_or_drops_the_producers_open_question(tmp_path):
    """An override of the producer drops its question, of the gate it waits at settles it as an undefined call; no later gate is asked it (R4-M2);
    an overridden PLAN-AGENTS means default shares and rungs even after a recorded attempt (R4-n9)."""
    r = Repo(tmp_path, gates={"SPEC-TO-TESTS-GATE": 1})
    r.start()
    res = r.play(modes={"PLAN-AGENTS:1": "needs_owner"}, env={"STUB_RUNG": "low"})
    assert res.json["checkpoint"]["kind"] == "question" and res.json["checkpoint"]["step"] == "PLAN-AGENTS"
    res = r.run("override", "--steps", "PLAN-AGENTS", "--quote", "skip it")
    assert res.code == 0 and res.json["kind"] == "resumed"
    res = r.play(until="PLAN-TO-SPEC")
    assert res.json["step"] == "PLAN-TO-SPEC" and res.json["agent"] == "max", "the recorded plan named low; overridden, the defaults apply"
    assert r.state()["pending_question"] is None and "PLAN-AGENTS overridden: its open question is dropped" in history(r)
    res = r.play(until="SPEC-TO-TESTS-GATE", auto_review=True)
    assert res.json["step"] == "SPEC-TO-TESTS-GATE"
    prompt = open(res.json["prompt_file"], encoding="utf-8").read()
    assert stub_agent.QUESTION not in prompt and "The producer's question, if any: none" in prompt
    rec = r.act(res.json, "pass")
    assert rec.code == 0 and not any("no ruling" in w for w in rec.json["warnings"])
    assert "assumed" not in r.read(f"{FOLDER}/UNDEFINED_JUDGMENT_CALLS.md") and r.state()["judgment_calls"]["undefined"] == 0
    r2 = Repo(tmp_path / "b", gates=ALL_GATES)
    r2.start(extra=["--delegate"])
    res = r2.play(until="PLAN-AGENTS-GATE", modes={"PLAN-AGENTS:1": "needs_owner"})
    assert res.json["step"] == "PLAN-AGENTS-GATE" and r2.state()["pending_question"]
    res = r2.run("override", "--steps", "PLAN-AGENTS", "--quote", "skip the step")
    assert res.code == 2 and res.json["error"] == "PLAN-AGENTS already ran; its gate PLAN-AGENTS-GATE is pending: override the gate instead", "R4-m5"
    res = r2.run("override", "--steps", "PLAN-AGENTS-GATE", "--quote", "skip the gate")
    assert res.code == 0
    res = r2.play(until="PLAN-TO-SPEC-GATE")
    assert res.json["step"] == "PLAN-TO-SPEC-GATE" and r2.state()["pending_question"] is None
    assert r2.json(f"{FOLDER}/FINDINGS/PLAN-AGENTS-GATE-1.json")["source"] == "override"
    line = f"- PLAN-AGENTS assumed: {stub_agent.ASSUMPTION} (runner: PLAN-AGENTS-GATE skipped (override); question: {stub_agent.QUESTION})"
    assert line in r2.read(f"{FOLDER}/UNDEFINED_JUDGMENT_CALLS.md").splitlines() and r2.state()["judgment_calls"]["undefined"] == 1
    assert "PLAN-AGENTS's question stands on its assumption: PLAN-AGENTS-GATE was skipped" in history(r2)
    assert stub_agent.QUESTION not in open(res.json["prompt_file"], encoding="utf-8").read()


def test_override_of_the_pending_step_discards_its_unrecorded_work(tmp_path):
    """Overriding the step whose attempt is pending reverts the agent's unrecorded files instead of committing them unchecked (R4-M1)."""
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    stub_agent.perform(a["prompt_file"], "pass", {"STUB_RUNG": "low"})
    assert r.exists(f"{FOLDER}/AGENTS-PLAN.json")
    res = r.run("override", "--steps", "PLAN-AGENTS", "--quote", "skip the agents plan")
    assert res.code == 0 and r.dirty() == "" and not r.exists(f"{FOLDER}/AGENTS-PLAN.json")
    assert r.log()[0] == "round 0001: override at active" and "AGENTS-PLAN.json" not in r.git("show", "--stat", "--format=", "HEAD")
    assert "override: unrecorded work of PLAN-AGENTS attempt 1 discarded: harness/archives/rounds/0001/AGENTS-PLAN.json" in history(r)
    res = r.next()
    assert res.json["step"] == "PLAN-TO-SPEC" and res.json["agent"] == "max", "skipped with defaults, not with the unrecorded plan"
    assert "PLAN-AGENTS" not in r.state()["attempts"] and r.state()["attempt_pending"]["step"] == "PLAN-TO-SPEC"
    d = Repo(tmp_path / "d")
    d.start(extra=["--delegate"])
    res = d.play(until="CLEANUP")
    stub_agent.perform(res.json["prompt_file"], "stray", {})
    d.append("src/toy/text.py", "\n\ndef unchecked():\n    return 1\n")
    res = d.run("override", "--steps", "CLEANUP", "--quote", "skip cleanup")
    assert res.code == 0 and d.dirty() == "" and not d.exists("stray.txt") and "unchecked" not in d.read("src/toy/text.py")
    line = [l for l in history(d).splitlines() if "unrecorded work of CLEANUP attempt 1 discarded" in l][0]
    assert "src/toy/text.py" in line and "stray.txt" in line
    res = d.play()
    assert res.json["kind"] == "done" and d.state()["landed_at"] and "CLEANUP" not in d.state()["attempts"]
    assert not d.exists("stray.txt") and "unchecked" not in d.read("src/toy/text.py") and "CLEANUP overridden: skipped with defaults" in history(d)
    assert not d.exists(f"{FOLDER}/FINDINGS/CLEANUP-1.mechanical.json") and "M1" not in history(d), "nothing was checked because nothing was kept"


def test_override_of_another_step_is_refused_while_an_attempt_has_unrecorded_work(tmp_path):
    """An override that does not name the pending step would commit that attempt's unrecorded work unchecked through the owner command's
    commit: it is refused until the work is recorded, and M1 then judges it (R5-M3); between record and next it goes through."""
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    message = stub_agent.perform(a["prompt_file"], "stray", {})
    res = r.run("override", "--steps", "TESTS-TO-SUITE", "--quote", "skip the suite step")
    assert res.code == 2 and res.json["error"].startswith("PLAN-AGENTS attempt 1 has unrecorded work (") and \
        res.json["error"].endswith("): record it first, or override PLAN-AGENTS to discard it")
    assert f"{FOLDER}/AGENTS-PLAN.json" in res.json["error"] and "stray.txt" in res.json["error"]
    assert r.exists("stray.txt") and r.exists(f"{FOLDER}/AGENTS-PLAN.json") and r.log()[0] == "round 0001: PLAN-AGENTS attempt 1 prompt"
    assert r.state()["overrides"] == [] and "RESUME" not in history(r)
    rec = r.record("PLAN-AGENTS", 1, message)
    f = r.json(f"{FOLDER}/FINDINGS/PLAN-AGENTS-1.mechanical.json")
    assert rec.code == 0 and [x["id"] for x in f["findings"]] == ["M1"] and "stray.txt" in f["findings"][0]["quote"], "the stray was judged, not swept in"
    assert not r.exists("stray.txt") and r.git("ls-files", "stray.txt") == "" and r.exists(f"{FOLDER}/AGENTS-PLAN.json")
    res = r.run("override", "--steps", "TESTS-TO-SUITE", "--quote", "skip the suite step")
    assert res.code == 0 and res.json["kind"] == "resumed" and r.state()["overrides"] == ["TESTS-TO-SUITE"] and r.dirty() == ""
    assert r.next().json["step"] == "PLAN-AGENTS" and r.state()["attempt_pending"]["attempt"] == 2


def test_a_refused_owner_command_leaves_no_trace(tmp_path):
    """A refusal raised after the quote was appended undoes the OWNER.log line and the RESUME entry: the pending attempt's record sees no M1
    on the runner's own files (R8b) and the next `next` counts no infrastructure error (R8a) (R5-M2); a resumed payload carries warnings (R5-m7)."""
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    message = stub_agent.perform(a["prompt_file"], "pass", {})
    res = r.run("override", "--steps", "LANDING", "--quote", "skip landing")
    assert res.code == 2 and "cannot be overridden" in res.json["error"]
    assert r.dirty().splitlines() == [f"?? {FOLDER}/AGENTS-PLAN.json"] and "RESUME" not in history(r), "only the agent's own work is dirty"
    rec = r.record("PLAN-AGENTS", 1, message)
    assert rec.code == 0 and rec.json["next_step"] == "PLAN-AGENTS-GATE" and r.state()["failures"] == {} and "M1" not in history(r)
    res = r.run("override", "--steps", "PLAN-AGENTS", "--quote", "skip it")
    assert res.code == 2 and "its gate PLAN-AGENTS-GATE is pending" in res.json["error"] and r.dirty() == ""
    res = r.next()
    assert res.code == 0 and res.json["step"] == "PLAN-TO-SPEC" and r.state()["infra_errors"] == {} and "dirty tree reset" not in history(r)
    res = r.run("override", "--steps", "POSTMORTEM", "--quote", "skip the postmortem")
    assert res.code == 0 and res.json["kind"] == "resumed" and res.json["warnings"] == ["override: quote recorded unverified (no owner log)"]
    slice_text = r.read(f"{FOLDER}/OWNER.log")
    assert "skip the postmortem" in slice_text and "skip landing" not in slice_text and "skip it" not in slice_text
    assert history(r).count("RESUME") == 1


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
    st = r.state()
    assert st["step"] == "PLAN-AGENTS-GATE" and st["failures"] == {} and "M0" not in history(r), "the runner's own commits are not an agent's"
    assert r.exists(f"{FOLDER}/RESULTS/PLAN-AGENTS-1.raw-1.txt") and "INVALID RESULT" in history(r)
    res = r.next()
    assert res.json["step"] == "PLAN-TO-SPEC" and r.act(res.json, "prose_wrapped").code == 0


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
    note = [l for l in history(r).splitlines() if l.startswith("## ") and "dirty tree reset" in l][-1]
    assert "harness/AGENTS.md" in note and "harness/junk.txt" in note and "src/toy/junk.py" in note, "the reset names what it reverted"


def test_pending_work_refused_without_discard(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    stub_agent.perform(a["prompt_file"], "pass", {})
    r.write("stray.txt", "a stray beside the in-scope work\n")
    res = r.next()
    assert res.code == 2 and "record it, or next --discard" in res.json["error"]
    assert r.exists(f"{FOLDER}/AGENTS-PLAN.json") and r.exists("stray.txt"), "a stray never turns the refusal into a reset of the work"
    assert r.state()["infra_errors"] == {}
    res = r.next("--discard")
    assert res.code == 0 and not r.exists(f"{FOLDER}/AGENTS-PLAN.json") and res.json["attempt"] == 1
    assert r.exists("stray.txt"), "the reset is scoped to harness/ and the living paths"


def test_reaccepted_spec_is_not_an_out_of_band_edit(tmp_path):
    r = Repo(tmp_path)
    r.start(extra=["--delegate"])
    res = r.play(until="SPEC-TO-TESTS")
    res = r.act(res.json, "upstream", env={"STUB_TARGET": "PLAN-TO-SPEC"})
    assert res.code == 0 and r.state()["step"] == "PLAN-TO-SPEC" and r.state()["round_retries"] == 1
    res = r.play(until="SPEC-TO-TESTS", env={"STUB_VERIFY_TIMEOUT": "121"})
    assert res.json["step"] == "SPEC-TO-TESTS" and res.json["attempt"] == 2 and r.json(f"{FOLDER}/SPEC.json")["verifyTimeoutSeconds"] == 121
    res = r.next()
    assert res.json["step"] == "SPEC-TO-TESTS" and res.json["attempt"] == 2 and r.state()["round_retries"] == 1
    assert "SPEC changed out of band" not in history(r)


def test_findings_omitted_from_resolutions_count_as_fixed(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    res = r.play(until="PLAN-AGENTS:2", modes={"PLAN-AGENTS-GATE:1": "fail"})
    obj = json.loads(stub_agent.perform(res.json["prompt_file"], "pass", {}))
    assert obj.pop("resolutions") == {"F1": {"status": "fixed", "reason": "stub fixed"}}
    rec = r.record("PLAN-AGENTS", 2, obj)
    assert rec.code == 0 and r.state()["step"] == "PLAN-AGENTS-GATE"
    e = r.state()["findings_ledger"]["F1"]
    assert e["status"] == "fixed" and e["resolution"] == {"status": "fixed", "reason": "omitted from resolutions"}
    assert "findings omitted from resolutions count as fixed: F1" in history(r)


def test_gate_inputs_name_the_producers_own_attempt(tmp_path):
    r = Repo(tmp_path, gates={"PLAN-AGENTS-GATE": 1})
    r.start()
    res = r.play(until="PLAN-AGENTS-GATE", modes={"PLAN-AGENTS:1": "bad_artifact"})
    assert res.json["step"] == "PLAN-AGENTS-GATE" and res.json["attempt"] == 1 and r.state()["attempts"]["PLAN-AGENTS"] == 2
    prompt = open(res.json["prompt_file"], encoding="utf-8").read()
    assert "RESULTS/PLAN-AGENTS-2.json" in prompt and "RESULTS/PLAN-AGENTS-1.json" not in prompt


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


GUARD_SUITE = [sys.executable, "src/run.py", "spec", "status"]  # the baseline guard as the permanent suite, as on the real repository
PROSE = "harness/locked_prose/COMMON-OVERVIEW.txt"


def test_spec_edit_keeps_the_branch_guard_green_until_the_owner_accepts(tmp_path):
    r = Repo(tmp_path, config={"suiteCommand": GUARD_SUITE})
    r.start(extra=["--delegate"])
    res = r.play(modes={"SPEC-TO-IMPLEMENTATION:1": "edit_spec"})
    assert res.json["kind"] == "checkpoint" and res.json["checkpoint"]["kind"] == "spec-edit", res
    assert not r.exists(f"{FOLDER}/FINDINGS/CLEANUP-1.mechanical.json") and r.state()["failures"] == {}, "M5 at CLEANUP is green on the branch"
    assert r.run("spec", "status").json["clean"] and r.dirty() == ""
    audit = [json.loads(l) for l in r.read("harness/archives/spec-changes.jsonl").splitlines() if l.strip()]
    assert "provisional" in audit[-1]["note"] and audit[-1]["changed"] == [PROSE]
    assert r.run("approve", "--quote", "accept the prose edit").code == 0
    assert "approved by the owner" in r.read("harness/archives/spec-changes.jsonl")
    res = r.play()
    assert res.json["kind"] == "done" and r.state()["landed_at"] and r.run("spec", "status").json["clean"]


def test_spec_edit_undone_later_in_the_round_needs_no_approval(tmp_path):
    r = Repo(tmp_path, config={"suiteCommand": GUARD_SUITE})
    r.start(extra=["--delegate"])
    before = r.read(PROSE)
    res = r.play(until="CLEANUP", modes={"SPEC-TO-IMPLEMENTATION:1": "edit_spec"})
    assert res.json["step"] == "CLEANUP" and r.state()["spec_edits"] == [PROSE]
    r.write(PROSE, before)
    rec = r.act(res.json, "pass")
    assert rec.code == 0, rec
    assert r.state()["spec_edits"] == [] and f"SPEC EDIT {PROSE} undone" in history(r)
    res = r.play()
    assert res.json["kind"] == "done" and r.state()["landed_at"] and r.run("spec", "status").json["clean"]


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
