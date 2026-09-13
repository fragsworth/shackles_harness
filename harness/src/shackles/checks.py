"""Mechanical checks: each returns findings {id, quote, reason, suggestion, blocking, source: mechanical}."""
import os
import shlex

from . import gitops, pipeline, procs, schemas, specguard

RUNNER_OWNED = ("state", "history", "ownerLog", "prompts", "results", "findings", "testsArchive")


def finding(fid, quote, reason, suggestion, blocking=True, source="mechanical"):
    return {"id": fid, "quote": quote, "reason": reason, "suggestion": suggestion, "blocking": blocking, "source": source}


def command_argv(command):
    if isinstance(command, list):
        return [str(c) for c in command]
    return shlex.split(str(command), posix=os.name != "nt")


def run_command(command, cwd, timeout, env=None):
    """(ok, tail of the output) for a verify or suite command run from cwd."""
    argv = command_argv(command)
    if not argv:
        return False, "empty command"
    try:
        proc = procs.run(argv, cwd=cwd, env=procs.child_env(base=env), timeout=timeout)
    except OSError as exc:
        return False, f"{' '.join(argv)}: {exc}"
    text = (proc.out + "\n" + proc.err).strip()
    if proc.timed_out:
        return False, f"timed out after {timeout} s\n" + text[-3000:]
    return proc.ok, text[-3000:]


def revert(root, items, merge_tree=None):
    """Undo the working-tree changes listed as (xy, path); restores from `merge_tree` on a merge attempt."""
    for xy, path in items:
        if merge_tree and gitops.git_ok(root, "cat-file", "-e", f"{merge_tree}:{path}"):
            gitops.git(root, "checkout", "-q", merge_tree, "--", path, check=False)
            continue
        if "?" in xy or xy[0] == "A":
            if xy[0] == "A":
                gitops.git(root, "rm", "-q", "--cached", "--", path, check=False)
            full = os.path.join(root, *path.split("/"))
            if os.path.isdir(full):
                procs.rmtree(full)
            elif os.path.exists(full):
                os.remove(full)
        else:
            gitops.git(root, "checkout", "-q", "HEAD", "--", path, check=False)


def dirty(root, exclude=()):
    return [(xy, p) for xy, p in gitops.status_paths(root) if p not in exclude and not p.endswith("/")]


def m1_strays(cfg, root, paths, allowed, items, merge_tree=None, exempt=()):
    """Changed paths (a dirty snapshot) outside the allowed H-relative prefixes and the round folder, or inside runner-owned round files;
    spec files are exempt (E1 shows them to the owner instead)."""
    allowed_rel = [cfg.repo_rel(p) for p in allowed] + [cfg.repo_rel(paths["folder"])]
    owned = [cfg.repo_rel(paths[k]) for k in RUNNER_OWNED]
    strays = []
    for xy, path in items:
        if path in exempt:
            continue
        inside = any(procs.under(path, a) for a in allowed_rel if a)
        owned_hit = any(procs.under(path, o) for o in owned)
        if not inside or owned_hit:
            strays.append((xy, path))
    if not strays:
        return [], []
    revert(root, strays, merge_tree)
    listed = [p for _, p in strays]
    return [finding("M1", "\n".join(listed), "changed paths outside WRITE_PATHS and the round folder, or runner-owned round files; reverted",
                    "change only files under WRITE_PATHS and the round folder")], listed


def m2_frozen(cfg, root, test_paths, items, merge_tree=None, conflicted=()):
    tests = [cfg.repo_rel(p) for p in test_paths]
    if not tests:
        return [], []
    touched = [(xy, p) for xy, p in items if any(procs.under(p, t) for t in tests if t)]
    hard = [(xy, p) for xy, p in touched if p not in conflicted]
    soft = [p for _, p in touched if p in conflicted]
    findings = []
    if hard:
        revert(root, hard, merge_tree)
        findings.append(finding("M2", "\n".join(p for _, p in hard), "tests changed after they froze; reverted",
                                "leave the frozen tests alone; a wrong test is UPSTREAM to SPEC-TO-TESTS"))
    if soft:
        findings.append(finding("T1", "\n".join(soft), "a frozen test was conflicted in the merge and hand-resolved; review it",
                                "keep the resolution minimal", blocking=False))
    return findings, [p for _, p in hard]


