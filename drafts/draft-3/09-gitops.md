# 09 — Git as the only lock: `gitops.py`

## `src/gitops.py`

**Owns:** every git invocation in the harness: fetching, branches, the compare-and-swap
claim, lease-guarded pushes (the fence), worktrees, commits of explicit paths,
reverting strays, merges and conflict inspection, reading trees and blobs of a ref
(for the ledger), diffs (for gate prompts). Knows nothing about rounds, steps or
prices. **Depends on:** `errors`, `subprocess`. **Depended on by:** `rounds`,
`recording`, `next_action`, `landing`, `checks`, `ledger` (tree listings), `suite`
(file contents at a ref), `doctor` (remote reachability), `gitfixtures` (tests).

Design rules: a plain push of a **new** branch is the claim (the remote refuses an
existing name); every later push uses `--force-with-lease=<branch>:<expected sha>` and a
rejection is a `FenceError`; `GIT_TERMINAL_PROMPT=0` and `-c core.hooksPath=/dev/null`
are set so nothing blocks or runs hooks; all output is captured; every failure becomes
`GitError(command, returncode, stderr)`.

### Types

- `Change` (frozen dataclass): `status: str` (`A M D R ? U` — added, modified,
  deleted, renamed, untracked, unmerged), `path: str` (posix, relative to the repo
  root), `old_path: str | None`.
- `MergeResult` (dataclass): `clean: bool`, `conflicted: list[str]`, `sha: str | None`
  (the merge commit when clean and committed), `already_up_to_date: bool`.
- `TreeEntry` (frozen dataclass): `path: str`, `blob: str`, `size: int`.

### `class Repo`

Constructed with `(repo_root: Path, remote: str = "origin", git: str = "git",
timeout: int = 300)`.

- `run(args: list[str], cwd: Path | None = None, check: bool = True, input: bytes |
  None = None) -> subprocess.CompletedProcess` — the single subprocess wrapper.
  Raises `GitError`.
- `has_remote() -> bool`; `remote_url() -> str | None`.
- `fetch(prune: bool = True) -> None` — `fetch <remote> --prune`; raises `GitError`
  (the caller turns an unreachable remote into a refusal).
- `rev_parse(ref: str, cwd=None) -> str`; `ref_exists(ref: str) -> bool`;
  `is_ancestor(a: str, b: str) -> bool`; `head(cwd: Path) -> str`.
- `remote_branches(prefix: str) -> list[str]` — names under `refs/remotes/<remote>/`
  starting with the prefix, without the remote prefix (e.g. `round/0001`).
- `local_branches(prefix: str) -> list[str]`.
- `show(ref: str, path: str) -> bytes | None` — `git show <ref>:<path>`, `None` when
  absent.
- `ls_tree(ref: str, prefixes: list[str]) -> list[TreeEntry]` — recursive, with sizes
  (`ls-tree -r -l`), limited to the given path prefixes (repo-relative).
- `cat_blob(blob: str) -> bytes`.
- `create_branch_from(branch: str, start_ref: str) -> None` — raises `GitError` if the
  local branch exists.
- `delete_local_branch(branch: str, force: bool = False) -> None`.
- `push_new_branch(branch: str) -> str` — `push <remote> <branch>` without force; a
  rejection (remote already has it) raises `FenceError("CLAIM_LOST")`; returns the
  pushed sha.
- `push_lease(branch: str, expected_remote_sha: str, cwd: Path | None = None) -> str`
  — `push <remote> <branch>:<branch> --force-with-lease=<branch>:<expected>`; rejection
  raises `FenceError("FENCE")` with the branch and expected sha; returns the new sha.
- `push_to(branch: str, target: str, expected_target_sha: str) -> str` — `push
  <remote> <branch>:<target> --force-with-lease=<target>:<expected>`; only fast-forward
  is intended (the caller merged first); rejection raises `FenceError("TARGET_MOVED")`.
- `worktree_add(path: Path, branch: str) -> None`; `worktree_remove(path: Path, force:
  bool = True) -> None`; `worktree_list() -> list[tuple[Path, str]]` (path, branch);
  `worktree_prune() -> None`.
- `checkout(cwd: Path, branch: str) -> None`; `reset_hard(cwd: Path, ref: str) ->
  None`; `fast_forward(cwd: Path, ref: str) -> bool` — `merge --ff-only`; returns
  False when not possible (no exception).
- `status(cwd: Path) -> list[Change]` — `status --porcelain=v1 -z --untracked-files=all`,
  ignoring nothing; paths repo-relative.
- `diff_name_status(a: str, b: str, cwd=None, paths: list[str] | None = None) ->
  list[Change]` — with rename detection (`-M`).
- `diff_text(a: str, b: str | None, paths: list[str] | None, cwd=None, max_bytes:
  int = 2_000_000) -> str` — `b=None` means the working tree; truncated with a
  marker line when longer than `max_bytes`.
- `add_and_commit(cwd: Path, paths: list[str], message: str, allow_empty: bool =
  False) -> str | None` — stages exactly the given paths (`add -A -- <paths>` so
  deletions count), commits with the message, returns the sha; returns `None` when
  nothing was staged and `allow_empty` is false.
- `revert_paths(cwd: Path, changes: list[Change]) -> list[str]` — tracked changes:
  `checkout -- <path>` (renames: restore the old path and remove the new); untracked:
  delete the file; returns what was reverted. Never touches paths not listed.
- `merge(cwd: Path, ref: str, message: str) -> MergeResult` — `merge --no-ff --no-edit
  -m <message> <ref>`; on conflict returns `clean=False` with `conflicted` from
  `diff --name-only --diff-filter=U`, leaving the index and working tree as git left
  them (the auto-merged tree); on `Already up to date` returns `already_up_to_date`.
- `abort_merge(cwd: Path) -> None`.
- `conflicted_files(cwd: Path) -> list[str]`.
- `files_with_conflict_markers(cwd: Path, paths: list[str]) -> list[str]` — a file
  counts when any line starts with `<<<<<<< `, `=======` or `>>>>>>> `.
- `commit_merge_resolution(cwd: Path, paths: list[str], message: str) -> str` —
  `add -- <paths>` then `commit --no-edit -m` (completes the in-progress merge);
  raises `GitError` if unmerged entries remain.
- `merge_in_progress(cwd: Path) -> bool` — `MERGE_HEAD` exists.
- `backup_branch(cwd: Path, name: str) -> None` — `branch <name> HEAD`; used by the
  fence recovery (`recording`) to keep orphaned work [JC-31].
- `config_identity(cwd: Path) -> None` — sets a local `user.name`/`user.email`
  (`shackles runner` / `runner@shackles.local`) when none is configured, so commits
  never fail on a fresh machine.
- `repo_relative(path: Path) -> str`.
