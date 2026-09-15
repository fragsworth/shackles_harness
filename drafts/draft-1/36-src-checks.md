# 36 — src/shackles/checks/ (what the runner checks at record)

Parent: `30-src.md`. Owns the mechanical checks on an attempt's uncommitted
diff, the test verification runner, and the TESTS-TO-SUITE file moves. These
never fail an attempt for a stray: strays are reverted and noted. Depends on:
`config/`, `steps/`, `git/`, `round/judgment_calls.py` (append-only test).
Depended on by: `engine/attempts.py`, `engine/landing_step.py`.

```
checks/
  mechanical.py   allowed paths per step; strays reverted; spec files immutable; frozen artifacts
  verify.py       runs the test command with a timeout; parses pass/fail
  suite_moves.py  moves archived test files into tests-archive/ per SUITE.json
```

## mechanical.py

Data: `Allowed(livingPrefixes: list[str], roundFiles: list[str],
appendOnly: list[str], conflicted: list[str])`; `CheckReport(kept:
list[FileChange], reverted: list[FileChange], notes: list[str], problems:
list[str])`. `problems` are contract failures the engine turns into a
mechanical retry (missing artifact, invalid JSON); `reverted` are strays.

- `allowed_for(step: Step, settings, round_folder: RoundFolder, conflicted: list[str]) -> Allowed`
  — from the step's `declaredPaths` rule: `NONE` -> no living prefixes;
  `TESTS` -> `testPaths`; `LIVING_EXCEPT_TESTS` -> `livingSourcePaths` minus
  `testPaths`; `CARRY_FORWARD` -> `carryForwardFiles`; `ALL_LIVING` ->
  `livingSourcePaths`; `CONFLICTED` -> the conflicted paths. `roundFiles` =
  the step's artifact paths; `appendOnly` = the two judgment-call files.
- `classify(changes: list[FileChange], allowed: Allowed, spec_files: frozenset[str], frozen: list[str]) -> CheckReport`
  — pure. A change is kept when its path is under an allowed prefix, is one of
  `roundFiles`, or is an `appendOnly` file; everything else is a stray. Spec
  files are always strays (note "spec file edit reverted"). Frozen artifacts
  (accepted earlier steps' artifacts) are strays. Deletions and renames are
  judged by both paths.
- `revert(repo, wt: Worktree, strays: list[FileChange]) -> None` — tracked
  files restored to the worktree base, untracked removed.
- `check_append_only(repo, wt, paths: list[str]) -> list[str]` — for each
  judgment-call file: old content must be a prefix of the new; otherwise the
  file is restored and a note recorded.
- `check_artifacts(step: Step, round_folder_in_wt: RoundFolder, validators) -> list[str]`
  — each artifact the step must write exists and validates (`artifacts.py`);
  missing or invalid -> problems.
- `run_all(repo, wt, step, settings, round_folder, spec_files, frozen, conflicted=[]) -> CheckReport`
  — the entry point the engine calls at record: classify, revert, append-only,
  artifacts; returns the report with everything noted.

## verify.py

Data: `VerifyResult(mode: COLLECT|PASS, ok: bool, timedOut: bool, passed: int,
failed: int, errors: int, collected: int, tail: str, durationSeconds: float,
command: list[str])`.

- `run(mode, tree: Path, settings, paths: Paths) -> VerifyResult` — builds the
  command from `verifyCommand` or `collectCommand` with `{testPaths}`
  substituted (space-joined), runs it in `tree` with `verifyTimeoutSeconds`,
  writes full output to `<harness>/.verify/<timestamp>.log`, parses the last
  summary line for counts (pytest's `N passed, M failed` form; any other
  runner is judged on exit code alone, counts `-1`), keeps the last 40 lines
  as `tail`. `ok` = exit code 0 and not timed out. A timeout is `ok=False,
  timedOut=True`; the engine pauses with reason VERIFY after
  `maxRoundAttempts` mechanical retries.
- `summary_line(result) -> str` — one line for HISTORY.

## suite_moves.py

Data: `Move(src: str, dst: str)`; `MovePlan(moves: list[Move], suiteTests:
list[str], archivedTests: list[str], problems: list[str])`.

- `new_tests(repo, base_commit: str, head: str, test_paths) -> list[str]` —
  `file::function` ids of test functions present at `head` and absent at
  `base_commit` under `testPaths` (`ledger/tokens.py` `count_tests` per file
  gives names) — the set `SUITE.json` must decide.
- `plan_moves(suite_doc: dict, new: list[str], tests_archive_rel: str) -> MovePlan`
  — every archived file (all of whose new tests are `archive`) moves to
  `<round folder>/tests-archive/<same relative path>`; a file with mixed
  decisions is a problem; a file with `archive` decisions that also contains
  pre-existing suite tests is a problem ("move the new tests to their own
  file").
- `apply(repo, wt: Worktree, plan: MovePlan) -> None` — `git mv` each file in
  the runner's worktree; the engine then runs `verify` in PASS mode on the
  suite that remains and commits "suite: archive N tests".
