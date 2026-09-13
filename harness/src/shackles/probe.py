"""probe: one real agent on one canned step in a temp repo, scored; sandbox: a temp clone with a local bare origin."""
import json
import os
import shutil
import sys
import tempfile

from . import agents, config as configmod, contract, gitops, pipeline, procs, schemas, specguard
from .gitops import RunnerError

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tests")
DEFECTS = os.path.join(TESTS, "fixtures", "defects")


def _fixtures():
    if TESTS not in sys.path:
        sys.path.insert(0, TESTS)
    import fixtures
    import stub_agent
    return fixtures, stub_agent


def defect_dirs():
    return sorted(d for d in os.listdir(DEFECTS) if os.path.isdir(os.path.join(DEFECTS, d))) if os.path.isdir(DEFECTS) else []


def load_defect(gate):
    folder = os.path.join(DEFECTS, gate)
    path = os.path.join(folder, "expect.json")
    if not os.path.exists(path):
        raise RunnerError(f"no defect fixture for {gate} under {DEFECTS}", 2)
    expect = procs.read_json(path)
    for key in ("verdict", "quote_contains", "files"):
        if key not in expect:
            raise RunnerError(f"{path}: missing {key}", 2)
    return folder, expect


def prepare(root, step, seed, agent, budget, folder=None):
    """A temp repo with the real spec and the toy project, played with the stub to just before `step`; returns (repo, action, expect)."""
    fixtures, stub_agent = _fixtures()
    folder = folder or tempfile.mkdtemp(prefix=f"shackles-probe-{step}-")
    os.makedirs(folder, exist_ok=True)
    cfg = configmod.load(root)
    gates = {g: 1 for g in pipeline.llm_gates()}
    config = {"agentCommand": cfg["agentCommand"], "gates": {**{g: 0 for g in pipeline.gates()}, **gates}}
    if agent:
        config["agentOverride"] = agent
    repo = fixtures.Repo(folder, gates=gates, config=config, spec="real")
    if cfg.get("claudePath"):
        fixtures.local_yaml(repo.root, {"claudePath": cfg["claudePath"]})
    res = repo.start(plan=dict(fixtures.PLAN, quote_usd=budget or fixtures.PLAN["quote_usd"]), extra=["--delegate"])
    if res.code != 0:
        raise RunnerError(f"probe start failed: {res.json}")
    s = pipeline.step(step)
    expect = {"verdict": "PASS", "quote_contains": None, "files": {}}
    if s.kind == "gate":
        producer = pipeline.producer_of(step)
        res = repo.play(until=producer, env={"STUB_ARCHIVE": "1"})
        if res.json.get("step") != producer:
            raise RunnerError(f"probe could not reach {producer}: {res.json}")
        rec = repo.act(res.json, "pass", env={"STUB_ARCHIVE": "1"})
        if rec.code != 0:
            raise RunnerError(f"probe: the stub's {producer} was not accepted: {rec.json}")
        if seed == "defect":
            dfolder, expect = load_defect(step)
            for rel, source in expect["files"].items():
                shutil.copyfile(os.path.join(dfolder, source), os.path.join(repo.root, "harness", *rel.split("/")))
            repo.git("add", "-A")
            repo.git("commit", "-q", "--allow-empty", "-m", f"probe: planted defect for {step}")
        res = repo.next()
    else:
        res = repo.play(until=step, env={"STUB_ARCHIVE": "1"})
    if res.json.get("step") != step:
        raise RunnerError(f"probe could not reach {step}: {res.json}")
    action = res.json
    procs.write_json(os.path.join(folder, "probe.json"), {"step": step, "seed": seed, "expect": expect, "root": repo.root, "action": action})
    return repo, action, expect


def score(folder, result_file):
    meta = procs.read_json(os.path.join(folder, "probe.json"))
    step, expect, root = meta["step"], meta["expect"], meta["root"]
    kind = "gate" if pipeline.step(step).kind == "gate" else "producer"
    text = procs.read_text(result_file)
    obj = schemas.extract_json(text)
    schema = "FINDINGS" if kind == "gate" else "RESULT"
    errors = schemas.validate(obj, schemas.SCHEMAS[schema], schema) if obj else ["no JSON object"]
    card = {"step": step, "seed": meta["seed"], "contract_valid": obj is not None, "schema_valid": not errors, "errors": errors}
    if kind == "gate" and obj:
        card["verdict"] = obj.get("verdict")
        card["verdict_as_expected"] = obj.get("verdict") == expect["verdict"]
        quotes = " ".join(f.get("quote", "") for f in obj.get("findings") or [])
        card["quote_contains_planted"] = (expect["quote_contains"] in quotes) if expect.get("quote_contains") else None
        jc = obj.get("judgment_calls") or {}
        card["judgment_lines"] = len(jc.get("defined") or []) + len(jc.get("undefined") or [])
    elif obj:
        card["status"] = obj.get("status")
        dirty = [p for _, p in gitops.status_paths(root)]
        allowed = contract.parse(procs.read_text(meta["action"]["prompt_file"])).get("WRITE_PATHS", "[]")
        try:
            allowed = json.loads(allowed)
        except ValueError:
            allowed = []
        cfg = configmod.load(root)
        allowed_rel = [cfg.repo_rel(p) for p in allowed]
        card["paths_confined"] = all(any(procs.under(p, a) for a in allowed_rel if a) or p.startswith("harness/archives/rounds/") for p in dirty)
        card["judgment_lines"] = sum(len(procs.read_text(os.path.join(root, "harness", "archives", "rounds", "0001", f)).splitlines()) - 1
                                     for f in ("DEFINED_JUDGMENT_CALLS.md", "UNDEFINED_JUDGMENT_CALLS.md"))
    meta_file = result_file.rsplit(".", 1)[0] + ".meta.json"
    if os.path.exists(meta_file):
        m = procs.read_json(meta_file)
        card["cost"], card["turns"] = m.get("total_cost_usd"), m.get("num_turns")
    return card


