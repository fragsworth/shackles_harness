# Round concurrency in `vision_harness` — a re-implementable design summary

Written from the `vision_harness` repo for a different codebase. Everything below is
self-contained. Target language: Python 3, standard library only (the original is
dependency-free and deliberately has no daemon, no database and no lock server).

---

## 1. The problem and the invariants

A *round* is one unit of agent-driven work on a repository: plan → spec → tests →
implementation → cleanup → land → postmortem. It runs for hours, costs real money, is driven
by an LLM session, and is interrupted constantly (checkpoints waiting on a human, crashes,
agent timeouts). Rounds are numbered `001`, `002`, … and each ends by landing on `main`.

Several rounds must run **at the same time**, started from the same checkout or from
different clones/machines/sessions, with no coordinating process. Without a mechanism they
collide four ways: **id collision** (two starts both pick 004 and write one folder);
**working-tree collision** (two rounds in one checkout stomp each other, and one round's
`git clean -fdq` recovery destroys the other's work); **driver collision** (two runner
processes advance the same round and diverge its branch); **landing collision** (two rounds
fast-forward `main` concurrently; the second overwrites the first, or lands without having
tested against it).

### The design in one sentence

**Git is the lock manager.** A remote ref update is an atomic compare-and-swap, so:
a round *id* is claimed by creating a branch on `origin` that must not already exist; a
round's *files* are isolated by `git worktree`; a round's *driver* is fenced by requiring
every state-changing command to succeed at `git push` of the round branch; and *landing* is
a bounded merge → re-check → fast-forward → push loop that absorbs concurrent landers.

### Invariants (what can and cannot happen)

