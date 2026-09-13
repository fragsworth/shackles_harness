"""Git as the lock manager: the claim, the landing phases, sync_main, siblings and the rounds report."""
import json
import os
import re

from . import checks, gitops, ledger, procs
from .gitops import RunnerError


def origin_round_ids(root):
    prefix = "refs/remotes/origin/round/"
    refs = gitops.git(root, "for-each-ref", "--format=%(refname)", prefix, check=False).splitlines()
    return [int(tail) for tail in (ref[len(prefix):] for ref in refs) if tail.isascii() and tail.isdigit()]


def claim(root, cfg, explicit=None):
    """Fetch, take the next free id and claim it on origin by compare-and-swap; nothing is created until it wins."""
    from .round import local_round_ids
    gitops.git(root, "fetch", "origin")
    rid = 1 + max(origin_round_ids(root) + local_round_ids(cfg) + [0])
    attempts = int(cfg["pushAttempts"])
    branch = None
    for _ in range(attempts):
        branch = explicit or f"round/{cfg.round_id(rid)}"
        proc = gitops.git_proc(root, "push", "--porcelain", f"--force-with-lease=refs/heads/{branch}:", "origin",
                               f"origin/{cfg['mainBranch']}:refs/heads/{branch}")
        if proc.ok and any(line.startswith("*") for line in proc.out.splitlines()):
            return rid, branch
        if explicit:
            raise RunnerError(f"round id taken: branch {explicit} exists on origin", 2)
        rid += 1
    raise RunnerError(f"round id: push rejected {attempts} times, last {branch}")


def merge_tree(root, ours, theirs):
    """(clean, tree oid, conflicted paths) from git merge-tree --write-tree."""
    proc = gitops.git_proc(root, "merge-tree", "--write-tree", "--name-only", ours, theirs)
    head_section = proc.out.replace("\r\n", "\n").split("\n\n", 1)[0]
    lines = [l for l in head_section.splitlines() if l.strip()]
    if proc.code == 0:
        return True, lines[0] if lines else None, []
    if proc.code == 1 and lines:
        return False, lines[0], sorted(set(procs.posix(p) for p in lines[1:]))
    raise RunnerError(f"git merge-tree failed: {(proc.err or proc.out).strip()[-300:]}")


def landing_target(r):
    cfg, root, st = r.cfg, r.root, r.state
    main = cfg["mainBranch"]
    if st["branch"] == main and st["mode"] == "no-branch":
        return None, None
    target = None
    if gitops.has_origin(root):
        gitops.git(root, "fetch", "origin")
        if gitops.ref_exists(root, f"refs/remotes/origin/{main}"):
            target = f"origin/{main}"
    if target is None and gitops.branch_exists(root, main):
        target = main
    if target is None:
        return None, None
    return target, gitops.git(root, "rev-parse", target + "^{commit}")


def landing_check(r, mutate=True):
    """(findings, target, target sha): merge the target into the round, then verify and the suite; never pushes or tags."""
    cfg, root, st = r.cfg, r.root, r.state
    target, sha = landing_target(r)
    if sha and not gitops.is_ancestor(root, sha, "HEAD"):
        clean, tree, conflicted = merge_tree(root, "HEAD", sha)
        if not clean:
            hrel = [cfg.harness_rel(p) for p in conflicted]
            f = checks.finding("L1", "\n".join(conflicted), f"merge conflict with {target}", "resolve the listed files on top of the target")
            if mutate:
                st["merge_pending"] = {"target": target, "target_sha": sha, "automerge_tree": tree, "conflicted": hrel}
            return [f], target, sha
        gitops.git(root, "merge", "--no-edit", "--no-verify", sha)
    spec = r.spec()
    for name, run in (("verify", lambda: checks.m3_verify(cfg, r.harness, spec)), ("suite", lambda: checks.m5_suite(cfg, r.harness))):
        found = run()
        if found:
            f = checks.finding("L2", found[0]["quote"], f"{name} failed at landing", "fix the implementation on the merged tree")
            return [f], target, sha
    return [], target, sha


