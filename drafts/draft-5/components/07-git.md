# 07 — Git (`gitops.py`)

**Purpose.** The only module that runs `git`. It offers the handful of operations the
engine needs — claim, fence, worktree, diff, revert, auto-merge, push with lease — as
plain functions returning plain data. It knows nothing about steps, prompts or money.

**Owns.** All `git` subprocess calls; the branch naming `round/NNNN`; the worktree
location `<repo>/.worktrees/round-NNNN`; conflict-marker detection; rename detection.

**Depends on.** 04 (`Paths` for the repo root and worktrees dir; `Config.gitRemote`,
`mainBranch`). Requires git ≥ 2.38.

**Depended on by.** 10 (engine, landing, mechanical), 09 (`ledger` uses `numstat` and
`show_bytes` for the living diff), 11 (doctor's git checks), 03 (`status`).

Every function takes `repo: Path` (a checkout: the driver's or a worktree) as its first
argument and runs git with `cwd=repo`. All raise `GitError(cmd, code, stderr)` on an
unexpected non-zero exit; the documented outcomes (rejected pushes, conflicts) are
returned, not raised.

---

## Types
- `class PushOutcome(Enum)`: `PUSHED`, `REJECTED` (lease/CAS failure), `NO_REMOTE`.
- `class MergeResult` (frozen): `tree: str` (sha of the auto-merged tree), `conflicts:
  list[str]` (paths), `clean: bool`, `messages: str` (git's informational output).
- `class FileChange` (frozen): `path: str`, `old_path: str | None` (rename source),
  `status: "A"|"M"|"D"|"R"`, `old_bytes: int`, `new_bytes: int`, `binary: bool`.

## Functions

Repository facts
- `git_version(repo) -> tuple[int, int]`; `require_version(repo, minimum=(2, 38))`.
- `remote_exists(repo, remote: str) -> bool`; `remote_url(repo, remote) -> str | None`.
- `fetch(repo, remote) -> None`.
- `rev_parse(repo, ref: str) -> str | None` — sha or `None` when unknown.
- `is_ancestor(repo, a: str, b: str) -> bool`.
- `dirty_paths(repo, roots: list[Path] | None = None) -> list[str]` — `status --porcelain`
  paths (tracked modifications and untracked files), optionally filtered to roots.
- `head(repo) -> str`; `current_branch(repo) -> str | None`.

Round branch and claim
- `next_round_id(repo, remote, rounds_dir_rel: str) -> str` — max over
  `<remote>/<main>:<rounds_dir_rel>/*` folder names and `refs/remotes/<remote>/round/*`
  branch names, + 1, zero-padded to the width of `NNNN` in the config pattern (4);
  starts at `0001`.
- `claim_round(repo, remote, main: str, round_id: str, first_commit_paths: list[Path],
  message: str) -> tuple[PushOutcome, str]` — creates local branch `round/<id>` at
  `<remote>/<main>`, commits the given paths, pushes with
  `--force-with-lease=refs/heads/round/<id>:` (expect absent). Returns the outcome and
  the commit sha. On `REJECTED` the local branch is deleted (JC-13).
- `fence_push(repo, remote, branch: str, expected_remote_sha: str | None) ->
  PushOutcome` — `--force-with-lease=<branch>:<expected>`; `expected None` means the
  branch must be absent.
- `commit_all(repo, paths: list[Path] | None, message: str, allow_empty: bool = False)
  -> str | None` — `add -A` on the paths (all when `None`), commit; `None` when nothing
  to commit and `allow_empty` is false.

Worktrees
- `worktree_add(repo, worktrees_dir: Path, branch: str, round_id: str) -> Path` —
  `git worktree add <dir>/round-<id> <branch>`; returns the path.
- `worktree_remove(repo, path: Path, force: bool = False) -> None`; `worktree_list(repo)
  -> list[tuple[Path, str]]` (path, branch); `worktree_prune(repo)`.

Diffs and reverts (used by mechanical checks and the ledger)
- `uncommitted_changes(repo, roots: list[Path] | None = None) -> list[FileChange]` —
  working tree vs HEAD, untracked included, renames detected (`-M`), byte counts from
  the blob (old) and the file (new).
- `changes_between(repo, base: str, target: str, roots: list[str] | None) ->
  list[FileChange]` — `diff --numstat -M --find-renames=50%` semantics with byte counts
  via `cat-file -s`; renames reported with `old_path` (JC-45).
- `revert_paths(repo, paths: list[str]) -> None` — tracked: `checkout HEAD -- path`;
  untracked: delete. Directories left empty are removed.
- `restore_from_tree(repo, tree: str, paths: list[str]) -> None` — `checkout <tree> --
  paths` (used to judge the conflict attempt against the auto-merged tree).
- `conflict_markers(repo, paths: list[str]) -> list[str]` — files among `paths` that
  contain a line starting with `<<<<<<< `, `=======` or `>>>>>>> `.
- `show_bytes(repo, ref: str, path: str) -> int | None` — blob size at ref, `None` if absent.
- `ls_tree_files(repo, ref: str, roots: list[str]) -> list[str]`.

Merging and landing
- `merge_tree(repo, base_ref: str, ours: str, theirs: str) -> MergeResult` —
  `git merge-tree --write-tree --merge-base=<base> <ours> <theirs>`; exit 1 = conflicts
  (parsed from the `CONFLICT` section), other non-zero = `GitError`.
- `checkout_tree_into_worktree(worktree: Path, tree: str) -> None` — `read-tree -u
  --reset <tree>` so the worktree shows the auto-merged content, markers included.
- `commit_tree(repo, tree: str, parents: list[str], message: str) -> str` — a commit
  object without touching any checkout.
- `push_ref(repo, remote, local_sha: str, remote_branch: str, expected_remote_sha: str)
  -> PushOutcome` — `push --force-with-lease=<branch>:<expected> <sha>:refs/heads/<branch>`.
- `update_branch(repo, branch: str, sha: str) -> None` — `update-ref`.
- `fast_forward_checkout(repo, remote, main) -> bool` — `merge --ff-only` in a clean
  checkout; `False` when not clean or not a fast-forward (never forces) (JC-24).
- `delete_remote_branch(repo, remote, branch) -> PushOutcome`.

## Invariants
- No `git push` without `--force-with-lease`; no `--force` anywhere.
- Every function is safe to call twice (idempotent or returns a documented outcome).
- `revert_paths` and `restore_from_tree` are the only functions that discard content, and
  they touch exactly the paths given.
- The module never inspects file *contents* except for conflict markers and byte sizes.

## Covered by
`tests/test_gitops.py` (uses a temporary bare remote; cases in 13-tests.md).
