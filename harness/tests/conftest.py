import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "harness", "src")
for path in (SRC, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

GITCONFIG = "[core]\n\tautocrlf = false\n\tlongpaths = true\n[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n"


@pytest.fixture(scope="session", autouse=True)
def hermetic_git(tmp_path_factory):
    cfg = tmp_path_factory.mktemp("gitcfg") / "gitconfig"
    cfg.write_text(GITCONFIG, encoding="utf-8")
    os.environ.update({"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                       "PYTHONUTF8": "1"})
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        os.environ.pop(key, None)
    yield cfg
