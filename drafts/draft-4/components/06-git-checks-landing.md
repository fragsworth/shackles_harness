# 06 — Git, mechanical checks, suite moves, landing

`gitops.py` is the only module that runs git. `checks.py` runs the mechanical checks at record on the attempt's uncommitted diff and reverts strays. `suite.py` enumerates test functions and performs suite/archive moves. `landing.py` orchestrates landing, conflict attempts, the bounded post-landing sync and abandonment.

## 6.1 `src/shackles/gitops.py`

**Owns:** every git subprocess: the CAS claim, the fence, worktrees, diffs, reverts, commits, merges, tree reads, remote probes. **Depends on:** `paths`, `errors`, `localcfg` (remote name, main branch). **Depended on by:** `commands/*`, `checks`, `suite`, `landing`, `specfiles` (injected `show_file`), `charges` callers (tree contents), `doctor`.

- `class Git`: `__init__(self, roots: Roots, *, remote: str, main: str, runner: Callable = subprocess.run)`; every method shells out with explicit `cwd`, captures output, and raises `GitError(message, detail={"cmd", "stdout", "stderr", "code"})` on non-zero exit unless the method documents otherwise. No method ever runs an interactive or editor-opening command; merges use `--no-edit`.
- Remote and refs: `fetch(self) -> None`; `remote_url(self) -> str | None`; `main_sha(self) -> str` (`refs/remotes/<remote>/<main>` after fetch); `remote_branch_sha(self, branch: str) -> str | None` (None when absent); `list_remote_round_branches(self, prefix: str) -> list[str]`; `detect_main_branch(self) -> str` (`refs/remotes/<remote>/HEAD` → name, fallback `main`).
- Claiming: `claim_round(self, *, id_width: int, prefix: str, existing_ids: Iterable[int], retries: int = 3) -> Claim` — compute the next id (max of `existing_ids` ∪ ids parsed from remote branches, +1), create the local branch at `main_sha`, push with `--force-with-lease=refs/heads/<branch>:` (expected empty = the ref must not exist); on rejection retry with the next id; after `retries` rejections raise `GitError("could not claim a round")`. Returns `Claim(round_id, branch, base_commit)`. (JC-43)
- `unclaim_round(self, branch: str) -> None` — delete the remote and local branch (used only when `start` fails after claiming).
- Worktrees: `add_worktree(self, branch: str, path: Path) -> None`; `remove_worktree(self, path: Path, *, force: bool) -> None`; `worktree_head(self, path) -> str`.
- The fence: `fence_push(self, wt: Path, branch: str, *, expected_remote_sha: str | None) -> str` — `push --force-with-lease=<branch>:<expected>` ; on rejection raise `FenceError("remote branch moved")`; returns the new remote sha. `fence_check(self, branch: str, expected: str | None) -> None` — fetch and compare; `FenceError` on mismatch.
- Working tree: `status_porcelain(self, wt: Path) -> list[Change]` (`Change(path, kind: "M"|"A"|"D"|"R"|"?", old_path)` over tracked and untracked files, renames detected); `diff_names(self, wt: Path, base: str, head: str = "HEAD", *, rename: bool = True) -> list[Change]`; `revert_paths(self, wt: Path, paths: list[str]) -> None` (checkout for tracked, delete for untracked); `has_conflict_markers(self, wt: Path, paths: list[str]) -> list[str]`.
- Committing: `commit_all(self, wt: Path, message: str, *, paths: list[str] | None = None) -> str | None` — stage the given paths (or everything) and commit; returns the sha or `None` when there was nothing to commit.
- Trees: `show_file(self, rev: str, repo_rel_path: str) -> str | None`; `tree_files(self, rev: str, prefixes: list[str]) -> dict[str, bytes]` (path → content for files under the prefixes; used by charges); `changed_between(self, a: str, b: str, prefixes) -> list[Change]`.
- Merging and landing: `merge_into_worktree(self, wt: Path, rev: str, message: str) -> MergeResult` — `git merge --no-ff --no-edit`; `MergeResult(clean: bool, conflicts: list[str], merged_sha: str | None)`; on conflict the merge is left in progress (index and markers as git produced them); `snapshot_automerge(self, wt: Path) -> str` — records git's auto-merged tree as a temporary ref (`refs/shackles/automerge/<branch>`) by writing the current index+worktree into a tree object without committing (`git write-tree` after `git add -A` of the conflicted state is *not* used; instead `git stash create`-style: a commit object created with `commit-tree` from the working tree, JC-44); `diff_against_ref(self, wt: Path, ref: str) -> list[Change]`; `conclude_merge(self, wt: Path, message: str) -> str` (`git commit --no-edit` after resolution; `GitError` if unmerged paths remain); `abort_merge(self, wt: Path) -> None`.
- `fast_forward_main(self, wt: Path, branch: str, *, expected_main_sha: str) -> bool` — `push <remote> <branch>:<main> --force-with-lease=<main>:<expected>`; returns False on rejection (caller retries), `GitError` on other failures; then `update_driver_checkout(self) -> None` (`git -C <repo> pull --ff-only <remote> <main>` in the driver checkout; `GitError` if it cannot fast-forward, e.g. the owner has local commits).
- `restore_paths_from(self, wt: Path, rev: str, prefixes: list[str]) -> None` — `git checkout <rev> -- <prefixes>` plus deletion of files present in the worktree but absent at `rev` under those prefixes (used by `abandon` to drop living changes and keep the record).
- `log_subjects(self, a: str, b: str, limit: int = 50) -> list[str]` (for the conflict prompt's context), `is_ancestor(self, a, b) -> bool`, `rev_parse(self, rev, cwd=None) -> str`.
- `probes(self) -> localcfg.EnvProbes` — the detection callables for `localcfg`.

Round constants (code, not settings): branch prefix `shackles/round-`, worktree dir `.worktrees/`, automerge ref namespace `refs/shackles/automerge/`.

## 6.2 `src/shackles/checks.py`

**Owns:** the mechanical checks run at record and the stray policy. **Depends on:** `gitops`, `steps`, `paths`, `config`, `specfiles`, `artifacts`, `suite`, `errors`. **Depended on by:** `commands/record`, `landing` (conflict attempts reuse `run_for_attempt`).

- `@dataclass class CheckReport`: `strays: list[str]` (reverted paths), `mechanical: list[str]` (each a one-line reason the attempt cannot be accepted), `warnings: list[str]` (advisory notes passed to the gate), `verify: dict | None` (`{"passed", "summary", "seconds", "timed_out"}`), `moves: list[tuple[str, str]]` (suite→archive moves to apply, TESTS-TO-SUITE only), `changed: list[str]` (paths kept in the diff).
- `declared_paths(step: Step, cfg: Config, rp: RoundPaths, *, conflicts: list[str]) -> list[str]` — expands the step's `writes` symbols: `<round>` → the round folder; `<living>` → `livingSourcePaths`; `<testPaths>`; `<living minus testPaths>`; `<carry-files>`; `<root-docs>`; `<conflicts>` → the literal conflict list; everything except `<root-docs>` and `<conflicts>` is intersected with the living paths (the round folder is under `archivesPath`, which is allowed explicitly). Gates get an empty list.
- `path_policy(changes: list[Change], allowed: list[str], spec_files: list[str], roots: Roots) -> tuple[list[Change], list[str]]` — split into kept and strays; any spec file, any path outside `allowed`, and any path under `.worktrees/`, `.claude/`, `spec.baseline.json`, `local.yaml`, `OWNER.log` is a stray. Renames count as a change of both paths.
- `run_for_attempt(session, rs: RoundState, rec: AttemptRecord, step: Step, msg: ProducerMessage | GateMessage | None) -> CheckReport` — 1) `status_porcelain` of the round worktree; 2) `path_policy` → `revert_paths(strays)`; 3) run each named check in `step.checks` (gate attempts: only the policy, with every change a stray); 4) assemble the report. A check that raises `GitError` becomes a mechanical entry, not an exception.
- `CHECKS: dict[str, Callable[[CheckContext], None]]` — each appends to the report:
  - `artifact-plan`, `artifact-agents-plan`, `artifact-spec`, `artifact-suite`, `artifact-postmortem` — the artifact file(s) exist and validate ([05] artifacts); errors → mechanical; warnings → warnings.
  - `non-goals-carried` — advisory (warnings only).
  - `tests-collect` — `python -m pytest --collect-only -q <testPaths>` in the worktree harness root, timeout `verifyTimeoutSeconds`; non-zero → mechanical with the tail of the output.
  - `new-tests-exist` — at least one test function added since `base_commit` under `testPaths` (`suite.new_tests`); none → mechanical.
  - `verify-suite` — `python -m pytest <testPaths> -m "not live"` with the timeout; failure or timeout → mechanical (`"suite failed: …"` / `"suite timed out after N s"`); the result is also stored in `report.verify` for the gate.
  - `suite-consistent` — `artifacts.validate_suite` against `suite.new_tests`; on success fills `report.moves` (archive-decided files → `tests-archive/<relative path>`).
  - `conflict-only` — every change vs the automerge ref is within `<conflicts>`; others are strays (already reverted by policy) — the check records the count.
  - `no-markers` — `gitops.has_conflict_markers(conflicts)` empty, else mechanical.
