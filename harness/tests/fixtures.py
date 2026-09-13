"""Test fixtures: the generated minimal spec, the toy project, throwaway repositories and origins."""
import atexit
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys

import yaml

from shackles import cli
from shackles import config as configmod
from shackles import gitops, pipeline, procs, specguard

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "harness", "src")
FIXTURES = os.path.join(HERE, "fixtures")
TOY = os.path.join(FIXTURES, "toy")
STUB = os.path.join(HERE, "stub_agent.py")
PRESENTED_AT = "2026-01-01T00:00:00Z"
PLAN = {"presented_at": PRESENTED_AT, "quote_usd": 100.0, "summary": "PLAN-SUMMARY-MARKER: add whisper to the toy",
        "scope": ["whisper(text) lowercases"], "validation": ["the toy tests pass"], "non_goals": ["NONGOAL-MARKER"], "assumptions": []}
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
GITIGNORE = ".claude/worktrees/\nharness/OWNER.log\nharness/local.yaml\n__pycache__/\n*.pyc\n.tmp-*\n"
_clock = [0]


def producer_prose(name):
    return (f"{name}: fixture prose.\n\n{{{{ prose.COMMON-PROJECT }}}}\n{{{{ prose.COMMON-ROUND }}}}\n{{{{ prose.COMMON-OVERVIEW }}}}\n\n"
            f"Retry cost {{{{ step.retry_cost }}}}.\n\nThe gate that judges you will have the following prose: {{{{ plumbing.GATE-PROSE }}}}\n\n"
            "{{ plumbing.PROCESS-INSTRUCTIONS }}\n")


def gate_prose(name):
    return (f"{name}: fixture gate prose.\n\n{{{{ prose.COMMON-PROJECT }}}}\n{{{{ prose.COMMON-ROUND }}}}\n{{{{ prose.COMMON-GATE }}}}\n\n"
            "Not sensible? Fail.\n\n{{ plumbing.PROCESS-INSTRUCTIONS }}\n")


def toy_verify():
    return [sys.executable, "-m", "unittest", "discover", "-s", "../tests/toy", "-p", "test_*.py", "-t", "../tests/toy"]


def stub_command():
    return [sys.executable, STUB, "{prompt_file}", "{model}", "{effort}", "{budget_cap_usd}", "{result_schema}", "{tool_flags}", "{task}"]


def fixture_project(gates=None, config=None):
    data = {k: configmod.DEFAULTS[k] for k in OWNER_KEYS}
    data = yaml.safe_load(yaml.safe_dump(data, sort_keys=False))
    data["shackles"] = "fixture project"
    data["livingSourcePaths"] = ["../src/", "../tests/", "docs/"]
    data["gates"] = {g: 0 for g in pipeline.gates()}
    for g, on in (gates or {}).items():
        data["gates"][g] = 1 if on else 0
    data["suiteCommand"] = toy_verify()
    data["agentCommand"] = stub_command()
    data["lostValuePerHour"] = 0
    data.update(config or {})
    return data


def write_spec(root, gates=None, config=None, spec="fixture"):
    """Write spec.yaml and a harness/ with the fixture spec (or the owner's files) into `root`."""
    h = os.path.join(root, "harness")
    prose_dir = os.path.join(h, "locked_prose")
    os.makedirs(prose_dir, exist_ok=True)
    if spec == "real":
        for rel in [specguard.SPEC_YAML] + specguard.spec_files(REPO_ROOT):  # spec.yaml and every path it lists, wherever it puts them
            dst = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(REPO_ROOT, *rel.split("/")), dst)
        for name in os.listdir(os.path.join(REPO_ROOT, "harness", "locked_prose")):
            shutil.copyfile(os.path.join(REPO_ROOT, "harness", "locked_prose", name), os.path.join(prose_dir, name))
        data = configmod.load_yaml(os.path.join(h, "project.yaml"))
        data["livingSourcePaths"] = ["../src/", "../tests/", "docs/"]
        data["suiteCommand"], data["agentCommand"], data["lostValuePerHour"] = toy_verify(), stub_command(), 0
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
        procs.write_text(os.path.join(prose_dir, f), gate_prose(s.name) if s.kind == "gate" else producer_prose(s.name))
        files.append(f"harness/locked_prose/{f}")
    procs.write_text(os.path.join(root, "spec.yaml"), "files:\n" + "".join(f"  - {f}\n" for f in sorted(files)))


