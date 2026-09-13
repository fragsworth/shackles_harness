"""Test fixtures: the generated minimal spec, the toy project, throwaway repositories and origins."""
import os
import shutil
import sys

import yaml

from shackles import config as configmod
from shackles import pipeline, procs

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "harness", "src")
FIXTURES = os.path.join(HERE, "fixtures")
TOY = os.path.join(FIXTURES, "toy")
STUB = os.path.join(HERE, "stub_agent.py")
OWNER_KEYS = ["shackles", "currency", "budget", "hardStopBudgetMultiple", "lostValuePerHour", "ownerHourlyRate",
              "costToWaitForOwner", "planCostPerWord", "specCostPerWord", "livingFileTokenCap", "livingFileCostPerToken",
              "livingFileCostPerTokenOverCap", "livingFileBaseCost", "testBaseCost", "tokenBytes", "maxRefactorOverhead",
              "gates", "defaultShares", "livingSourcePaths", "lockedProsePath", "archivesPath", "roundPaths",
              "maxSimultaneousSubAgentsPerRound", "maxRoundAttempts", "maxFailuresBeforeStop", "maxTurnsPerRun",
              "maxRunWallClockHours", "verifyTimeoutSeconds", "gatesFraction", "workFraction", "estOutputFraction",
              "driverUsdPerStep", "subAgentsFile", "maxAgent", "gateAgent", "systemTestAgent"]
ROSTER = {
    "max": {"name": "Max", "model": "claude-fable-5-1", "effort": "max", "inputUsdPerMTok": 10, "outputUsdPerMTok": 50,
            "cacheReadUsdPerMTok": 1, "cacheWriteUsdPerMTok": 12.5, "spawnCost": 0.21},
    "high": {"name": "High", "model": "claude-fable-5-1", "effort": "low", "inputUsdPerMTok": 10, "outputUsdPerMTok": 50,
             "cacheReadUsdPerMTok": 1, "cacheWriteUsdPerMTok": 12.5, "spawnCost": 0.07},
    "medium": {"name": "Medium", "model": "claude-opus-5", "effort": "high", "inputUsdPerMTok": 5, "outputUsdPerMTok": 25,
               "cacheReadUsdPerMTok": 0.5, "cacheWriteUsdPerMTok": 6.25, "spawnCost": 0.06},
    "low": {"name": "Low", "model": "claude-sonnet-5", "effort": "high", "inputUsdPerMTok": 2, "outputUsdPerMTok": 10,
            "cacheReadUsdPerMTok": 0.2, "cacheWriteUsdPerMTok": 2.5, "spawnCost": 0.02},
}
COMMON = {
    "COMMON-PROJECT": "Project {{ project.shackles }}: budget {{ project.budget }}, remaining {{ project.remaining }}, gates {{ project.gates }}.\n",
    "COMMON-ROUND": "ROUND {{ round.id }} folder {{ round.folder }} base {{ round.base_commit }}.\nPlan:\n{{ round.plan }}\nQuote {{ round.budget }}; spent {{ round.spend }}; remaining {{ round.remaining }}.\n",
    "COMMON-OVERVIEW": "Fixture overview: end DONE, NEEDS-OWNER, UPSTREAM or BLOCKED.\n",
    "COMMON-GATE": "Fixture gate: PASS or FAIL. A FAIL costs {{ step.retry_cost }}.\n",
}
AGENTS_MD = "# harness/\n\nFixture AGENTS.md: the driver runs the runner; {{ plumbing.PROCESS-INSTRUCTIONS }} is inserted by it.\n"


def producer_prose(name):
    return (f"{name}: fixture prose.\n\n{{{{ prose.COMMON-PROJECT }}}}\n{{{{ prose.COMMON-ROUND }}}}\n{{{{ prose.COMMON-OVERVIEW }}}}\n\n"
            f"Retry cost {{{{ step.retry_cost }}}}.\n\nThe gate that judges you will have the following prose: {{{{ plumbing.GATE-PROSE }}}}\n\n"
            "{{ plumbing.PROCESS-INSTRUCTIONS }}\n")


