# 12 — Landing and the suite: `landing.py`, `suite.py`

## `src/landing.py` — landing, the conflict attempt, the bounded sync

**Owns:** merging the round into `main`, the projected-charge hard stop, turning a
textual conflict into one agent attempt judged against git's auto-merged tree, the
push of `main` with a lease, the fast-forward of the main checkout, and the bounded
post-landing sync that brings POSTMORTEM/CLEANUP commits back into `main`. **Depends
on:** `gitops`, `state`, `ledger` (projected living charge), `verify`, `checks`,
`pauses`, `history`, `prompts` (through `next_action` for the attempt prompt — this
module only returns the conflicted list), `config`, `paths`, `errors`. **Depended on
by:** `next_action` (`land`), `recording` (`after_conflict_resolved`, `sync`),
`rounds` (`sync` on abandon after landing).

### Types

- `LandOutcome` (dataclass): `kind` (`landed | conflict | paused`), `conflicted:
  list[str]`, `landed_commit: str | None`, `reason: str | None`, `loops: int`.
- `SyncOutcome` (dataclass): `kind` (`synced | conflict | failed`), `synced_commit:
  str | None`, `conflicted: list[str]`, `loops: int`, `reason: str | None`.

### Functions

- `land(world, lr: LoadedRound, now) -> LandOutcome` — the loop of
  `02-lifecycle.md §4 LANDING`, at most `maxRoundAttempts` iterations
  (`state.landing.loops` counts across calls so a conflict attempt's return continues
  the count) [JC-16]: fetch; `pre_landing_main = rev_parse(origin/main)` (recorded
  once, on the first loop, and never changed afterwards because the living charge is
  measured from it); `projected = ledger.living_charge(repo, cfg, pre_landing_main,
  branch tip)`; `pauses.check_hard_stop(st, cfg, projected)` → `paused` with reason
  `HARD_STOP` and the projected number in the message; `repo.merge(worktree,
  origin/main)`; on conflict → `state.landing.conflict_attempts += 1` (a second
  conflict → `abort_merge`, `paused LANDING_FAILED`) and return `conflict` with the
  conflicted list, leaving git's auto-merged index and working tree in place; on a
  clean merge → `verify.run(suite)`; failure → `abort`-free (the merge commit exists)
  pause `LANDING_FAILED` with the verify tail [JC-35]; success →
  `push_lease(branch)`, `push_to(branch, "main", expected = pre_landing_main of this
  loop)`; `FenceError("TARGET_MOVED")` → next loop; success → record
  `landed_commit`, `landed_at`, history, and `fast_forward` the main checkout to
  `origin/main` [JC-10]; return `landed`.
- `after_conflict_resolved(world, lr, attempt: AttemptRecord, now) -> LandOutcome` —
  called by `recording` once a LANDING attempt passed its checks (no markers, no
  strays beyond the conflicted files, suite green): `commit_merge_resolution`, then
  re-enter `land` at the push stage (a moved `main` starts a new loop, which may
  conflict again and is bounded as above).
- `conflict_declared_paths(conflicted: list[str]) -> list[str]` — exact files.
- `sync(world, lr, now) -> SyncOutcome` — the bounded sync of `02-lifecycle.md §7`:
  while `sync.loops < maxRoundAttempts`: fetch; if `origin/main` is an ancestor of the
  branch tip → `push_to(branch, main, expected)`; success → `synced`; otherwise
  `merge(worktree, origin/main)`; clean → `verify.run(suite)` (failure → `failed`)
  and push; conflict → return `conflict` (the caller prepares a LANDING attempt exactly
  as for landing; its `after_conflict_resolved` re-enters `sync`). Exhausted loops →
  `failed` with reason `SYNC_LOOPS`. Records `sync.status`, `synced_commit`,
  history. The round stays `DONE`; a `failed` sync sets `sync.status = failed` and the
  message tells the owner how to finish by hand (`git merge round/NNNN` on main).
- `remove_worktree(world, round_id) -> None` — after a successful sync or abandon.
- `projected_charge_text(projected: float, spend: float, limit: float) -> str` — the
  owner message line for the hard-stop pause.

## `src/suite.py` — round tests and `SUITE.json` application

**Owns:** what "this round's tests" are, counting test functions for the ledger,
and moving archived test functions out of the suite files into `tests-archive/`.
Uses `ast` on Python sources; a test is a top-level or class-level function whose name
starts with `test` in a file under `testPaths` whose name matches `test_*.py` or
`*_test.py` (pytest's defaults) [JC-36]. **Depends on:** `gitops` (file contents at a
ref), `config`, `paths`, `errors`, `ast`. **Depended on by:** `next_action`
(TESTS-TO-SUITE prompt), `recording` (validation and apply), `ledger` (counts),
`checks` (frozen file lists).

- `TestRef` (frozen dataclass): `file: str` (harness-relative posix), `qualname: str`
  (`test_x` or `TestClass::test_x`), `ref` property → `file::qualname`, `lineno:
  int`, `end_lineno: int`, `decorator_lineno: int` (first decorator line, else
  `lineno`), `source_hash: str` (sha256 of the function's source segment, whitespace-
  normalised).
- `test_files(root: Path, test_paths: list[str]) -> list[str]` — pytest-named files
  under the test paths, sorted.
- `tests_in_source(source: str, file: str) -> list[TestRef]` — parses with `ast`;
  a syntax error raises `InvalidError("TEST_SYNTAX")` naming the file.
- `tests_at_ref(repo: Repo, ref: str, harness_rel: str, test_paths) -> dict[str,
  TestRef]` — every test in the tree of a commit, keyed by `ref` string.
- `tests_in_worktree(wt_harness: Path, test_paths) -> dict[str, TestRef]`.
- `enumerate_round_tests(repo, base_commit: str, wt_harness: Path, harness_rel,
  test_paths) -> list[TestRef]` — tests in the worktree that are absent at
  `base_commit` or whose `source_hash` differs (added or changed this round), sorted
  by file then line.
- `count_tests(repo, ref, harness_rel, test_paths) -> int` — for the ledger's
  `testBaseCost`.
- `apply(doc: SuiteDoc, wt_harness: Path, rp: RoundPaths, test_paths) -> ApplyReport`
  — for every `archive` decision: cut the function's source segment (decorators
  included, plus the blank lines directly after it) from its file, append it to
  `tests-archive/<same relative file>` (created with the original file's import block
  — every top-level `import`/`from` statement — copied at the top when the archive
  file is new); a class-level test is cut from the class and archived as a top-level
  function with the class name prefixed to its name [JC-37]; a file left with no
  tests and no other top-level statements besides imports is deleted; an archived
  file already containing the same function name gets a numeric suffix. Returns
  `ApplyReport(moved: list[str], deleted_files: list[str], touched: list[str])`.
  Never runs tests; `recording` verifies afterwards.
- `frozen_file_list(refs: list[TestRef]) -> list[str]` — distinct files, for
  `state.frozen_tests`.
