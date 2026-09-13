"""Prompt contexts (project.*, round.*, step.*), the prose and plumbing readers, and prompt assembly."""
import os

from . import gitops, pipeline, procs, render, schemas
from .gitops import RunnerError

PLUMBING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plumbing")
AGENTS_MD = "AGENTS.md"
CHAT_GATE_SENTENCE = ("CHAT-TO-PLAN-GATE is mechanical: start validates PLAN.json and requires the owner's word "
                      "recorded in it.")
ROUND_KEYS = ("id", "number", "folder", "worktree", "harness_root", "branch", "base_commit", "prose_commit", "plan",
              "budget", "spend", "remaining", "status", "step", "history", "postmortems", "postmortem_paths",
              "judgment_files", "judgment_calls", "owner_log", "todos", "clarifications", "steps", "runner")
BEFORE_ROUND = ("history", "postmortems", "postmortem_paths", "remaining", "todos", "clarifications", "steps", "runner")


def plumbing_reader():
    def read(name):
        path = os.path.join(PLUMBING_DIR, name + ".txt")
        return procs.read_text(path) if os.path.exists(path) else None
    return read


def prose_reader(cfg, root, prose_commit=None, names=None):
    """A `name -> text or None` reader: from the working tree, or from prose_commit in one batched git call."""
    prose_dir = cfg.prose_dir()
    cache = {}

    def read(name):
        rel = cfg.repo_rel(f"{prose_dir}/{name}.txt")
        if prose_commit:
            if not cache:
                listed = names if names is not None else prose_names(cfg, root, prose_commit)
                paths = [cfg.repo_rel(f"{prose_dir}/{n}") for n in listed] + [cfg.repo_rel(AGENTS_MD)]
                cache.update(gitops.show_many(root, prose_commit, paths))
                cache.setdefault("", None)
            return cache.get(rel)
        path = os.path.join(root, *rel.split("/"))
        return procs.read_text(path) if os.path.exists(path) else None
    read.cache = cache
    return read


def prose_names(cfg, root, prose_commit=None):
    rel = cfg.repo_rel(cfg.prose_dir())
    if prose_commit:
        return sorted(os.path.basename(p) for p in gitops.ls_tree(root, prose_commit, rel) if p.endswith(".txt"))
    folder = os.path.join(root, *rel.split("/"))
    return sorted(n for n in os.listdir(folder) if n.endswith(".txt")) if os.path.isdir(folder) else []


def agents_md(cfg, root, prose_commit=None):
    rel = cfg.repo_rel(AGENTS_MD)
    if prose_commit:
        text = gitops.show(root, prose_commit, rel)
    else:
        path = os.path.join(root, *rel.split("/"))
        text = procs.read_text(path) if os.path.exists(path) else None
    return text if text is not None else f"# {AGENTS_MD} missing\n"


def project_context(cfg, remaining=None, spent=0.0):
    ctx = dict(cfg.data)
    ctx["remaining"] = cfg["budget"] - spent if remaining is None else remaining
    ctx["spent"] = spent
    ctx["agents"] = cfg.agents
    return ctx


def empty_round_context(**known):
    ctx = {key: "n/a" for key in ROUND_KEYS}
    for key in BEFORE_ROUND:
        ctx[key] = "none"
    ctx["steps"] = []
    ctx["runner"] = "harness/src/run.py"
    ctx.update(known)
    return ctx


def plan_text(plan):
    lines = [str(plan.get("summary", ""))]
    for key, title in (("scope", "Scope"), ("validation", "Validation"), ("non_goals", "Non-goals"), ("assumptions", "Assumptions")):
        items = plan.get(key) or []
        if items:
            lines.append(f"{title}:")
            lines += [f"- {item}" for item in items]
    if plan.get("quote_usd") is not None:
        lines.append(f"Quote: {render.fmt(plan['quote_usd'])}")
    if plan.get("todos"):
        lines.append("TODOs: " + render.fmt(plan["todos"]))
    extra = {k: v for k, v in plan.items() if k not in ("summary", "scope", "validation", "non_goals", "assumptions",
                                                          "quote_usd", "todos", "presented_at", "approval", "round",
                                                          "owner_words", "provided_artifacts")}
    if extra:
        lines.append(render.fmt(extra))
    return "\n".join(lines)


def step_table(cfg, overrides=()):
    rows = []
    for s in pipeline.PIPELINE:
        if s.kind in ("plan", "producer", "code"):
            gate = pipeline.gate_of(s.name)
            llm = bool(gate) and pipeline.step(gate).kind == "gate"  # the approval gate is mechanical: no agent, no gate share
            rows.append({"step": s.name, "gate": gate, "overridden": s.name in overrides,
                         "gate_runs": llm and cfg.gate_enabled(gate) and gate not in overrides and s.name not in overrides})
    return rows


def advances(name):
    return f"the round advances to {name}" if name else "the round finishes"