def main_checked_out(root, main):
    return gitops.worktree_of_branch(root, main)


def ff_local_main(r):
    cfg, root, st = r.cfg, r.root, r.state
    main = cfg["mainBranch"]
    where = main_checked_out(root, main)
    if where is None:
        gitops.git(root, "branch", "-f", main, "HEAD")
        return True
    if procs.same_path(where, root):
        return True
    if not gitops.status_paths(where):
        gitops.git(where, "merge", "--ff-only", "-q", st["branch"])
        return True
    raise RunnerError(f"landing: {main} is checked out and dirty at {where}; commit or stash there, then rerun next")


def land(r, push=True):
    """LANDING: the check phase, then the bounded push loop, the living charge once, the tag; [] once landed."""
    cfg, root, st = r.cfg, r.root, r.state
    main = cfg["mainBranch"]
    findings, target, sha = landing_check(r, mutate=True)
    if findings:
        return findings
    tests = r.spec().get("testPaths") or []
    living, rows = 0.0, []
    for attempt in range(1, int(cfg["pushAttempts"]) + 1):
        living, rows = ledger.living_charge(cfg, root, sha or st["base_commit"], "HEAD", tests)
        if sha is None:
            break
        if gitops.has_origin(root) and st["mode"] == "worktree":
            if not push:
                break
            proc = gitops.git_proc(root, "push", "--porcelain", "origin", f"HEAD:refs/heads/{main}")
            if proc.ok:
                break
            if attempt == int(cfg["pushAttempts"]):
                raise RunnerError(f"landing: push of {main} rejected {attempt} times")
            findings, target, sha = landing_check(r, mutate=True)
            if findings:
                return findings
        else:
            ff_local_main(r)
            break
    ledger.append(st, "LANDING", st["attempts"].get("LANDING", 1), living, "living", json.dumps(rows, ensure_ascii=False)[:1500])
    gitops.git(root, "tag", "-f", f"round/{r.id}-landed")
    st["landed_at"] = procs.now()
    if gitops.has_origin(root) and st["mode"] == "worktree" and push:
        gitops.git(root, "push", "-f", "origin", f"refs/tags/round/{r.id}-landed", check=False)
        if main_checked_out(root, main) is None:
            gitops.git(root, "fetch", "-q", "origin", f"{main}:{main}", check=False)
        else:
            r.flag(f"{main} is checked out at {main_checked_out(root, main)}: run git pull --ff-only there")
    r.history(f"LANDED on {target or 'this checkout'} at {st['landed_at']}; living charge ${living}")
    return []


def sync_main(r, push=True):
    """After the round's last commit: bring the tail onto main by a bounded merge-and-push loop; never raises."""
    cfg, root, st = r.cfg, r.root, r.state
    main = cfg["mainBranch"]
    if not st.get("landed_at"):
        return False
    if st["mode"] == "no-branch" and st["branch"] == main:
        return True
    try:
        if not gitops.has_origin(root) or st["mode"] == "no-branch":
            where = main_checked_out(root, main)
            if where is None:
                return gitops.git_ok(root, "branch", "-f", main, "HEAD")
            if procs.same_path(where, root):
                return True
            return not gitops.status_paths(where) and gitops.git_ok(where, "merge", "--ff-only", "-q", st["branch"])
        for _ in range(int(cfg["pushAttempts"])):
            if not gitops.git_ok(root, "fetch", "origin"):
                return False
            remote = f"refs/remotes/origin/{main}"
            if not gitops.ref_exists(root, remote) or gitops.is_ancestor(root, remote, "HEAD"):
                if not push or gitops.git_ok(root, "push", "origin", f"HEAD:refs/heads/{main}"):
                    return True
                continue
            if not gitops.git_ok(root, "merge", "--no-edit", "--no-verify", remote):
                gitops.git(root, "merge", "--abort", check=False)
                r.history("sync_main: conflict with origin; tail commits arrive with the next landing")
                return False
        return False
    except RunnerError:
        return False


