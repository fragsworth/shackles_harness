"""Effective configuration: code DEFAULTS < project.yaml < local.yaml, roster from subAgentsFile."""
import copy
import os
import re

import yaml

from . import procs
from .gitops import RunnerError

HARNESS_DIR = "harness"
PROJECT_FILE = "project.yaml"
LOCAL_FILE = "local.yaml"

DEFAULTS = {
    # owner keys, valued as project.yaml is today
    "shackles": "",
    "currency": "USD",
    "budget": 50000,
    "hardStopBudgetMultiple": 6,
    "lostValuePerHour": 1,
    "ownerHourlyRate": 10,
    "costToWaitForOwner": 5,
    "planCostPerWord": 0.1,
    "specCostPerWord": 0.1,
    "livingFileTokenCap": 10000,
    "livingFileCostPerToken": 0.25,
    "livingFileCostPerTokenOverCap": 0.5,
    "livingFileBaseCost": 10,
    "testBaseCost": 3,
    "tokenBytes": 4,
    "maxRefactorOverhead": 0.3,
    "gates": {
        "CHAT-TO-PLAN-GATE": 0, "PLAN-AGENTS-GATE": 0, "PLAN-TO-SPEC-GATE": 0, "SPEC-TO-TESTS-GATE": 0,
        "SPEC-TO-IMPLEMENTATION-GATE": 0, "TESTS-TO-SUITE-GATE": 0, "POSTMORTEM-GATE": 0,
    },
    "defaultShares": {"work": {"CHAT-TO-PLAN": 0.05, "PLAN-AGENTS": 0.03},
                      "gates": {"CHAT-TO-PLAN": 0.02, "PLAN-AGENTS": 0.03}},
    "livingSourcePaths": ["src/", "docs/", "tests/"],
    "lockedProsePath": "locked_prose/",
    "archivesPath": "archives/",
    "roundPaths": {
        "folder": "archives/rounds/NNNN/",
        "artifacts": {"plan": "PLAN.json", "agentsPlan": "AGENTS-PLAN.json", "spec": "SPEC.json",
                      "specProse": "SPEC.md", "suite": "SUITE.json", "postmortem": "POSTMORTEM.md"},
        "runner": {"state": "STATE.json", "history": "HISTORY.md", "ownerLog": "OWNER.log"},
        "attempts": {"prompts": "PROMPTS/", "results": "RESULTS/", "findings": "FINDINGS/"},
        "testsArchive": "tests-archive/",
        "judgmentCalls": {"defined": "DEFINED_JUDGMENT_CALLS.md", "undefined": "UNDEFINED_JUDGMENT_CALLS.md"},
    },
    "maxSimultaneousSubAgentsPerRound": 2,
    "maxRoundAttempts": 2,
    "maxFailuresBeforeStop": 3,
    "maxTurnsPerRun": 120,
    "maxRunWallClockHours": 12,
    "verifyTimeoutSeconds": 600,
    "gatesFraction": 0.3,
    "workFraction": 0.7,
    "estOutputFraction": 0.2,
    "driverUsdPerStep": 1.0,
    "subAgentsFile": "subAgents.yaml",
    "maxAgent": "max",
    "gateAgent": "max",
    "systemTestAgent": "medium",
    # runner keys
    "mainBranch": "main",
    "worktreeDir": ".claude/worktrees",
    "pushAttempts": 5,
    "infraRetries": 3,
    "checkpointsAfter": ["PLAN-TO-SPEC-GATE", "CLEANUP"],
    "ownerMinutesPerCheckpoint": 10,
    "minRunUsd": 1.0,
    "promptTokenWarn": 60000,
    "postmortemFeedRounds": 3,
    "findingQuoteMaxChars": 600,
    "testFunctionPattern": r"^\s*(async\s+)?def\s+test_\w+",
    "suiteCommand": ["py", "-3.13", "-m", "pytest", "-q", "tests", "-m", "not real"],
    "suiteTimeoutSeconds": 1800,
    "gitTimeoutSeconds": 300,
    "agentCommand": ["{claude}", "--print", "--output-format", "json", "--system-prompt-file", "{prompt_file}",
                     "--model", "{model}", "--effort", "{effort}", "--max-budget-usd", "{budget_cap_usd}",
                     "--json-schema", "{result_schema}", "--no-session-persistence", "{tool_flags}",
                     "--permission-mode", "bypassPermissions", "{task}"],
    "agentTask": "Do the task in your system prompt. Your final message must be exactly the JSON object it specifies.",
    "claudePath": None,
    "gateToolFlags": ["--tools", "Read", "Grep", "Glob"],
    "producerToolFlags": ["--disallowedTools", "Bash(git commit:*)", "Bash(git push:*)", "Bash(git tag:*)",
                          "Bash(git reset:*)", "Bash(git checkout:*)", "Bash(git clean:*)", "Bash(git merge:*)",
                          "Bash(git rebase:*)"],
    "scrubEnv": ["GH_TOKEN", "GITHUB_TOKEN", "GIT_ASKPASS"],
    "modelAliases": {"claude-fable-5-1": "fable", "claude-opus-5": "opus", "claude-sonnet-5": "sonnet"},
    "gitIdentity": {"name": "shackles-runner", "email": "runner@shackles.local"},
    "envelopePrefixes": ["<system-reminder", "<task-notification", "[SYSTEM NOTIFICATION", "<wake ",
                         "<webhook-payload", "<event "],
    "agentOverride": None,
    "carryForwardFiles": ["docs/TODO.md", "docs/CLARIFICATIONS.md"],
}

