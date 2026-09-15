# 04 — Git: plumbing, the round worktree, landing, the post-landing sync

Parent: [`../SPEC.md`](../SPEC.md). Four modules under `harness/src/`. Git is the only
lock in this system: a compare-and-swap push claims a round, and every state change is
pushed as a fence. These modules are the only ones that run `git`.

---

## gitops.py — thin, explicit git plumbing

**Owns:** every `git` invocation, as named functions with typed results; no policy.
**Depends on:** `paths`. **Depended on by:** `worktree`, `landing`, `sync`, `round`,
`ledger` (tree reads), `speclock` (none), `doctor` (read-only queries), tests.

All functions take `repo: Path` (a working tree or worktree root) and run `git -C repo`.
Output parsing is limited to porcelain formats. Every failure raises `GitError` carrying
the command, exit code, stdout and stderr.

```python
class GitError(HarnessError): ...
class PushRejected(GitError): ...          # a lease/CAS push was refused: someone else moved the ref

@dataclass(frozen=True)
class Change:                              # one line of `git status --porcelain=v1 -z` or `diff --name-status`
    status: str                            # "M", "A", "D", "R", "?", "U" ...
    path: str                              # repo-relative, new path for renames
    old_path: str | None = None

def run(repo: Path, *args: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess
def toplevel(start: Path) -> Path
def head(repo: Path) -> str                                       # full sha
def rev_parse(repo: Path, ref: str) -> str | None                 # None when the ref does not exist
def fetch(repo: Path, remote: str, *refspecs: str) -> None
def remote_ref(repo: Path, remote: str, branch: str) -> str | None   # sha of refs/remotes/<remote>/<branch> after fetch
def ls_remote_heads(repo: Path, remote: str, pattern: str) -> dict[str, str]   # "round/*" -> {branch: sha}
def branch_create(repo: Path, name: str, at: str) -> None
def branch_delete(repo: Path, name: str, *, force: bool = False) -> None
def push_cas(repo: Path, remote: str, branch: str, expected_remote_sha: str | None) -> None
    # `git push <remote> <branch>:<branch> --force-with-lease=refs/heads/<branch>:<expected>`;
    # expected None means "must not exist" (the claim). Raises PushRejected on refusal.
def push_ff(repo: Path, remote: str, branch: str, expected_remote_sha: str) -> None   # same, but also refuses non-fast-forward
def worktree_add(repo: Path, path: Path, branch: str) -> None
def worktree_remove(repo: Path, path: Path, *, force: bool = True) -> None
def worktree_list(repo: Path) -> list[tuple[Path, str]]           # (path, branch or "detached")
def status(repo: Path) -> list[Change]                            # uncommitted changes incl. untracked (-uall)
def checkout_paths(repo: Path, paths: Iterable[str]) -> None      # revert tracked files to HEAD
def clean_paths(repo: Path, paths: Iterable[str]) -> None         # remove untracked files
def add_all(repo: Path, paths: Iterable[str]) -> None             # `git add -A -- <paths>`
def commit(repo: Path, message: str, *, allow_empty: bool = False) -> str    # returns sha; author "shackles runner <runner@shackles>"
def diff_names(repo: Path, a: str, b: str, *, rename_detection: bool = True) -> list[Change]   # `git diff --name-status -M a b`
def show_file(repo: Path, rev: str, path: str) -> bytes | None    # None if absent at rev
def ls_tree(repo: Path, rev: str, prefix: str) -> list[str]       # files under prefix at rev
def merge(repo: Path, ref: str, message: str) -> tuple[bool, list[str]]
    # `git merge --no-ff --no-commit`? No: `git merge --no-edit -m msg ref`; returns (clean, conflicted_paths);
    # on conflict the index and tree are left in the conflicted state for landing.py to inspect.
def merge_abort(repo: Path) -> None
def conflicted_paths(repo: Path) -> list[str]                     # `git diff --name-only --diff-filter=U`
def has_conflict_markers(path: Path) -> bool
def is_ancestor(repo: Path, a: str, b: str) -> bool
def config_get(repo: Path, key: str) -> str | None
```

---

## worktree.py — the round's working tree and path discipline

**Owns:** creating and removing the round worktree under `HARNESS_ROOT/.worktrees/`,
translating declared path classes into concrete prefixes, reverting strays, and the
append-only check for the judgment-call files. **Depends on:** `paths`, `config`,
`steps`, `gitops`. **Depended on by:** `round` (at start, next, record, cleanup),
`landing`, `verify`.

One worktree per round, on branch `round/NNNN`, at `.worktrees/round-NNNN/` (JC-20).
The runner writes the round folder there; producers work there; the driver's own checkout
is never written by a round except by `sync` at the end.

