"""The scripted fake agent: invoked like the CLI (argv from agentCommand) or in-process through perform().

It parses the contract lines of the rendered prompt, writes canned artifacts for the toy project, and prints
the CLI envelope. STUB_MODE or STUB_SCRIPT (JSON {"STEP:attempt"|"STEP"|"*": mode}) picks the behaviour;
STUB_LOG=<file> records argv, cwd and env keys per call; STUB_JUDGMENT="d,u" appends judgment lines.
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CANNED = os.path.join(HERE, "fixtures", "canned")
for path in (HERE, os.path.join(os.path.dirname(HERE), "src")):
    if path not in sys.path:
        sys.path.insert(0, path)
from shackles import contract, pipeline  # noqa: E402

COST = 0.01
FAIL_REASON = "STUB-FAIL-REASON"
QUESTION = "STUB-QUESTION: which colour should whisper use?"
ASSUMPTION = "STUB-ASSUMPTION: lowercase"
UPSTREAM_NOTES = "STUB-UPSTREAM-NOTES: the earlier artifact contradicts the plan"
BLOCKED_NOTES = "STUB-BLOCKED-NOTES: narrow the step to whisper only"
ANSWER = "STUB-ANSWER: assume lowercase"
NB_QUOTE = "STUB-NONBLOCKING-QUOTE"
IMPL = "../src/toy/text.py"
TESTS = ["../tests/toy/test_text.py", "../tests/toy/test_scratch.py"]
RUNGS = {"PLAN-TO-SPEC": "max", "POSTMORTEM": "max", "PLAN-AGENTS": "medium", "TESTS-TO-SUITE": "medium"}  # the code steps run on low
WEIGHTS = {"PLAN-TO-SPEC": 3, "SPEC-TO-TESTS": 2, "SPEC-TO-IMPLEMENTATION": 4, "CLEANUP": 2}  # of the work budget; every other step 1


def canned(name):
    with open(os.path.join(CANNED, name), encoding="utf-8") as f:
        return f.read()


def write(harness, rel, text):
    path = os.path.join(harness, *rel.split("/")) if not os.path.isabs(rel) else rel
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def append(harness, rel, text):
    path = os.path.join(harness, *rel.split("/")) if not os.path.isabs(rel) else rel
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def prompt_json(text, label):
    for line in text.splitlines():
        if line.startswith(label):
            tail = line[len(label):].strip()
            if tail in ("", "none"):
                return None
            try:
                return json.loads(tail)
            except ValueError:
                return None
    return None


def toy_verify():
    return [sys.executable, "-m", "unittest", "discover", "-s", "../tests/toy", "-p", "test_*.py", "-t", "../tests/toy"]


def write_artifact(step, keys, text, mode, env):
    harness, artifact = keys["HARNESS"], keys.get("ARTIFACT")
    rnd = int(keys.get("ROUND", "1"))
    if mode == "noop":
        return
    if step == "PLAN-AGENTS":
        rows = prompt_json(text, "Steps this round, with their gates and whether each gate runs:") or []
        minimum = (prompt_json(text, "Minimum shares, for the steps and gates present this round:") or {}).get("work") or {}
        present = [r["step"] for r in rows if not r.get("overridden") and r["step"] != "CHAT-TO-PLAN"]
        gated = [r["step"] for r in rows if r.get("gate_runs") and r["gate"] != "CHAT-TO-PLAN-GATE" and not r.get("overridden")]
        spent = {k: v for k, v in minimum.items() if k == "CHAT-TO-PLAN"}  # booked at start, as the prompt says: listed so the map sums to 1
        total = sum(WEIGHTS.get(p, 1) for p in present) or 1
        work = dict(spent, **{p: round((1.0 - sum(spent.values())) * WEIGHTS.get(p, 1) / total, 6) for p in present})
        plan = {"round": rnd, "agents": {p: env.get("STUB_RUNG") or RUNGS.get(p, "low") for p in present},
                "shares": {"work": work, "gates": {p: round(1.0 / len(gated), 6) for p in gated} if gated else {}},
                "subAgents": {}, "notes": "STUB-AGENTS-PLAN-NOTES"}
        if present:
            plan["shares"]["work"][present[-1]] = round(1.0 - sum(v for k, v in work.items() if k != present[-1]), 6)
        if gated:
            plan["shares"]["gates"][gated[-1]] = round(1.0 - sum(v for k, v in plan["shares"]["gates"].items() if k != gated[-1]), 6)
        if mode == "bad_artifact":
            plan["shares"]["work"] = {p: 0.9 for p in present}
        write(harness, artifact, json.dumps(plan, indent=1) + "\n")
    elif step == "PLAN-TO-SPEC":
        verify = json.loads(env["STUB_VERIFY"]) if env.get("STUB_VERIFY") else toy_verify()
        spec = {"round": rnd, "summary": "STUB-SPEC: add whisper to the toy", "verify": verify,
                "verifyTimeoutSeconds": float(env.get("STUB_VERIFY_TIMEOUT", "120")),
                "implPaths": ["../src/"], "testPaths": ["../tests/"], "nonGoals": ["NONGOAL-MARKER"], "refactor": [],
                "testPlan": "test whisper and shout"}
        if mode == "bad_artifact":
            spec["testPaths"] = ["../src/toy/"]
        write(harness, artifact, json.dumps(spec, indent=1) + "\n")
        write(harness, os.path.join(os.path.dirname(artifact), "SPEC.md"), canned("SPEC.md"))
    elif step == "SPEC-TO-TESTS":
        write(harness, TESTS[0], canned("test_text.py"))
        write(harness, TESTS[1], canned("test_scratch.py"))
    elif step == "SPEC-TO-IMPLEMENTATION":
        conflicts = prompt_json(text, "MERGE_IN_PROGRESS:")
        if conflicts:
            if mode == "resolve":
                for rel in conflicts:
                    resolve_markers(harness, rel)
            return
        write(harness, IMPL, canned("text_broken.py" if mode == "break" else "text.py"))
        if mode == "big":
            write(harness, "../src/toy/big.py", "# " + ("x" * 60000) + "\n")
    elif step == "TESTS-TO-SUITE":
        changed = prompt_json(text, "Test files changed this round under testPaths:") or TESTS
        archive = [p for p in changed if "scratch" in p] if env.get("STUB_ARCHIVE") else []
        keep = [p for p in changed if p not in archive]
        if mode == "bad_artifact":
            keep = []
        write(harness, artifact, json.dumps({"round": rnd, "keep": keep, "archive": archive, "notes": "stub suite selection"}, indent=1) + "\n")
    elif step == "POSTMORTEM":
        write(harness, artifact, canned("POSTMORTEM.md"))
        for rel in ("docs/TODO.md", "docs/CLARIFICATIONS.md"):
            path = os.path.join(harness, *rel.split("/"))
            if os.path.exists(path):
                append(harness, rel, f"\n## round {keys.get('ROUND')}\n- STUB-CARRY: from round {keys.get('ROUND')}\n")


def resolve_markers(harness, rel):
    path = os.path.join(harness, *rel.split("/"))
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        if line.startswith(("<<<<<<<", "=======", ">>>>>>>")):
            continue
        out.append(line)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def side_effects(step, keys, mode, env):
    harness, worktree = keys["HARNESS"], keys["WORKTREE"]
    if mode == "stray":
        write(harness, "../stray.txt", "STUB-STRAY\n")
    if mode == "touch_tests":
        append(harness, TESTS[0], "\n# STUB-TOUCHED-FROZEN-TEST\n")
    if mode == "rewrite_judgment":
        path = judgment_file(keys, "DEFINED")
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        lines[0] = "# REWRITTEN HEADER"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    if mode == "edit_spec":
        append(harness, "locked_prose/COMMON-OVERVIEW.txt", "STUB-SPEC-EDIT\n")
    if mode == "commit":
        subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True)
        subprocess.run(["git", "-c", "user.name=stub", "-c", "user.email=stub@example.com", "commit", "-q", "--allow-empty", "-m", "STUB-AGENT-COMMIT"], cwd=worktree, capture_output=True)
    if mode == "dirty":
        write(harness, "../gate-wrote-this.txt", "STUB-GATE-WROTE\n")
    if mode == "slow":
        time.sleep(float(env.get("STUB_SLEEP", "30")))
    d, u = (env.get("STUB_JUDGMENT") or "0,0").split(",")
    for n, key in ((int(d), "DEFINED"), (int(u), "UNDEFINED")):
        for i in range(n):
            append(harness, judgment_file(keys, key), f"- {step} attempt {keys.get('ATTEMPT')}: STUB-{key}-CALL {i + 1}\n")


def judgment_file(keys, kind):
    return os.path.join(keys["HARNESS"], "archives", "rounds", keys["ROUND"], f"{kind}_JUDGMENT_CALLS.md")


def open_ids(text, label):
    items = prompt_json(text, label) or []
    return [f["id"] for f in items if isinstance(f, dict) and f.get("status") in ("open", "settled", "disputed") and f.get("source") in ("gate", "owner")], \
        [f["id"] for f in items if isinstance(f, dict) and f.get("status") == "disputed"]


def gate_message(step, text, mode, env):
    m = re.search(r"Ids continue from F(\d+)", text)
    next_id = int(m.group(1)) if m else 1
    _, disputed = open_ids(text, "Prior findings with the producer's resolutions and rulings:")
    finding = {"id": f"F{next_id}", "quote": env.get("STUB_QUOTE", "STUB-QUOTE"), "reason": FAIL_REASON,
               "suggestion": "STUB-SUGGESTION", "blocking": True}
    if mode == "fail":
        return {"verdict": "FAIL", "findings": [finding], "notes": "stub fail"}
    if mode == "pass_nb":
        return {"verdict": "PASS", "findings": [dict(finding, quote=NB_QUOTE, blocking=False)], "notes": "stub pass with a note"}
    if mode == "uphold":
        return {"verdict": "FAIL", "findings": [], "rulings": {i: {"status": "upheld", "quote": "STUB-QUOTE"} for i in disputed}, "notes": "stub upholds"}
    if mode == "withdraw":
        return {"verdict": "PASS", "findings": [], "rulings": {i: {"status": "withdrawn", "quote": "STUB-QUOTE"} for i in disputed}, "notes": "stub withdraws"}
    if mode == "q_uphold":
        return {"verdict": "PASS", "findings": [], "needs_owner": {"status": "upheld", "reason": "only the owner can choose"}, "notes": "stub upholds the question"}
    if mode == "q_withdraw":
        return {"verdict": "PASS", "findings": [], "needs_owner": {"status": "withdrawn", "reason": ANSWER}, "notes": "stub withdraws the question"}
    if mode == "judgment":
        return {"verdict": "PASS", "findings": [], "judgment_calls": {"defined": ["STUB-GATE-DEFINED"], "undefined": ["STUB-GATE-UNDEFINED"]}, "notes": "stub judgment"}
    if mode == "inconsistent":
        return {"verdict": "PASS", "findings": [finding], "notes": "stub PASS with a blocking finding"}
    return {"verdict": "PASS", "findings": [], "notes": "stub pass"}


def producer_message(step, text, mode, env):
    ids, _ = open_ids(text, "Findings to resolve (every gate or owner finding id must appear in your resolutions as fixed, disputed or deferred; an omitted id counts as fixed; a settled id cannot be disputed; a mechanical finding needs no resolution entry, fix it):")
    status = {"dispute": "disputed", "deferred": "deferred"}.get(mode, "fixed")
    resolutions = {i: {"status": status, "reason": f"stub {status}"} for i in ids}
    d, u = (env.get("STUB_JUDGMENT") or "0,0").split(",")
    base = {"notes": f"stub {mode} at {step}", "resolutions": resolutions, "judgment_calls": {"defined": int(d), "undefined": int(u)}}
    if mode == "needs_owner":
        return dict(base, status="NEEDS-OWNER", question=QUESTION, assumption=ASSUMPTION)
    if mode == "upstream":
        earlier = pipeline.earlier_producers(step)
        return dict(base, status="UPSTREAM", notes=UPSTREAM_NOTES, target=env.get("STUB_TARGET") or earlier[-1])
    if mode == "blocked":
        return dict(base, status="BLOCKED", notes=BLOCKED_NOTES, narrow=BLOCKED_NOTES)
    return dict(base, status="DONE")


def perform(prompt_file, mode="pass", env=None):
    """Act on one rendered prompt; returns the final message text the driver saves."""
    env = dict(env or {})
    with open(prompt_file, encoding="utf-8") as f:
        text = f.read()
    keys = contract.parse(text)
    step, kind = keys.get("STEP"), keys.get("KIND")
    if not step or not kind:
        raise SystemExit(f"stub_agent: prompt has no STEP/KIND lines: {prompt_file}")
    if mode == "garbage":
        return "this is not json at all {{{"
    if kind == "gate":
        side_effects(step, keys, mode, env) if mode in ("dirty", "slow") else None
        obj = gate_message(step, text, mode, env)
    else:
        if env.get("STUB_REPLAY"):
            return replay(step, keys, env)
        write_artifact(step, keys, text, mode, env)
        side_effects(step, keys, mode, env)
        obj = producer_message(step, text, mode, env)
    message = json.dumps(obj)
    if mode == "fence":
        return "```json\n" + message + "\n```"
    if mode == "prose_wrapped":
        return "Here is my final message:\n\n" + message + "\n\nThanks."
    return message


def replay(step, keys, env):
    folder = env["STUB_REPLAY"]
    result = os.path.join(folder, f"{step}-{keys.get('ATTEMPT')}.json")
    artifacts = os.path.join(folder, "artifacts", step)
    if os.path.isdir(artifacts):
        for dirpath, _, names in os.walk(artifacts):
            for name in names:
                src = os.path.join(dirpath, name)
                rel = os.path.relpath(src, artifacts).replace("\\", "/")
                with open(src, encoding="utf-8") as f:
                    write(keys["HARNESS"], rel, f.read())
    with open(result, encoding="utf-8") as f:
        return f.read()


def mode_for(step, attempt, env):
    script = env.get("STUB_SCRIPT")
    if script:
        table = json.loads(script)
        return table.get(f"{step}:{attempt}") or table.get(step) or table.get("*") or "pass"
    return env.get("STUB_MODE", "pass")


def prompt_arg(argv):
    if "--system-prompt-file" in argv:
        return argv[argv.index("--system-prompt-file") + 1]
    return argv[1]


def main(argv):
    env = os.environ
    prompt_file = prompt_arg(argv)
    with open(prompt_file, encoding="utf-8") as f:
        keys = contract.parse(f.read())
    mode = mode_for(keys.get("STEP"), keys.get("ATTEMPT"), env)
    if env.get("STUB_LOG"):
        with open(env["STUB_LOG"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "mode": mode, "env_keys": sorted(env.keys())}) + "\n")
    if env.get("STUB_EXIT"):
        print("stub failure", file=sys.stderr)
        return int(env["STUB_EXIT"])
    message = perform(prompt_file, mode, env)
    if mode == "garbage":
        print(message)
        return 0
    try:
        structured = json.loads(message)
    except ValueError:
        structured = None
    envelope = {"result": message, "total_cost_usd": float(env.get("STUB_COST", COST)),
                "usage": {"input_tokens": 1000, "output_tokens": 100}, "num_turns": 2, "session_id": "stub", "is_error": False}
    if structured is not None and not env.get("STUB_NO_STRUCTURED"):
        envelope["structured_output"] = structured
    print(json.dumps(envelope))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
