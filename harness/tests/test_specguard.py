import json
import os

from shackles import specguard


def make(tmp_path):
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "a.txt").write_text("alpha one\nalpha two\n", encoding="utf-8")
    (tmp_path / "harness" / "b.txt").write_text("beta\n", encoding="utf-8")
    (tmp_path / "spec.yaml").write_text("files:\n  - harness/a.txt\n  - harness/b.txt\n", encoding="utf-8")
    root = str(tmp_path)
    specguard.accept(root, "initial")
    return root


def write(root, rel, text, newline="\n"):
    with open(os.path.join(root, rel), "w", encoding="utf-8", newline=newline) as f:
        f.write(text)


def test_baseline_missing(tmp_path):
    (tmp_path / "spec.yaml").write_text("files:\n  - x.txt\n", encoding="utf-8")
    result = specguard.check(str(tmp_path))
    assert result["baseline_missing"] and not result["clean"] and result["missing"] == ["x.txt"]


def test_unchanged_is_clean(tmp_path):
    root = make(tmp_path)
    result = specguard.check(root)
    assert result["clean"] and specguard.summary(result) == "clean"


def test_one_byte_change_and_whitespace_only(tmp_path):
    root = make(tmp_path)
    write(root, "harness/a.txt", "alpha one\nalpha twp\n")
    assert specguard.check(root)["changed"] == ["harness/a.txt"]
    write(root, "harness/a.txt", "alpha one\nalpha two \n")
    assert specguard.check(root)["changed"] == ["harness/a.txt"]


def test_crlf_and_bom_rewrite_is_clean(tmp_path):
    root = make(tmp_path)
    write(root, "harness/a.txt", "﻿alpha one\r\nalpha two\r\n", newline="")
    assert specguard.check(root)["clean"]


def test_added_removed_missing_and_spec_yaml(tmp_path):
    root = make(tmp_path)
    write(root, "harness/c.txt", "gamma\n")
    write(root, "spec.yaml", "files:\n  - harness/a.txt\n  - harness/c.txt\n  - harness/d.txt\n")
    result = specguard.check(root)
    assert result["added"] == ["harness/c.txt"]
    assert result["removed"] == ["harness/b.txt"]
    assert result["missing"] == ["harness/d.txt"]
    assert result["spec_yaml_changed"] and not result["clean"]
    assert "added: harness/c.txt" in specguard.summary(result)


def test_accept_then_clean_and_audit_line(tmp_path):
    root = make(tmp_path)
    write(root, "harness/a.txt", "changed\n")
    assert not specguard.check(root)["clean"]
    baseline = specguard.accept(root, "reviewed the change")
    assert specguard.check(root)["clean"]
    assert baseline["note"] == "reviewed the change" and set(baseline["files"]) == {"harness/a.txt", "harness/b.txt"}
    lines = [json.loads(l) for l in open(specguard.audit_path(root), encoding="utf-8") if l.strip()]
    assert len(lines) == 2 and lines[-1]["changed"] == ["harness/a.txt"] and lines[-1]["note"] == "reviewed the change"


def test_diff_text_without_git_reports_line_counts(tmp_path):
    root = make(tmp_path)
    write(root, "harness/a.txt", "x\ny\nz\n")
    text = specguard.diff_text(root)
    assert "harness/a.txt: content changed, now 3 lines" in text