- `run_pytest(cwd: Path, args: list[str], timeout_s: int) -> VerifyResult` — the single place that spawns pytest; captures the last 40 lines.

Rule: strays are **reverted and reported**, never a reason to reject; the attempt is judged on what remains.

## 6.3 `src/shackles/suite.py`

**Owns:** what a "test" is (a function whose name starts with `test` at module level or inside a class whose name starts with `Test`, in a `.py` file under `testPaths`), enumerating tests in a tree, the new tests of a round, and moving archived tests. **Depends on:** `paths`, `gitops` (tree contents / changed files), `errors`; parsing via `ast`. **Depended on by:** `checks`, `charges` (test counts before/after), `prompts` (`suite_stats`, `new_tests` input), `commands/record` (apply moves).

- `@dataclass(frozen=True) class TestRef`: `file: str` (harness-relative), `name: str` (qualified `Class::func` or `func`).
- `enumerate_file(source: str, file: str) -> list[TestRef]` — `ast` parse; a syntax error yields an empty list plus a flag (`enumerate_file_safe -> tuple[list, bool]`).
- `enumerate_tree(files: dict[str, bytes], test_paths: list[str]) -> set[TestRef]`.
- `test_names(refs: Iterable[TestRef]) -> Counter[str]` — bare names (the last segment), used by charges so a move between files is neither charged nor refunded.
- `new_tests(git: Git, wt: Path, base: str, test_paths) -> list[TestRef]` — refs present in the worktree but absent at `base`.
- `plan_moves(info: SuiteInfo, rp: RoundPaths, test_paths) -> list[tuple[str, str]]` — file → `tests-archive/<path relative to its test path root>`.
- `apply_moves(git: Git, wt: Path, moves: list[tuple[str, str]]) -> None` — `git mv` each; the move is committed with the attempt.
- `stats(refs: set[TestRef]) -> dict` — counts of files and tests.