def artifact_contract(name, paths):
    s = pipeline.step(name)
    if s.kind == "code":
        return "the files you change under WRITE_PATHS; the runner commits them and shows the gate the diff"
    if s.artifact == "postmortem":
        return f"{paths['postmortem']}: non-empty prose, plain English"
    schema = schemas.ARTIFACT_SCHEMA.get(s.artifact)
    if s.kind == "plan":
        return schemas.describe(schema)
    text = f"{paths[s.artifact]}: {schemas.describe(schema)}" if schema else paths.get(s.artifact, "none")
    if s.artifact == "spec":
        text += f"; and {paths['specProse']}: the spec body the owner reads, plain English, non-empty"
    return text


def step_context(cfg, name, attempt, paths, worktree, harness_root, spec=None, budget=0.0, budget_cap=0.0,
                 retry_cost=0.0, rung=None, gate_runs=False, overrides=(), delegated=False, findings=(), carried=(),
                 previous="none", question="none", conflicts=(), next_finding_id=1, frozen=False, sibling_paths=(),
                 changed_tests=(), sub_agents=0, merge=False, verify_timeout=None, producer_attempt=None):
    s = pipeline.step(name)
    spec = spec or {}
    rung_name, agent = rung or (cfg["maxAgent"], cfg.agents.get(cfg["maxAgent"], {}))
    producer = pipeline.producer_of(name) if s.kind == "gate" else name
    gate = pipeline.gate_of(name) if s.kind != "gate" else name
    folder = paths["folder"]
    impl, tests = list(spec.get("implPaths") or []), list(spec.get("testPaths") or [])
    living = cfg.living_paths()
    write = {"round": [folder], "testPaths": tests + [folder], "implPaths": impl + list(conflicts) + [folder],
             "cleanup": impl + [p for p in living if not any(procs.under(p, t) for t in tests)] + ["INDEX.md", folder],
             "postmortem": [folder] + list(cfg["carryForwardFiles"])}.get(s.writes, [folder])
    write = list(dict.fromkeys(write))
    absolute = lambda rel: os.path.join(harness_root, *rel.split("/"))
    prompt_file = absolute(f"{paths['prompts']}/{name}-{attempt}.txt")
    result_file = absolute(f"{paths['results']}/{name}-{attempt}.json")
    producer_step = pipeline.step(producer) if producer else None
    artifact = "none"
    if producer_step and producer_step.artifact:
        artifact = absolute(paths[producer_step.artifact])
    elif producer_step and producer_step.kind == "code":
        artifact = "a diff under WRITE_PATHS"
    diff_file = "none"
    if s.kind == "gate" and producer_step and producer_step.kind == "code":
        diff_file = absolute(f"{paths['prompts']}/{name}-{attempt}.diff")
    inputs = [paths["plan"]]
    if producer in ("PLAN-TO-SPEC", "SPEC-TO-TESTS", "SPEC-TO-IMPLEMENTATION", "TESTS-TO-SUITE", "CLEANUP"):
        inputs.append(paths["agentsPlan"])
    if producer in ("SPEC-TO-TESTS", "SPEC-TO-IMPLEMENTATION", "TESTS-TO-SUITE", "CLEANUP"):
        inputs += [paths["spec"], paths["specProse"]]
    if producer in ("SPEC-TO-IMPLEMENTATION", "TESTS-TO-SUITE", "CLEANUP"):
        inputs += tests
    if producer == "CLEANUP":
        inputs.append(paths["suite"])
    if producer == "POSTMORTEM":
        inputs = [paths["history"], paths["findings"], paths["results"], paths["defined"], paths["undefined"],
                  paths["ownerLog"], paths["state"], paths["plan"], paths["specProse"]] + list(cfg["carryForwardFiles"])
    if s.kind == "gate":
        if producer_step.artifact:
            inputs = [paths[producer_step.artifact]] + ([paths["specProse"]] if producer_step.artifact == "spec" else []) + inputs
        inputs += [paths["defined"], paths["undefined"],
                   f"{paths['results']}/{producer}-{attempt if producer_attempt is None else producer_attempt}.json"]
    inputs = list(dict.fromkeys(inputs))
    review = " after a review checkpoint with the owner" if (name in cfg["checkpointsAfter"] or (gate in cfg["checkpointsAfter"] and not gate_runs)) and not delegated else ""
    if gate and gate_runs:
        after_done = f"the mechanical checks, then {gate}"
        after_needs_owner = ("the gate rules on your question: withdrawn means you are judged on your assumption; "
                             "upheld pauses the round for the owner, whose answer returns to you as a finding")
    else:
        after_done = "the mechanical checks; " + (f"{gate} is disabled this round, so " if gate else "") + f"a clean DONE is accepted and {advances(pipeline.next_after(gate or name))}{review}"
        after_needs_owner = ("the round proceeds on your stated assumption, logged as an undefined judgment call" if delegated
                             else "the round pauses for the owner; their answer returns to you as a finding")
    after_pass = f"{advances(pipeline.next_after(name))}{review}" if s.kind == "gate" else "none"
    verify = spec.get("verify") or "none"
    ctx = {
        "name": name, "kind": s.kind, "attempt": attempt, "budget": round(budget, 2), "budget_cap": round(budget_cap, 2),
        "max_turns": cfg["maxTurnsPerRun"], "wall_clock_hours": cfg["maxRunWallClockHours"], "retry_cost": round(retry_cost, 2),
        "agent": rung_name, "model": agent.get("model", "none"), "model_alias": cfg.model_alias(agent.get("model", "none")),
        "effort": agent.get("effort", "none"), "producer": producer or "none", "gate": gate or "none", "gate_enabled": bool(gate_runs),
        "artifact": artifact, "artifact_contract": artifact_contract(producer or name, paths) if producer else "none",
        "diff_file": diff_file, "result_file": result_file, "prompt_file": prompt_file,
        "write_paths": write if s.kind != "gate" else [], "frozen_paths": tests if frozen else [],
        "inputs": inputs, "checks": "; ".join(f"{c}: {pipeline.CHECKS[c]}" for c in pipeline.checks_for(producer or name, merge)),
        "findings": list(findings) or "none", "carried": list(carried) or "none", "previous": previous or "none",
        "question": question or "none", "sub_agents": sub_agents, "conflicts": list(conflicts) or "none",
        "next_finding_id": next_finding_id, "after_done": after_done, "after_needs_owner": after_needs_owner,
        "after_pass": after_pass, "verify": verify, "verify_timeout": verify_timeout or spec.get("verifyTimeoutSeconds") or cfg["verifyTimeoutSeconds"],
        "suite_command": cfg["suiteCommand"], "carry_forward": list(cfg["carryForwardFiles"]),
        "sibling_paths": list(sibling_paths) or "none", "changed_tests": list(changed_tests) or "none",
    }
    return ctx