def m3_verify(cfg, harness_root, spec, env=None):
    command = spec.get("verify") if spec else None
    if not command:
        return [finding("M3", "none", "SPEC.json declares no verify command", "declare verify in SPEC.json")]
    timeout = spec.get("verifyTimeoutSeconds") or cfg["verifyTimeoutSeconds"]
    ok, tail = run_command(command, harness_root, timeout, env)
    if ok:
        return []
    return [finding("M3", tail, "verify failed", "make verify pass within its timeout")]


def m4_judgment(root, prompt_commit, files):
    """The judgment-call files only grew since the prompt commit; a rewrite is restored from it."""
    rewritten, current = [], None
    for line in gitops.git(root, "diff", prompt_commit, "--", *files, check=False).splitlines():
        if line.startswith("diff --git "):
            current = line.split(" b/", 1)[-1]
        elif line.startswith("-") and not line.startswith("---") and current and current not in rewritten:
            rewritten.append(current)
    if not rewritten:
        return [], []
    for path in rewritten:
        gitops.git(root, "checkout", "-q", prompt_commit, "--", path, check=False)
    return [finding("M4", "\n".join(rewritten), "a judgment-call file lost or changed existing lines; restored",
                    "append lines; never rewrite existing ones")], rewritten


def m5_suite(cfg, harness_root, env=None):
    ok, tail = run_command(cfg["suiteCommand"], harness_root, cfg["suiteTimeoutSeconds"], env)
    return [] if ok else [finding("M5", tail, "the permanent suite is red", "make suiteCommand green")]


def e1_spec_edits(root, base_commit, spec_files):
    """{path: unified diff} for every spec file that differs from base_commit."""
    out = {}
    if not spec_files:
        return out
    changed = gitops.git(root, "diff", "--name-only", base_commit, "--", *spec_files, check=False).splitlines()
    for path in (procs.posix(p) for p in changed if p.strip()):
        out[path] = gitops.git(root, "diff", base_commit, "--", path, check=False)
    for path in gitops.git(root, "ls-files", "--others", "--exclude-standard", "--", *spec_files, check=False).splitlines():
        if path.strip():
            out[procs.posix(path)] = f"(new file {path})"
    return out


def s1_agents_plan(cfg, obj, gate_runs, overrides):
    errors = schemas.validate(obj, schemas.SCHEMAS["AGENTS_PLAN"], "AGENTS_PLAN")
    if errors:
        return errors
    present = [p for p in pipeline.producers() if p not in overrides and p != "CHAT-TO-PLAN"]
    gated = [pipeline.producer_of(g) for g in pipeline.llm_gates() if gate_runs(g)]
    for key, rung in list(obj.get("agents", {}).items()) + list((obj.get("gateAgents") or {}).items()):
        if rung not in cfg.agents:
            errors.append(f"AGENTS_PLAN: {key} names unknown rung {rung!r}")
    for p in present:
        if p not in obj["agents"]:
            errors.append(f"AGENTS_PLAN: agents has no entry for {p}")
        if p not in obj["shares"]["work"]:
            errors.append(f"AGENTS_PLAN: shares.work has no entry for {p}")
    for p in gated:
        if p not in obj["shares"]["gates"]:
            errors.append(f"AGENTS_PLAN: shares.gates has no entry for {p} (its gate runs)")
    for name in ("work", "gates"):
        total = sum(float(v) for v in obj["shares"][name].values())
        if obj["shares"][name] and abs(total - 1.0) > 0.01:
            errors.append(f"AGENTS_PLAN: shares.{name} sums to {round(total, 3)}, not 1")
    cap = int(cfg["maxSimultaneousSubAgentsPerRound"])
    for step, count in (obj.get("subAgents") or {}).items():
        if int(count) > cap:
            errors.append(f"AGENTS_PLAN: subAgents.{step} is {count}, over maxSimultaneousSubAgentsPerRound {cap}")
    return errors


