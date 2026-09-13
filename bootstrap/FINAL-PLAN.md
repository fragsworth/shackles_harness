# FINAL PLAN: what the implementer builds

Written by the coordinating session after reading `bootstrap/merged/merged-A.md` and `bootstrap/merged/merged-B.md`, which were each merged from the six plans in `bootstrap/plans/`. This file is short on purpose: it names the base document and lists every amendment. Where this file and merged-B disagree, this file wins. Where merged-B is silent, merged-A is the second reference, then the six plans.

## Base

**merged-B is the plan**, in full: its decision log, design (sections 2.1 to 2.17), test strategy (section 3), the two spec-file edits (section 4, exactly those, in their own commit, flagged), interpretations (section 5), risks (section 6), implementation sequence (section 7) and the real-agent testing ladder (section 8).

## Amendments (adopted from merged-A or decided here)

1. **Gate verdict is authoritative** (merged-A decision 9 replaces merged-B decision 12's normalization). The gate's `verdict` field is the verdict. `blocking` flags are normalized to it: PASS with a blocking finding sets that finding non-blocking; FAIL with no blocking finding keeps the findings as given. Either mismatch is one HISTORY line. `needs_owner.upheld` still raises the `question` checkpoint whatever the verdict says, because that is routing, not judgment. Reason: "FAIL iff a blocking finding" encodes today's COMMON-GATE cost rule into the runner; the owner may reword that rule at any time.

2. **Carry-forward files** (merged-A decision 5 replaces merged-B decision 16). `docs/TODO.md` and `docs/CLARIFICATIONS.md` are living files, named in `DEFAULTS.carryForwardFiles`, created by the bootstrap with a one-line header each. POSTMORTEM's write paths include them. CHAT-TO-PLAN's plumbing feeds both files verbatim plus the paths (not bodies) of the last `postmortemFeedRounds` landed POSTMORTEM.md files. The runner never parses either file. Edits to the carry-forward files after LANDING are merged into main by `sync_main` and are exempt from the living charge; say so in PROCESS.md.

3. **Spec baseline lives under archives** (merged-A decision 8 for location; merged-B 2.13 for everything else). `harness/archives/spec-baseline.json` and `harness/archives/spec-changes.jsonl`. The test stays `harness/tests/test_spec_baseline.py` and reads the baseline by path. The meta-test that proves the guard fires stays exactly as merged-B 3.4 describes.

4. **Per-rung agent definitions, generated** (merged-A decision 15 replaces merged-B's two static definitions). `run.py agents --write` generates `.claude/agents/shackles-producer-<rung>.md` and `.claude/agents/shackles-gate-<rung>.md` from the roster: frontmatter `model` (alias from `modelAliases`), `effort`, and for gates `tools: Read, Grep, Glob`; for producers the git-command restrictions merged-B lists. They are committed. The action JSON names the `agent_type` to use. A test checks the generated frontmatter against the roster. Verified fact for DRIVER.md: **agent definitions register only at session start; one created mid-session is "not found"**. Documented fallback when the type is unavailable: `subagent_type: general-purpose` with `model: <alias>`; effort then inherits the driver session's setting. Verified fact: a `general-purpose` sub-agent spawned with `model: fable` from a max-effort session reports model `claude-fable-5-1` and a visible `reasoning_effort` of `max`.

5. **Worktree location.** `DEFAULTS.worktreeDir` is `.claude/worktrees` (this machine's rule: worktrees live at `.claude/worktrees/` inside the repo) and a round's worktree folder is `round-NNNN` under it. `.gitignore` carries `.claude/worktrees/`. Nothing else about the claim, fence or landing changes.

6. **Wording-adjacent checks are warnings, not test failures.** merged-B 3.4 has `test_spec_structure.py` assert that the status and verdict words appear in the locked prose. Make that a `doctor` warning instead. Tests fail only on: the baseline drift test, structural lint (steps, gates, prose file names, artifact keys, roster keys, spec files present), unresolved tokens outside the waiver file, and prompts that fail to render. No test asserts on any sentence of the owner's prose.

7. **Simulated agents carry the suite.** The stub agent of merged-B 3.1 (`stub_agent.py` with scripted modes per step and attempt, editing the toy project's fake source, tests and docs, producing canned artifacts, judgment lines, garbage, strays, frozen-test edits, spec edits, conflicts, commits, slow runs, replays) is the primary instrument. Go as far as it can go: every routing row in merged-B 2.9, every checkpoint kind, every mechanical check, every owner command, the caps and stops, the spec guard, both landing conflict paths, the races and the fence, all driven by the stub without any real agent. A real agent is never spawned by the test suite.

8. **Surface undefined judgment calls loudly.** Counts of defined and undefined judgment calls, and the last five undefined lines with the file's absolute path, appear in every checkpoint message, in `status`, in the `done` JSON and in HISTORY per attempt (merged-B 2.14 already says most of this; make it complete). A later real-agent test will fabricate a situation that forces an undefined judgment call and check that the harness reports it.

9. **Headless mode stays secondary but must actually work on this machine.** Implement merged-B 2.15 as written; the suite exercises it only through the stub. `doctor` must find `claude.exe` here and `doctor --probe-cli` must succeed once during the build (one call, low rung, capped at a few cents). Reason: the test driver in later phases may have to run rounds headlessly if nested sub-agent spawning turns out to be unavailable; see the note appended at the end of this file.

10. **Everything else in merged-B stands**, including: the runner never matches a prose phrase; owner words are interpreted by the driver and passed with `--quote`; the step table is code cross-checked against the spec's data; config is `DEFAULTS` < `project.yaml` < `harness/local.yaml`; prose is pinned at `prose_commit`, config read live; mechanical checks at `record` on the uncommitted diff with strays reverted; landing conflicts converge through one agent attempt measured against `git merge-tree --write-tree`; landing pushes `HEAD:refs/heads/main`; `index.jsonl` with `merge=union`; invalid results are booked as infra errors; prompts open with `harness/AGENTS.md` verbatim and unrendered; prompt handoff by path with the fixed one-line wrapper; the cut list in merged-B decision 26 (ERRATA.md is cut; UNDEFINED_JUDGMENT_CALLS.md serves).

## Constraints from the owner, restated for the implementer

- Python 3.13 via `py -3.13`; PyYAML and pytest are installed there; no other dependencies. Windows 11, PowerShell, git 2.45. The whole suite must pass on this machine with `py -3.13 -m pytest`.
- The files `spec.yaml` lists are the owner's. Exactly the two one-token edits of merged-B section 4, in their own commit, with the diff in the commit body. Do not add the new files to `spec.yaml`. Do not touch `bootstrap/`.
- Everything must survive arbitrary changes to the locked prose: no mechanical behavior depends on wording; the mechanics tests run on the generated minimal fixture spec (merged-B 2.17), not on the owner's files.
- You are not subject to the harness's runtime rules while building it (harness/AGENTS.md governs agents inside rounds). Commit freely on your branch, one commit per milestone at least, repo-local identity already configured.
- Do not spawn sub-agents. Do not start servers or browsers. Do not touch the screen.
- If you run low on context before finishing: commit everything, write `bootstrap/HANDOFF.md` describing exactly what is done, what is not, and what is failing, and stop. A second session continues from it.

## Verified after writing the above

- A sub-agent spawned with the Agent tool does have the Agent tool itself and can spawn its own sub-agents (probed: a nested spawn returned "pong"). Driver mode is therefore the primary path for every later real-agent test: a driver session runs `next`, spawns one sub-agent per action, saves the final message, runs `record`. Headless mode remains secondary, but amendment 9 stands: `doctor --probe-cli` must succeed once on this machine.