def render_prompt(cfg, root, name, round_ctx, step_ctx, project_ctx=None, prose_commit=None, gate_runs=False,
                  header=None, prose=None):
    """(text, unresolved tokens, warnings) for one step; the header is AGENTS.md inserted raw."""
    s = pipeline.step(name)
    prose = prose or prose_reader(cfg, root, prose_commit)
    gate_name = gate_note = gate_sentence = None
    if s.kind in ("producer", "code", "plan"):
        gate_name = pipeline.gate_of(name)
        if gate_name and pipeline.step(gate_name).kind == "approval":
            gate_name, gate_sentence = None, CHAT_GATE_SENTENCE
        elif gate_name and not gate_runs:
            gate_note = render.DISABLED_NOTE
    context = {"project": project_ctx or project_context(cfg), "round": round_ctx, "step": step_ctx}
    r = render.Renderer(prose, plumbing_reader(), context, s.kind, name, gate_name, gate_note, gate_sentence)
    prose_file = pipeline.prose_file(name)
    text = prose(prose_file[:-4]) if prose_file else None
    if text is None:
        raise RunnerError(f"step {name} has no prose {prose_file}: restore it or override the step", 2)
    if header is None:
        cached = getattr(prose, "cache", {}).get(cfg.repo_rel(AGENTS_MD)) if prose_commit else None
        header = cached if cached is not None else agents_md(cfg, root, prose_commit)
    out = render.assemble(header, text, r)
    tokens = len(out.encode("utf-8")) / max(cfg["tokenBytes"], 1)
    if tokens > cfg["promptTokenWarn"]:
        r.warnings.append(f"W2: prompt is about {int(tokens)} tokens, over promptTokenWarn {cfg['promptTokenWarn']}")
    return out, r.unresolved, r.warnings


def fixture_contexts(cfg, root, name, attempt=1):
    """Synthetic round and step contexts so every prompt renders before any round exists."""
    paths = cfg.round_paths(1)
    spec = {"verify": ["py", "-3.13", "-m", "pytest", "-q"], "implPaths": ["src/"], "testPaths": ["tests/"],
            "verifyTimeoutSeconds": cfg["verifyTimeoutSeconds"]}
    round_ctx = empty_round_context(
        id=cfg.round_id(1), number=1, folder=paths["folder"], worktree=root, harness_root=cfg.harness_root,
        branch="round/" + cfg.round_id(1), base_commit="0" * 40, prose_commit="0" * 40,
        plan=plan_text({"summary": "fixture plan", "scope": ["a"], "validation": ["b"], "non_goals": ["c"], "quote_usd": 100}),
        budget=100, spend=0, remaining=100, status="active", step=name, steps=step_table(cfg),
        judgment_files=[cfg.abs_path(paths["defined"]), cfg.abs_path(paths["undefined"])],
        judgment_calls={"defined": 0, "undefined": 0}, owner_log="none")
    gate = pipeline.gate_of(name) if pipeline.step(name).kind != "gate" else name
    gate_runs = bool(gate) and cfg.gate_enabled(gate)
    step_ctx = step_context(cfg, name, attempt, paths, root, cfg.harness_root, spec=spec, budget=10.0, budget_cap=60.0,
                            retry_cost=12.0, gate_runs=gate_runs, frozen=name in ("SPEC-TO-IMPLEMENTATION", "CLEANUP"))
    return round_ctx, step_ctx, gate_runs