ROUND_PATH_KEYS = {
    "plan": ("artifacts", "plan"), "agentsPlan": ("artifacts", "agentsPlan"), "spec": ("artifacts", "spec"),
    "specProse": ("artifacts", "specProse"), "suite": ("artifacts", "suite"), "postmortem": ("artifacts", "postmortem"),
    "state": ("runner", "state"), "history": ("runner", "history"), "ownerLog": ("runner", "ownerLog"),
    "prompts": ("attempts", "prompts"), "results": ("attempts", "results"), "findings": ("attempts", "findings"),
    "testsArchive": ("testsArchive",), "defined": ("judgmentCalls", "defined"), "undefined": ("judgmentCalls", "undefined"),
}


def load_yaml(path):
    text = procs.read_text(path)
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RunnerError(f"{path}: not a mapping", 2)
    return data


def _compatible(default, value):
    if isinstance(default, bool):
        return isinstance(value, (bool, int))
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


class Config:
    def __init__(self, harness_root, data, sources, warnings, agents):
        self.harness_root = os.path.abspath(harness_root)
        self.repo_root = os.path.dirname(self.harness_root)
        self.data, self.sources, self.warnings, self.agents = data, sources, warnings, agents
        self.gates = self._gates()
        self.id_width = self._id_width()

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __contains__(self, key):
        return key in self.data

    def _gates(self):
        raw = self.data.get("gates") or {}
        gates = {}
        for name, value in raw.items():
            if value not in (0, 1, True, False):
                self.warnings.append(f"gates.{name}: value {value!r} read as {bool(value)}")
            gates[str(name)] = bool(value)
        return gates

    def gate_enabled(self, name):
        return self.gates.get(name, False)

    def _id_width(self):
        last = [p for p in procs.posix(self.data["roundPaths"].get("folder", "")).split("/") if p]
        match = re.search(r"N+", last[-1]) if last else None
        if not match:
            self.warnings.append("roundPaths.folder has no N-run; using archives/rounds/NNNN/")
            return 4
        return len(match.group(0))

    def round_id(self, rid):
        return str(rid).zfill(self.id_width)

    def round_folder(self, rid):
        folder = self.data["roundPaths"].get("folder") or DEFAULTS["roundPaths"]["folder"]
        parts = [p for p in procs.posix(folder).split("/") if p]
        if not re.search(r"N+", parts[-1]):
            parts = ["archives", "rounds", "NNNN"]
        parts[-1] = re.sub(r"N+", self.round_id(rid), parts[-1], count=1)
        return "/".join(parts)

    def round_paths(self, rid):
        """Every round file as an H-relative posix path (folders without a trailing slash)."""
        rp, folder, out = self.data["roundPaths"], self.round_folder(rid), {}
        out["folder"] = folder
        for key, route in ROUND_PATH_KEYS.items():
            node, default = rp, DEFAULTS["roundPaths"]
            for part in route:
                node = node.get(part) if isinstance(node, dict) else None
                default = default[part]
            if not isinstance(node, str):
                self.warnings.append(f"roundPaths.{'.'.join(route)} missing; using {default}")
                node = default
            out[key] = folder + "/" + procs.posix(node).strip("/")
        return out

    def artifact(self, key):
        return (self.data["roundPaths"].get("artifacts") or {}).get(key) or DEFAULTS["roundPaths"]["artifacts"].get(key)

    def living_paths(self):
        return [procs.posix(p) for p in self.data.get("livingSourcePaths") or []]

    def prose_dir(self):
        return procs.posix(self.data.get("lockedProsePath") or "locked_prose/").rstrip("/")

    def repo_rel(self, path):
        """H-relative posix path -> repo-relative posix path; refuses one that escapes the repository."""
        rel = os.path.normpath(os.path.join(HARNESS_DIR, procs.posix(path)))
        rel = procs.posix(rel)
        if rel == ".." or rel.startswith("../") or os.path.isabs(rel):
            raise RunnerError(f"path escapes the repository: {path}", 2)
        return "" if rel == "." else rel

    def abs_path(self, path):
        return os.path.join(self.harness_root, *procs.posix(path).split("/"))

    def rung(self, key):
        """(rung name, roster entry) with fallback to maxAgent then the first roster key, each a warning."""
        if key in self.agents:
            return key, self.agents[key]
        fallback = self.data.get("maxAgent")
        if fallback in self.agents:
            self.warnings.append(f"agent rung {key!r} unknown; using maxAgent {fallback!r}")
            return fallback, self.agents[fallback]
        if not self.agents:
            raise RunnerError("no agents in the roster", 2)
        first = next(iter(self.agents))
        self.warnings.append(f"agent rung {key!r} unknown; using first roster key {first!r}")
        return first, self.agents[first]

    def model_alias(self, model):
        return (self.data.get("modelAliases") or {}).get(model, model)


