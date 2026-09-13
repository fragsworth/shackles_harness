"""Thin git wrapper: argv lists, a fixed identity, no shell."""
import os

from . import procs

IDENTITY = ["-c", "user.name=shackles-runner", "-c", "user.email=runner@shackles.local"]
TIMEOUT = [300]


class RunnerError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def set_identity(name, email):
    IDENTITY[1], IDENTITY[3] = f"user.name={name}", f"user.email={email}"


def git_proc(root, *args, timeout=None, env=None):
    env = procs.child_env(base=env, extra={"GIT_TERMINAL_PROMPT": "0"})
    return procs.run(["git"] + IDENTITY + [str(a) for a in args], cwd=root, env=env, timeout=timeout or TIMEOUT[0])


def git(root, *args, check=True, timeout=None):
    proc = git_proc(root, *args, timeout=timeout)
    if check and not proc.ok:
        raise RunnerError(f"git {' '.join(str(a) for a in args)} failed: {(proc.err or proc.out).strip()}")
    return proc.out.strip()


def git_ok(root, *args):
    return git_proc(root, *args).ok


def head(root):
    return git(root, "rev-parse", "HEAD") if git_ok(root, "rev-parse", "--verify", "-q", "HEAD") else None


def ref_exists(root, ref):
    return git_ok(root, "rev-parse", "--verify", "-q", ref + "^{commit}")


def branch_exists(root, name):
    return ref_exists(root, "refs/heads/" + name)


def has_origin(root):
    return git_ok(root, "remote", "get-url", "origin")


def current_branch(root):
    out = git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    return out if out and out != "HEAD" else None


def is_ancestor(root, a, b):
    return git_ok(root, "merge-base", "--is-ancestor", a, b)


def main_root(root):
    """The main checkout of root's repository: root unless root is a linked worktree."""
    try:
        common = git(root, "rev-parse", "--git-common-dir")
    except RunnerError:
        return os.path.abspath(root)
    return os.path.dirname(os.path.abspath(os.path.join(root, common)))


def repo_root(path):
    try:
        return os.path.abspath(git(path, "rev-parse", "--show-toplevel"))
    except RunnerError:
        return None


def status_paths(root, *scope):
    """[(xy, posix path)] for every changed or untracked file, optionally limited to `scope` paths."""
    out = git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--", *scope) if scope else \
        git(root, "status", "--porcelain", "-z", "--untracked-files=all")
    items, fields = [], [f for f in out.split("\0") if f]
    i = 0
    while i < len(fields):
        xy, path = fields[i][:2], fields[i][3:]
        if xy[0] in "RC":
            i += 1
        items.append((xy, procs.posix(path)))
        i += 1
    return items


def show(root, commit, path):
    proc = git_proc(root, "show", f"{commit}:{path}")
    return procs.normalize_text(proc.out) if proc.ok else None


def blob_size(root, commit, path):
    proc = git_proc(root, "cat-file", "-s", f"{commit}:{path}")
    return int(proc.out.strip()) if proc.ok else None


def ls_tree(root, commit, *paths):
    proc = git_proc(root, "ls-tree", "-r", "--name-only", commit, "--", *paths)
    return [procs.posix(p) for p in proc.out.splitlines() if p] if proc.ok else []


def worktrees(root):
    lines = git(root, "worktree", "list", "--porcelain").splitlines()
    return [os.path.abspath(line[len("worktree "):]) for line in lines if line.startswith("worktree ")]


def checked_out_branches(root):
    lines = git(root, "worktree", "list", "--porcelain").splitlines()
    return [line[len("branch refs/heads/"):] for line in lines if line.startswith("branch refs/heads/")]


def worktree_of_branch(root, name):
    lines = git(root, "worktree", "list", "--porcelain").splitlines()
    current = None
    for line in lines:
        if line.startswith("worktree "):
            current = os.path.abspath(line[len("worktree "):])
        elif line == f"branch refs/heads/{name}":
            return current
    return None
