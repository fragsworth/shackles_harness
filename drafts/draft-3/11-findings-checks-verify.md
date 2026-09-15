# 11 — Findings, mechanical checks, verification: `findings.py`, `checks.py`, `verify.py`

## `src/findings.py` — the findings lifecycle

**Owns:** turning a gate's message into finding records, rulings, the verdict-wins
rule, the repeat-of-withdrawn rule, settling, resolutions from producers,
runner-raised findings, and the views that prompts show. Pure functions over
`RoundState`. **Depends on:** `state`, `schemas`, `errors`. **Depended on by:**
`recording`, `next_action` (views), `pauses` (open non-blocking lists).

Statuses of a finding: `open` (blocking, unresolved) · `fixed` (producer says fixed;
the next gate may re-raise) · `disputed` (awaiting a ruling) · `withdrawn` (gate
withdrew) · `settled` (upheld twice; only `fixed` is accepted from now on) ·
`dropped` (repeated a withdrawn one) · `flagged` (non-blocking; goes to the owner) ·
`closed` (step accepted with it fixed).

- `FindingView` (dataclass): `id`, `severity`, `status`, `quote`, `text`,
  `suggestion`, `resolutions: list[tuple[str, str]]` (resolution, note), `rulings:
  list[tuple[str, str]]` (ruling, quote), `needs_resolution: bool`.
- `normalise_quote(text: str) -> str` — whitespace runs → one space, trimmed,
  case preserved.
- `apply_gate(st: RoundState, step: str, attempt: int, doc: FindingsDoc, now) ->
  GateOutcome` — in order: (1) rulings: `upheld` increments `upheld` and, at 2, sets
  `settled`, else returns the finding to `open`; `withdrawn` sets `withdrawn`;
  (2) new findings: one whose normalised quote equals a withdrawn finding's quote in
  this step is **dropped** (recorded with status `dropped`, and a note is returned
  for HISTORY) [JC-17]; the rest get ids and status `open` (blocking) or `flagged`
  (non-blocking); (3) verdict wins: `FAIL` with no blocking finding left open → every
  new finding becomes blocking/`open`; `PASS` with blocking findings → they become
  `flagged` [JC-34]; (4) returns `GateOutcome(verdict, new_ids, dropped_notes,
  flags_added: list[int], to_resolve: list[str])`.
- `apply_resolutions(st, step, res: list[Resolution]) -> list[str]` — `fixed` →
  status `fixed`; `disputed` → `disputed` with the note; returns problems (unknown id,
  disputed on settled) — `validate_result` already rejected those, so this is a guard.
- `raise_runner(st, step, attempt, text: str, quote: str, suggestion: str) -> str` —
  a blocking finding with an `R<n>` id (verify failures); returns the id.
- `close_on_accept(st, step) -> None` — `fixed` and `open`-but-passed findings become
  `closed`; `flagged` ones stay for delivery.
- `views_for_prompt(st, step) -> list[FindingView]` — every finding of the step except
  `closed`/`dropped`, oldest first; `needs_resolution` for `open` and `settled`.
- `open_non_blocking(st) -> list[FindingView]` — `flagged` and undelivered (delivery is
  tracked through the flags list: `apply_gate` adds a flag per non-blocking finding).

## `src/checks.py` — mechanical checks at `record`

**Owns:** classifying the attempt's uncommitted diff into accepted changes and strays,
reverting strays, checking artifacts exist and validate, and the always-on invariants
(spec files untouched, runner files untouched, no conflict markers). Never judges
content. **Depends on:** `gitops`, `steps`, `schemas`, `paths`, `config`,
`specfiles` (the spec file list), `errors`. **Depended on by:** `recording`,
`landing`.

- `Classification` (dataclass): `accepted: list[Change]`, `strays: list[Change]`,
  `reasons: dict[str, str]` (path → why it is a stray).
- `classify_changes(changes: list[Change], declared: list[str], harness_rel: str,
  spec_files: list[str], runner_files: list[str], frozen_tests: list[str] | None,
  test_paths: list[str]) -> Classification` — a change is accepted when its harness-
  relative path is under a declared prefix or equals a declared file, **and** is not a
  spec file, **and** is not a runner-owned round file (`STATE.json`, `HISTORY.md`,
  `OWNER.log`, `PROMPTS/`, `FINDINGS/`, `RESULTS/` other than this attempt's own
  result), **and** (when tests are frozen) is not under `testPaths`. The attempt's own
  result file is accepted. Everything else is a stray with a reason.
- `run_for_attempt(repo: Repo, wt_harness: Path, harness_rel: str, step: Step, rp:
  RoundPaths, cfg, st: RoundState, attempt: int, conflicted: list[str] = ()) ->
  CheckReport` — computes declared paths (`steps.resolve_scopes`), classifies
  `repo.status(worktree)`, reverts strays (`repo.revert_paths`), then runs
  `validate_artifacts`; returns `CheckReport(accepted_paths, strays_reverted,
  problems, warnings)`. Strays never fail the attempt; problems do (they become an
  `InvalidError` in `recording`).
- `validate_artifacts(step: Step, rp: RoundPaths, cfg, agents, overrides,
  expected_tests: set[str] | None) -> tuple[list[str], list[str]]` — per artifact key
  the matching `schemas` validator (`plan`, `agentsPlan`, `spec` + non-empty
  `specProse`, `suite` with `expected_tests`, `postmortem` non-empty); missing file is a
  problem; returns (problems, warnings).
- `runner_owned_round_files(rp: RoundPaths) -> list[str]`.
- `spec_file_rels(repo_root, harness_root) -> list[str]` — harness-relative forms of
  the spec files (those outside the harness root can never be touched from inside it
  but are listed for completeness).
- `conflict_marker_check(repo, wt: Path, paths: list[str]) -> list[str]` — wraps
  `gitops.files_with_conflict_markers`.

## `src/verify.py` — running the suite

**Owns:** running the project's own test suite (or its collection) inside the
worktree with the configured timeout, capturing the tail, and reporting pass/fail.
**Depends on:** `config`, `paths`, `errors`, `subprocess`. **Depended on by:**
`recording`, `landing`, `suite` (after moves), `doctor` (a dry `--collect-only` when
asked).

- `VerifyResult` (dataclass): `ok: bool`, `mode: str` (`collect | suite`), `returncode:
  int | None`, `timed_out: bool`, `duration_s: float`, `tail: str` (last 4000 chars),
  `log_path: Path | None`.
- `run(cfg: ProjectConfig, wt_harness: Path, mode: str, log_path: Path) -> VerifyResult` [JC-59] [JC-70]
  — command = `verifyCommand` (+ `--collect-only` for `collect`), cwd = the worktree
  harness root, env with `PYTHONDONTWRITEBYTECODE=1` and `SHACKLES_VERIFY=1` (so tests
  can detect they run under the runner), timeout `verifyTimeoutSeconds`; writes the
  full output to `log_path`; a timeout is `ok=False, timed_out=True`.
- `finding_text(res: VerifyResult) -> tuple[str, str, str]` — (text, quote,
  suggestion) for `findings.raise_runner`: quote = the tail's failure summary lines,
  suggestion = "make the frozen tests pass; see <log path>".
