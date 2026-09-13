"""Subcommands beyond config and spec."""
import sys

from . import config as configmod
from . import doctor as doctormod
from . import landing, pipeline, prompts
from .cli import EXIT_CHECK, EXIT_ERROR, EXIT_OK, emit, say
from .gitops import RunnerError


def add_parsers(sub):
    d = sub.add_parser("doctor", help="environment, config, lint, drift, hook, claude, every prompt rendered")
    d.add_argument("--probe-cli", action="store_true", help="one capped real claude call (costs cents)")
    r = sub.add_parser("render", help="render one step's prompt without side effects")
    r.add_argument("--step", required=True, choices=pipeline.NAMES)
    r.add_argument("--attempt", type=int, default=1)
    r.add_argument("--fixture", action="store_true", help="render on a synthetic round")
    r.add_argument("--raw", action="store_true", help="print the prompt text instead of JSON")
    s = sub.add_parser("start", help="start a round from an approved PLAN.json")
    s.add_argument("--plan", required=True)
    s.add_argument("--budget", type=float)
    s.add_argument("--branch")
    s.add_argument("--no-branch", action="store_true", help="run in this checkout: no claim, worktree or push")
    s.add_argument("--delegate", action="store_true")
    s.add_argument("--through")
    s.add_argument("--accept-spec", action="store_true", help="fold acceptance of spec drift into the start commit")
    s.add_argument("--agent", help="force one rung for every step this round")
    s.add_argument("--unverified", action="store_true", help="record the approval words without finding them in the owner log")
    s.add_argument("--no-push", action="store_true")
    n = sub.add_parser("next", help="mechanical work until an agent run is due")
    n.add_argument("--discard", action="store_true", help="reset unrecorded work for the pending attempt")
    n.add_argument("--no-push", action="store_true")
    rc = sub.add_parser("record", help="record an agent's final message and route the outcome")
    rc.add_argument("--step", required=True, choices=pipeline.NAMES)
    rc.add_argument("--attempt", type=int, required=True)
    rc.add_argument("--result", required=True)
    rc.add_argument("--cost", type=float)
    rc.add_argument("--tokens", type=int)
    rc.add_argument("--agent")
    rc.add_argument("--spawns", type=int, default=0)
    rc.add_argument("--no-push", action="store_true")
    for name in ("approve", "delegate", "answer", "override", "abandon"):
        o = sub.add_parser(name, help=f"owner command: {name}, with the owner's words quoted")
        o.add_argument("--quote", required=True)
        o.add_argument("--unverified", action="store_true")
        o.add_argument("--no-push", action="store_true")
        if name == "delegate":
            o.add_argument("--through")
        if name == "answer":
            o.add_argument("--text", required=True)
        if name == "override":
            o.add_argument("--steps", required=True)
        if name == "abandon":
            o.add_argument("--reason", required=True)
    sub.add_parser("status", help="where the round is")
    sp = sub.add_parser("spend", help="the round's spend, or the project's with --project")
    sp.add_argument("--project", action="store_true")
    sub.add_parser("rounds", help="every round: folders, origin branches, worktrees, tags")
    sub.add_parser("check", help="the current step's mechanical checks, nothing recorded")
    ag = sub.add_parser("agents", help="the per-rung agent definitions under .claude/agents/")
    ag.add_argument("--write", action="store_true")
    ru = sub.add_parser("run", help="headless loop: next, agent command, record")
    ru.add_argument("--until", choices=["checkpoint", "step", "done"], default="checkpoint")
    ru.add_argument("--no-push", action="store_true")
    ru.add_argument("--max-actions", type=int, default=200)
    pr = sub.add_parser("probe", help="one real agent on one canned step in a temp repo")
    pr.add_argument("--step", choices=pipeline.NAMES)
    pr.add_argument("--seed", choices=["clean", "defect"], default="clean")
    pr.add_argument("--agent")
    pr.add_argument("--budget", type=float)
    pr.add_argument("--manual", action="store_true", help="prepare the repo and print the action; do not run an agent")
    pr.add_argument("--dir", help="where to build the temp repo (default: a temp dir)")
    pr.add_argument("--changed", action="store_true", help="probe only the steps whose prose the baseline reports changed")
    pr.add_argument("--check", metavar="RESULT_FILE", help="score a result file against the probe's expectation")
    sb = sub.add_parser("sandbox", help="a temp clone with a local bare origin, the harness and the toy project "
                                        "(src/toy/text.py already holds shout(text), with one test; the JSON prints their content)")
    sb.add_argument("--dir", required=True, help="a folder outside any repository; DIR/repo and DIR/origin.git are created")


def cmd_doctor(args, root):
    report = doctormod.run(root, probe_cli=args.probe_cli)
    for line in report["errors"]:
        say("error: " + line)
    for line in report["warnings"]:
        say("warning: " + line)
    emit(report)
    return EXIT_ERROR if report["errors"] else EXIT_OK


