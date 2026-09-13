"""Subcommands beyond config and spec."""
import os

from . import config as configmod
from . import doctor as doctormod
from . import pipeline, prompts
from .cli import EXIT_ERROR, EXIT_OK, EXIT_USAGE, emit, say
from .gitops import RunnerError


def add_parsers(sub):
    d = sub.add_parser("doctor", help="environment, config, lint, drift, hook, claude, every prompt rendered")
    d.add_argument("--probe-cli", action="store_true", help="one capped real claude call (costs cents)")
    d.add_argument("--json", action="store_true", help="(the output is always JSON; kept for symmetry)")
    r = sub.add_parser("render", help="render one step's prompt without side effects")
    r.add_argument("--step", required=True, choices=pipeline.NAMES)
    r.add_argument("--attempt", type=int, default=1)
    r.add_argument("--fixture", action="store_true", help="render on a synthetic round")
    r.add_argument("--raw", action="store_true", help="print the prompt text instead of JSON")


def cmd_doctor(args, root):
    report = doctormod.run(root, probe_cli=args.probe_cli)
    for line in report["errors"]:
        say("error: " + line)
    for line in report["warnings"]:
        say("warning: " + line)
    emit(report)
    return EXIT_ERROR if report["errors"] else EXIT_OK


def cmd_render(args, root):
    cfg = configmod.load(root)
    if args.fixture or args.step == "CHAT-TO-PLAN":
        if args.fixture:
            round_ctx, step_ctx, gate_runs = prompts.fixture_contexts(cfg, root, args.step, args.attempt)
        else:
            from . import round as roundmod
            round_ctx, step_ctx, gate_runs = roundmod.planning_contexts(cfg, root)
        text, unresolved, warnings = prompts.render_prompt(cfg, root, args.step, round_ctx, step_ctx, gate_runs=gate_runs)
    else:
        from . import round as roundmod
        rnd = roundmod.open_round(root, args.round)
        text, unresolved, warnings = rnd.render_step(args.step, args.attempt, write=False)
    if args.raw:
        import sys
        sys.stdout.write(text)
        return EXIT_OK
    emit({"step": args.step, "attempt": args.attempt, "prompt": text, "unresolved": sorted(set(unresolved)), "warnings": warnings})
    return EXIT_OK
