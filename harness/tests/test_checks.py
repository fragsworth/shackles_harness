"""Each mechanical check: the id, the revert, the routing."""
import json
import sys

import stub_agent
from fixtures import Repo
from shackles import pipeline

ALL_GATES = {g: 1 for g in pipeline.llm_gates()}
FOLDER = "harness/archives/rounds/0001"


def mechanical(r, step, attempt=1):
    return r.json(f"{FOLDER}/FINDINGS/{step}-{attempt}.mechanical.json")


def ids(findings):
    return [f["id"] for f in findings["findings"]]


def test_s1_artifact_messages(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    res = r.act(a, "bad_artifact")
    assert res.code == 0
    f = mechanical(r, "PLAN-AGENTS")
    assert ids(f) == ["S1"] and "shares.work sums to" in f["findings"][0]["quote"] and r.state()["failures"]["PLAN-AGENTS"] == 1
    prompt = open(r.next().json["prompt_file"], encoding="utf-8").read()
    assert "shares.work sums to" in prompt and '"source":"mechanical"' in prompt
    r2 = Repo(tmp_path / "b")
    r2.start()
    res = r2.play(until="PLAN-TO-SPEC")
    r2.act(res.json, "bad_artifact")
    f = mechanical(r2, "PLAN-TO-SPEC")
    assert ids(f) == ["S1"] and "overlap" in f["findings"][0]["quote"]


def test_s2_suite_partition(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.play(until="TESTS-TO-SUITE", auto_review=True)
    r.act(res.json, "bad_artifact")
    f = mechanical(r, "TESTS-TO-SUITE")
    assert ids(f) == ["S1"] and "appears 0 times" in f["findings"][0]["quote"]
    res = r.next()
    assert res.json["step"] == "TESTS-TO-SUITE" and res.json["attempt"] == 2
    assert "Test files changed this round under testPaths: [" in open(res.json["prompt_file"], encoding="utf-8").read()


def test_m1_stray_reverted_and_in_scope_kept(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    res = r.act(a, "stray")
    assert res.code == 0
    f = mechanical(r, "PLAN-AGENTS")
    assert ids(f) == ["M1"] and "stray.txt" in f["findings"][0]["quote"]
    assert not r.exists("stray.txt") and r.exists(f"{FOLDER}/AGENTS-PLAN.json") and r.dirty() == ""
    assert r.state()["failures"]["PLAN-AGENTS"] == 1


def test_m2_frozen_test_reverted(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True)
    before = r.read("tests/toy/test_text.py")
    res = r.act(res.json, "touch_tests")
    f = mechanical(r, "SPEC-TO-IMPLEMENTATION")
    assert ids(f) == ["M2"] and r.read("tests/toy/test_text.py") == before
    assert "whisper" in r.read("src/toy/text.py"), "the in-scope work is kept"


def test_upstream_reverts_out_of_scope_changes_with_a_record(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True)
    before = r.read("tests/toy/test_text.py")
    stub_agent.perform(res.json["prompt_file"], "touch_tests", {})
    stub_agent.write(r.root + "/harness", "../stray.txt", "STUB-STRAY\n")
    rec = r.record("SPEC-TO-IMPLEMENTATION", 1, {"status": "UPSTREAM", "target": "SPEC-TO-TESTS", "notes": "the tests are wrong"})
    assert rec.code == 0 and r.state()["step"] == "SPEC-TO-TESTS"
    assert r.read("tests/toy/test_text.py") == before and not r.exists("stray.txt") and r.dirty() == ""
    assert "SPEC-TO-IMPLEMENTATION attempt 1: UPSTREAM; out-of-scope changes reverted: tests/toy/test_text.py, stray.txt" in r.read(f"{FOLDER}/HISTORY.md")
    assert "whisper" in r.read("src/toy/text.py"), "the in-scope work is kept"


def test_m3_verify_red_and_timeout(tmp_path):
    r = Repo(tmp_path)
    r.start()
    res = r.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True)
    r.act(res.json, "break")
    f = mechanical(r, "SPEC-TO-IMPLEMENTATION")
    assert ids(f) == ["M3"] and "FAIL" in f["findings"][0]["quote"]
    slow = Repo(tmp_path / "slow")
    slow.start()
    env = {"STUB_VERIFY": json.dumps([sys.executable, "-c", "import time; time.sleep(30)"]), "STUB_VERIFY_TIMEOUT": "1"}
    res = slow.play(until="SPEC-TO-IMPLEMENTATION", auto_review=True, env=env)
    res = slow.act(res.json, "pass")
    f = mechanical(slow, "SPEC-TO-IMPLEMENTATION")
    assert ids(f) == ["M3"] and "timed out" in f["findings"][0]["quote"]


def test_m4_judgment_rewrite_restored(tmp_path):
    r = Repo(tmp_path)
    r.start()
    a = r.next().json
    r.act(a, "rewrite_judgment")
    f = mechanical(r, "PLAN-AGENTS")
    assert ids(f) == ["M4"]
    assert r.read(f"{FOLDER}/DEFINED_JUDGMENT_CALLS.md").startswith("# DEFINED JUDGMENT CALLS")


def test_m5_suite_red_at_cleanup(tmp_path):
    r = Repo(tmp_path, config={"suiteCommand": [sys.executable, "-c", "import sys; print('SUITE-RED'); sys.exit(1)"]})
    r.start()
    res = r.play(until="CLEANUP", auto_review=True)
    r.act(res.json, "pass")
    f = mechanical(r, "CLEANUP")
    assert ids(f) == ["M5"] and "SUITE-RED" in f["findings"][0]["quote"]


def test_w2_prompt_size_warning(tmp_path):
    r = Repo(tmp_path, config={"promptTokenWarn": 10})
    r.start()
    a = r.next().json
    assert any(w.startswith("W2") for w in a["warnings"])
    assert "W2" in r.read(f"{FOLDER}/HISTORY.md")


def test_judgment_counts_per_attempt_and_gate_lines_via_runner(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    res = r.play(until="PLAN-AGENTS-GATE", env={"STUB_JUDGMENT": "2,1"})
    st = r.state()
    assert st["judgment_calls"] == {"defined": 2, "undefined": 1}
    assert "judgment calls +2 defined, +1 undefined" in r.read(f"{FOLDER}/HISTORY.md")
    r.act(res.json, "judgment")
    assert "STUB-GATE-DEFINED (via runner, PLAN-AGENTS-GATE-1)" in r.read(f"{FOLDER}/DEFINED_JUDGMENT_CALLS.md")
    assert "STUB-GATE-UNDEFINED (via runner, PLAN-AGENTS-GATE-1)" in r.read(f"{FOLDER}/UNDEFINED_JUDGMENT_CALLS.md")
    assert r.state()["judgment_calls"] == {"defined": 3, "undefined": 2}
    status = r.run("status").json
    assert status["undefined_tail"][-1].startswith("- STUB-GATE-UNDEFINED")
    res = r.play(modes={"PLAN-TO-SPEC:1": "blocked"})
    assert res.json["checkpoint"]["kind"] == "blocked"
    assert "undefined 2 (2 undefined since the last checkpoint)" in res.json["message"] and "STUB-GATE-UNDEFINED" in res.json["message"]
    assert res.json["undefined_file"].endswith("UNDEFINED_JUDGMENT_CALLS.md")


def test_gate_verdict_is_authoritative(tmp_path):
    r = Repo(tmp_path, gates=ALL_GATES)
    r.start()
    res = r.play(until="PLAN-AGENTS-GATE")
    r.act(res.json, "inconsistent")
    verdict = r.json(f"{FOLDER}/FINDINGS/PLAN-AGENTS-GATE-1.json")
    assert verdict["verdict"] == "PASS" and verdict["findings"][0]["blocking"] is False
    assert "set non-blocking (the verdict is authoritative)" in r.read(f"{FOLDER}/HISTORY.md")
    assert r.state()["step"] == "PLAN-TO-SPEC" and r.state()["carried"][0]["id"] == "F1"