def cmd_render(args, root):
    from . import round as roundmod
    cfg = configmod.load(root)
    if args.fixture or args.step == "CHAT-TO-PLAN":
        if args.fixture:
            round_ctx, step_ctx, gate_runs = prompts.fixture_contexts(cfg, root, args.step, args.attempt)
        else:
            round_ctx, step_ctx, gate_runs = roundmod.planning_contexts(cfg, root)
        text, unresolved, warnings = prompts.render_prompt(cfg, root, args.step, round_ctx, step_ctx, gate_runs=gate_runs)
    else:
        rnd = roundmod.open_round(root, args.round)
        text, unresolved, warnings = rnd.render_step(args.step, args.attempt, write=False)
    if args.raw:
        sys.stdout.write(text)
        return EXIT_OK
    emit({"step": args.step, "attempt": args.attempt, "prompt": text, "unresolved": sorted(set(unresolved)), "warnings": warnings})
    return EXIT_OK


def cmd_start(args, root):
    from . import round as roundmod
    out = roundmod.start(root, args.plan, budget=args.budget, branch=args.branch, no_branch=args.no_branch, delegate=args.delegate,
                         through=args.through, accept_spec=args.accept_spec, agent=args.agent, unverified=args.unverified,
                         push=not args.no_push)
    emit(out)
    return EXIT_OK


def finish(rnd, payload, code):
    for note in rnd.notes:
        say("note: " + note)
    for line in payload.get("undefined_new") or []:
        say("undefined judgment call: " + line)
    if payload.get("kind") == "checkpoint":
        say(payload["message"])
    emit(payload)
    return code


def cmd_next(args, root):
    from . import round as roundmod
    rnd = roundmod.open_round(root, args.round)
    payload, code = rnd.next(push=not args.no_push, discard=args.discard)
    return finish(rnd, payload, code)


def cmd_record(args, root):
    from . import round as roundmod
    rnd = roundmod.open_round(root, args.round)
    payload, code = rnd.record(args.step, args.attempt, args.result, cost=args.cost, tokens=args.tokens, agent=args.agent,
                               spawns=args.spawns, push=not args.no_push)
    return finish(rnd, payload, code)


def owner_command(name):
    def handler(args, root):
        from . import round as roundmod
        rnd = roundmod.open_round(root, args.round)
        payload, code = rnd.owner_command(name, args.quote, unverified=args.unverified, text=getattr(args, "text", None),
                                          through=getattr(args, "through", None),
                                          steps=[s.strip() for s in getattr(args, "steps", "").split(",") if s.strip()] if getattr(args, "steps", None) else None,
                                          reason=getattr(args, "reason", None), push=not args.no_push)
        return finish(rnd, payload, code)
    return handler


cmd_approve, cmd_delegate, cmd_answer, cmd_override, cmd_abandon = [owner_command(n) for n in ("approve", "delegate", "answer", "override", "abandon")]


def cmd_status(args, root):
    from . import round as roundmod
    rnd = roundmod.open_round(root, args.round)
    payload = rnd.status_payload()
    if rnd.state["status"] == "checkpoint":
        say(rnd.state["checkpoint"]["message"])
    emit(payload)
    return EXIT_OK


def cmd_spend(args, root):
    from . import round as roundmod
    rnd = roundmod.open_round(root, args.round)
    emit(rnd.project_spend() if args.project else rnd.spend())
    return EXIT_OK


def cmd_rounds(args, root):
    cfg = configmod.load(root)
    emit(landing.rounds_report(root, cfg))
    return EXIT_OK


def cmd_check(args, root):
    from . import round as roundmod
    rnd = roundmod.open_round(root, args.round)
    payload = rnd.check_payload()
    emit(payload)
    return EXIT_CHECK if [f for f in payload["findings"] if f.get("blocking")] else EXIT_OK


def cmd_agents(args, root):
    from . import agentdefs
    cfg = configmod.load(root)
    if args.write:
        emit({"written": agentdefs.write(cfg, root)})
        return EXIT_OK
    drift = agentdefs.drift(cfg, root)
    emit({"definitions": agentdefs.expected(cfg), "drift": drift})
    return EXIT_CHECK if drift else EXIT_OK


def cmd_run(args, root):
    from . import agents, round as roundmod
    rnd = roundmod.open_round(root, args.round)
    payload, code = agents.run_loop(rnd, until=args.until, push=not args.no_push, max_actions=args.max_actions)
    return finish(rnd, payload, code)


def cmd_probe(args, root):
    from . import probe
    payload, code = probe.cmd(args, root)
    emit(payload)
    return code


def cmd_sandbox(args, root):
    from . import probe
    emit(probe.sandbox(root, args.dir))
    return EXIT_OK
