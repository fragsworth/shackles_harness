import io
import json
import os
import subprocess
import sys

import owner_log_hook
from fixtures import Repo
from shackles import config as configmod
from shackles import gitops, owner


def test_escape_roundtrip_and_parse():
    line = owner.append_line.__doc__ or ""
    text = "a\\b\nc"
    assert owner.unescape(owner.escape(text)) == text
    assert owner.parse_line("2026-01-01T00:00:00Z\thello\tworld") == ("2026-01-01T00:00:00Z", "hello\tworld")
    assert owner.parse_line("no tab") is None and owner.parse_line("bad\tts") is None


def test_envelopes_and_slice(tmp_path):
    path = str(tmp_path / "OWNER.log")
    owner.append_line(path, "first", at="2026-01-01T00:00:00Z")
    owner.append_line(path, "<system-reminder>noise", at="2026-01-01T00:00:01Z")
    owner.append_line(path, "second\nline", at="2026-01-01T00:00:02Z")
    prefixes = configmod.DEFAULTS["envelopePrefixes"]
    lines = owner.slice_since(path, "2026-01-01T00:00:01Z", prefixes)
    assert lines == ["2026-01-01T00:00:02Z\tsecond\\nline"]
    assert len(owner.slice_since(path, None, prefixes)) == 2
    assert owner.is_envelope("  <task-notification>x", prefixes)


def test_verify_quote_windows(tmp_path):
    path = str(tmp_path / "OWNER.log")
    assert owner.verify_quote(path, "anything", None) is None
    owner.append_line(path, "please   approve the plan", at="2026-01-01T01:00:00Z")
    assert owner.verify_quote(path, "approve the plan", "2026-01-01T00:00:00Z") is True
    assert owner.verify_quote(path, "please approve", "2026-01-01T00:00:00Z") is True
    assert owner.verify_quote(path, "approve the plan", "2026-01-01T02:00:00Z") is False
    assert owner.verify_quote(path, "reject", "2026-01-01T00:00:00Z") is False
    assert owner.verify_quote(path, "", "2026-01-01T00:00:00Z") is False


def test_hook_matches_the_runner_prefix_list():
    assert list(owner_log_hook.ENVELOPES) == list(configmod.DEFAULTS["envelopePrefixes"])


def test_hook_resolves_the_main_checkout_from_a_worktree(tmp_path):
    root = str(tmp_path / "main")
    os.makedirs(root)
    gitops.git(root, "init", "-q", "-b", "main")
    open(os.path.join(root, "f"), "w").write("x")
    gitops.git(root, "add", "-A")
    gitops.git(root, "commit", "-q", "-m", "base")
    wt = str(tmp_path / "wt")
    gitops.git(root, "worktree", "add", "-q", "-b", "side", wt)
    env = {"CLAUDE_PROJECT_DIR": wt}
    out = owner_log_hook.main(io.StringIO(json.dumps({"prompt": "hello\nowner \\ words", "session_id": "s"})), env)
    assert out == os.path.join(root, "harness", "OWNER.log")
    lines = open(out, encoding="utf-8").read().splitlines()
    assert len(lines) == 1 and lines[0].endswith("\thello\\nowner \\\\ words") and owner.parse_line(lines[0])
    assert owner_log_hook.main(io.StringIO(json.dumps({"prompt": "<system-reminder>x"})), env) is None
    assert owner_log_hook.main(io.StringIO(json.dumps({"prompt": "   "})), env) is None
    assert owner_log_hook.main(io.StringIO(json.dumps({"prompt": "x"})), dict(env, SHACKLES_SUBAGENT="1")) is None
    assert owner_log_hook.main(io.StringIO("not json"), env) is None
    assert owner_log_hook.main(io.StringIO("[1, 2]"), env) is None
    assert len(open(out, encoding="utf-8").read().splitlines()) == 1


def test_hook_script_runs_as_a_subprocess(tmp_path):
    root = str(tmp_path / "repo")
    os.makedirs(os.path.join(root, "harness"))
    gitops.git(root, "init", "-q", "-b", "main")
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "owner_log_hook.py")
    proc = subprocess.run([sys.executable, script], input=json.dumps({"prompt": "from the hook"}), capture_output=True, text=True,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=root), cwd=root)
    assert proc.returncode == 0 and proc.stdout == "" and proc.stderr == ""
    assert "from the hook" in open(os.path.join(root, "harness", "OWNER.log"), encoding="utf-8").read()


def test_round_slice_and_driver_lines(tmp_path):
    r = Repo(tmp_path)
    r.owner("before the plan", at="2025-12-31T00:00:00Z")
    r.owner("thinking about whisper", at="2026-01-01T00:30:00Z")
    r.start()
    r.owner("<system-reminder>ignored", at="2026-01-01T01:00:00Z")
    r.owner("go on", at="2026-01-01T01:30:00Z")
    res = r.play()
    assert res.json["kind"] == "checkpoint"
    text = r.read("harness/archives/rounds/0001/OWNER.log")
    assert "thinking about whisper" in text and "go on" in text and "before the plan" not in text and "ignored" not in text
    assert r.run("approve", "--quote", "not said").code == 2
    r.owner("approve the spec")
    assert r.run("approve", "--quote", "approve the spec").code == 0
    text = r.read("harness/archives/rounds/0001/OWNER.log")
    assert "[via driver: approve]\tapprove the spec" in text, "the line names the command, so override then approve with one sentence are two acts (R5-n1)"