def load(root):
    """Effective config for the repository at `root` (its harness lives at <root>/harness)."""
    harness_root = os.path.join(os.path.abspath(root), HARNESS_DIR)
    data, sources, warnings = copy.deepcopy(DEFAULTS), {k: "default" for k in DEFAULTS}, []
    for name in (PROJECT_FILE, LOCAL_FILE):
        path = os.path.join(harness_root, name)
        if not os.path.exists(path):
            if name == PROJECT_FILE:
                warnings.append(f"{name} missing; every key at its default")
            continue
        for key, value in load_yaml(path).items():
            if key in DEFAULTS and DEFAULTS[key] is not None and value is not None and not _compatible(DEFAULTS[key], value):
                raise RunnerError(f"{name}: key {key!r} should be {type(DEFAULTS[key]).__name__}, got {type(value).__name__}", 2)
            data[key], sources[key] = value, name
    roster_path = os.path.join(harness_root, str(data.get("subAgentsFile") or "subAgents.yaml"))
    agents = {}
    if os.path.exists(roster_path):
        roster = load_yaml(roster_path).get("agents")
        if isinstance(roster, dict):
            agents = {str(k): v for k, v in roster.items() if isinstance(v, dict)}
        else:
            warnings.append(f"{os.path.basename(roster_path)}: no agents mapping")
    else:
        warnings.append(f"{os.path.basename(roster_path)} missing; no agent roster")
    for key in ("maxAgent", "gateAgent", "systemTestAgent"):
        if agents and data.get(key) not in agents:
            warnings.append(f"{key} {data.get(key)!r} is not a roster key")
    return Config(harness_root, data, sources, warnings, agents)