def write_toy(root):
    for dirpath, dirs, names in os.walk(TOY):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if name.endswith(".pyc"):
                continue
            src = os.path.join(dirpath, name)
            dst = os.path.join(root, os.path.relpath(src, TOY))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
    for rel, header in (("harness/docs/TODO.md", "# TODO: carry-forward items, one section per round.\n"),
                        ("harness/docs/CLARIFICATIONS.md", "# CLARIFICATIONS: questions for the owner, one section per round.\n")):
        path = os.path.join(root, *rel.split("/"))
        if not os.path.exists(path):  # the sandbox keeps the copied files, so its planner sees the real items
            procs.write_text(path, header)


def copy_runner(root):
    shutil.copytree(SRC, os.path.join(root, "harness", "src"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)


def local_yaml(root, extra=None):
    procs.write_text(os.path.join(root, "harness", "local.yaml"), yaml.safe_dump(extra or {}, sort_keys=False))


def future_ts(minutes=None):
    import datetime
    _clock[0] += 1
    delta = datetime.timedelta(minutes=minutes if minutes is not None else _clock[0])
    return (datetime.datetime.now(datetime.timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


class Result:
    def __init__(self, code, stdout, stderr):
        self.code, self.stdout, self.stderr = code, stdout, stderr
        self.json = None
        for line in reversed(stdout.strip().splitlines()):
            try:
                self.json = json.loads(line)
                break
            except ValueError:
                continue

    def __repr__(self):
        return f"Result(code={self.code!r}, stdout={self.stdout[-1500:]!r}, stderr={self.stderr[-1500:]!r})"


@contextlib.contextmanager
def environ(extra):
    saved = {k: os.environ.get(k) for k in extra}
    os.environ.update({k: str(v) for k, v in extra.items() if v is not None})
    for k, v in extra.items():
        if v is None:
            os.environ.pop(k, None)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


TEMPLATES = {}


def build_repo(root, gates, config, spec):
    os.makedirs(root)
    write_spec(root, gates, config, spec)
    write_toy(root)
    copy_runner(root)
    procs.write_text(os.path.join(root, ".gitignore"), GITIGNORE)
    procs.write_text(os.path.join(root, ".gitattributes"), "harness/archives/**/*.jsonl merge=union\n")
    specguard.accept(root, "fixture baseline")
    gitops.git(root, "init", "-q", "-b", "main")
    gitops.git(root, "add", "-A")
    gitops.git(root, "commit", "-q", "-m", "base")


def _remove_at_exit(folder):
    try:
        procs.rmtree(folder)
    except OSError:
        pass


def template_repo(gates, config, spec):
    """One built repository per distinct (gates, config, spec), copied for every test that asks for it; removed at exit."""
    key = json.dumps([gates, config, spec], sort_keys=True, default=str)
    if key not in TEMPLATES:
        import tempfile
        folder = tempfile.mkdtemp(prefix="shackles-template-")
        atexit.register(_remove_at_exit, folder)
        root = os.path.join(folder, "repo")
        build_repo(root, gates, config, spec)
        TEMPLATES[key] = root
    return TEMPLATES[key]


class Repo:
    """A throwaway repository holding the fixture spec, the toy project and a copy of the runner."""

    def __init__(self, tmp, gates=None, config=None, spec="fixture", branch=None):
        self.tmp = str(tmp)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(self.tmp, exist_ok=True)
        shutil.copytree(template_repo(gates, config, spec), self.root)
        if branch:
            self.git("checkout", "-q", "-b", branch)
        self.scratch = os.path.join(self.tmp, "scratch")
        os.makedirs(self.scratch, exist_ok=True)
        self.stub_log = os.path.join(self.tmp, "stub.log")
        self.origin = None
        self.explicit_root = self.root

    # -- files and git -------------------------------------------------------
    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def write(self, rel, text):
        procs.write_text(self.path(rel), text)

    def append(self, rel, text):
        procs.append_text(self.path(rel), text)

    def read(self, rel):
        return procs.read_text(self.path(rel))

    def json(self, rel):
        return procs.read_json(self.path(rel))

    def exists(self, rel):
        return os.path.exists(self.path(rel))

    def git(self, *args, check=True):
        return gitops.git(self.root, *args, check=check)

    def head(self):
        return self.git("rev-parse", "HEAD")

    def dirty(self):
        return self.git("status", "--porcelain")

    def tags(self):
        return self.git("tag").split()

    def log(self):
        return self.git("log", "--format=%s").splitlines()

    def owner(self, message, at=None):
        from shackles import owner as ownermod
        main = gitops.main_root(self.root)
        ownermod.append_line(ownermod.log_path(main), message, at=at or future_ts())

    # -- runner ----------------------------------------------------------------
    def run(self, *argv, env=None, subprocess_mode=False):
        full = ["--root", self.explicit_root] + [str(a) for a in argv]
        if subprocess_mode:
            proc = subprocess.run([sys.executable, os.path.join(self.root, "harness", "src", "run.py")] + full, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", env=dict(os.environ, **{k: str(v) for k, v in (env or {}).items()}),
                                  cwd=self.root)
            return Result(proc.returncode, proc.stdout, proc.stderr)
        out, err = io.StringIO(), io.StringIO()
        with environ(env or {}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(full)
        return Result(code, out.getvalue(), err.getvalue())

    def plan_file(self, plan=None):
        _clock[0] += 1
        path = os.path.join(self.scratch, f"PLAN-{_clock[0]}.json")
        procs.write_json(path, plan or PLAN)
        return path

    def start(self, plan=None, no_branch=True, extra=(), env=None):
        args = ["start", "--plan", self.plan_file(plan)] + (["--no-branch"] if no_branch else []) + list(extra)
        return self.run(*args, env=env)

    def next(self, *extra, env=None):
        return self.run("next", *extra, env=env)

    def record(self, step, attempt, message, cost=0.01, extra=(), env=None):
        _clock[0] += 1
        path = os.path.join(self.scratch, f"result-{step}-{attempt}-{_clock[0]}.txt")
        procs.write_text(path, message if isinstance(message, str) else json.dumps(message))
        args = ["record", "--step", step, "--attempt", str(attempt), "--result", path]
        if cost is not None:
            args += ["--cost", str(cost)]
        return self.run(*args, *extra, env=env)

    def owner_cmd(self, name, quote="ok", *extra, env=None):
        return self.run(name, "--quote", quote, *extra, env=env)

    def state(self, rid=1):
        cfg = configmod.load(self.explicit_root)
        return procs.read_json(cfg.abs_path(cfg.round_paths(rid)["state"]))

    def folder(self, rid=1):
        cfg = configmod.load(self.explicit_root)
        return cfg.abs_path(cfg.round_paths(rid)["folder"])

    def act(self, action, mode="pass", env=None, cost=0.01, extra=()):
        import stub_agent
        stub_env = dict(env or {})
        message = stub_agent.perform(action["prompt_file"], mode, stub_env)
        procs.write_text(action["result_file"], message)
        args = ["record", "--step", action["step"], "--attempt", str(action["attempt"]), "--result", action["result_file"]]
        if cost is not None:
            args += ["--cost", str(cost)]
        return self.run(*args, *extra)

    def play(self, until=None, modes=None, env=None, limit=80, cost=0.01, auto_review=False):
        """next/act until the action for `until` ("STEP" or "STEP:attempt") is due, or a checkpoint, done or error."""
        modes = modes or {}
        for _ in range(limit):
            res = self.next()
            if auto_review and res.code == 10 and res.json.get("checkpoint", {}).get("kind") == "review":
                assert self.owner_cmd("approve", "approve").code == 0
                continue
            if res.json is None or res.code != 0 or res.json.get("kind") in ("checkpoint", "done"):
                return res
            step, attempt = res.json["step"], res.json["attempt"]
            if until in (step, f"{step}:{attempt}"):
                return res
            mode = modes.get(f"{step}:{attempt}") or modes.get(step) or modes.get("*") or "pass"
            rec = self.act(res.json, mode, env=env, cost=cost)
            if auto_review and rec.code == 10 and rec.json.get("checkpoint", {}).get("kind") == "review":
                assert self.owner_cmd("approve", "approve").code == 0
                continue
            if rec.code != 0:
                return rec
        raise AssertionError(f"play() did not reach {until} in {limit} actions")

    # -- origins and clones -------------------------------------------------------
    def add_origin(self):
        self.origin = Origin(os.path.join(self.tmp, "origin.git"))
        gitops.git(self.tmp, "init", "-q", "--bare", "-b", "main", self.origin.path)
        self.git("remote", "add", "origin", self.origin.path)
        self.git("push", "-q", "-u", "origin", "main")
        return self.origin

    def clone(self, name="clone"):
        other = Repo.__new__(Repo)
        other.tmp = os.path.join(self.tmp, name + "-tmp")
        os.makedirs(other.tmp, exist_ok=True)
        other.root = os.path.join(other.tmp, "repo")
        gitops.git(other.tmp, "clone", "-q", self.origin.path, other.root)
        other.scratch = os.path.join(other.tmp, "scratch")
        os.makedirs(other.scratch, exist_ok=True)
        other.stub_log = os.path.join(other.tmp, "stub.log")
        other.origin = self.origin
        other.explicit_root = other.root
        return other

    def view(self, worktree):
        v = Repo.__new__(Repo)
        v.__dict__.update(self.__dict__)
        v.explicit_root = worktree
        v.root = worktree
        return v


HOOK = '''#!{python}
import os, subprocess, sys
refname = sys.argv[1]
log = {log!r}
import fnmatch
if not fnmatch.fnmatch(refname, {pattern!r}):
    sys.exit(0)
with open(log, "a", encoding="utf-8") as f:
    f.write(refname + "\\n")
with open(log, encoding="utf-8") as f:
    count = len(f.read().splitlines())
{body}
'''
REJECT_BODY = '''reject = {reject!r}
if reject == "all" or count <= int(reject):
    sys.exit(1)
sys.exit(0)
'''
MOVE_BODY = '''if count == 1:
    subprocess.run(["git", "update-ref", "refs/heads/main", "refs/heads/side"], check=True)
    sys.exit(1)
sys.exit(0)
'''


class Origin:
    """A bare origin: origin-side truth read with git -C, and an installable Python update hook."""

    def __init__(self, path):
        self.path = path
        self.hook = os.path.join(path, "hooks", "update")
        self.log = os.path.join(os.path.dirname(path), "hook.log")

    def git(self, *args):
        return gitops.git(self.path, *args)

    def sha(self, branch):
        return self.git("rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")

    def branches(self, prefix="refs/heads/"):
        return self.git("for-each-ref", "--format=%(refname:short)", prefix).splitlines()

    def tags(self):
        return self.git("tag").split()

    def install_reject_hook(self, pattern, reject):
        self._install(HOOK.format(python=sys.executable.replace("\\", "/"), log=self.log, pattern=pattern, body=REJECT_BODY.format(reject=reject)))

    def install_move_and_reject_once_hook(self):
        self._install(HOOK.format(python=sys.executable.replace("\\", "/"), log=self.log, pattern="refs/heads/main", body=MOVE_BODY))

    def _install(self, text):
        with open(self.hook, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.chmod(self.hook, 0o755)

    def remove_hook(self):
        if os.path.exists(self.hook):
            os.remove(self.hook)

    def hook_log(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return f.read().splitlines()
