"""Agent invocation: the headless command, {claude} resolution, agent definitions."""
import glob
import os
import shutil

from . import procs
from .gitops import RunnerError


def resolve_claude(cfg):
    """SHACKLES_CLAUDE env, then claudePath (local.yaml), then PATH, then the newest %APPDATA% install."""
    tried = []
    for source, candidate in (("SHACKLES_CLAUDE", os.environ.get("SHACKLES_CLAUDE")), ("claudePath", cfg.get("claudePath"))):
        if candidate:
            if os.path.exists(candidate):
                return os.path.abspath(candidate), source
            tried.append(f"{source}={candidate} (missing)")
    found = shutil.which("claude")
    if found:
        return found, "PATH"
    tried.append("PATH")
    appdata = os.environ.get("APPDATA")
    if appdata:
        pattern = os.path.join(appdata, "Claude", "claude-code", "*", "claude.exe")
        matches = sorted(glob.glob(pattern), key=lambda p: [int(x) if x.isdigit() else x for x in
                                                             os.path.basename(os.path.dirname(p)).split(".")])
        if matches:
            return matches[-1], "APPDATA"
        tried.append(pattern)
    raise RunnerError("claude not found; tried " + ", ".join(tried) + "; set SHACKLES_CLAUDE or claudePath in local.yaml", 2)


def claude_version(path):
    proc = procs.run([path, "--version"], cwd=os.path.dirname(path), timeout=60)
    return proc.out.strip() if proc.ok else None