def changed_steps(root):
    result = specguard.check(root)
    steps = set()
    for path in result["changed"] + result["added"]:
        owner = pipeline.prose_owner(os.path.basename(path))
        if owner == "COMMON":
            return [s.name for s in pipeline.PIPELINE if s.kind in pipeline.AGENT_KINDS]
        if owner:
            steps.add(owner)
    return [n for n in pipeline.NAMES if n in steps]


def cmd(args, root):
    if args.check:
        folder = args.dir or os.path.dirname(os.path.abspath(args.check))
        return score(folder, args.check), 0
    steps = changed_steps(root) if args.changed else ([args.step] if args.step else [])
    if not steps:
        return {"steps": [], "hint": "nothing to probe: pass --step, or --changed with drifted prose"}, 0
    out = []
    for step in steps:
        if pipeline.step(step).kind not in pipeline.AGENT_KINDS:
            raise RunnerError(f"{step} is not an agent step", 2)
        folder = args.dir if args.dir and len(steps) == 1 else None
        repo, action, expect = prepare(root, step, args.seed, args.agent, args.budget, folder)
        folder = os.path.dirname(repo.root)
        item = {"step": step, "seed": args.seed, "dir": folder, "action": action, "expect": expect}
        if not args.manual:
            from . import round as roundmod
            rnd = roundmod.open_round(repo.root)
            text, meta, error = agents.run_agent(rnd.cfg, rnd.harness, action)
            procs.write_json(action["result_file"].rsplit(".", 1)[0] + ".meta.json", dict(meta, error=error))
            procs.write_text(action["result_file"], text if text is not None else f"(no result: {error})")
            item["error"] = error
            item["scorecard"] = score(folder, action["result_file"])
        else:
            item["hint"] = f"spawn the agent on {action['prompt_file']}, save its final message to {action['result_file']}, then probe --check {action['result_file']} --dir {folder}"
        out.append(item)
    return ({"probes": out} if len(out) > 1 else out[0]), 0


def sandbox(root, target):
    """<target>/origin.git (bare) and <target>/repo: the harness copied from `root`, the toy project as its target project."""
    fixtures, _ = _fixtures()
    target = os.path.abspath(target)
    os.makedirs(target, exist_ok=True)
    repo = os.path.join(target, "repo")
    if os.path.exists(repo):
        raise RunnerError(f"{repo} already exists", 2)
    os.makedirs(repo)
    for name in ("spec.yaml", ".gitignore", ".gitattributes", "pytest.ini", "README.md", "CLAUDE.md"):
        src = os.path.join(root, name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(repo, name))
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "archives", "OWNER.log", "local.yaml", "DRAFT-PLAN.json")
    shutil.copytree(os.path.join(root, "harness"), os.path.join(repo, "harness"), ignore=ignore)
    archives = os.path.join(repo, "harness", "archives")
    os.makedirs(archives, exist_ok=True)
    for name in ("spec-baseline.json", "spec-changes.jsonl"):
        src = os.path.join(root, "harness", "archives", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(archives, name))
    if os.path.isdir(os.path.join(root, ".claude", "agents")):
        shutil.copytree(os.path.join(root, ".claude", "agents"), os.path.join(repo, ".claude", "agents"))
    fixtures.write_toy(repo)
    project_path = os.path.join(repo, "harness", "project.yaml")
    data = configmod.load_yaml(project_path)
    data["livingSourcePaths"] = ["../src/", "../tests/", "docs/"]
    data["suiteCommand"] = fixtures.toy_verify()
    import yaml
    procs.write_text(project_path, yaml.safe_dump(data, sort_keys=False))
    specguard.accept(repo, "sandbox: living paths point at the toy project")
    gitops.git(repo, "init", "-q", "-b", "main")
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", "sandbox base")
    origin = os.path.join(target, "origin.git")
    gitops.git(target, "init", "-q", "--bare", "-b", "main", origin)
    gitops.git(repo, "remote", "add", "origin", origin)
    gitops.git(repo, "push", "-q", "-u", "origin", "main")
    return {"repo": repo, "origin": origin, "runner": os.path.join(repo, "harness", "src", "run.py"),
            "hint": f"py -3.13 {os.path.join(repo, 'harness', 'src', 'run.py')} --root {repo} start --plan <PLAN.json> --delegate"}
