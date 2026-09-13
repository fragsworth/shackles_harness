"""Agent invocation: {claude} resolution, the headless command, the run loop, the capped CLI probe."""
import glob
import json
import os
import shutil
import tempfile

from . import procs, schemas
from .gitops import RunnerError

PROBE_SCHEMA = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
PROBE_TASK = 'Reply with exactly the JSON object {"ok": true} and nothing else.'


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


def build_command(cfg, values, kind):
    """agentCommand with its {tokens} substituted; {tool_flags} expands in place by kind."""
    command = list(cfg["agentCommand"])
    if any("{claude}" in str(item) for item in command):
        values = dict(values, claude=resolve_claude(cfg)[0])
    flags = cfg["gateToolFlags"] if kind == "gate" else cfg["producerToolFlags"]
    argv = []
    for item in command:
        item = str(item)
        if item == "{tool_flags}":
            argv.extend(str(f) for f in flags)
            continue
        for key, value in values.items():
            item = item.replace("{" + key + "}", str(value))
        argv.append(item)
    return argv


def agent_env(cfg):
    return procs.child_env(scrub=cfg["scrubEnv"], extra={"SHACKLES_SUBAGENT": "1"})


def parse_envelope(stdout):
    """(result text, meta) from the --output-format json envelope; the text is None when nothing usable came back."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None, {}
    if not isinstance(data, dict):
        return None, {}
    meta = {k: data.get(k) for k in ("total_cost_usd", "usage", "num_turns", "session_id", "is_error")}
    structured = data.get("structured_output")
    if isinstance(structured, dict):
        return json.dumps(structured, ensure_ascii=False), meta
    result = data.get("result")
    return (result if isinstance(result, str) and result.strip() else None), meta


def run_agent(cfg, harness_root, action):
    """(result text, meta, error) for one headless agent run of the printed action."""
    kind = action["kind"]
    schema = json.dumps(schemas.json_schema("FINDINGS" if kind == "gate" else "RESULT"), separators=(",", ":"))
    values = {"prompt_file": action["prompt_file"], "model": action["model"], "effort": action["effort"],
              "budget_cap_usd": action["budget_cap_usd"], "result_schema": schema, "task": cfg["agentTask"]}
    argv = build_command(cfg, values, kind)
    timeout = float(cfg["maxRunWallClockHours"]) * 3600.0
    try:
        proc = procs.run(argv, cwd=harness_root, env=agent_env(cfg), timeout=timeout)
    except OSError as exc:
        return None, {}, f"cannot run {argv[0]}: {exc}"
    if proc.timed_out:
        return None, {}, f"timed out after {timeout} s"
    text, meta = parse_envelope(proc.out)
    if proc.code != 0 or meta.get("is_error"):
        return None, meta, f"exit {proc.code}: {(proc.err or proc.out).strip()[-400:]}"
    if text is None:
        return proc.out, meta, "no result in the envelope"
    return text, meta, None


def run_loop(rnd, until="checkpoint", push=True, max_actions=200):
    """next, agent, record, repeated until a checkpoint, one recorded step, or done."""
    from . import round as roundmod
    root, rid = rnd.root, rnd.rid
    for _ in range(max_actions):
        rnd = roundmod.open_round(root, rid)
        payload, code = rnd.next(push=push)
        if code != 0 or payload.get("kind") == "done":
            return payload, code
        text, meta, error = run_agent(rnd.cfg, rnd.harness, payload)
        procs.write_json(payload["result_file"].rsplit(".", 1)[0] + ".meta.json", dict(meta, error=error))
        procs.write_text(payload["result_file"], text if text is not None else f"(no result: {error})")
        cost = meta.get("total_cost_usd") if isinstance(meta.get("total_cost_usd"), (int, float)) else None
        rnd = roundmod.open_round(root, rid)
        payload, code = rnd.record(payload["step"], payload["attempt"], payload["result_file"], cost=cost, push=push,
                                   note=f"headless agent error: {error}" if error else None)
        if code == 10 or payload.get("kind") == "done" or (code == 0 and until == "step") or code not in (0, 2):
            return payload, code
    return {"kind": "stopped", "reason": f"{max_actions} actions"}, 1


def probe_cli(cfg, root):
    """One real --print call on the low rung, capped at a few cents, asking for {"ok": true}."""
    rung_name, rung = cfg.rung("low")
    folder = tempfile.mkdtemp(prefix="shackles-probe-")
    prompt_file = os.path.join(folder, "prompt.txt")
    procs.write_text(prompt_file, "You are a probe. " + PROBE_TASK + "\n")
    values = {"prompt_file": prompt_file, "model": rung.get("model"), "effort": rung.get("effort"), "budget_cap_usd": "0.05",
              "result_schema": json.dumps(PROBE_SCHEMA, separators=(",", ":")), "task": PROBE_TASK}
    try:
        argv = build_command(cfg, values, "gate")
        proc = procs.run(argv, cwd=root, env=agent_env(cfg), timeout=300)
    except (RunnerError, OSError) as exc:
        return {"ok": False, "error": str(exc), "rung": rung_name}
    text, meta = parse_envelope(proc.out)
    obj = schemas.extract_json(text) if text else None
    ok = proc.ok and isinstance(obj, dict) and obj.get("ok") is True
    error = None
    if not ok:
        error = (text or "").strip()[-300:] or proc.err.strip()[-300:] or proc.out.strip()[-300:] or "no output"
        if "not logged in" in error.lower():
            error += " (the standalone CLI has no login: run `claude auth login` in a terminal, or set ANTHROPIC_API_KEY)"
    return {"ok": ok, "rung": rung_name, "model": rung.get("model"), "exit": proc.code, "cost_usd": meta.get("total_cost_usd"),
            "num_turns": meta.get("num_turns"), "timed_out": proc.timed_out, "error": error, "claude": argv[0]}
