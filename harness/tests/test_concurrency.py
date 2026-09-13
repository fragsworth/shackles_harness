"""Claims, worktrees, the fence, landing against a moving main, conflicts and sync_main, on a local bare origin."""
import json
import os

import pytest

import stub_agent
from fixtures import PLAN, Repo
from shackles import gitops, procs

pytestmark = pytest.mark.slow
FOLDER = "harness/archives/rounds/0001"


def with_origin(tmp_path, **kw):
    r = Repo(tmp_path, **kw)
    r.add_origin()
    return r


def start_wt(r, **kw):
    res = r.start(no_branch=False, **kw)
    assert res.code == 0, res
    return res, r.view(res.json["worktree"])


def assert_nothing_created(r, rid="0001"):
    assert not os.path.exists(os.path.join(r.root, ".claude", "worktrees", f"round-{rid}"))
    assert f"round/{rid}" not in r.git("branch", "--list", "--format=%(refname:short)").split()
    assert r.git("log", "--all", "--format=%s", "--", f"harness/archives/rounds/{rid}") == ""
    assert r.dirty() == "" and r.git("rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_claim_creates_the_worktree_on_the_claimed_branch(tmp_path):
    r = with_origin(tmp_path)
    head = r.head()
    res, v = start_wt(r)
    out = res.json
    assert out["branch"] == "round/0001" and out["worktree"].endswith(os.path.join(".claude", "worktrees", "round-0001"))
    assert gitops.current_branch(v.root) == "round/0001"
    assert v.git("rev-parse", "HEAD~1") == r.origin.sha("main") == head
    assert r.origin.sha("round/0001") == v.head()
    assert r.head() == head and r.dirty() == "" and not os.path.exists(os.path.join(r.root, FOLDER))
    assert not os.path.exists(os.path.join(v.root, "harness", "OWNER.log"))
    assert v.state()["mode"] == "worktree" and v.state()["branch"] == "round/0001"


def test_lost_race_takes_the_next_id_and_creates_nothing_for_the_lost_one(tmp_path):
    r = with_origin(tmp_path)
    start_wt(r)
    b = r.clone("b")
    b.git("config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
    res, vb = start_wt(b)
    assert res.json["branch"] == "round/0002" and res.json["id"] == "0002"
    assert_nothing_created(b, "0001")
    assert sorted(r.origin.branches()) == ["main", "round/0001", "round/0002"]


def test_reject_all_hook_bounds_the_claim_loop(tmp_path):
    r = with_origin(tmp_path, config={"pushAttempts": 3})
    r.origin.install_reject_hook("refs/heads/round/*", "all")
    res = r.start(no_branch=False)
    assert res.code == 1 and res.json["error"] == "round id: push rejected 3 times, last round/0003"
    assert r.origin.hook_log() == ["refs/heads/round/0001", "refs/heads/round/0002", "refs/heads/round/0003"]
    assert r.origin.branches() == ["main"]
    assert_nothing_created(r)


def test_explicit_branch_taken_pushes_once(tmp_path):
    r = with_origin(tmp_path)
    r.origin.install_reject_hook("refs/heads/*", "all")
    res = r.start(no_branch=False, extra=["--branch", "round/0007"])
    assert res.code == 2 and "round id taken" in res.json["error"]
    assert r.origin.hook_log() == ["refs/heads/round/0007"]
    assert_nothing_created(r, "0007")


def test_worktree_add_failure_keeps_the_claim(tmp_path):
    r = with_origin(tmp_path)
    blocker = os.path.join(r.root, ".claude", "worktrees", "round-0001")
    os.makedirs(blocker)
    procs.write_text(os.path.join(blocker, "junk"), "x")
    res = r.start(no_branch=False)
    assert res.code == 2 and "already exists" in res.json["error"]
    assert r.origin.branches() == ["main", "round/0001"]
    res = r.start(no_branch=False)
    assert res.code == 0 and res.json["id"] == "0002"


def test_id_sourcing_ignores_malformed_branches_and_tags(tmp_path):
    r = with_origin(tmp_path)
    for name in ("round/003-x", "round/abc", "round/0002"):
        r.git("push", "-q", "origin", f"main:refs/heads/{name}")
    r.git("tag", "round/0009-landed")
    r.git("push", "-q", "origin", "--tags")
    res, v = start_wt(r)
    assert res.json["id"] == "0003"


def test_preconditions(tmp_path):
    r = Repo(tmp_path)
    res = r.start(no_branch=False)
    assert res.code == 2 and "no origin" in res.json["error"]
    r.add_origin()
    r.write(".gitignore", "harness/OWNER.log\n")
    r.git("commit", "-q", "-am", "drop the worktree ignore")
    res = r.start(no_branch=False)
    assert res.code == 2 and "not gitignored" in res.json["error"]
    assert_nothing_created(r)


def test_worktree_round_reads_the_owner_log_from_main_and_pushes_from_the_worktree(tmp_path):
    r = with_origin(tmp_path)
    r.owner("thinking", at="2026-01-01T00:30:00Z")
    res, v = start_wt(r)
    assert "thinking" in v.read(FOLDER + "/OWNER.log")
    a = v.next().json
    assert a["worktree"] == v.root and a["runner"] == os.path.join(v.root, "harness", "src", "run.py")
    rec = v.act(a)
    assert rec.code == 0 and r.origin.sha("round/0001") == v.head()
    assert v.run("status").json["step"] == "PLAN-AGENTS-GATE"
    res = v.play()
    assert res.json["kind"] == "checkpoint"
    assert v.run("approve", "--quote", "not said").code == 2
    r.owner("approve the spec")
    assert v.run("approve", "--quote", "approve the spec").code == 0
    assert r.origin.sha("round/0001") == v.head()
    v.write(FOLDER + "/HISTORY.md", v.read(FOLDER + "/HISTORY.md") + "\nlocal note\n")
    v.git("commit", "-q", "-am", "an unpushed commit")
    assert r.origin.sha("round/0001") != v.head()
    assert v.next().code == 0 and r.origin.sha("round/0001") == v.head()


def test_fence_another_runner_owns_the_round(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    a = v.next().json
    b = r.clone("b")
    b.git("fetch", "-q", "origin")
    b.git("checkout", "-q", "round/0001")
    b.write("moved.txt", "another runner")
    b.git("add", "-A")
    b.git("commit", "-q", "-m", "another runner advances the round")
    b.git("push", "-q", "origin", "round/0001")
    rec = v.act(a)
    assert rec.code == 1 and rec.json["error"] == "another runner owns this round (push rejected)"


def sibling_pushes(r, rel, text, branch="main", clone="sib"):
    b = r.clone(clone)
    b.git("fetch", "-q", "origin")
    b.git("checkout", "-q", "main")
    b.write(rel, text)
    b.git("add", "-A")
    b.git("commit", "-q", "-m", f"sibling: {rel}")
    if branch != "main":
        b.git("push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    else:
        b.git("push", "-q", "origin", "main")
    return b


def to_landing(v, env=None):
    res = v.play(until="CLEANUP", auto_review=True, env=env)
    assert res.json["step"] == "CLEANUP", res
    rec = v.act(res.json)
    assert rec.code == 10 and rec.json["checkpoint"]["kind"] == "review", rec
    assert v.run("approve", "--quote", "land it").code == 0
    assert v.state()["step"] == "LANDING"


def test_landing_after_a_sibling_moved_main(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    to_landing(v, env={"STUB_ARCHIVE": "1"})
    sibling_pushes(r, "src/sibling.py", "SIBLING = 1\n")
    main_before = r.origin.sha("main")
    check = v.run("check")
    assert check.code == 0 and check.json["findings"] == []
    assert r.origin.sha("main") == main_before and "round/0001-landed" not in v.tags() and v.state()["landed_at"] is None
    assert not [e for e in v.state()["spend"]["entries"] if e["source"] == "living"]
    assert v.exists("src/sibling.py"), "check merges into the round worktree only"
    res = v.play(env={"STUB_ARCHIVE": "1"})
    assert res.json["kind"] == "done" and res.json["main_synced"] is True
    assert r.origin.sha("main") == v.head()
    assert v.exists("src/sibling.py") and "whisper" in v.read("src/toy/text.py")
    living = [e for e in v.state()["spend"]["entries"] if e["source"] == "living"]
    assert len(living) == 1 and "sibling" not in living[0]["note"] and living[0]["usd"] > 0
    assert v.state()["attempts"]["LANDING"] == 1
    assert "round/0001-landed" in r.origin.tags()
    r.git("pull", "-q", "--ff-only", "origin", "main")
    assert r.exists(FOLDER + "/POSTMORTEM.md") and r.exists("src/sibling.py")


def test_move_and_reject_once_retries_inside_one_next(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    to_landing(v)
    sibling_pushes(r, "src/sibling.py", "SIBLING = 1\n", branch="side")
    r.origin.install_move_and_reject_once_hook()
    res = v.next()
    assert res.code == 0 and res.json["step"] == "POSTMORTEM"
    st = v.state()
    assert st["attempts"]["LANDING"] == 1 and st["landed_at"]
    assert r.origin.hook_log() == ["refs/heads/main", "refs/heads/main"]
    assert v.exists("src/sibling.py") and r.origin.sha("main") == v.head()


def test_reject_all_on_main_leaves_the_round_at_landing(tmp_path):
    r = with_origin(tmp_path, config={"pushAttempts": 2})
    res, v = start_wt(r)
    to_landing(v)
    r.origin.install_reject_hook("refs/heads/main", "all")
    res = v.next()
    assert res.code == 1 and "landing: push of main rejected 2 times" in res.json["error"]
    st = v.state()
    assert st["step"] == "LANDING" and st["landed_at"] is None and "round/0001-landed" not in v.tags()
    assert not [e for e in st["spend"]["entries"] if e["source"] == "living"]
    r.origin.remove_hook()
    res = v.next()
    assert res.code == 0 and v.state()["landed_at"] and r.origin.sha("main") == v.head()


def conflicting_sibling(r):
    return sibling_pushes(r, "src/toy/text.py", "def shout(text):\n    return str(text).upper()\n")


def test_conflict_becomes_a_merge_attempt_that_converges(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    to_landing(v)
    conflicting_sibling(r)
    res = v.next()
    assert res.code == 0 and res.json["step"] == "SPEC-TO-IMPLEMENTATION" and res.json["attempt"] == 2
    st = v.state()
    l1 = v.json(FOLDER + "/FINDINGS/LANDING-1.mechanical.json")["findings"][0]
    assert l1["id"] == "L1" and "src/toy/text.py" in l1["quote"]
    assert st["merge_pending"]["conflicted"] == ["../src/toy/text.py"] and st["resume_step"] == "LANDING"
    assert st["failures"]["SPEC-TO-IMPLEMENTATION"] == 1 and st["round_retries"] == 1
    assert gitops.ref_exists(v.root, "MERGE_HEAD") and "<<<<<<<" in v.read("src/toy/text.py")
    dirty = [p for _, p in gitops.status_paths(v.root)]
    assert dirty and all(p == "src/toy/text.py" for p in dirty)
    prompt = open(res.json["prompt_file"], encoding="utf-8").read()
    assert 'MERGE_IN_PROGRESS: ["../src/toy/text.py"]' in prompt and '"../src/toy/text.py"' in prompt.split("WRITE_PATHS:")[1].splitlines()[0]
    again = v.next()
    assert again.json["prompt_file"] == res.json["prompt_file"] and gitops.ref_exists(v.root, "MERGE_HEAD")
    rec = v.act(again.json, "pass")
    assert rec.code == 0
    l3 = v.json(FOLDER + "/FINDINGS/SPEC-TO-IMPLEMENTATION-2.mechanical.json")["findings"]
    assert [f["id"] for f in l3] == ["L3"] and gitops.ref_exists(v.root, "MERGE_HEAD")
    res = v.next()
    assert res.json["attempt"] == 3
    stub_agent.write(v.root + "/harness", "../stray.txt", "STUB-STRAY\n")
    rec = v.act(res.json, "resolve")
    assert rec.code == 0, rec
    commit = v.git("log", "-1", "--format=%P", "--", ".")
    merge_commit = v.git("rev-list", "-n", "1", "--merges", "HEAD")
    assert merge_commit and not gitops.ref_exists(v.root, "MERGE_HEAD") and not v.exists("stray.txt")
    assert "M1" in json.dumps(v.json(FOLDER + "/FINDINGS/SPEC-TO-IMPLEMENTATION-3.mechanical.json")) or v.state()["step"] == "SPEC-TO-IMPLEMENTATION-GATE" or v.state()["step"] == "LANDING"
    res = v.play()
    assert res.json["kind"] == "done", res
    assert v.state()["landed_at"] and r.origin.sha("main") == v.head()
    text = v.read("src/toy/text.py")
    assert "whisper" in text and "str(text)" in text


def test_hand_merge_lands_without_a_command(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    to_landing(v)
    conflicting_sibling(r)
    v.git("fetch", "-q", "origin")
    v.git("merge", "--no-commit", "origin/main", check=False)
    v.write("src/toy/text.py", "def shout(text):\n    return str(text).upper()\n\n\ndef whisper(text):\n    return text.lower()\n")
    v.git("add", "-A")
    v.git("commit", "-q", "-m", "hand merge by the owner")
    res = v.play()
    assert res.json["kind"] == "done" and v.state()["landed_at"] and v.state()["round_retries"] == 0


def test_l2_reenters_implementation_from_the_merge_commit(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    to_landing(v)
    sibling_pushes(r, "tests/toy/test_more.py",
                   "import os, sys, unittest\nsys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src'))\n"
                   "from toy import text\n\n\nclass MoreTest(unittest.TestCase):\n    def test_yell(self):\n        self.assertEqual(text.yell('a'), 'A!')\n")
    res = v.next()
    assert res.code == 0 and res.json["step"] == "SPEC-TO-IMPLEMENTATION" and res.json["attempt"] == 2
    l2 = v.json(FOLDER + "/FINDINGS/LANDING-1.mechanical.json")["findings"][0]
    assert l2["id"] == "L2" and v.state()["merge_pending"] is None and not gitops.ref_exists(v.root, "MERGE_HEAD")
    assert v.git("rev-list", "-n", "1", "--merges", "HEAD"), "the merge commit stands"
    v.write("src/toy/text.py", v.read("src/toy/text.py") + "\n\ndef yell(text):\n    return text.upper() + '!'\n")
    msg = json.dumps({"status": "DONE", "notes": "added yell"})
    open(res.json["result_file"], "w", encoding="utf-8").write(msg)
    rec = v.run("record", "--step", "SPEC-TO-IMPLEMENTATION", "--attempt", "2", "--result", res.json["result_file"], "--cost", "0.01")
    assert rec.code == 0, rec
    res = v.play()
    assert res.json["kind"] == "done" and v.state()["landed_at"] and r.origin.sha("main") == v.head()


def test_two_rounds_land_and_their_index_lines_merge_through_the_union_attribute(tmp_path):
    r = with_origin(tmp_path)
    res1, v1 = start_wt(r)
    res2, v2 = start_wt(r)
    assert res2.json["id"] == "0002"
    res = v1.play(auto_review=True)
    assert res.json["kind"] == "done" and res.json["main_synced"] is True
    res = v2.play(auto_review=True)
    assert res.json["kind"] == "done" and res.json["main_synced"] is True, res
    r.git("pull", "-q", "--ff-only", "origin", "main")
    rows = [json.loads(l) for l in r.read("harness/archives/rounds/index.jsonl").splitlines() if l.strip()]
    assert sorted(row["id"] for row in rows) == [1, 2] and all(row["outcome"] == "landed" for row in rows)
    assert r.exists("harness/archives/rounds/0001/POSTMORTEM.md") and r.exists("harness/archives/rounds/0002/POSTMORTEM.md")
    assert v1.next().json["main_synced"] is True, "idempotent"
    report = r.run("rounds").json
    assert [row["id"] for row in report["rounds"]] == ["0001", "0002"] and all(row["landed"] for row in report["rounds"])
    assert len(report["worktrees"]) == 2


def test_sync_main_false_on_a_genuine_conflict(tmp_path):
    r = with_origin(tmp_path)
    res, v = start_wt(r)
    to_landing(v)
    res = v.play(until="POSTMORTEM")
    assert res.json["step"] == "POSTMORTEM" and v.state()["landed_at"]
    sibling_pushes(r, "harness/docs/TODO.md", "# TODO rewritten by a sibling\n")
    rec = v.act(res.json)
    assert rec.code == 0 and rec.json["kind"] == "recorded"
    res = v.next()
    assert res.json["kind"] == "done" and res.json["main_synced"] is False
    assert "tail commits arrive with the next landing" in v.read(FOLDER + "/HISTORY.md")
    assert not gitops.ref_exists(v.root, "MERGE_HEAD") and v.dirty() == ""


def test_w1_warns_about_a_live_sibling_declaring_the_same_paths(tmp_path):
    r = with_origin(tmp_path)
    res1, v1 = start_wt(r)
    res2, v2 = start_wt(r)
    v1.play(until="SPEC-TO-TESTS", auto_review=True)
    res = v2.play(until="PLAN-TO-SPEC")
    rec = v2.act(res.json)
    assert rec.code == 0
    carried = v2.state(2)["carried"]
    assert carried and carried[0]["id"] == "W1" and "round 0001" in carried[0]["quote"]
    prompt = open(v2.next().json["prompt_file"], encoding="utf-8").read()
    assert "W1" in prompt


def test_abandon_pushes_the_tag_and_rounds_reports_claimed_but_empty(tmp_path):
    r = with_origin(tmp_path)
    r.git("push", "-q", "origin", "main:refs/heads/round/0003")
    res, v = start_wt(r)
    assert res.json["id"] == "0004"
    assert v.run("abandon", "--reason", "no", "--quote", "stop").code == 0
    assert "round/0004-abandoned" in r.origin.tags()
    report = r.run("rounds").json
    by = {row["id"]: row for row in report["rounds"]}
    assert by["0003"].get("claimed_but_empty") is True and by["0004"]["abandoned"] is True and by["0004"]["status"] == "abandoned"