def live_sibling_branches(r):
    root = r.root
    if not gitops.has_origin(root):
        return []
    gitops.git(root, "fetch", "origin", check=False)
    gitops.git(root, "fetch", "origin", "--tags", check=False)
    out = []
    for rid in origin_round_ids(root):
        if rid == r.rid:
            continue
        name = f"round/{r.cfg.round_id(rid)}"
        if gitops.ref_exists(root, f"refs/tags/{name}-landed") or gitops.ref_exists(root, f"refs/tags/{name}-abandoned"):
            continue
        out.append((rid, f"refs/remotes/origin/{name}"))
    return out


def sibling_states(r):
    out = []
    try:
        for rid, ref in live_sibling_branches(r):
            text = gitops.show(r.root, ref, r.cfg.repo_rel(r.cfg.round_paths(rid)["state"]))
            if text:
                try:
                    st = json.loads(text)
                except ValueError:
                    continue
                if st.get("status") not in ("finished", "abandoned"):
                    out.append((rid, st))
    except RunnerError:
        pass
    return out


def sibling_overlaps(r, spec):
    mine = [procs.posix(p) for p in (spec.get("implPaths") or []) + (spec.get("testPaths") or [])]
    overlaps = []
    try:
        for rid, ref in live_sibling_branches(r):
            text = gitops.show(r.root, ref, r.cfg.repo_rel(r.cfg.round_paths(rid)["spec"]))
            if not text:
                continue
            try:
                theirs = json.loads(text)
            except ValueError:
                continue
            for p in (theirs.get("implPaths") or []) + (theirs.get("testPaths") or []):
                for q in mine:
                    if procs.under(p, q) or procs.under(q, p):
                        overlaps.append(f"round {r.cfg.round_id(rid)}: {p} overlaps {q}")
    except RunnerError:
        pass
    return sorted(set(overlaps))


def rounds_report(root, cfg):
    from .round import local_round_ids
    rows = {}
    for rid in local_round_ids(cfg):
        path = cfg.abs_path(cfg.round_paths(rid)["state"])
        st = procs.read_json(path) if os.path.exists(path) else {}
        rows[rid] = {"id": cfg.round_id(rid), "where": "local folder", "status": st.get("status"), "step": st.get("step"),
                     "spend": ledger.totals(cfg, st)["total_usd"] if st else None}
    if gitops.has_origin(root):
        gitops.git(root, "fetch", "origin", check=False)
        gitops.git(root, "fetch", "origin", "--tags", check=False)
        main = cfg["mainBranch"]
        base = gitops.git(root, "rev-parse", f"origin/{main}", check=False)
        for rid in origin_round_ids(root):
            name = f"round/{cfg.round_id(rid)}"
            ref = f"refs/remotes/origin/{name}"
            row = rows.setdefault(rid, {"id": cfg.round_id(rid), "where": "origin", "status": None, "step": None, "spend": None})
            row["origin_branch"] = name
            row["landed"] = gitops.ref_exists(root, f"refs/tags/{name}-landed")
            row["abandoned"] = gitops.ref_exists(root, f"refs/tags/{name}-abandoned")
            tip = gitops.git(root, "rev-parse", ref, check=False)
            text = gitops.show(root, ref, cfg.repo_rel(cfg.round_paths(rid)["state"]))
            if text:
                try:
                    st = json.loads(text)
                    row.update({"status": st.get("status"), "step": st.get("step"), "spend": ledger.totals(cfg, st)["total_usd"]})
                except ValueError:
                    pass
            else:
                row["claimed_but_empty"] = tip == base or not text
    worktrees = {}
    for path in gitops.worktrees(root):
        m = re.search(r"round-(\d+)$", path.replace("\\", "/"))
        if m:
            worktrees[int(m.group(1))] = {"path": path, "exists": os.path.isdir(path)}
    for rid, wt in worktrees.items():
        rows.setdefault(rid, {"id": cfg.round_id(rid), "where": "worktree", "status": None, "step": None, "spend": None})["worktree"] = wt
    return {"rounds": [rows[k] for k in sorted(rows)], "worktrees": [w["path"] for w in worktrees.values()]}
