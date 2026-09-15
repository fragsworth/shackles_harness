# Draft profile schema

One profile per draft, written by an analyst who read only that draft.
Every profile uses exactly these numbered headings, in this order, so the
five profiles can be compared side by side. Be factual and terse. Cite the
draft's own file names and section titles. Never invent detail the draft
does not contain; write "not specified" where the draft is silent.

1. Format and size
   Files, total bytes, how the spec is organised (entry point plus which
   component files), whether judgment calls are cited inline, reading order
   if given.

2. Language, runtime, packaging, tooling
   Implementation language and version, package manifest, dependency list,
   lint/format/type tools, CI, scripts, anything generated.

3. Repository layout
   The proposed top-level tree, compact (one line per entry, two levels
   deep is enough). Where the harness code lives, where rounds/archives
   live, what is gitignored, where owner files sit.

4. Actors and roles
   Who/what the draft says exists (owner, driver, runner, sub-agents, gate
   agents, hooks ...) and what each does, one line each.

5. Architecture: the main mechanisms
   For each of the following, one or two lines: which module(s) own it and
   the key design choice.
   a. step table / process definition
   b. round lifecycle and state machine (where state is stored)
   c. prompt assembly / template engine / locked prose handling
   d. owner channel (owner log, hooks, quote verification, decisions)
   e. git model (claim, fence, worktrees, landing, conflicts, sync)
   f. results, verdicts, findings lifecycle
   g. money: token estimates, pricing, ledger, limits, hard stops
   h. checks: mechanical checks, verify, test suite handling
   i. doctor / lint / index generation
   j. robustness to arbitrary edits of the spec.yaml files (how achieved)

6. Module inventory
   Every source module/file the draft defines, with its exact name and a
   one-line responsibility. Give the total count. Note any class names.

7. Data contracts
   Every schema/file format the draft defines (STATE.json, PLAN, FINDINGS,
   OWNER.log ...) with one line each, and where each is persisted.

8. Testing
   Test infrastructure (stub agent, fixtures, generated spec, fake git
   remote ...), number of test files, unit vs integration vs live-probe
   split, how live probes work, anything notable about assertions.

9. Docs
   Every doc file proposed and one line on its content.

10. Notable or unusual decisions
   Up to 12 bullets: choices that another drafter might plausibly have
   made differently (self-hosting or not, where the driver runs, what the
   runner's only state is, defaulted config keys, etc.).

11. Judgment calls
   Total count. The classification scheme, verbatim as stated. Then group
   the calls by theme with counts (e.g. platform/tooling facts, gaps in the
   owner files, ambiguity, money rules, git semantics, taste). Then list
   the 10 most consequential calls, one line each with their IDs.

12. Traceability
   Does the draft map owner requirements to components? How (table,
   inline, none)? Does it flag any inconsistency in the owner's files
   (e.g. an undefined config key)? List those flags.

13. Gaps against the brief
   The brief asked for: folder structure, source files, doc files, classes,
   functions (signatures with params, types, return, purpose, errors), test
   files (cases and assertions), high-level architecture, other files
   (config, CI, scripts, fixtures, templates). Note anywhere the draft
   falls short, and anywhere it drifts into line-by-line implementation.