## 6.4 `src/shackles/landing.py`

**Owns:** LANDING, conflict attempts, the post-landing sync, and abandon's record-only landing. **Depends on:** `gitops`, `state`, `checks`, `ledger`, `charges`, `limits`, `history`, `prompts`, `steps`, `config`. **Depended on by:** `commands/next_`, `commands/record`, `commands/owner`.

- `land(session, rs: RoundState) -> LandOutcome` — called by `next` when the cursor reaches LANDING:
  1. `fetch`; `main_before = main_sha()`.
  2. Hard stop: `projected = charges.living_charge(tree_files(main_before, living), tree_files(worktree HEAD, living), …)`; if `ledger.round_total + projected.total > effective(hardStopBudgetMultiple) × quote` → `rs.pause("hard-stop", …)`, return `LandOutcome(paused=True)`. (JC-45)
  3. `merge_into_worktree(wt, main_before, "land round NNNN: merge main")`: clean → step 5; conflict → `snapshot_automerge`, store `landing.conflicts`, open a `conflict` attempt via `prompts.open_attempt(step=LANDING, kind="conflict")`, return `LandOutcome(attempt=…)`.
  4. (On record of a conflict attempt, `commands/record` calls `checks.run_for_attempt` with `conflict-only`, `no-markers`, `verify-suite`; accepted → `conclude_merge`, then `finish_landing`; rejected → the merge stays in progress and a new conflict attempt is opened, bounded by `maxTurnsPerGate` like any step.)
  5. `finish_landing(session, rs, main_before) -> None`: `verify-suite` on the merged worktree (failure → pause `mechanical` with reason "merged tree fails the suite", JC-46); `fast_forward_main(wt, branch, expected_main_sha=main_before)`; if rejected (main moved), go back to step 1 up to `SYNC_BOUND` (3) times, then pause `sync`; `update_driver_checkout`; set `landing.main_before`, `landing.landed`; advance the cursor to POSTMORTEM.
- `sync(session, rs: RoundState) -> SyncOutcome` — after CLEANUP's record (and on `resume` from a `sync` pause): loop up to `SYNC_BOUND`: `fetch`; if `is_ancestor(branch, main)` → done; `merge_into_worktree(main)`: conflict → open a conflict attempt (attempt ids continue as `LANDING-n`, history says "sync conflict", JC-47) and return; clean → `fast_forward_main` with lease; rejected → next iteration. Exhausted → `rs.pause("sync", …)`. On success `landing.synced = True`, `update_driver_checkout`.
- `abandon(session, rs: RoundState, reason: str) -> None` — if not landed: `restore_paths_from(wt, base_commit, living paths)` so the branch tree equals main plus the round folder; commit "abandon round NNNN"; then `sync` (which lands the record only). If landed: nothing to restore; `sync` the record. Either way the round folder reaches main and the worktree is removed by the command after `end_round`. (JC-48)
- `remove_round_worktree(session, rs) -> None` — after `done`/`abandoned` and a successful sync; keeps the branch on the remote (the record's second copy).
- `SYNC_BOUND = 3` (code constant; JC-49).
