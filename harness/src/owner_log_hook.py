"""UserPromptSubmit hook: append every owner chat message to <main checkout>/harness/OWNER.log; stdlib only, never raises."""
import datetime
import json
import os
import subprocess
import sys

ENVELOPES = ("<system-reminder", "<task-notification", "[SYSTEM NOTIFICATION", "<wake ", "<webhook-payload", "<event ")


def main_root(start):
    try:
        proc = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=start, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0 and proc.stdout.strip():
            return os.path.dirname(os.path.abspath(os.path.join(start, proc.stdout.strip())))
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.abspath(start)


def main(stdin=None, environ=None):
    environ = os.environ if environ is None else environ
    try:
        data = json.load(stdin or sys.stdin)
    except Exception:
        return None
    if not isinstance(data, dict) or environ.get("SHACKLES_SUBAGENT"):
        return None
    prompt = str(data.get("prompt", ""))
    if not prompt.strip() or prompt.lstrip().startswith(ENVELOPES):
        return None
    root = main_root(environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp}\t{prompt.replace(chr(92), chr(92) * 2).replace(chr(10), chr(92) + 'n')}\n"
    path = os.path.join(root, "harness", "OWNER.log")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
    except OSError:
        return None
    return path


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
