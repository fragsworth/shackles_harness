"""Command line: one JSON object on stdout per command, humans read stderr."""
import argparse
import json
import os
import sys

from . import config as configmod
from . import specguard
from .gitops import RunnerError

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_CHECK, EXIT_CHECKPOINT = 0, 1, 2, 3, 10
HELP = """shackles runner.

Exit codes: 0 ok or finished, 1 error, 2 usage or guard refusal or invalid input,
3 check failed or spec drift, 10 checkpoint (the owner's word is needed).
"""


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def say(text):
    sys.stderr.write(text.rstrip("\n") + "\n")
    sys.stderr.flush()


def find_root(explicit):
    if explicit:
        root = os.path.abspath(explicit)
        if not os.path.exists(os.path.join(root, specguard.SPEC_YAML)):
            raise RunnerError(f"--root {explicit}: no {specguard.SPEC_YAML} there", EXIT_USAGE)
        return root
    here = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(here, specguard.SPEC_YAML)):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            raise RunnerError(f"no {specguard.SPEC_YAML} in any ancestor of the current directory; pass --root", EXIT_USAGE)
        here = parent


def cmd_config(args, root):
    cfg = configmod.load(root)
    emit({"root": root, "harness": cfg.harness_root, "config": cfg.data, "sources": cfg.sources,
          "agents": cfg.agents, "warnings": cfg.warnings})
    return EXIT_OK


def cmd_spec(args, root):
    if args.action == "accept":
        baseline = specguard.accept(root, args.note or "")
        emit({"accepted": True, "head_at_accept": baseline["accepted_commit"], "files": len(baseline["files"])})  # the acceptance lands in the next commit
        return EXIT_OK
    result = specguard.check(root)
    if args.action == "diff":
        result["diff"] = specguard.diff_text(root, result)
    emit(result)
    return EXIT_OK if result["clean"] else EXIT_CHECK


def build_parser():
    p = argparse.ArgumentParser(prog="run.py", description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", help="repo root or round worktree (default: nearest ancestor with spec.yaml)")
    p.add_argument("--round", type=int, help="round id (default: from the branch, else the single unfinished round)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("config", help="effective config and the source of each key")
    s = sub.add_parser("spec", help="the spec-change guard")
    s.add_argument("action", choices=["status", "diff", "accept"])
    s.add_argument("--note", help="accept: what was reviewed")
    from . import commands
    commands.add_parsers(sub)
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = build_parser().parse_args(argv)
    try:
        root = find_root(args.root)
        handler = globals().get("cmd_" + args.cmd)
        if handler is None:
            from . import commands
            handler = getattr(commands, "cmd_" + args.cmd.replace("-", "_"))
        return handler(args, root)
    except RunnerError as exc:
        say(f"error: {exc}")
        emit({"error": str(exc), "exit": exc.code})
        return exc.code
