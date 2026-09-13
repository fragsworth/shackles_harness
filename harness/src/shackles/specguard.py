"""The spec-change guard: a hash baseline over spec.yaml and every file it lists."""
import json
import os

import yaml

from . import gitops, procs

SPEC_YAML = "spec.yaml"
BASELINE = "harness/archives/spec-baseline.json"
AUDIT = "harness/archives/spec-changes.jsonl"
INSTRUCTION = (
    "Review the effects: run `doctor` (pipeline and prose-file consistency, unresolved tokens), "
    "`render --step` for the affected steps, PROCESS.md's wording-adjacent table; "
    "a step, gate or artifact key change means `pipeline.py`; a config key change means `config.DEFAULTS`; "
    "then `spec accept --note \"<what you reviewed>\"` in the same commit."
)


def spec_files(root):
    path = os.path.join(root, SPEC_YAML)
    if not os.path.exists(path):
        return []
    data = yaml.safe_load(procs.read_text(path)) or {}
    files = data.get("files") if isinstance(data, dict) else None
    return [procs.posix(str(f)) for f in files] if isinstance(files, list) else []


def baseline_path(root):
    return os.path.join(root, *BASELINE.split("/"))


def audit_path(root):
    return os.path.join(root, *AUDIT.split("/"))


def load_baseline(root):
    path = baseline_path(root)
    return procs.read_json(path) if os.path.exists(path) else None


def check(root):
    result = {"changed": [], "added": [], "removed": [], "missing": [], "spec_yaml_changed": False,
              "baseline_missing": False, "accepted_commit": None}
    baseline = load_baseline(root)
    listed = spec_files(root)
    if baseline is None:
        result["baseline_missing"] = True
        result["missing"] = [f for f in listed if not os.path.exists(os.path.join(root, f))]
        result["added"] = [f for f in listed if f not in result["missing"]]
        result["clean"] = False
        return result
    result["accepted_commit"] = baseline.get("accepted_commit")
    spec_path = os.path.join(root, SPEC_YAML)
    result["spec_yaml_changed"] = not os.path.exists(spec_path) or procs.sha256_file(spec_path) != baseline.get("spec_yaml")
    known = baseline.get("files") or {}
    for f in listed:
        path = os.path.join(root, f)
        if not os.path.exists(path):
            result["missing"].append(f)
        elif f not in known:
            result["added"].append(f)
        elif procs.sha256_file(path) != known[f]:
            result["changed"].append(f)
    result["removed"] = [f for f in known if f not in listed]
    result["clean"] = not any(result[k] for k in ("changed", "added", "removed", "missing", "spec_yaml_changed"))
    return result


def accept(root, note):
    listed = spec_files(root)
    before = check(root)
    spec_path = os.path.join(root, SPEC_YAML)
    baseline = {
        "accepted_at": procs.now(),
        "accepted_commit": gitops.head(root) if gitops.git_ok(root, "rev-parse", "--git-dir") else None,
        "note": note,
        "spec_yaml": procs.sha256_file(spec_path) if os.path.exists(spec_path) else None,
        "files": {f: procs.sha256_file(os.path.join(root, f)) for f in listed if os.path.exists(os.path.join(root, f))},
    }
    procs.write_json(baseline_path(root), baseline)
    line = {"at": baseline["accepted_at"], "commit": baseline["accepted_commit"], "note": note,
            "changed": before["changed"], "added": before["added"], "removed": before["removed"]}
    procs.append_text(audit_path(root), json.dumps(line, ensure_ascii=False) + "\n")
    return baseline


def diff_text(root, result=None, cap=200):
    """Unified diffs for the changed files from the accepted commit when git has it, else line counts."""
    result = result or check(root)
    commit = result.get("accepted_commit")
    out = []
    paths = result["changed"] + ([SPEC_YAML] if result["spec_yaml_changed"] else [])
    have_commit = bool(commit) and gitops.ref_exists(root, commit)
    for path in paths:
        if have_commit:
            text = gitops.git(root, "diff", commit, "--", path, check=False)
            lines = text.splitlines()
            if len(lines) > cap:
                lines = lines[:cap] + [f"... ({len(lines) - cap} more lines)"]
            out.append("\n".join(lines) if lines else f"{path}: changed (no textual diff)")
        else:
            full = os.path.join(root, path)
            count = len(procs.read_text(full).splitlines()) if os.path.exists(full) else 0
            out.append(f"{path}: content changed, now {count} lines (accepted commit not available locally)")
    return "\n".join(out)


def summary(result):
    lines = []
    for key in ("changed", "added", "removed", "missing"):
        if result[key]:
            lines.append(f"{key}: {', '.join(result[key])}")
    if result["spec_yaml_changed"]:
        lines.append("spec.yaml changed")
    if result["baseline_missing"]:
        lines.append("baseline missing: " + BASELINE)
    return "\n".join(lines) if lines else "clean"
