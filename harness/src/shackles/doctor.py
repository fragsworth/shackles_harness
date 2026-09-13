"""doctor: environment, config, lint, drift, hook, claude, every prompt rendered on a fixture round."""
import json
import os
import platform
import sys

from . import agents, config as configmod, contract, gitops, pipeline, prompts, procs, specguard
from .gitops import RunnerError

HOOK_SCRIPT = "harness/src/owner_log_hook.py"
SETTINGS = ".claude/settings.json"
WAIVERS = "harness/tests/spec_waivers.json"


def hook_configured(root):
    path = os.path.join(root, *SETTINGS.split("/"))
    if not os.path.exists(path):
        return False
    try:
        data = procs.read_json(path)
    except ValueError:
        return False
    return "owner_log_hook.py" in json.dumps(data.get("hooks", {}).get("UserPromptSubmit", []))


def waivers(root):
    path = os.path.join(root, *WAIVERS.split("/"))
    return procs.read_json(path) if os.path.exists(path) else {}


def wording_warnings(cfg, root):
    """Every status and verdict word should appear somewhere in the locked prose (a warning, never a failure)."""
    text = "\n".join(t for t in (prompts.prose_reader(cfg, root)(n[:-4]) for n in prompts.prose_names(cfg, root)) if t)
    return [f"the word {w!r} does not appear in the locked prose (the runner's contract uses it)"
            for w in contract.STATUSES + contract.VERDICTS if w not in text]


def render_all(cfg, root, prose_commit=None):
    """{step: {unresolved, warnings, tokens}} for every agent step plus CHAT-TO-PLAN on the fixture round."""
    out = {}
    for s in pipeline.PIPELINE:
        if s.kind not in pipeline.AGENT_KINDS + ("plan",):
            continue
        if s.kind == "gate" and pipeline.prose_file(s.name) not in prompts.prose_names(cfg, root, prose_commit):
            continue
        round_ctx, step_ctx, gate_runs = prompts.fixture_contexts(cfg, root, s.name)
        try:
            text, unresolved, warnings = prompts.render_prompt(cfg, root, s.name, round_ctx, step_ctx,
                                                               prose_commit=prose_commit, gate_runs=gate_runs)
        except RunnerError as exc:
            out[s.name] = {"error": str(exc), "unresolved": [], "warnings": [], "text": ""}
            continue
        out[s.name] = {"unresolved": sorted(set(unresolved)), "warnings": warnings,
                       "tokens": int(len(text.encode("utf-8")) / max(cfg["tokenBytes"], 1)), "text": text}
    return out


def run(root, probe_cli=False):
    errors, warnings, info = [], [], {}
    info["python"] = sys.version.split()[0]
    info["platform"] = platform.platform()
    info["git"] = gitops.git(root, "--version", check=False) or None
    if not info["git"]:
        errors.append("git not found")
    try:
        cfg = configmod.load(root)
    except RunnerError as exc:
        errors.append(f"config: {exc}")
        return {"errors": errors, "warnings": warnings, "info": info}
    warnings += [f"config: {w}" for w in cfg.warnings]
    info["harness"] = cfg.harness_root
    files = specguard.spec_files(root)
    present = {f: os.path.exists(os.path.join(root, f)) for f in files}
    if not files:
        errors.append("spec.yaml lists no files")
    lint_errors, lint_warnings = pipeline.lint(cfg, prompts.prose_names(cfg, root), present)
    errors += [f"lint: {e}" for e in lint_errors]
    warnings += [f"lint: {w}" for w in lint_warnings]
    drift = specguard.check(root)
    info["spec"] = specguard.summary(drift)
    if not drift["clean"]:
        errors.append("spec drift: " + specguard.summary(drift).replace("\n", "; "))
    info["hook_configured"] = hook_configured(root)
    if not info["hook_configured"]:
        warnings.append(f"hook: {SETTINGS} has no UserPromptSubmit hook running {HOOK_SCRIPT}; quotes are recorded unverified")
    main_root = gitops.main_root(root)
    info["owner_log"] = os.path.join(main_root, "harness", "OWNER.log")
    if not os.path.exists(info["owner_log"]):
        warnings.append("owner log missing: " + info["owner_log"] + " (created by the hook on the first prompt)")
    if gitops.git_ok(root, "rev-parse", "--git-dir"):
        wt = cfg["worktreeDir"]
        info["worktreeDir_ignored"] = gitops.git_ok(root, "check-ignore", "-q", wt.rstrip("/") + "/probe")
        if not info["worktreeDir_ignored"]:
            warnings.append(f"worktreeDir {wt} is not gitignored; start refuses until it is")
        info["origin"] = gitops.git(root, "remote", "get-url", "origin", check=False) or None
        if info["origin"] is None:
            warnings.append("no origin remote; only --no-branch rounds can start")
        info["worktrees"] = gitops.worktrees(root)
        running = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        expected = os.path.join(root, "harness", "src")
        info["runner_skew"] = not procs.same_path(running, expected)
        if info["runner_skew"]:
            warnings.append(f"runner skew: running {running}, the repository's runner is {expected}")
    else:
        warnings.append("not a git repository")
    try:
        path, source = agents.resolve_claude(cfg)
        info["claude"] = {"path": path, "source": source, "version": agents.claude_version(path)}
        if info["claude"]["version"] is None:
            warnings.append(f"claude at {path} did not report a version")
    except RunnerError as exc:
        info["claude"] = None
        warnings.append(str(exc))
    if probe_cli:
        info["probe_cli"] = agents.probe_cli(cfg, root)
        if not info["probe_cli"].get("ok"):
            errors.append("probe-cli failed: " + str(info["probe_cli"].get("error")))
    warnings += [f"wording: {w}" for w in wording_warnings(cfg, root)]
    waived = waivers(root)
    rendered = render_all(cfg, root)
    info["prompts"] = {}
    for step, r in rendered.items():
        info["prompts"][step] = {k: v for k, v in r.items() if k != "text"}
        if r.get("error"):
            errors.append(f"render {step}: {r['error']}")
        for token in r.get("unresolved", []):
            (warnings if token in waived else errors).append(f"render {step}: unresolved token {token}" + (f" (waived: {waived[token]})" if token in waived else ""))
        for w in r.get("warnings", []):
            warnings.append(f"render {step}: {w}")
    try:
        from . import agentdefs
        info["agent_definitions"] = agentdefs.drift(cfg, root)
        warnings += [f"agents: {d}" for d in info["agent_definitions"]]
    except ImportError:
        pass
    return {"errors": errors, "warnings": warnings, "info": info}