```python
class WorktreeError(HarnessError): ...

def path_for(roots: Roots, round_id: str) -> Path
def create(roots: Roots, cfg: Config, round_id: str, branch: str) -> Path        # worktree_add; raises if exists
def remove(roots: Roots, round_id: str) -> None
def round_folder(roots: Roots, cfg: Config, round_id: str, worktree: Path) -> Path   # worktree/<prefix>/<roundPaths.folder with NNNN>
def declared_prefixes(cfg: Config, step: Step, round_id: str, *, conflicted: Iterable[str] = ()) -> tuple[str, ...]
    # PathClass -> repo-relative prefixes: round_folder -> the round folder; test_paths -> cfg.test_paths;
    # living_non_test -> livingSourcePaths minus test_paths; living_all -> livingSourcePaths;
    # carry_forward -> ("docs/TODO.md", "docs/CLARIFICATIONS.md") (JC-21); conflicted_files -> the given list.
def spec_file_paths(roots: Roots) -> tuple[str, ...]              # repo-relative, from speclock.list_files
def frozen_test_paths(cfg: Config, step: Step) -> tuple[str, ...]  # test_paths when the step may not touch tests (SPEC-TO-IMPLEMENTATION)

@dataclass(frozen=True)
class Triage:
    kept: tuple[Change, ...]
    strays: tuple[Change, ...]          # outside declared prefixes, or a spec file, or a frozen test: reverted
    refusals: tuple[str, ...]           # problems that refuse the record (see below)

def triage(worktree: Path, changes: Iterable[Change], declared: Iterable[str],
           never: Iterable[str], round_folder: str, jc_files: Iterable[str],
           head_contents: Callable[[str], bytes | None]) -> Triage
    # A change is kept when under a declared prefix or the round folder and not under `never`.
    # Refusals: a judgment-call file whose previous content is not a prefix of the new content
    # (append-only); a change to STATE.json or HISTORY.md by a producer (runner-only files);
    # a deleted or rewritten PROMPTS/ or RESULTS/ file.
def revert(worktree: Path, strays: Iterable[Change]) -> list[str]     # checkout_paths + clean_paths; returns paths reverted
def runner_only_files(cfg: Config) -> tuple[str, ...]                # STATE.json, HISTORY.md, OWNER.log, PROMPTS/, FINDINGS/ (round-folder-relative)
```

Strays are reverted and noted, never a failure: the owner's rule. Refusals are the few
cases where silently reverting would destroy the record.

---

## landing.py — merging the round into main

**Owns:** the LANDING step's mechanics: the pre-landing hard-stop check, the merge, the
conflict attempt, the mechanical judgment of that attempt, and pushing main.
**Depends on:** `paths`, `config`, `gitops`, `worktree`, `verify` (file 05), `ledger`
(projected living charge, file 06), `limits`, `state`, `history`. **Depended on by:**
`round`.

Procedure `land(...)`, run inside `next` when LANDING becomes the pending step:
1. Fetch; `main_before = remote_ref(main)`; record it in `state.landing.main_before`.
2. Projected living charge = `ledger.living_charge(main_before, round_tip)`; hard-stop check
   against `state.owner.hard_stop_multiple × quote`; a hit pauses with `hard-stop`.
3. Create a landing worktree `.worktrees/landing-NNNN/` at `main_before` (detached).
4. `merge(round branch)`. Clean: run `verify.suite`; pass → `push_ff(main, expected=main_before)`
   → record `landed_at`, `merge_commit`; remove the landing worktree; step accepted. Verify
   fails → pause with reason `conflict`, detail = the verify tail (the owner decides; JC-22).
5. Conflict: leave the auto-merged tree in place; record `conflicted_files`; commit the
   conflicted tree as-is on a temporary branch `round/NNNN-landing` (so the reference tree is
   a commit); the round pauses **not** — instead `next` returns a `spawn` for attempt
   `LANDING-1`, role `landing-conflict`, cwd = the landing worktree, declared = the conflicted
   files. Its record (in `round.py`) calls `judge_resolution`.
6. `PushRejected` at step 4 (main moved during landing): abort, remove the landing worktree,
   retry from step 1 up to 3 times; then pause with reason `conflict`.

```python
class LandingError(HarnessError): ...

@dataclass(frozen=True)
class MergeOutcome:
    clean: bool; conflicted: tuple[str, ...]; landing_worktree: Path; reference_commit: str | None

def begin(roots: Roots, cfg: Config, state: State, round_tip: str) -> MergeOutcome
def judge_resolution(roots: Roots, cfg: Config, state: State, outcome: MergeOutcome) -> list[str]
    # Mechanical, returns problems (empty = accepted): every change vs reference_commit is inside
    # conflicted files or the round folder (others reverted as strays); no file under the
    # conflicted set still has conflict markers; verify.suite passes within the timeout.
def finish(roots: Roots, cfg: Config, state: State, outcome: MergeOutcome) -> str
    # Commits the resolution (or the clean merge), push_ff main with lease = main_before, returns landed sha.
def abort(roots: Roots, outcome: MergeOutcome) -> None
```

A landing conflict attempt that fails judgment gets one more attempt (`LANDING-2`), then
the round pauses with reason `conflict` (JC-23).

---

## sync.py — bounded merge of post-landing commits into main

**Owns:** bringing POSTMORTEM and CLEANUP commits (and the round folder itself) from the
round branch into main after landing, and updating the driver's checkout.
**Depends on:** `paths`, `config`, `gitops`, `history`. **Depended on by:** `round`
(at the end of CLEANUP and on abandon).

Bounded means: at most 3 fetch-merge-push cycles; only files under the round folder, the
carry-forward files, and the living paths may differ between main and the merge result
(anything else means main moved in ways this round did not own → refuse); a merge conflict
never gets an agent — it pauses the round with reason `sync-conflict` for the owner (JC-24).

```python
class SyncError(HarnessError): ...

@dataclass(frozen=True)
class SyncResult:
    main_sha: str; cycles: int; merged_paths: tuple[str, ...]

def sync_to_main(roots: Roots, cfg: Config, round_branch: str, *, only_prefixes: Iterable[str] | None = None) -> SyncResult
    # only_prefixes: on abandon, restrict the merge to the round folder (everything else is dropped
    # via `git checkout <main> -- <other paths>` before committing). Raises SyncError("conflict", paths)
    # or SyncError("moved", paths) or SyncError("exhausted").
def update_control_checkout(roots: Roots, cfg: Config) -> str | None
    # If the driver's checkout is on mainBranch with no uncommitted changes: `pull --ff-only`;
    # returns the new sha, or None (with a HISTORY note) when it could not safely update.
```