def s1_spec(cfg, obj, harness_root, paths, budget_usd, spec_files):
    errors = schemas.validate(obj, schemas.SCHEMAS["SPEC"], "SPEC")
    if errors:
        return errors
    impl, tests = [procs.posix(p) for p in obj["implPaths"]], [procs.posix(p) for p in obj["testPaths"]]
    protected = [paths["folder"], cfg.prose_dir()] + [os.path.relpath(f, "harness").replace("\\", "/") for f in spec_files]
    for p in impl + tests:
        try:
            rel = cfg.repo_rel(p)
        except Exception as exc:
            errors.append(f"SPEC: {exc}")
            continue
        for q in protected:
            if procs.under(p, q) or (q.startswith("../") and procs.under(rel, q[3:])):
                errors.append(f"SPEC: path {p} lies inside the protected path {q}")
    for a in impl:
        for b in tests:
            if procs.under(a, b) or procs.under(b, a):
                errors.append(f"SPEC: implPaths {a} and testPaths {b} overlap")
    refactor = sum(float(r.get("budget_usd", 0)) for r in obj.get("refactor") or [])
    cap = float(cfg["maxRefactorOverhead"]) * float(budget_usd)
    if refactor > cap + 1e-9:
        errors.append(f"SPEC: refactor budgets total {refactor}, over maxRefactorOverhead {cfg['maxRefactorOverhead']} x {budget_usd} = {round(cap, 2)}")
    prose = os.path.join(harness_root, *paths["specProse"].split("/"))
    if not os.path.exists(prose) or not procs.read_text(prose).strip():
        errors.append(f"SPEC: {paths['specProse']} missing or empty")
    return errors


def changed_tests(cfg, root, base_commit, test_paths):
    tests = [cfg.repo_rel(p) for p in test_paths]
    if not tests:
        return []
    committed = gitops.git(root, "diff", "--name-only", base_commit, "--", *tests, check=False).splitlines()
    untracked = [p for xy, p in gitops.status_paths(root, *tests) if "?" in xy]
    return sorted(set(procs.posix(p) for p in committed + untracked if p))


def s2_suite(cfg, obj, root, harness_root, base_commit, test_paths):
    errors = schemas.validate(obj, schemas.SCHEMAS["SUITE"], "SUITE")
    if errors:
        return errors
    listed = [procs.posix(p) for p in obj["keep"]] + [procs.posix(p) for p in obj["archive"]]
    listed_rel = []
    for p in listed:
        try:
            listed_rel.append(cfg.repo_rel(p))
        except Exception as exc:
            errors.append(f"SUITE: {exc}")
    for p, rel in zip(listed, listed_rel):
        if not os.path.exists(os.path.join(root, *rel.split("/"))):
            errors.append(f"SUITE: listed file {p} does not exist")
    changed = changed_tests(cfg, root, base_commit, test_paths)
    for path in changed:
        n = listed_rel.count(path)
        if n != 1:
            errors.append(f"SUITE: changed test file {cfg.harness_rel(path)} appears {n} times in keep/archive (must be exactly once)")
    return errors


def l3_unmerged(root, conflicted):
    """Conflicted files (repo-relative) that still carry conflict markers in the working tree."""
    left = []
    for path in conflicted:
        full = os.path.join(root, *path.split("/"))
        if not os.path.exists(full):
            continue
        for line in procs.read_text(full).splitlines():
            if line.startswith(("<<<<<<< ", ">>>>>>> ")) or line == "=======":
                left.append(path)
                break
    if not left:
        return []
    return [finding("L3", "\n".join(left), "conflicted files left unresolved", "resolve every listed file and remove the markers")]


def spec_paths(root):
    return specguard.spec_files(root)
