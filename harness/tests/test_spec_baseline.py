"""The spec-change guard on the real repository, and the meta-test that proves it fires."""
import os
import shutil
import subprocess
import sys

import pytest

from shackles import gitops, specguard

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))


def guard_root():
    return os.environ.get("SHACKLES_ROOT") or REPO_ROOT


def test_spec_files_unchanged_since_baseline():
    root = guard_root()
    result = specguard.check(root)
    if result["clean"]:
        return
    pytest.fail("spec files changed since the accepted baseline\n" + specguard.summary(result) + "\n"
                + specguard.diff_text(root, result) + "\n" + specguard.INSTRUCTION)


def copy_spec(dst):
    os.makedirs(dst, exist_ok=True)
    for rel in [specguard.SPEC_YAML] + specguard.spec_files(REPO_ROOT):
        src = os.path.join(REPO_ROOT, rel)
        if os.path.exists(src):
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(src, target)


def test_guard_fires(tmp_path, monkeypatch):
    root = str(tmp_path / "copy")
    copy_spec(root)
    gitops.git(root, "init", "-q", "-b", "main")
    gitops.git(root, "add", "-A")
    gitops.git(root, "commit", "-q", "-m", "spec copy")
    specguard.accept(root, "meta-test baseline")
    monkeypatch.setenv("SHACKLES_ROOT", root)
    test_spec_files_unchanged_since_baseline()
    victim = specguard.spec_files(root)[-1]
    path = os.path.join(root, victim)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\nMUTATED-BY-META-TEST\n")
    with pytest.raises(pytest.fail.Exception) as exc:
        test_spec_files_unchanged_since_baseline()
    message = str(exc.value)
    assert victim in message and "+MUTATED-BY-META-TEST" in message and "spec accept --note" in message
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", __file__,
                           "-k", "test_spec_files_unchanged_since_baseline"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, SHACKLES_ROOT=root), cwd=REPO_ROOT)
    assert proc.returncode == 1 and victim in proc.stdout, proc.stdout + proc.stderr
    specguard.accept(root, "meta-test re-accept")
    test_spec_files_unchanged_since_baseline()
