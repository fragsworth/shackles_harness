# 35 — src/shackles/git/ (git is the only lock)

Parent: `30-src.md`. Owns every git command the harness runs: the thin
wrapper, the lease (compare-and-swap push that claims a round and fences every
state change), per-attempt worktrees, the landing merge, and the bounded
post-landing sync. Depends on: the `git` binary, `config/paths.py`, `errors`.
Depended on by: `engine/`, `checks/` (diffs), `ledger/living.py` (trees),
`config/spec_files.py` (drift diff).

```
git/
  repo.py        subprocess wrapper; every git call in the harness goes through it
  lease.py       round ids, CAS claim, fence pushes, lease loss
  worktrees.py   create / remove attempt worktrees; stage-and-commit from one
  landing.py     merge main into the round branch; conflict detection; auto-merged tree; push to main
  sync.py        bounded merge of post-landing commits back into main
```

## repo.py

Data: `Repo(root: Path)`; `RunResult(code: int, out: str, err: str)`.

- `run(self, *args: str, check: bool = True, cwd: Path | None = None) -> RunResult`
  — runs `git -C <cwd or root> <args>`; raises `GitError` when `check` and the
  code is non-zero. Never uses a shell.
- `head(self, cwd=None) -> str`, `rev_parse(self, ref) -> str | None`.
- `fetch(self, remote: str, refspec: str | None = None) -> None`.
- `branch_exists(self, name, remote: str | None) -> bool`.
- `create_branch(self, name, at: str) -> None`.
- `push_with_lease(self, remote, src: str, dst: str, expected: str | None) -> bool`
  — `git push --force-with-lease=<dst>:<expected or empty> <remote> <src>:refs/heads/<dst>`;
  returns `False` on a lease rejection (stderr contains `stale info` or
  `rejected`), raises `GitError` on any other failure.
- `status_porcelain(self, cwd) -> list[tuple[str, str]]` — (code, path) pairs
  including untracked.
- `diff(self, a: str, b: str | None, paths: list[str] | None = None) -> str`.
- `diff_names(self, a, b, paths=None) -> list[FileChange]` —
  `FileChange(status: A|M|D|R, path, oldPath|None)` with rename detection (`-M`).
- `show_file(self, ref, path) -> bytes | None` — `None` when absent at ref.
- `ls_tree(self, ref, prefix: str) -> list[str]`.
- `checkout_paths(self, cwd, paths, source_ref: str | None) -> None` — revert
  paths to the index/ref (used for strays).
- `clean_paths(self, cwd, paths) -> None` — remove untracked paths.
- `add(self, cwd, paths) -> None`, `commit(self, cwd, message, allow_empty=False) -> str`
  — returns the new sha; commits are authored `shackles-runner`.
- `update_ref(self, ref, new: str, old: str) -> bool` — CAS on a local ref.
- `merge_base(self, a, b) -> str`, `is_ancestor(self, a, b) -> bool`.
- `config_identity_present(self) -> bool` — doctor check.

## lease.py

Data: `Lease(branch: str, remote: str, sha: str)`.

- `next_round_id(repo, paths, settings) -> str` — one more than the largest
  id among `archives/rounds/*` at `main` (`ls_tree`) and `refs/remotes/<remote>/round/*`
  after a fetch; `format_round_id`.
- `claim(repo, remote, round_id, base_commit: str, first_commit: str) -> Lease`
  — pushes `first_commit` to `refs/heads/round/NNNN` with an empty expected
  value (the ref must not exist). On rejection: refetch, recompute the id
  once, retry with the next id; a second rejection raises `LeaseLostError`.
  Returns the lease with `sha = first_commit`.
- `fence(repo, lease: Lease, new_sha: str) -> Lease` — `push_with_lease`
  expecting `lease.sha`; on rejection raises `LeaseLostError(branch,
  expected, actual)`. The engine calls this after every commit to the round
  branch; a loss pauses the round with reason LEASE and the driver is told
  another runner moved the round.
- `verify(repo, lease) -> bool` — fetch and compare the remote ref to
  `lease.sha`; used at `resume` and `next` before opening an attempt.

## worktrees.py

Data: `Worktree(path: Path, base: str, attempt: str)`.

- `create(repo, paths, attempt_id: str, at: str) -> Worktree` — `git worktree
  add --detach <harness>/.worktrees/<round>-<attempt> <at>`; the folder name
  is the attempt id prefixed by the round id. Refuses when the path exists.
- `remove(repo, wt: Worktree, force: bool = True) -> None` — `git worktree
  remove`; prunes.
- `changes(repo, wt) -> list[FileChange]` — the uncommitted diff of the
  worktree against its base including untracked files.
- `commit_from(repo, wt, paths: list[str], message: str) -> str | None` —
  stages exactly `paths` in the worktree, commits on the detached HEAD, returns
  the sha (`None` when nothing to commit).
- `advance_branch(repo, branch: str, new_sha: str, old_sha: str) -> None` —
  `update_ref` CAS; raises `LeaseLostError` locally if the branch moved.
- `runner_worktree(repo, paths, round_id, branch) -> Worktree` — the one
  persistent worktree of the round, checked out on the branch itself, where
  the runner writes the round folder; created at `start`, removed at end.
- `list_stale(repo, paths) -> list[Path]` — worktrees of ended rounds, for
  doctor and cleanup.

## landing.py

Data: `MergeOutcome(clean: bool, mergedTree: str | None, conflicted:
list[str], autoMergedCommit: str | None)`.

- `merge_main_into(repo, wt: Worktree, main_ref: str) -> MergeOutcome` — in a
  fresh worktree on the round branch head: `git merge --no-commit <main_ref>`;
  clean -> commit "land: merge main" and return the sha; conflicts -> record
  the conflicted paths, commit the auto-merged state *with conflict markers*
  as `autoMergedCommit` (so the conflict attempt starts from exactly git's
  auto-merge), and return `clean = False`.
- `judge_resolution(repo, wt: Worktree, outcome: MergeOutcome) -> list[str]`
  — the mechanical judgment of a conflict attempt: the paths changed in the
  worktree relative to `autoMergedCommit` must be a subset of `conflicted`
  (extras are strays for `checks/mechanical.py` to revert), and no conflicted
  file may still contain conflict markers (returned as problems).
- `push_to_main(repo, remote, main_branch, round_sha: str, expected_main: str) -> bool`
  — `push_with_lease` of the round branch head onto `main` expecting the
  `main` sha fetched before the merge; `False` when main moved (the engine
  retries the merge, bounded by `syncAttempts`).

## sync.py

- `sync_to_main(repo, remote, main_branch, round_branch, attempts: int) -> SyncResult`
  — for post-landing commits (POSTMORTEM, CLEANUP, booking, abandon record):
  loop up to `attempts` times: fetch; if `main` is an ancestor of the round
  head, push with lease; else `merge main` into the round branch: clean ->
  commit and push; conflict -> abort the merge and return `SyncResult(ok=False,
  reason="conflict", paths=[...])`. Returns `ok=True` with the new `main` sha,
  or `ok=False, reason="exhausted"` after `attempts` lease rejections. Never
  force-pushes.
- `sync_round_folder_only(repo, remote, main_branch, round_branch, folder_rel: str, attempts) -> SyncResult`
  — for abandoned rounds: creates a commit on top of `main` that adds only the
  round folder from the round branch (`git checkout <round> -- <folder>` in
  a worktree on `main`), then pushes with lease; same bounds.
