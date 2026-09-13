"""The step table: code, cross-checked against the spec's data by lint and tests."""
from collections import namedtuple

Step = namedtuple("Step", "name kind artifact writes checks")

PIPELINE = [
    Step("CHAT-TO-PLAN", "plan", "plan", "round", ["PLAN"]),
    Step("CHAT-TO-PLAN-GATE", "approval", None, None, []),
    Step("PLAN-AGENTS", "producer", "agentsPlan", "round", ["S1"]),
    Step("PLAN-AGENTS-GATE", "gate", None, None, []),
    Step("PLAN-TO-SPEC", "producer", "spec", "round", ["S1", "W1"]),
    Step("PLAN-TO-SPEC-GATE", "gate", None, None, []),
    Step("SPEC-TO-TESTS", "code", None, "testPaths", ["M1"]),
    Step("SPEC-TO-TESTS-GATE", "gate", None, None, []),
    Step("SPEC-TO-IMPLEMENTATION", "code", None, "implPaths", ["M1", "M2", "M3"]),
    Step("SPEC-TO-IMPLEMENTATION-GATE", "gate", None, None, []),
    Step("TESTS-TO-SUITE", "producer", "suite", "round", ["S1", "S2"]),
    Step("TESTS-TO-SUITE-GATE", "gate", None, None, []),
    Step("CLEANUP", "code", None, "cleanup", ["M1", "M2", "M3", "M5"]),
    Step("LANDING", "landing", None, None, ["L1", "L2"]),
    Step("POSTMORTEM", "producer", "postmortem", "postmortem", ["S1"]),
    Step("POSTMORTEM-GATE", "gate", None, None, []),
]
BY_NAME = {s.name: s for s in PIPELINE}
NAMES = [s.name for s in PIPELINE]
AGENT_KINDS = ("producer", "code", "gate")
NOT_OVERRIDABLE = ("CHAT-TO-PLAN", "CHAT-TO-PLAN-GATE", "PLAN-TO-SPEC", "SPEC-TO-IMPLEMENTATION", "LANDING")
ALWAYS = ["M0", "M4", "E1"]
CHECKS = {
    "S1": "the artifact is readable and valid against its contract",
    "S2": "every test file changed this round under testPaths is listed exactly once in keep or archive",
    "M0": "HEAD did not move during the attempt (an agent commit is undone)",
    "M1": "no changed path outside WRITE_PATHS and the round folder (strays are reverted)",
    "M2": "no change under testPaths after the tests froze (reverted)",
    "M3": "SPEC.verify passes within its timeout",
    "M4": "the judgment-call files only grew",
    "M5": "the permanent suite (suiteCommand) is green",
    "E1": "a change to a spec file is diffed into HISTORY and shown to the owner before landing",
    "G1": "a gate run that changed files is discarded",
    "W1": "a live sibling round declares an overlapping path (warning)",
    "W2": "the prompt is larger than promptTokenWarn tokens (warning)",
    "L1": "the round merges cleanly with the landing target",
    "L2": "verify and the permanent suite are green on the merged tree",
    "L3": "every conflicted file is resolved (no unmerged index entries)",
    "PLAN": "PLAN.json is valid and carries the owner's approval when the gate is enabled",
}


def step(name):
    if name not in BY_NAME:
        raise KeyError(f"unknown step {name}")
    return BY_NAME[name]


def index(name):
    return NAMES.index(name)


def next_after(name):
    i = index(name)
    return NAMES[i + 1] if i + 1 < len(NAMES) else None


def producer_of(gate):
    i = index(gate)
    return NAMES[i - 1] if BY_NAME[gate].kind in ("gate", "approval") and i > 0 else None


def gate_of(producer):
    nxt = next_after(producer)
    return nxt if nxt and BY_NAME[nxt].kind in ("gate", "approval") else None


def producers():
    return [s.name for s in PIPELINE if s.kind in ("plan", "producer", "code")]


def gates():
    return [s.name for s in PIPELINE if s.kind in ("gate", "approval")]


def llm_gates():
    return [s.name for s in PIPELINE if s.kind == "gate"]


def earlier_producers(name):
    return [p for p in producers() if index(p) < index(name)]


def downstream(name):
    return NAMES[index(name) + 1:]


def is_overridable(name):
    return name in BY_NAME and name not in NOT_OVERRIDABLE


def prose_file(name):
    s = step(name)
    if s.kind in ("plan", "producer", "code"):
        return f"{name}-OVERVIEW.txt"
    if s.kind == "gate":
        return f"{name}.txt"
    return None


def prose_owner(filename):
    """The step a locked_prose file belongs to, "COMMON" for COMMON-*.txt, else None."""
    if not filename.endswith(".txt"):
        return None
    base = filename[:-4]
    if base.startswith("COMMON-"):
        return "COMMON"
    if base.endswith("-OVERVIEW") and base[:-9] in BY_NAME and BY_NAME[base[:-9]].kind in ("plan", "producer", "code"):
        return base[:-9]
    if base in BY_NAME and BY_NAME[base].kind == "gate":
        return base
    return None


def checks_for(name, merge_attempt=False):
    s = step(name)
    ids = list(s.checks)
    if s.kind in ("producer", "code"):
        ids = ALWAYS + ids
    if merge_attempt and name == "SPEC-TO-IMPLEMENTATION":
        ids.append("L3")
    return ids


def lint(cfg, prose_names, spec_files_present):
    """(errors, warnings) for the structural cross-checks between the table and the spec's data."""
    errors, warnings = [], []
    gate_keys = list(cfg.gates)
    pipeline_gates = gates()
    for key in gate_keys:
        if key not in pipeline_gates:
            errors.append(f"gates.{key} names no pipeline gate")
    ordered = [k for k in gate_keys if k in pipeline_gates]
    if ordered != sorted(ordered, key=pipeline_gates.index):
        errors.append("gates keys are not in pipeline order: " + ", ".join(ordered))
    for gate in pipeline_gates:
        if gate not in cfg.gates:
            warnings.append(f"gate {gate} absent from gates (disabled)")
    for name in prose_names:
        if prose_owner(name) is None:
            warnings.append(f"unknown prose file {name}")
    for s in PIPELINE:
        if s.kind in ("producer", "code", "plan") and prose_file(s.name) not in prose_names:
            errors.append(f"step {s.name} has no prose {prose_file(s.name)}: restore it or override the step")
        if s.kind == "gate" and cfg.gate_enabled(s.name) and prose_file(s.name) not in prose_names:
            warnings.append(f"gate {s.name} is enabled but {prose_file(s.name)} is missing (disabled)")
    artifacts = (cfg["roundPaths"].get("artifacts") or {})
    for s in PIPELINE:
        if s.artifact and s.artifact not in artifacts:
            warnings.append(f"roundPaths.artifacts.{s.artifact} missing (default used)")
    for key in ("maxAgent", "gateAgent", "systemTestAgent"):
        if cfg.get(key) not in cfg.agents:
            errors.append(f"{key} {cfg.get(key)!r} is not a roster key")
    for name in cfg.get("checkpointsAfter") or []:
        if name not in BY_NAME:
            warnings.append(f"checkpointsAfter names unknown step {name}")
    for path, present in spec_files_present.items():
        if not present:
            errors.append(f"spec file missing: {path}")
    return errors, warnings