def gate_prose(name):
    return (f"{name}: fixture gate prose.\n\n{{{{ prose.COMMON-PROJECT }}}}\n{{{{ prose.COMMON-ROUND }}}}\n{{{{ prose.COMMON-GATE }}}}\n\n"
            "Not sensible? Fail.\n\n{{ plumbing.PROCESS-INSTRUCTIONS }}\n")


def fixture_project(gates=None, config=None):
    data = {k: configmod.DEFAULTS[k] for k in OWNER_KEYS}
    data = yaml.safe_load(yaml.safe_dump(data, sort_keys=False))
    data["shackles"] = "fixture project"
    data["livingSourcePaths"] = ["../src/", "../tests/", "docs/"]
    data["gates"] = {g: 0 for g in pipeline.gates()}
    for g, on in (gates or {}).items():
        data["gates"][g] = 1 if on else 0
    data.update(config or {})
    return data


def write_spec(root, gates=None, config=None, spec="fixture"):
    """Write spec.yaml and a harness/ with the fixture spec (or the owner's files) into `root`."""
    h = os.path.join(root, "harness")
    prose_dir = os.path.join(h, "locked_prose")
    os.makedirs(prose_dir, exist_ok=True)
    if spec == "real":
        for name in ("AGENTS.md", "project.yaml", "subAgents.yaml"):
            shutil.copyfile(os.path.join(REPO_ROOT, "harness", name), os.path.join(h, name))
        for name in os.listdir(os.path.join(REPO_ROOT, "harness", "locked_prose")):
            shutil.copyfile(os.path.join(REPO_ROOT, "harness", "locked_prose", name), os.path.join(prose_dir, name))
        shutil.copyfile(os.path.join(REPO_ROOT, "spec.yaml"), os.path.join(root, "spec.yaml"))
        if config or gates:
            data = configmod.load_yaml(os.path.join(h, "project.yaml"))
            for g, on in (gates or {}).items():
                data["gates"][g] = 1 if on else 0
            data.update(config or {})
            procs.write_text(os.path.join(h, "project.yaml"), yaml.safe_dump(data, sort_keys=False))
        return
    procs.write_text(os.path.join(h, "AGENTS.md"), AGENTS_MD)
    procs.write_text(os.path.join(h, "project.yaml"), yaml.safe_dump(fixture_project(gates, config), sort_keys=False))
    procs.write_text(os.path.join(h, "subAgents.yaml"), yaml.safe_dump({"agents": ROSTER}, sort_keys=False))
    files = ["harness/AGENTS.md", "harness/project.yaml", "harness/subAgents.yaml"]
    for name, text in COMMON.items():
        procs.write_text(os.path.join(prose_dir, name + ".txt"), text)
        files.append(f"harness/locked_prose/{name}.txt")
    for s in pipeline.PIPELINE:
        f = pipeline.prose_file(s.name)
        if not f:
            continue
        text = gate_prose(s.name) if s.kind == "gate" else producer_prose(s.name)
        procs.write_text(os.path.join(prose_dir, f), text)
        files.append(f"harness/locked_prose/{f}")
    procs.write_text(os.path.join(root, "spec.yaml"), "files:\n" + "".join(f"  - {f}\n" for f in sorted(files)))


def write_toy(root):
    """The toy project at <root>/src and <root>/tests, the target of fixture rounds."""
    for dirpath, _, names in os.walk(TOY):
        for name in names:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, TOY)
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)


def copy_runner(root):
    dst = os.path.join(root, "harness", "src")
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)


def local_yaml(root, agent_command=None, suite_command=None, extra=None):
    data = {"agentCommand": agent_command or [sys.executable, STUB, "{prompt_file}", "{model}", "{effort}",
                                               "{budget_cap_usd}", "{result_schema}", "{tool_flags}", "{task}"],
            "suiteCommand": suite_command or toy_verify()}
    data.update(extra or {})
    procs.write_text(os.path.join(root, "harness", "local.yaml"), yaml.safe_dump(data, sort_keys=False))


def toy_verify():
    return [sys.executable, "-m", "unittest", "discover", "-s", "../tests/toy", "-p", "test_*.py", "-t", "../tests/toy"]