| # | Invariant |
| --- | --- |
| I1 | At most one round exists per id. Two concurrent `start`s never both win the same id. |
| I2 | **Nothing is created until the claim wins**: no round folder, no local branch, no worktree, no commit, and the starting checkout's branch and working tree are untouched. A lost race leaves zero garbage to clean up. |
| I3 | Each round's files live in its own worktree. A round never reads or writes another round's worktree, and never writes the main checkout (one exception, read-only: the owner log). |
| I4 | Nothing touches `main` before the LANDING step. |
| I5 | Only one runner may advance a given round: every mutation commits and pushes the round branch, and a **rejected push aborts the runner** with `another runner owns this round (push rejected)`. Non-forced push, so divergence is a hard stop, never a silent overwrite. |
| I6 | `main` on `origin` only ever fast-forwards, and after a round lands it contains that round **on top of** everything that landed meanwhile. |
| I7 | `main` is never force-pushed and merge conflicts are never auto-resolved. A conflict degrades to more agent work, never to lost commits. |
| I8 | Exactly one "living cost" ledger entry per landed round, computed against the tip actually merged — so a round is never charged for a sibling's diff. |
| I9 | The read-only probe command (`check`) never pushes, moves a branch, tags, or writes the ledger (it *does* merge into the round's own worktree). |
| I10 | Agents get no push credential: the runner scrubs `GH_TOKEN`/`GITHUB_TOKEN`/`GIT_ASKPASS` from the agent's environment and passes `--disallowedTools Bash(git push:*) Bash(git commit:*)`. Only the runner commits and pushes. |
| I11 | Crash-recoverable: all state is files committed after every step; a dirty tree on resume is reset and the step redone as an "infrastructure error"; rerunning the command that crashed resumes correctly. |

Explicit **non**-invariants, and they matter: there is **no lease expiry, no heartbeat, no
TTL, and no stale-holder takeover**. A claimed id stays claimed forever; a crashed round is
resumed by rerunning, never by a timeout. There is also **no cross-round path arbitration**:
two live rounds may declare the same source files and only discover the clash at landing.

---

## 2. Data model

### 2.1 Naming and ids

| Thing | Value |
| --- | --- |
| Round id | integer, rendered `NNN` = `f"{rid:03d}"` |
| Round branch | `round/NNN` (or an explicit `--branch NAME`) |
| Worktree path | `<main_root>/<worktreeDir>/NNN`, e.g. `<repo>/.worktrees/004` |
| Round folder | `harness/archives/rounds/NNN/` **inside the worktree**, on the round branch |
| Landed tag | `round/NNN-landed` |
| Abandoned tag | `round/NNN-abandoned` |
| Next id | `1 + max(local round-folder ints, origin round-branch ints)` |

`main_root(root)` is the key path helper: it turns any checkout into *the* main checkout —

```python
os.path.dirname(os.path.abspath(os.path.join(root, git(root, "rev-parse", "--git-common-dir"))))
```

In the main checkout `git rev-parse --git-common-dir` prints `.git`, so this is `root`; in a
linked worktree it prints the absolute `<main checkout>/.git`, so this is the main checkout.
If it fails (not a repo), fall back to `os.path.abspath(root)`.

### 2.2 Files, and where each lives

- `harness/project.json` (on the round branch, in the worktree) — config: `mainBranch`,
  `worktreeDir`, budgets and prices, agent definitions, `maxTurnsPerRun`,
  `maxRunWallClockSeconds`, `verifyTimeoutSeconds`, `suiteCommand`, `agentCommand` template,
  `gateToolFlags`/`producerToolFlags`, `scrubEnv`.
- `harness/archives/rounds/NNN/` — **the only round state**: `PLAN.json`,
  `AGENTS-PLAN.json`, `SPEC.json` + `SPEC.md`, `STATE.json`, `HISTORY.md` (append-only
  narrative), `OWNER.log` (this round's slice of the human's messages),
  `FINDINGS/<STEP>-<attempt>.json`, `RESULTS/<STEP>-<attempt>.json`,
  `PROMPTS/<STEP>-<attempt>.txt`, `SUITE.json`, `POSTMORTEM.md`, `tests-archive/`.
- `harness/archives/rounds/index.jsonl` — one JSON line per *finished or abandoned* round
  (`{id, quote_usd, spend, attempts, failures, outcome, prose_commit, landed_at|abandoned_at}`),
  appended **on the round branch** and merged into `main` by landing. Append-only JSONL is
  deliberate: two rounds appending different lines merge cleanly, where a single JSON array
  would conflict every time.
- `<main_root>/harness/OWNER.log` — **gitignored**, shared by every worktree, and the *only*
  file the runner reads outside `root`. Format `<UTC ISO-8601 Z>\t<message, newlines as \n>`,
  appended by a chat hook. Each round copies new lines forward into its own folder slice, so
  committed state stays self-describing.
- `<main_root>/harness/DRIVER.json` — gitignored pointer to the driving session's transcript.
- `.gitignore` **must** contain `<worktreeDir>/` — a hard precondition, not a nicety: the
  dirty-tree recovery runs `git clean -fdq`, which would delete every sibling worktree if
  they were untracked-but-not-ignored.

### 2.3 `STATE.json` — validated on every save

Required: `round` (int), `branch` (str), `created_at`, `status`, `step`, `attempts` (step →
int), `failures`, `infra_errors`, `step_commits` (step → sha at its PASS), `inputs_hash`,
`budget_usd`, `spend`.
Optional / concurrency-relevant: `base_commit` (HEAD at start), `prose_commit` (the commit
prompts are rendered from — see 3.6), `kind_pending`, `delegated`, `approval`, `checkpoint`,
`pending_question`, `carried_findings`, `last_findings`, `findings_ledger`, `mech_ok`,
`step_starts` (step → HEAD when it first ran), `landed_at`, `abandoned_at`, `main_before`
(audit: local `main`'s tip before LANDING merged), `owner_since`, `hard_stop_raised`,
`round_limit_raised`, driver-cost cursors.

There is **no** `worktree` key: the worktree path is derivable and is printed by `start`.
There is **no** lock/lease/owner/pid field anywhere. Ownership is entirely implicit in "can I
still push this branch".

### 2.4 Status lifecycle

```
                 start
                   |
                   v
   +----------> active <-----------+
   |             |   |             |
   |  checkpoint |   | POSTMORTEM  | owner word: approve / delegate
   |             v   v             |
   +---------- checkpoint      finished
                   |
                   | owner word: abandon        (or `abandon` command from any status)
                   v
               abandoned
```

Steps, in order — `P`=producer (LLM writes an artifact), `G`=gate (read-only LLM judge),
`M`=mechanical (deterministic code), `C`=human checkpoint:

`CHAT-TO-PLAN (P)` → `CHAT-TO-PLAN-GATE (M)` → `PLAN-AGENTS (P)` → `PLAN-AGENTS-GATE (G)` →
`PLAN-TO-SPEC (P)` → `PLAN-TO-SPEC-GATE (G, C)` → `SPEC-TO-TESTS (P)` →
`SPEC-TO-TESTS-GATE (G)` → `SPEC-TO-IMPLEMENTATION (P)` →
`SPEC-TO-IMPLEMENTATION-GATE (G)` → `OWNER-REVIEW (C)` → `TESTS-TO-SUITE (P)` →
`TESTS-TO-SUITE-GATE (G)` → `CLEANUP (P then M)` → `LANDING (M)` → `POSTMORTEM (P)`.

Only `LANDING` and the post-round sync touch `main`; only `start` claims ids; every other
step is ordinary work on the round branch.

---

## 3. The protocol

### 3.1 `start` — claim the id (compare-and-swap)

Order matters: **validate the plan file first**, before any git command, so a malformed
input can never leave a claim behind.

```
git fetch origin                                   # failure => exit 1, nothing created
ids   = ints parsed from refs/remotes/origin/round/<tail> where tail.isascii() and tail.isdigit()
rid   = 1 + max(highest local round folder or 0, max(ids, default 0))
for attempt in 1..PUSH_ATTEMPTS:                   # PUSH_ATTEMPTS = 5, counts pushes not retries
    branch = explicit_name or f"round/{rid:03d}"
    git push --porcelain --force-with-lease=refs/heads/<branch>: origin HEAD:refs/heads/<branch>
    won = (exit == 0) and any(line.startswith("*") for line in stdout.splitlines())
    if won: break
    if explicit_name: raise "round id taken: branch <NAME> exists on origin"
    rid += 1                                       # no re-fetch between attempts
else: raise f"round id: push rejected {PUSH_ATTEMPTS} times, last {branch}"
```

Three details you must not get wrong:

- The lease value after the colon is **empty**: "this ref must not exist on origin". This is
  what makes the push a true CAS.
- Win is `exit 0` **and** a porcelain line starting with `*` (git's flag for *newly created
  ref*). A plain `git push HEAD:refs/heads/<branch>` is not a valid implementation: when the
  branch already exists at exactly our HEAD it exits 0 with `=` (up to date) and you would
  wrongly believe you won. `=` is a loss. `!` (stale info / hook declined) is a loss.
- Exactly one push when a branch name was given explicitly — never fall through to the next
  id, because the lease rejection is client-side and an origin hook cannot even observe it.

On a win:

```
git worktree add -b <branch> <main_root>/<worktreeDir>/NNN HEAD
```

…then everything else happens **with the worktree as root**: create the round folder, write
`PLAN.json` (with `round` = the claimed id), `STATE.json` (`branch`, `base_commit` =
`prose_commit` = the worktree HEAD), `HISTORY.md`, the owner-log slice, the opening ledger
entry; then `git add -A`, `git commit -m "round NNN: start"`, `git push -u origin <branch>`.
Print exactly one line: `{"round", "folder", "branch", "worktree"}`.

If `git worktree add` fails (path or local branch already exists) the **claim stays claimed**
and the command errors; a rerun simply skips that id. Ids are cheap and monotonic; claims are
never released.

`--no-branch` is the degenerate single-checkout mode: id = highest local folder + 1, no fetch,
no CAS, no worktree, no push. Useful for tests and offline work.

### 3.2 `next` — advance deterministically, then hand off to an agent

`next` is the only place mechanical steps execute. In order: (1) if `status` is
`finished`/`abandoned`, sync main (3.5) and return `done`; (2) re-hash `PLAN.json`/`SPEC.json`
— an out-of-band edit re-enters at the first step whose input changed and resets downstream
attempt counts; (3) **dirty-tree recovery** — `git status --porcelain` non-empty ⇒
`git checkout -- .`, `git clean -fdq`, `infra_errors[step] += 1`, history line (this is why
the worktree dir must be gitignored); (4) refresh the owner-log slice from the main
checkout's log; (5) if `status == checkpoint`, look for a newer human word (`approve`,
`delegate`, `delegate through STEP`, `abandon`) *after the checkpoint's own timestamp* and
resume, else return `checkpoint` with exit code 10; (6) loop over mechanical work until an
LLM run is due, then render the prompt to `PROMPTS/<STEP>-<attempt>.txt`, save state, commit
(no push), and return the action JSON `{round, step, kind, attempt, prompt_file, result_file,
artifact, tools, budget_usd, max_turns, agent, model, effort, spend}`.

### 3.3 `record` — fence and commit

`record --step S --attempt N --result FILE [--cost USD] [--no-push]`:

- Reject unless `status == "active"`, `state.step == S`, and `N == attempts[S] + 1`
  (exit code 2). This is the idempotency guard: a replayed or out-of-order record is refused
  rather than double-applied.
- Copy the agent's result JSON into `RESULTS/`, validate it against its schema, add ledger
  entries, route producer vs. gate outcomes, update `STATE.json` and `HISTORY.md`.
- `git add -A`; if nothing is staged, return; else commit `round NNN: <step> attempt <N>`
  and `git push -u origin <branch>`. **A rejected push raises
  `RunnerError("another runner owns this round (push rejected)")` and the runner stops.**
  That is the whole fencing mechanism — no leases, no pids, no timestamps.

### 3.4 `LANDING` — the concurrent-landing protocol

LANDING is mechanical: `next` executes it, and it splits into a *check* phase and a *land*
phase. Only the land phase mutates anything shared.

**Check phase** (also exactly what the `check` command runs at LANDING — I9):

1. If the round runs on `mainBranch`, or `refs/heads/<mainBranch>` doesn't exist → `target = None`.
2. Else, if an origin exists: `git fetch origin`; `target = "origin/<mainBranch>"` if that
   remote-tracking ref exists, else the local `<mainBranch>`.
3. `git merge --no-edit <target>` into the round branch. On failure: `git merge --abort` and
   return one blocking finding `L1` (`quote: "git merge <target>"`,
   `reason: "merge conflict with <target>"`).
4. Run the spec's `verify` command, then the project-wide `suiteCommand`, each under
   `verifyTimeoutSeconds`. A failure returns one blocking finding `L2`.
5. Otherwise no findings. The check phase must not add a ledger entry, move a branch, push,
   tag, or set `landed_at`.

**Land phase** (only inside `next`, only when the check phase was clean):

```python
for attempt in range(1, PUSH_ATTEMPTS + 1):
    living = living_charge(target or state["base_commit"])   # priced against the tip actually merged
    if target is None: break
    git("branch", "-f", mainBranch, "HEAD")                  # fast-forward local main
    if not push or not has_origin(): break
    if git_ok("push", "origin", f"{mainBranch}:{mainBranch}"): break
    if attempt == PUSH_ATTEMPTS:
        raise RunnerError(f"landing: push of {mainBranch} rejected {PUSH_ATTEMPTS} times")
    findings, target = landing_check()                       # re-fetch, re-merge, re-run verify + suite
    if findings: return findings                             # conflict or red on the new tip
add_spend("LANDING", 1, living, "living")                    # exactly one entry per landed round (I8)
git("tag", "-f", f"round/{rid:03d}-landed")
state["landed_at"] = now()
```

Why each piece exists:

- A **rejected push means origin's `main` moved after our fetch** — a sibling landed. The
  retry merges the *new* tip and re-runs verify **and** the full suite before pushing again,
  so `main` always contains this round on top of everything that landed meanwhile, tested
  together (I6).
- The living/diff cost is recomputed each attempt against the tip actually merged and
  recorded once, after the push succeeded — otherwise this round is billed for the sibling's
  files (I8).
- Exhausting the bound raises and does **not** save `STATE.json`. Merge commits made so far
  are ordinary commits on the round branch; rerunning `next` simply lands again from LANDING.
  That is the contention/crash recovery story: idempotent by re-entry.
- `L1`/`L2` findings are routed to `SPEC-TO-IMPLEMENTATION` as a new attempt — a conflict
  becomes agent work, never a force-push (I7).

**Precondition, unenforced:** `mainBranch` must not be checked out in *any* worktree, because
git refuses `git branch -f` on a checked-out branch. In practice the main checkout parks on a
session branch. The refusal surfaces as an ordinary git error and `next` can be rerun after
switching.

### 3.5 After the last commit — `sync_main`

The round's final commit (POSTMORTEM, or an abandon *after* landing) is not yet on `main`.
`sync_main(push)` runs after `record` finishes the round, and at every `done` return of
`next`. It is deliberately timid — it never raises, never fetches, never merges, never
forces:

```python
return (bool(state.get("landed_at")) and state["branch"] != mainBranch
        and branch_exists(mainBranch)
        and git_ok("merge-base", "--is-ancestor", mainBranch, "HEAD")   # fast-forward only
        and git_ok("branch", "-f", mainBranch, "HEAD")
        and (not push or not has_origin() or git_ok("push", "origin", f"{main}:{main}")))
```

It reports its boolean as `main_synced` in the `done` action. If another round moved `main`
first, the ancestry check or the push fails, `main_synced` is `False`, nothing is retried or
forced, and the tail commits simply arrive with the next round's landing merge. Idempotent:
called when `main` is already at HEAD it returns `True` and changes nothing.

### 3.6 How concurrent rounds avoid conflicting edits

Four layers, from strongest to weakest:

1. **Separate worktrees** — different working directories over one object store. Rounds
   cannot see or overwrite each other's uncommitted files at all.
2. **Separate branches, fenced by push** — commits never interleave; a second driver on the
   same round is stopped at its first push (I5).
3. **Declared path confinement inside a round** — `SPEC.json` declares `implPaths` and
   `testPaths` (validated disjoint by prefix). After each code step, a mechanical check
   diffs `step_starts[step]..HEAD` and raises finding `M1` for any file outside the declared
   paths plus the round folder; `M2` rejects any change to tests after the tests gate passed.
   This bounds a round's blast radius, but it is *per round* — it does not stop two rounds
   declaring the same paths.
4. **Landing merge** — the only cross-round arbitration. Non-overlapping edits merge; true
   conflicts become `L1`.

Prompt determinism is part of isolation too: prompts are rendered from
`git show <prose_commit>:<file>`, not from the working tree, so a sibling round landing new
prose mid-round cannot change what this round's agents are told.

---

## 4. Runner / driver split

**Deterministic code (`run.py`, ~1360 lines, no LLM, no daemon, no dependencies):** id
claiming, worktrees, all git, schema validation, state machine, mechanical checks, prompt
rendering, ledger, checkpoints, landing, tagging, index lines. Exit codes:
`0` ok/finished, `1` error, `2` usage, `3` check failed, `10` checkpoint.

**The driver (an LLM session):** runs `next`, takes the printed `prompt_file`, spawns a
*fresh* sub-agent with that file as its system prompt (read-only tools for gates), saves the
sub-agent's final JSON message to `result_file`, runs `record`. It never does a gate's job
itself and never commits or pushes.

**The step agents:** fresh per run, no memory, no push credential, confined to their
declared paths and the round folder.

CLI surface (global `--root DIR`, `--round N`):

| Command | Reads | Writes |
| --- | --- | --- |
| `start --plan F [--budget] [--branch] [--no-branch] [--delegated]` | plan file, origin refs, owner log | origin claim ref, worktree, round folder, start commit + push; prints `{round, folder, branch, worktree}` |
| `next [--no-push]` | STATE, owner log, git | mechanical step effects, prompt file, STATE, commit; prints an action or a checkpoint (exit 10) |
| `record --step --attempt --result F [--cost] [--no-push]` | result JSON, STATE | RESULTS/, FINDINGS/, STATE, HISTORY, commit + **push (the fence)** |
| `run --until checkpoint\|step\|done [--no-push]` | — | headless loop: `next` → spawn agent via `agentCommand` → `record`; 3 retries per agent run, each retry resetting the tree and counting an infra error |
| `status`, `spend [--project]` | STATE, `index.jsonl`, sibling round folders | nothing |
| `check` | STATE, git, verify/suite | nothing shared (at LANDING it merges into the round worktree only) |
| `abandon --reason R` | STATE | `abandoned` status, tag `round/NNN-abandoned`, index line, local commit (no push) |

`spend --project` is the only command that reads *across* rounds: it sums `index.jsonl` plus
every round folder not yet in the index, i.e. including live siblings.

---

## 5. How it is tested

Strategy: **partial integration, no mocks of git.** Every test builds a throwaway repository
in a temp dir containing a copy of the real config (with the agent command repointed at a
stub), real prose, and the real runner; then drives it **through the CLI** with
`subprocess.run`, asserting on exit codes, stdout JSON, files, and git state. ~122 tests,
~100 s.

Fixtures worth copying:

- **`Repo`** — temp repo, `git init`, generated `.gitignore` (including `<worktreeDir>/`),
  hermetic git env (`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`,
  `GIT_TERMINAL_PROMPT=0`, fixed author/committer) so the suite cannot touch user config.
- **`Repo.add_origin()`** — a **local bare repo** as `origin`, added by *absolute* path (a
  relative one resolves against the worktree). Local path remotes run hooks — the whole trick
  below. **`Repo.clone()`** is a second clone: "another machine".
- **`Repo.view(worktree)`** — a shallow copy that runs every command as
  `run.py --root <worktree>` while reading files under the worktree, so one test object
  expresses both "the main checkout" and "the round's view".
- **`Origin`** — origin-side truth read with `git -C origin.git rev-parse`, *never* from a
  clone's remote-tracking refs (they lag until a fetch). Plus installable `hooks/update`
  scripts in two shapes: **reject-N** (log every push of a refname glob, decline the first N
  or all — deterministically produces "claim rejected" and "`main` push rejected"), and
  **move-and-reject-once** (on the first push of `refs/heads/main`, run
  `git update-ref refs/heads/main refs/heads/side` and exit 1 — this simulates a sibling
  landing in the microsecond between our fetch and our push, the exact race the retry loop
  exists for).
- **`stub_agent.py`** — the fake agent, invoked exactly like the real one: it reads the
  rendered prompt, finds the last `STEP:`, `ARTIFACT:` and `RESULT_FILE:` lines (the prompts
  emit these as a machine-readable contract), writes a canned valid artifact, and prints
  `{"result": "<json>", "total_cost_usd": 0.01}`. Behaviour switches on env vars:
  `STUB_MODE=pass|fail|dispute|needs_owner|upstream|blocked|garbage`, `STUB_FENCE=1` (wrap
  the JSON in a code fence, to test unwrapping), `STUB_ARCHIVE=1`, `STUB_LOG=<file>` (append
  argv/cwd/env-keys per invocation so tests assert *how* the runner invoked the agent). The
  same module exposes `perform()` so tests drive it **in-process** —
  `Repo.play(until="CLEANUP")` runs a whole round to a chosen step in seconds. One scripted
  agent thus serves as subprocess agent, in-process driver, and assertion vocabulary
  (`FAIL_REASON`, `QUESTION` markers the tests grep for).

Races are made deterministic without threads. The best example: to force clone B to lose the
claim for `round/001`, the test narrows B's fetch refspec —
`git -C B config remote.origin.fetch '+refs/heads/main:refs/remotes/origin/main'` — so B
never learns round branches exist and *must* compute id 1 and lose. Both loss shapes are
covered: `!` (branch exists at another commit) and `=` (branch exists at exactly our HEAD).

What the concurrency tests assert:

- **Claim**: exit 0, one-line stdout with exactly `{round, folder, branch, worktree}`;
  worktree on `round/001` whose `HEAD~1` is the pre-start HEAD; `origin round/001 == worktree
  HEAD`; round folder only in the worktree; main checkout still on `main`, clean, HEAD
  unchanged, no round folder; `<worktree>/harness/OWNER.log` does not exist.
- **Lost race**: winner untouched, loser silently takes the next id, and a shared
  `assertNothingCreated`/`assertRaceLost` helper proves I2 — no round folder in the checkout,
  in the worktree, **or in any commit** (`git log --all -- .../rounds/001` empty), no
  `.worktrees/001`, exactly one local `round/*` branch, clean tree, still on `main`.
- **Bounds**: reject-all hook ⇒ hook log is exactly `round/001..round/005`, stderr
  `round id: push rejected 5 times, last round/005`, origin has no round branch, nothing
  created. **Explicit branch taken**: exactly one push, clear error, no fall-through.
  **`worktree add` failure**: claim survives, rerun takes the next id.
- **Id sourcing**: 1 + max over *both* local folders and origin branches; `round/003-x` and
  `round/abc` ignored; tags never count.
- **Worktree operation**: the owner log is read from the main checkout even for a checkpoint
  raised in a worktree; `status`/`spend`/`check` work under `--root`; `record` pushes the
  round branch from the worktree.
- **Landing after a sibling moved main**: `check` merges and does nothing else (no tag, no
  ledger entry, local `main` unmoved); then `run --until done` leaves
  `origin/main == local main == the round tip`, containing both rounds' files, with exactly
  one living entry equal to *this round's* diff (`0.01`, not `0.03`) — this proves I8.
- **Rejected main push**: hook log shows rejection then acceptance;
  `attempts["LANDING"] == 1` (the retry is inside one `next`); result contains the sibling's
  file. Reject-all: exit 1, origin's main unchanged, no tag, no living entry, clean tree,
  state still at LANDING — remove the hook and it lands on a rerun.
- **Conflict**: `next` returns a `SPEC-TO-IMPLEMENTATION` attempt-2 action, `failures` is 1,
  the findings file's first entry is `L1` quoting `git merge origin/main`, no tag, worktree
  clean (merge aborted).
- **Fence**: another clone moves the round branch on origin; the next `record` exits 1 with
  `another runner owns this round`.
- **Post-round sync**: `main_synced: true` when it fast-forwards, idempotent on a second
  call, `false` with origin untouched when a sibling moved `main` first.

---

## 6. Known limitations, rough edges, and what I would change

Observed for real: rounds 004 and 005 ran in parallel on this mechanism and both landed, so
the core works. The failures below are all recorded in the project's own postmortems.

1. **The conflict path cannot converge.** A LANDING `L1` re-enters `SPEC-TO-IMPLEMENTATION`,
   but that step's own mechanical checks reject the only possible fix: `M1` rejects a diff
   touching anything outside `implPaths` (a merge commit brings in everything) and `M2`
   rejects any change to the frozen tests. For a same-line conflict no agent edit can clear
   it. Real cost when it fired: $11.22 and 51 minutes of retries producing a byte-identical
   tree, resolved by a human hand-merge outside the loop. **Fix:** on `L1`, start the new
   attempt from a *merge* of the target and diff `M1`/`M2` against the merge base — or
   declare in process docs that a landing conflict escalates to a human merge plus a rerun.
2. **Runner/config version skew between worktrees.** Each worktree carries its own
   `project.json` *and* its own `run.py`, and which runner drives a round is unspecified. A
   sibling landing a new required config key broke an in-flight round (`KeyError` on a key
   the older branch's config lacked). **Fix:** read new config keys with defaults, pin the
   runner to the round's own branch copy, and write down which runner drives a round.
3. **Landing ordering is manual.** Because the post-round fast-forward lives in whichever
   runner version has it, one of two parallel rounds must land second; the operator held one
   round 40 minutes by hand. Needs an explicit rule or an ordering primitive.
4. **No lease expiry, no stale-holder recovery.** A claim is permanent, and the runner never
   cleans worktrees, branches, remote-tracking refs or tags. A defensible trade (ids are
   cheap; expiry reintroduces the clock-skew problem CAS avoids) but a `prune` command
   reporting claimed-but-never-committed ids would help.
5. **Unenforced preconditions** that fail late: `<worktreeDir>/` gitignored, and `mainBranch`
   not checked out anywhere. Both should be checked by `start` and refused up front.
6. **No cross-round path arbitration.** Nothing warns that a starting round declares
   `implPaths` a live sibling already owns; the clash surfaces only at landing. Cheap fix:
   at `start`, read live siblings' `SPEC.json` from their branches and warn on overlap.
   Keeping shared prose files to one sentence per line measurably reduced conflicts.
7. **Validation is only verify + suite**, so a round's own plan-level validation items ("two
   rounds land in parallel") can go unchecked and the round still lands green.
8. **Cross-round accounting double-counts**: one driver session driving two rounds books the
   same turns to both ledgers.
9. **Freeze rules interact badly with everything.** Tests are byte-frozen from the tests gate
   through landing and the whole spec is hashed for out-of-band-edit detection, so a defect
   found mid-round often cannot be fixed in that round. Hash only normative sections; allow
   an append-only errata block.

### Source files I drew from

| Path (under `C:\Users\twolf\Claude\vision_harness\`) | What it is |
| --- | --- |
| `harness/src/run.py` | The whole runner: `claim_round`, `cmd_start`, `Round.next/record/land/landing_check/sync_main/commit`, `main_root`, `PUSH_ATTEMPTS`. |
| `harness/archives/rounds/003/SPEC.md` | The normative design document for this exact feature ("round-ID concurrency"): CAS semantics, worktree layout, LANDING phases, test plan, non-goals. The single most useful file. |
| `harness/archives/rounds/003/PLAN.json` | Scope and validation items the feature was built against. |
| `harness/archives/rounds/003/POSTMORTEM.md` | Costs, findings, and the admission that the feature shipped untested in the wild. |
| `harness/archives/rounds/004/SPEC.md` | `main_before` and the post-round `sync_main` fast-forward (sections 8.1-8.3). |
| `harness/archives/rounds/004/POSTMORTEM.md`, `005/POSTMORTEM.md` | The real parallel-rounds experience: conflict non-convergence, runner/config skew, landing order, accounting double-count — source for section 6. |
| `harness/tests/test_run.py` | The suite. `Origin`/`Repo`/`HarnessTest` fixtures (l. 62-440), `WorktreeStartTest` (claim/race/bounds, l. 1812-2037), `WorktreeRoundTest` (worktree ops + LANDING, l. 2042-2243), `RealSpendTest` T9/T10 (`sync_main`, l. 2724-2817). |
| `harness/tests/stub_agent.py` | The scripted fake agent and its `STUB_*` behaviour switches. |
| `harness/docs/PROCESS.md` | The normative prose rule set: Round, Runner, Failure/dispute, Spec and code rules. |
| `harness/project.json` | Config keys the mechanism reads: `mainBranch`, `worktreeDir`, `scrubEnv`, tool flags, timeouts, `suiteCommand`. |
| `harness/src/schemas.json` | `STATE` and artifact schemas (every field listed in §2.3). |
| `harness/src/owner_log_hook.py` | How the shared, gitignored owner log and driver pointer are written. |
| `harness/AGENTS.md`, `harness/INDEX.md`, `harness/prose/COMMON/COMMON-PROCESS.txt` | Driver/runner/agent split and the `STEP:` / `ARTIFACT:` / `RESULT_FILE:` prompt contract the stub agent parses. |
