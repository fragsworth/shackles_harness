"""The round: STATE.json and HISTORY.md, next, record, the owner commands and the read-only views."""
import hashlib
import json
import os
import re
import shutil

from . import agentdefs, checks, config as configmod, contract, gitops, landing, ledger, owner as ownermod, pipeline, procs, prompts, schemas, specguard
from .gitops import RunnerError

NOTE_CAP = 2000
HEADERS = {"defined": "# DEFINED JUDGMENT CALLS, round {id}: one line per call, appended by the agent that made it.\n",
           "undefined": "# UNDEFINED JUDGMENT CALLS, round {id}: one line per call, appended by the agent that made it.\n"}
SKIP_SOURCES = ("disabled", "override", "no-prose")
OPEN = ("open", "disputed", "settled")
RESUME = {
    "review": ["approve", "delegate", "answer", "override", "abandon"],
    "question": ["answer", "approve", "abandon"], "blocked": ["answer", "approve", "override", "abandon"],
    "failure-limit": ["approve", "override", "abandon"], "round-limit": ["approve", "abandon"],
    "hard-stop": ["approve", "abandon"], "spec-edit": ["approve", "abandon"], "upstream-plan": ["approve", "abandon"],
    "approval": ["approve", "delegate", "abandon"], "infra": ["approve", "override", "abandon"],
}
HINTS = {"approve": 'approve --quote "<the owner\'s words>"', "delegate": 'delegate --quote "<words>"',
         "answer": 'answer --text "<the answer>" --quote "<words>"', "override": 'override --steps A,B --quote "<words>"',
         "abandon": 'abandon --reason "<why>" --quote "<words>"'}


def sha_of(path):
    return hashlib.sha256(procs.read_bytes_normalized(path)).hexdigest() if os.path.exists(path) else None


def local_round_ids(cfg):
    folder = cfg.round_folder(0)
    parent = os.path.dirname(cfg.abs_path(folder))
    pattern = re.compile(re.escape(os.path.basename(folder)).replace("0" * cfg.id_width, r"(\d+)"))
    ids = []
    if os.path.isdir(parent):
        for name in os.listdir(parent):
            m = pattern.fullmatch(name)
            if m:
                ids.append(int(m.group(1)))
    return sorted(ids)


class Round:
    def __init__(self, root, cfg, rid):
        self.root, self.cfg, self.rid = os.path.abspath(root), cfg, rid
        self.harness = cfg.harness_root
        self.id = cfg.round_id(rid)
        self.paths = cfg.round_paths(rid)
        self.folder = self.abs(self.paths["folder"])
        state_path = self.abs(self.paths["state"])
        self.state = procs.read_json(state_path) if os.path.exists(state_path) else None
        self.notes = []
        self.checkpoint_entry = None  # the CHECKPOINT line for HISTORY, written by save() after the attempt entry that raised it
        self._prose_names = None
        self._cache = {}

    def cached(self, key, compute):
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    @property
    def main_root(self):
        return self.cached("main_root", lambda: gitops.main_root(self.root))

    @property
    def owner_log(self):
        return ownermod.log_path(self.main_root)

    @property
    def git_dir(self):
        return self.cached("git_dir", lambda: gitops.git_dir(self.root))

    def has_origin(self):
        return self.cached("has_origin", lambda: gitops.has_origin(self.root))

    def merging(self):
        return gitops.merging(self.root, self.git_dir)

    # ---- paths and files -------------------------------------------------
    def abs(self, rel):
        return self.cfg.abs_path(rel)

    def repo_rel(self, rel):
        return self.cfg.repo_rel(rel)

    def read_json(self, key):
        path = self.abs(self.paths[key])
        return procs.read_json(path) if os.path.exists(path) else None

    def spec(self):
        return self.read_json("spec") or {}

    def agents_plan(self):
        st = self.state  # an overridden PLAN-AGENTS means default shares and rungs, even when a recorded attempt left a plan behind
        return self.read_json("agentsPlan") if "PLAN-AGENTS-GATE" in st["step_commits"] and "PLAN-AGENTS" not in st["overrides"] else None

    def plan(self):
        return self.read_json("plan") or {}

    def save(self):
        errors = schemas.validate(self.state, schemas.SCHEMAS["STATE"], "STATE")
        if errors:
            raise RunnerError("STATE invalid: " + "; ".join(errors))
        if self.checkpoint_entry:
            self.history(self.checkpoint_entry)
            self.checkpoint_entry = None
        procs.write_json(self.abs(self.paths["state"]), self.state)

    def history(self, text):
        procs.append_text(self.abs(self.paths["history"]), f"## {procs.now()} {text}\n\n")

    def flag(self, text, who="runner"):
        self.notes.append(text)
        procs.append_text(self.abs(self.paths["history"]), f"FLAG ({who}): {text}\n\n")

    def judgment_files(self):
        return [self.abs(self.paths["defined"]), self.abs(self.paths["undefined"])]

    def judgment_lines(self, key):
        path = self.abs(self.paths[key])
        lines = procs.read_text(path).splitlines() if os.path.exists(path) else []
        return [l for l in lines[1:] if l.strip()]

    def judgment_counts(self):
        return {"defined": len(self.judgment_lines("defined")), "undefined": len(self.judgment_lines("undefined"))}

    def undefined_tail(self, n=5):
        return self.judgment_lines("undefined")[-n:]

    def judgment_report(self):
        counts = self.judgment_counts()
        since = counts["undefined"] - self.state.get("undefined_at_checkpoint", 0)
        lines = [f"Judgment calls: defined {counts['defined']}, undefined {counts['undefined']} ({since} undefined since the last checkpoint)."]
        tail = self.undefined_tail()
        if tail:
            lines.append("Last undefined lines (" + self.abs(self.paths["undefined"]) + "):")
            lines += ["  " + l for l in tail]
        return "\n".join(lines)

    def spend(self):
        return ledger.totals(self.cfg, self.state)

    def spend_line(self):
        t = self.spend()
        return (f"Spend ${t['total_usd']} of quote ${t['quote_usd']} (agent {t['agent_usd']}, driver {t['driver_usd']}, "
                f"owner {t['owner_usd']}, living {t['living_usd']}, time {t['time_usd']}).")

    # ---- git ---------------------------------------------------------------
    def head(self):
        return gitops.head(self.root)

    def commit(self, message, push=True, merge=False):
        """Commit everything; during a merge attempt only the merge commit itself is made (merge=True)."""
        if self.merging() and not merge:
            return
        gitops.git(self.root, "add", "-A")
        proc = gitops.git_proc(self.root, "commit", "-q", "--no-verify", "-m", f"round {self.id}: {message}")
        if not proc.ok and "nothing to commit" not in proc.out + proc.err and "nothing added to commit" not in proc.out + proc.err:
            raise RunnerError(f"git commit failed: {(proc.err or proc.out).strip()[-300:]}")
        if push:
            self.push()

    def push(self):
        if self.state["mode"] != "worktree" or not self.has_origin():
            return
        proc = gitops.git_proc(self.root, "push", "--porcelain", "origin", f"HEAD:refs/heads/{self.state['branch']}")
        if proc.ok:
            return
        text = proc.out + proc.err
        if "rejected" in text or "non-fast-forward" in text or "fetch first" in text or "stale info" in text:
            raise RunnerError("another runner owns this round (push rejected)", 1)
        raise RunnerError(f"push failed: {text.strip()[-400:]}; rerun next, which pushes when the branch is ahead", 1)

    def ahead(self):
        proc = gitops.git_proc(self.root, "rev-list", "--count", f"refs/remotes/origin/{self.state['branch']}..HEAD")
        return not proc.ok or proc.out.strip() not in ("", "0")

    def prompt_commit(self, step, attempt):
        message = f"round {self.id}: {step} attempt {attempt} prompt"
        out = gitops.git(self.root, "rev-list", "-n", "1", "--fixed-strings", f"--grep={message}", "HEAD", check=False)
        return out or None

    def runner_head(self):
        """The runner's newest commit (every one is titled `round NNNN: ...`): anything HEAD has beyond it, an agent committed."""
        return gitops.git(self.root, "rev-list", "-n", "1", "--extended-regexp", f"--grep=^round {self.id}: ", "HEAD", check=False) or None

    # ---- pipeline helpers --------------------------------------------------
    def prose_names(self):
        if self._prose_names is None:
            self._prose_names = prompts.prose_names(self.cfg, self.root, self.state["prose_commit"])
        return self._prose_names

    def prose(self):
        return self.cached("prose", lambda: prompts.prose_reader(self.cfg, self.root, self.state["prose_commit"], self.prose_names()))

    def gate_runs(self, gate):
        producer = pipeline.producer_of(gate)
        return (pipeline.step(gate).kind == "gate" and self.cfg.gate_enabled(gate) and gate not in self.state["overrides"]
                and producer not in self.state["overrides"] and pipeline.prose_file(gate) in self.prose_names())

    def skip_source(self, gate):
        if gate in self.state["overrides"] or pipeline.producer_of(gate) in self.state["overrides"]:
            return "override"
        if not self.cfg.gate_enabled(gate):
            return "disabled"
        return "no-prose"

    def delegated(self):
        a = self.state.get("approval") or {}
        return a.get("mode") == "delegated"

    def delegated_through(self, name):
        """Delegation skips the review checkpoint after `name`: every one when `through` is absent, null or empty, else those at or
        before it, anchored on the producer so that `through` may name the producer or its gate."""
        a = self.state.get("approval") or {}
        if a.get("mode") != "delegated":
            return False
        through = a.get("through")
        anchor = pipeline.producer_of(name) or name
        return not through or (through in pipeline.BY_NAME and pipeline.index(anchor) <= pipeline.index(through))

    def budgets(self):
        work, gates = ledger.shares(self.cfg, self.agents_plan(), self.state["overrides"], self.gate_runs)
        return {name: ledger.step_budget(self.cfg, self.state["budget_usd"], name, work, gates) for name in pipeline.NAMES}

    def rung_for(self, name):
        forced = self.state.get("agent_override") or self.cfg.get("agentOverride")
        if forced:
            return self.cfg.rung(forced)
        plan = self.agents_plan() or {}
        if pipeline.step(name).kind == "gate":
            key = (plan.get("gateAgents") or {}).get(name) or self.cfg["gateAgent"]
        else:
            key = (plan.get("agents") or {}).get(name) or self.cfg["maxAgent"]
        return self.cfg.rung(key)

    def sub_agents_for(self, name):
        plan = self.agents_plan() or {}
        return int((plan.get("subAgents") or {}).get(name, 0))

    def owned_artifacts(self, step):
        """The other steps' artifacts, runner-owned for this producer: an edit is reverted by M1, never read as the owner's out-of-band edit."""
        owner = {s.artifact: s.name for s in pipeline.PIPELINE if s.artifact}
        owner["specProse"] = owner["spec"]
        return [self.paths[key] for key, name in owner.items() if name != step]

    def findings_for(self, producer, statuses=OPEN):
        return [dict(e, id=k) for k, e in self.state["findings_ledger"].items() if e.get("step") == producer and e.get("status") in statuses]

    def next_finding_id(self):
        ids = [int(m.group(1)) for k in self.state["findings_ledger"] for m in [re.fullmatch(r"F(\d+)", k)] if m]
        return max(ids + [0]) + 1

    def add_finding(self, producer, f, source, attempt=None, status="open"):
        key = f["id"]
        k = 1
        while key in self.state["findings_ledger"]:
            k += 1
            key = f"{f['id']}#{k}"
        self.state["findings_ledger"][key] = {"step": producer, "attempt": attempt, "quote": f.get("quote", ""), "reason": f.get("reason", ""),
                                              "suggestion": f.get("suggestion", ""), "blocking": bool(f.get("blocking", True)),
                                              "source": source, "status": status, "upholds": 0}
        return key

    def write_findings(self, name, obj):
        procs.write_json(self.abs(name), obj)
        return name

    # ---- rendering ---------------------------------------------------------
    def index_rows(self):
        path = os.path.join(os.path.dirname(self.folder), "index.jsonl")
        rows = []
        if os.path.exists(path):
            for line in procs.read_text(path).splitlines():
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        return rows

    def landed_postmortems(self):
        out = []
        for row in self.index_rows():
            if row.get("outcome") != "landed" or row.get("id") == self.rid:
                continue
            rel = self.cfg.round_paths(int(row["id"]))["postmortem"]
            if os.path.exists(self.abs(rel)):
                out.append((int(row["id"]), rel))
        return out[-int(self.cfg["postmortemFeedRounds"]):]

    def carry_text(self, rel):
        path = self.abs(rel)
        return procs.read_text(path) if os.path.exists(path) else "none"

    def round_context(self):
        st, t = self.state, self.spend()
        pms = self.landed_postmortems()
        postmortems = "\n\n".join(f"## round {self.cfg.round_id(i)}\n{procs.read_text(self.abs(rel))}" for i, rel in pms) or "none"
        history = [f"round {r.get('id')}: quoted {r.get('quote_usd')} actual {(r.get('spend') or {}).get('total_usd')} ({r.get('outcome')})"
                   for r in self.index_rows()][-5:]
        slice_path = self.abs(self.paths["ownerLog"])
        carry = list(self.cfg["carryForwardFiles"])
        return prompts.empty_round_context(
            id=self.id, number=self.rid, folder=self.paths["folder"], worktree=self.root, harness_root=self.harness,
            branch=st["branch"], base_commit=st["base_commit"], prose_commit=st["prose_commit"], plan=prompts.plan_text(self.plan()),
            budget=st["budget_usd"], spend=t["total_usd"], remaining=round(st["budget_usd"] - t["total_usd"], 2), status=st["status"],
            step=st["step"], history="\n".join(history) or "none", postmortems=postmortems,
            postmortem_paths=[rel for _, rel in pms] or "none", judgment_files=self.judgment_files(),
            judgment_calls={k: "\n".join(self.judgment_lines(k)) or "none" for k in ("defined", "undefined")},
            owner_log=procs.read_text(slice_path) if os.path.exists(slice_path) else "none",
            todos=self.carry_text(carry[0]) if carry else "none", clarifications=self.carry_text(carry[1]) if len(carry) > 1 else "none",
            steps=prompts.step_table(self.cfg, st["overrides"]), runner=os.path.join(self.harness, "src", "run.py"))

    def step_context(self, name, attempt):
        st, s = self.state, pipeline.step(name)
        producer = pipeline.producer_of(name) if s.kind == "gate" else name
        gate = name if s.kind == "gate" else pipeline.gate_of(name)
        budgets = self.budgets()
        rung = self.rung_for(name)
        budget = budgets.get(name, 0.0)
        producer_budget = budgets.get(producer, 0.0)
        previous = "none"
        producer_attempt = st["attempts"].get(producer, 0) if s.kind == "gate" else attempt - 1
        rel = f"{self.paths['results']}/{producer}-{producer_attempt}.json"
        if os.path.exists(self.abs(rel)):
            previous = procs.read_text(self.abs(rel)).strip()
        findings = self.findings_for(producer, OPEN if s.kind != "gate" else ("open", "disputed", "settled", "fixed", "deferred", "withdrawn"))
        q = st.get("pending_question") or {}
        question = f"{q.get('question')} (assumption: {q.get('assumption') or 'none stated'})" if q else "none"
        merge = bool(st.get("merge_pending")) and name == "SPEC-TO-IMPLEMENTATION"
        conflicts = (st.get("merge_pending") or {}).get("conflicted") or [] if merge else []
        spec = self.spec()
        return prompts.step_context(
            self.cfg, name, attempt, self.paths, self.root, self.harness, spec=spec, budget=budget,
            budget_cap=ledger.budget_cap(self.cfg, budget), retry_cost=ledger.retry_cost(self.cfg, producer_budget, self.rung_for(producer)[1]),
            rung=rung, gate_runs=bool(gate) and self.gate_runs(gate), overrides=st["overrides"], delegated=self.delegated(),
            findings=findings, carried=st["carried"], previous=previous, question=question, conflicts=conflicts,
            next_finding_id=self.next_finding_id(), frozen=bool(st.get("tests_frozen_at")), sibling_paths=st.get("sibling_paths") or [],
            changed_tests=[self.cfg.harness_rel(p) for p in checks.changed_tests(self.cfg, self.root, st["base_commit"], spec.get("testPaths") or [])]
            if producer == "TESTS-TO-SUITE" else [],
            sub_agents=self.sub_agents_for(name), merge=merge, producer_attempt=producer_attempt)

    def render_step(self, name, attempt, write=True):
        st = self.state
        s = pipeline.step(name)
        step_ctx = self.step_context(name, attempt)
        gate = name if s.kind == "gate" else pipeline.gate_of(name)
        text, unresolved, warnings = prompts.render_prompt(
            self.cfg, self.root, name, self.round_context(), step_ctx,
            project_ctx=prompts.project_context(self.cfg, remaining=self.project_remaining()),
            prose_commit=st["prose_commit"], gate_runs=bool(gate) and self.gate_runs(gate), prose=self.prose())
        if write:
            procs.write_text(self.abs(f"{self.paths['prompts']}/{name}-{attempt}.txt"), text)
            producer = pipeline.producer_of(name)
            if s.kind == "gate" and pipeline.step(producer).kind == "code":
                declared = [self.repo_rel(p) for p in self.step_context(producer, attempt)["write_paths"] if p != self.paths["folder"]]
                diff = gitops.git(self.root, "diff", st["step_starts"].get(producer, st["base_commit"]), "HEAD", "--", *declared, check=False) if declared else ""
                procs.write_text(self.abs(f"{self.paths['prompts']}/{name}-{attempt}.diff"), diff + ("\n" if diff and not diff.endswith("\n") else ""))
            if unresolved:
                self.flag("unresolved tokens in " + name + ": " + ", ".join(sorted(set(unresolved))))
            for w in warnings:
                self.flag(f"{name}: {w}")
        return text, unresolved, warnings

    def project_remaining(self):
        return round(float(self.cfg["budget"]) - self.cached("project_spend", self.project_spend)["total_usd"], 2)

    def project_spend(self):
        total = {"agent_usd": 0.0, "driver_usd": 0.0, "owner_usd": 0.0, "living_usd": 0.0, "time_usd": 0.0, "total_usd": 0.0, "rounds": []}
        seen = set()
        for row in self.index_rows():
            seen.add(int(row.get("id", -1)))
            for k in total:
                if k != "rounds":
                    total[k] += float((row.get("spend") or {}).get(k, 0) or 0)
            total["rounds"].append({"id": row.get("id"), "outcome": row.get("outcome"), "total_usd": (row.get("spend") or {}).get("total_usd")})
        for rid in local_round_ids(self.cfg):
            if rid in seen:
                continue
            path = self.abs(self.cfg.round_paths(rid)["state"])
            if os.path.exists(path):
                st = procs.read_json(path)
                t = ledger.totals(self.cfg, st)
                for k in t:
                    if k in total:
                        total[k] += t[k]
                total["rounds"].append({"id": rid, "outcome": st.get("status"), "total_usd": t["total_usd"]})
                seen.add(rid)
        for rid, st in landing.sibling_states(self):
            if rid not in seen:
                t = ledger.totals(self.cfg, st)
                for k in t:
                    if k in total:
                        total[k] += t[k]
                total["rounds"].append({"id": rid, "outcome": "live sibling", "total_usd": t["total_usd"]})
        for k in list(total):
            if k != "rounds":
                total[k] = round(total[k], 4)
        return total

    # ---- checkpoints -------------------------------------------------------
    def raise_checkpoint(self, kind, step, question=None, artifact=None):
        st = self.state
        st["status"] = "checkpoint"
        st["checkpoint"] = {"kind": kind, "step": step, "at": procs.now(), "question": question, "artifact": artifact, "message": ""}
        ledger.append(st, step, st["attempts"].get(step, 0), ledger.owner_checkpoint_cost(self.cfg), "owner", f"checkpoint {kind}")
        st["checkpoint"]["message"] = self.checkpoint_message()
        st["undefined_at_checkpoint"] = self.judgment_counts()["undefined"]
        self.checkpoint_entry = f"CHECKPOINT {kind} at {step}\n\n{st['checkpoint']['message']}"

    def resume_commands(self, kind):
        runner = f"py -3.13 {procs.quoted(os.path.join(self.harness, 'src', 'run.py'))} --root {procs.quoted(self.root)}"
        return [f"{runner} {HINTS[c]}" for c in RESUME.get(kind, ["approve", "abandon"])]

    def checkpoint_message(self):
        cp = self.state["checkpoint"]
        lines = [f"CHECKPOINT {cp['kind']} at {cp['step']} (round {self.id}): the owner's word is needed."]
        if cp.get("question"):
            lines.append("Question: " + cp["question"])
        if cp.get("artifact"):
            lines.append("Review: " + cp["artifact"])
        lines.append(self.spend_line())
        lines.append(self.judgment_report())
        lines.append("Resume with one of:")
        lines += ["  " + c for c in self.resume_commands(cp["kind"])]
        return "\n".join(lines)

    def checkpoint_payload(self):
        cp = self.state["checkpoint"]
        return {"kind": "checkpoint", "round": self.id, "checkpoint": {k: cp.get(k) for k in ("kind", "step", "at", "question", "artifact")},
                "message": cp["message"], "resume": self.resume_commands(cp["kind"]), "spend": self.spend(),
                "judgment_calls": self.judgment_counts(), "undefined_tail": self.undefined_tail(),
                "undefined_file": self.abs(self.paths["undefined"]), "warnings": self.notes}

    def done_payload(self, synced):
        st = self.state
        return {"kind": "done", "round": self.id, "status": st["status"], "main_synced": bool(synced), "landed_at": st.get("landed_at"),
                "spend": self.spend(), "judgment_calls": self.judgment_counts(), "undefined_tail": self.undefined_tail(),
                "undefined_file": self.abs(self.paths["undefined"]),
                "hint": "run git pull --ff-only in the main checkout" if st["mode"] == "worktree" else "the round ran in this checkout"}

    def action_payload(self, name, attempt):
        st, s = self.state, pipeline.step(name)
        ctx = self.step_context(name, attempt)
        rung_name, rung = self.rung_for(name)
        kind = "gate" if s.kind == "gate" else "producer"
        alias = self.cfg.model_alias(rung.get("model", ""))
        runner = os.path.join(self.harness, "src", "run.py")
        record = (f"py -3.13 {procs.quoted(runner)} --root {procs.quoted(self.root)} record --step {name} --attempt {attempt} "
                  f"--result {procs.quoted(ctx['result_file'])}")
        warnings = list((st.get("attempt_pending") or {}).get("warnings") or [])
        running = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not procs.same_path(running, os.path.join(self.harness, "src")):
            warnings.append(f"runner_skew: this command runs {running}; drive the round with {runner}")
        return {"kind": kind, "round": self.id, "step": name, "attempt": attempt, "prompt_file": ctx["prompt_file"],
                "result_file": ctx["result_file"], "artifact": ctx["artifact"], "diff_file": ctx["diff_file"],
                "agent": rung_name, "agent_type": f"shackles-{kind}-{rung_name}", "fallback_agent_type": agentdefs.FALLBACK,
                "model": rung.get("model"), "model_alias": alias, "effort": rung.get("effort"),
                "rungs": {r: self.cfg.model_alias(e.get("model", "")) for r, e in self.cfg.agents.items()},
                "task": contract.WRAPPER.format(prompt_file=ctx["prompt_file"]),
                "budget_usd": ctx["budget"], "budget_cap_usd": ctx["budget_cap"],
                "max_turns": ctx["max_turns"], "wall_clock_hours": ctx["wall_clock_hours"], "sub_agents": ctx["sub_agents"],
                "tools": "read-only" if kind == "gate" else "all", "worktree": self.root, "runner": runner,
                "record_command": record, "spend": self.spend(), "judgment_calls": self.judgment_counts(), "warnings": warnings}

    # ---- next ---------------------------------------------------------------
    def next(self, push=True, discard=False):
        st = self.state
        if st["status"] in ("finished", "abandoned"):
            synced = False
            if st["status"] == "finished":
                synced = landing.sync_main(self, push)
                if checks.dirty(self.root):
                    self.commit("sync note", push=False)
                    if push:
                        try:
                            self.push()
                        except RunnerError as exc:
                            self.notes.append(str(exc))
            return self.done_payload(synced), 0
        if st["mode"] == "worktree" and push and self.ahead():
            self.push()
        self.finish_crashed_prompt()
        self.tree_state(discard)
        self.out_of_band()
        self.refresh_owner_slice()
        if st["status"] == "active" and ledger.hard_stop(self.cfg, st) and not st["hard_stop_raised"]:
            st["hard_stop_raised"] = True
            self.raise_checkpoint("hard-stop", st["step"], question=f"spend exceeds {self.cfg['hardStopBudgetMultiple']} x the quote")
        if st["status"] == "checkpoint":
            self.save()
            self.commit("checkpoint", push)
            return self.checkpoint_payload(), 10
        name = self.mechanical_loop(push)
        if st["status"] == "checkpoint":
            self.save()
            self.commit("checkpoint", push)
            return self.checkpoint_payload(), 10
        if st["status"] != "active":
            self.history("FINISHED")
            self.save()
            self.commit("finish", push)
            return self.next(push)
        attempt = self.prepare_attempt(name, push)
        return self.action_payload(name, attempt), 0

    def finish_crashed_prompt(self):
        pending = self.state.get("attempt_pending")
        if pending and self.prompt_commit(pending["step"], pending["attempt"]) is None and not self.merging():
            self.commit(f"{pending['step']} attempt {pending['attempt']} prompt", push=False)

    def reset_downstream(self, name):
        st = self.state
        own = [name] if pipeline.step(name).kind in ("plan", "producer", "code") else []
        for step in own + pipeline.downstream(name):
            for key in ("failures", "step_starts", "step_commits"):
                st[key].pop(step, None)
            for k, e in st["findings_ledger"].items():
                if e.get("step") == step and e.get("status") in OPEN:
                    e["status"] = "reset"
        if pipeline.index(name) <= pipeline.index("SPEC-TO-TESTS"):
            st["tests_frozen_at"] = None
        st["merge_pending"], st["resume_step"], st["attempt_pending"] = None, None, None

    def out_of_band(self):
        st = self.state
        plan_hash = sha_of(self.abs(self.paths["plan"]))
        if st["inputs_hash"].get("PLAN") and plan_hash != st["inputs_hash"]["PLAN"]:
            self.history("PLAN.json changed out of band: back to CHAT-TO-PLAN-GATE; the owner must approve again")
            self.reset_downstream("CHAT-TO-PLAN")
            st["step"], st["approval"], st["pending_question"] = "CHAT-TO-PLAN-GATE", None, None
            st["inputs_hash"]["PLAN"] = plan_hash
            st["round_retries"] += 1
            st["checkpoint"] = None
            return
        spec_hash = self.spec_hash()
        if st["inputs_hash"].get("SPEC") and spec_hash != st["inputs_hash"]["SPEC"] and pipeline.index(st["step"]) > pipeline.index("PLAN-TO-SPEC-GATE"):
            self.history("SPEC changed out of band: back to SPEC-TO-TESTS")
            self.reset_downstream("PLAN-TO-SPEC-GATE")
            st["step"], st["inputs_hash"]["SPEC"], st["pending_question"] = "SPEC-TO-TESTS", spec_hash, None
            st["round_retries"] += 1

    def spec_hash(self):
        a, b = sha_of(self.abs(self.paths["spec"])), sha_of(self.abs(self.paths["specProse"]))
        return f"{a}:{b}" if a or b else None

    def pending_allowed(self):
        pending = self.state.get("attempt_pending")
        if not pending:
            return []
        s = pipeline.step(pending["step"])
        if s.kind == "gate":
            return [self.repo_rel(self.paths["folder"])]
        return [self.repo_rel(p) for p in self.step_context(pending["step"], pending["attempt"])["write_paths"]]

    def tree_state(self, discard):
        st = self.state
        pending = st.get("attempt_pending")
        merging = self.merging()
        expected = bool(st.get("merge_pending")) and st["step"] == "SPEC-TO-IMPLEMENTATION"
        notes = []
        if merging and not expected:
            gitops.abort_merge(self.root)
            st["infra_errors"][st["step"]] = st["infra_errors"].get(st["step"], 0) + 1
            notes.append("unexpected merge in progress: aborted (infrastructure error)")
        elif merging:
            return
        dirty = checks.dirty(self.root)
        if dirty:
            if pending and not discard:
                allowed = self.pending_allowed()
                if any(any(procs.under(p, a) for a in allowed if a) for _, p in dirty):
                    raise RunnerError(f"uncommitted work for {pending['step']} attempt {pending['attempt']}: record it, or next --discard", 2)
            scope = [self.repo_rel(".")] + [self.repo_rel(p) for p in self.cfg.living_paths()]
            scope = [s for s in dict.fromkeys(scope) if s]
            gitops.git(self.root, "checkout", "-q", "--", *scope, check=False)
            gitops.git(self.root, "clean", "-fdq", "--", *scope, check=False)
            st["infra_errors"][st["step"]] = st["infra_errors"].get(st["step"], 0) + 1
            listed = [p for _, p in dirty]
            shown = ", ".join(listed[:20]) + (f" and {len(listed) - 20} more" if len(listed) > 20 else "")
            notes.append(f"dirty tree reset under {', '.join(scope)}: {shown} (infrastructure error at {st['step']})")
        for note in notes:
            self.history(note)

    def refresh_owner_slice(self):
        if not os.path.exists(self.owner_log):
            return
        slice_path = self.abs(self.paths["ownerLog"])
        existing = set(procs.read_text(slice_path).splitlines()) if os.path.exists(slice_path) else set()
        new = [l for l in ownermod.slice_since(self.owner_log, self.state.get("owner_since"), self.cfg["envelopePrefixes"]) if l not in existing]
        if new:
            procs.append_text(slice_path, "".join(l + "\n" for l in new))

    def mechanical_loop(self, push):
        st = self.state
        while st["status"] == "active":
            name = st["step"]
            if st["round_retries"] > int(self.cfg["maxRoundAttempts"]) and not st["round_limit_raised"]:
                st["round_limit_raised"] = True
                self.raise_checkpoint("round-limit", name, question=f"the round was re-entered {st['round_retries']} times, over maxRoundAttempts {self.cfg['maxRoundAttempts']}")
                return name
            s = pipeline.step(name)
            if s.kind == "approval":
                if st.get("approval") is None:
                    self.raise_checkpoint("approval", name, question="the plan changed; approve it again with the owner's words", artifact=self.paths["plan"])
                    return name
                a = st["approval"]
                st["attempts"][name] = st["attempts"].get(name, 0) + 1
                self.history(f"{name} passed mechanically (PLAN.json valid; approval: {a.get('mode')} {a.get('words')!r} from {a.get('source')})")
                self.complete(name)
            elif s.kind == "plan":
                self.raise_checkpoint("upstream-plan", name, question="the plan must change: edit PLAN.json, then approve", artifact=self.paths["plan"])
                return name
            elif s.kind == "gate":
                if self.gate_runs(name):
                    return name
                self.skip_gate(name)
            elif s.kind in ("producer", "code"):
                if name == "SPEC-TO-IMPLEMENTATION" and self.hand_merged():
                    continue
                if name not in st["overrides"]:
                    return name
                self.skip_producer(name)
            elif s.kind == "landing":
                self.landing_step(push)
        return st["step"]

    def hand_merged(self):
        """A merge attempt the owner concluded by hand: the target is already in HEAD, so the round returns to LANDING."""
        st = self.state
        mp = st.get("merge_pending")
        if not mp or self.merging() or not gitops.is_ancestor(self.root, mp["target_sha"], "HEAD"):
            return False
        for e in st["findings_ledger"].values():
            if e.get("step") == "SPEC-TO-IMPLEMENTATION" and e.get("source") == "landing" and e.get("status") in OPEN:
                e["status"] = "fixed"
        st["merge_pending"], st["attempt_pending"] = None, None
        st["step"], st["resume_step"] = st.get("resume_step") or "LANDING", None
        self.history(f"{mp['target']} ({mp['target_sha'][:12]}) is already merged into HEAD, a hand merge: back to {st['step']}")
        return True

    def skip_gate(self, name):
        st = self.state
        source = self.skip_source(name)
        n = st["attempts"].get(name, 0) + 1
        st["attempts"][name] = n
        rel = f"{self.paths['findings']}/{name}-{n}.json"
        self.write_findings(rel, {"verdict": "PASS", "findings": [], "source": source, "step": name, "attempt": n})
        self.history(f"{name} skipped ({source})")
        producer = pipeline.producer_of(name)
        if st.get("pending_question"):  # the question waited at this gate and nobody rules on it: the assumption stands, an undefined call
            self.settle_question(producer, f"{name} skipped ({source})")
            self.history(f"{producer}'s question stands on its assumption: {name} was skipped")
        self.accept_producer(producer)
        self.complete(name)

    def skip_producer(self, name):
        st = self.state
        self.history(f"{name} overridden: skipped with defaults")
        if st.get("pending_question"):
            st["pending_question"] = None
            self.history(f"{name} overridden: its open question is dropped")
        st["step_commits"][name] = self.head()
        gate = pipeline.gate_of(name)
        if gate:
            st["step"] = gate
        else:
            self.accept_producer(name)
            self.complete(name)

    def accept_producer(self, producer):
        st = self.state
        if producer == "PLAN-TO-SPEC":
            st["inputs_hash"]["SPEC"] = self.spec_hash()
            if not st.get("words_charged", {}).get("spec"):
                path = self.abs(self.paths["specProse"])
                text = procs.read_text(path) if os.path.exists(path) else ""
                ledger.append(st, producer, st["attempts"].get(producer, 0), ledger.word_cost(self.cfg, "specCostPerWord", text), "owner", f"{procs.words(text)} spec words")
                st.setdefault("words_charged", {})["spec"] = True
        elif producer == "SPEC-TO-TESTS" and producer not in st["overrides"]:
            st["tests_frozen_at"] = self.head()
            self.history(f"tests frozen at {st['tests_frozen_at'][:12]}")
        elif producer == "TESTS-TO-SUITE" and producer not in st["overrides"]:
            suite = self.read_json("suite") or {}
            self.archive_tests(suite)
            for item in suite.get("raise_with_owner") or []:  # the route for "flag it": HISTORY, and the carried list every later producer and POSTMORTEM see
                self.history(f"flagged for the owner: {item}")
                st["carried"].append({"id": "raise_with_owner", "quote": str(item), "reason": "TESTS-TO-SUITE flagged it for the owner",
                                      "suggestion": "", "source": "flag"})

    def archive_tests(self, suite):
        archive = self.abs(self.paths["testsArchive"])
        os.makedirs(archive, exist_ok=True)
        moved = []
        for rel in suite.get("archive") or []:
            src = self.repo_rel(rel)
            base = os.path.basename(src)
            target = os.path.join(archive, base)
            k = 1
            while os.path.exists(target):
                k += 1
                stem, ext = os.path.splitext(base)
                target = os.path.join(archive, f"{stem}-{k}{ext}")
            target_rel = procs.posix(os.path.relpath(target, self.root))
            if gitops.git_ok(self.root, "mv", "-k", src, target_rel):
                moved.append(f"{src} -> {target_rel}")
        if moved:
            self.history("archived tests:\n" + "\n".join(moved))

    def complete(self, name):
        st = self.state
        st["step_commits"][name] = self.head()
        nxt = st.get("resume_step") or pipeline.next_after(name)
        st["resume_step"] = None
        if nxt is None:
            self.finish()
            return
        st["step"] = nxt
        if name in self.cfg["checkpointsAfter"]:
            if self.delegated_through(name):
                self.history(f"review checkpoint after {name} skipped (delegated)")
            else:
                self.raise_checkpoint("review", name, artifact=self.review_artifact(name))

    def review_artifact(self, name):
        if name == "CLEANUP" or pipeline.step(name).kind == "code":
            living = [self.repo_rel(p) for p in self.cfg.living_paths()]
            return "git diff --stat " + st_base(self) + "..HEAD:\n" + gitops.git(self.root, "diff", "--stat", self.state["base_commit"], "HEAD", "--", *living, check=False)
        producer = pipeline.producer_of(name) if pipeline.step(name).kind == "gate" else name
        s = pipeline.step(producer)
        if s.artifact == "spec":
            return f"{self.abs(self.paths['spec'])} and {self.abs(self.paths['specProse'])}"
        return self.abs(self.paths[s.artifact]) if s.artifact else self.paths["folder"]

    def landing_step(self, push):
        st = self.state
        if st["spec_edits"] and not st.get("spec_edits_approved"):
            diff = "\n".join(checks.e1_spec_edits(self.root, st["base_commit"], specguard.spec_files(self.root)).values())
            self.raise_checkpoint("spec-edit", "LANDING", question="this round changed spec files; approve accepts them into the baseline", artifact=diff)
            return
        st["attempts"]["LANDING"] = st["attempts"].get("LANDING", 0) + 1
        findings = landing.land(self, push)
        if findings:
            self.route_landing_findings(findings)
            return
        self.complete("LANDING")

    def route_landing_findings(self, findings):
        st = self.state
        n = st["attempts"]["LANDING"]
        rel = f"{self.paths['findings']}/LANDING-{n}.mechanical.json"
        self.write_findings(rel, {"verdict": "FAIL", "findings": findings, "source": "landing", "step": "LANDING", "attempt": n})
        for f in findings:
            self.add_finding("SPEC-TO-IMPLEMENTATION", f, "landing", n)
        st["failures"]["SPEC-TO-IMPLEMENTATION"] = st["failures"].get("SPEC-TO-IMPLEMENTATION", 0) + 1
        st["round_retries"] += 1
        st["resume_step"], st["step"] = "LANDING", "SPEC-TO-IMPLEMENTATION"
        st["step_starts"].pop("SPEC-TO-IMPLEMENTATION", None)
        self.history(f"LANDING attempt {n}: {', '.join(f['id'] for f in findings)}; back to SPEC-TO-IMPLEMENTATION")

    def prepare_attempt(self, name, push):
        st = self.state
        attempt = st["attempts"].get(name, 0) + 1
        pending = st.get("attempt_pending")
        if not (pending and pending["step"] == name and pending["attempt"] == attempt):
            st["step_starts"].setdefault(name, self.head())
            text, unresolved, warnings = self.render_step(name, attempt, write=True)
            st["attempt_pending"] = {"step": name, "attempt": attempt, "infra": 0, "warnings": [w for w in warnings if w.startswith("W2")],
                                     "judgment": self.judgment_counts()}
        self.save()
        self.commit(f"{name} attempt {attempt} prompt", push=False)
        if st.get("merge_pending") and name == "SPEC-TO-IMPLEMENTATION" and not self.merging():
            gitops.git(self.root, "merge", "--no-commit", "--no-ff", st["merge_pending"]["target_sha"], check=False)
        return attempt

    # ---- record -------------------------------------------------------------
    def record(self, step, attempt, result_path, cost=None, tokens=None, agent=None, spawns=0, push=True, note=None):
        st = self.state
        if st["status"] != "active":
            raise RunnerError(f"round is {st['status']}, not active", 2)
        if st["step"] != step:
            raise RunnerError(f"the current step is {st['step']}, not {step}", 2)
        pending = st.get("attempt_pending")
        if attempt != st["attempts"].get(step, 0) + 1 or not pending or pending["step"] != step or pending["attempt"] != attempt:
            raise RunnerError(f"no pending attempt {attempt} of {step} (next attempt is {st['attempts'].get(step, 0) + 1}, pending {pending})", 2)
        if agent and agent not in self.cfg.agents:
            raise RunnerError(f"--agent {agent} is not a roster key (one of {', '.join(self.cfg.agents)})", 2)
        s = pipeline.step(step)
        kind = "gate" if s.kind == "gate" else "producer"
        try:
            text = procs.read_text(result_path)
        except OSError as exc:
            raise RunnerError(f"result file unreadable: {exc}", 2)
        obj = schemas.extract_json(text)
        schema = "FINDINGS" if kind == "gate" else "RESULT"
        errors = schemas.validate(obj, schemas.SCHEMAS[schema], schema) if obj is not None else [f"{schema}: no JSON object in the final message"]
        planned = self.rung_for(step)[0]
        off_plan = bool(agent) and agent != planned  # priced at the rung that ran; HISTORY flags that the plan's rung was not honoured
        rung_name, rung = self.cfg.rung(agent) if off_plan else self.rung_for(step)
        usd, source, note_text = ledger.agent_cost(self.cfg, rung, cost, tokens, spawns, self.budgets().get(step, 0.0))
        result_rel = f"{self.paths['results']}/{step}-{attempt}"
        exclude = (self.repo_rel(result_rel + ".json"), self.repo_rel(result_rel + ".meta.json"))
        merge = bool(st.get("merge_pending")) and step == "SPEC-TO-IMPLEMENTATION"
        pc = self.runner_head()
        moved = bool(pc) and self.head() != pc
        if moved and merge:
            gitops.git(self.root, "reset", "-q", "--hard", pc)
            return self.infra(step, attempt, text, ["M0: HEAD moved during the merge attempt; the agent's commit was discarded"],
                              usd, source, note_text, push, self.snapshot(exclude, False))
        if moved:
            gitops.git(self.root, "reset", "-q", "--soft", pc)
            gitops.git(self.root, "reset", "-q")
        snapshot = self.snapshot(exclude, merge)  # taken before this record writes anything, so its own HISTORY lines are never strays
        if moved:
            self.flag(f"M0: HEAD moved during {step} attempt {attempt}; the agent's commit was undone (soft reset)")
        if off_plan:
            self.flag(f"{step} attempt {attempt}: ran on rung {agent}, the action named {planned}")
        if not errors and kind == "gate" and snapshot:
            errors = ["G1: the gate run changed files; discarded"]
        if errors:
            return self.infra(step, attempt, text, errors + ([note] if note else []), usd, source, note_text, push, snapshot)
        if note:
            self.flag(f"headless agent note at {step} attempt {attempt}: {note}")
        ledger.append(st, step, attempt, usd, source, note_text + (f" (rung {rung_name})" if off_plan else ""))
        ledger.append(st, step, attempt, self.cfg["driverUsdPerStep"], "driver")
        st["attempts"][step] = attempt
        before = pending.get("judgment") or st["judgment_calls"]
        st["attempt_pending"] = None
        if kind == "gate":
            obj, notes = schemas.normalize_findings(obj, step, attempt, self.next_finding_id(), self.withdrawn_quotes(), int(self.cfg["findingQuoteMaxChars"]))
            for n in notes:
                self.flag(f"{step} attempt {attempt}: {n}")
            obj.update({"source": "gate", "step": step, "attempt": attempt})
            procs.write_json(self.abs(result_rel + ".json"), obj)
            self.record_gate(step, attempt, obj)
        else:
            procs.write_json(self.abs(result_rel + ".json"), obj)
            self.record_producer(step, attempt, obj, pc, merge, snapshot, before)
        after = self.judgment_counts()
        st["judgment_calls"] = after
        delta = f"judgment calls +{after['defined'] - before['defined']} defined, +{after['undefined'] - before['undefined']} undefined"
        notes = obj.get("notes") or ""
        if len(notes) > NOTE_CAP:
            notes = notes[:NOTE_CAP] + f" [cut at {NOTE_CAP} characters; the whole message is {result_rel}.json]"
        self.history(f"{step} attempt {attempt}: {obj.get('status') or obj.get('verdict')}\n\n{notes}"
                     f"\n\ncost ${round(usd, 4)} ({source}); {delta}\n" + self.judgment_report())
        if st["status"] == "finished":
            self.history("FINISHED")
        self.save()
        self.commit(f"{step} attempt {attempt}", push)
        if st["status"] == "checkpoint":
            return self.checkpoint_payload(), 10
        if st["status"] == "finished":
            return self.done_payload(landing.sync_main(self, push)), 0
        new = after["undefined"] - before["undefined"]  # the lines this attempt appended: the driver relays them, delegated or not
        return {"kind": "recorded", "round": self.id, "step": step, "attempt": attempt, "next_step": st["step"],
                "spend": self.spend(), "judgment_calls": after, "undefined_new": self.undefined_tail(new) if new > 0 else [],
                "undefined_file": self.abs(self.paths["undefined"]), "warnings": self.notes}, 0

    def snapshot(self, exclude, merge):
        """The dirty tree; on a merge attempt only what differs from the automerge tree, so the sibling's changes never count."""
        items = checks.dirty(self.root, exclude)
        if merge and self.merging():
            out = gitops.git(self.root, "diff", "--name-only", "-z", self.state["merge_pending"]["automerge_tree"], check=False)
            changed = {procs.posix(p) for p in out.split("\0") if p}
            items = [(xy, p) for xy, p in items if p in changed or "?" in xy]
        return items

    def infra(self, step, attempt, text, errors, usd, source, note, push, snapshot):
        st = self.state
        pending = st["attempt_pending"]
        pending["infra"] = pending.get("infra", 0) + 1
        st["infra_errors"][step] = st["infra_errors"].get(step, 0) + 1
        if self.merging():
            gitops.abort_merge(self.root)
            errors = errors + ["the merge is aborted and re-established by next"]
        checks.revert(self.root, snapshot)
        raw = self.abs(f"{self.paths['results']}/{step}-{attempt}.raw-{pending['infra']}.txt")
        procs.write_text(raw, text)
        if usd:
            ledger.append(st, step, attempt, usd, source, "invalid result: " + note)
        ledger.append(st, step, attempt, self.cfg["driverUsdPerStep"], "driver")
        self.history(f"{step} attempt {attempt}: INVALID RESULT ({'; '.join(errors)}); rerun the same attempt (infra error {pending['infra']} of {self.cfg['infraRetries']})")
        if pending["infra"] >= int(self.cfg["infraRetries"]):
            self.raise_checkpoint("infra", step, question=f"{pending['infra']} invalid results at {step} attempt {attempt}: {'; '.join(errors)}")
        self.save()
        self.commit(f"{step} attempt {attempt} invalid result", push)
        if st["status"] == "checkpoint":
            return self.checkpoint_payload(), 10
        return {"kind": "invalid", "round": self.id, "step": step, "attempt": attempt, "errors": errors,
                "hint": "rerun the same attempt: run next, which prints the action again", "spend": self.spend(), "warnings": self.notes}, 2

    def withdrawn_quotes(self):
        return {" ".join(e.get("quote", "").split()) for e in self.state["findings_ledger"].values() if e.get("status") == "withdrawn"}

    def apply_resolutions(self, step, attempt, obj):
        st = self.state
        resolutions = obj.get("resolutions") or {}
        if obj.get("status") in ("DONE", "NEEDS-OWNER"):
            omitted = [k for k, e in st["findings_ledger"].items()
                       if e.get("step") == step and e.get("source") in ("gate", "owner") and e.get("status") in OPEN and k not in resolutions]
            for k in omitted:
                st["findings_ledger"][k].update(status="fixed", resolution={"status": "fixed", "reason": "omitted from resolutions"})
            if omitted:
                self.flag(f"{step} attempt {attempt}: findings omitted from resolutions count as fixed: {', '.join(omitted)}")
        for key, res in resolutions.items():
            e = st["findings_ledger"].get(key)
            if not e or e.get("step") != step:
                self.flag(f"resolution for unknown finding {key} ignored")
                continue
            status = res.get("status")
            if status == "disputed" and (e["status"] == "settled" or e.get("source") != "gate"):
                self.flag(f"dispute of {key} ignored: " + ("settled (upheld twice)" if e["status"] == "settled" else "not a gate finding"))
                continue
            e["resolution"] = {"status": status, "reason": res.get("reason", "")}
            if status == "disputed":
                e["status"] = "disputed"
            elif status == "deferred":
                e["status"] = "deferred"
                st["carried"].append({"id": key, "quote": e["quote"], "reason": e["reason"], "suggestion": e.get("suggestion", ""),
                                      "source": "deferred", "note": res.get("reason", "")})
            else:
                e["status"] = "fixed"

    def claimed_calls(self, step, attempt, obj, before):
        """The message's judgment-call counts (ints, or list lengths) against what the files gained since the prompt; a mismatch is one FLAG."""
        jc = obj.get("judgment_calls")
        if not isinstance(jc, dict):
            return
        after = self.judgment_counts()
        claimed = {k: len(v) if isinstance(v, list) else int(v or 0) for k, v in ((k, jc.get(k, 0)) for k in ("defined", "undefined"))}
        gained = {k: after[k] - before[k] for k in ("defined", "undefined")}
        if claimed != gained:
            self.flag(f"{step} attempt {attempt}: message claims {claimed['defined']}/{claimed['undefined']} judgment calls, "
                      f"the files gained {gained['defined']}/{gained['undefined']}")

    def record_producer(self, step, attempt, obj, prompt_commit, merge, snapshot, before):
        st = self.state
        status = obj["status"]
        self.apply_resolutions(step, attempt, obj)
        findings, reverted = [], []
        f4, r4 = checks.m4_judgment(self.root, prompt_commit or st["base_commit"], [self.repo_rel(self.paths["defined"]), self.repo_rel(self.paths["undefined"])])
        findings += f4
        self.claimed_calls(step, attempt, obj, before)
        self.e1(checks.e1_spec_edits(self.root, st["base_commit"], specguard.spec_files(self.root)))
        merge_tree = (st.get("merge_pending") or {}).get("automerge_tree") if merge else None
        conflicted = [self.repo_rel(p) for p in (st.get("merge_pending") or {}).get("conflicted") or []] if merge else []
        if status in ("UPSTREAM", "BLOCKED"):
            if merge:
                gitops.abort_merge(self.root)
                st["merge_pending"] = None
            reverted = []
            if st.get("tests_frozen_at") and step != "SPEC-TO-TESTS":
                reverted += checks.m2_frozen(self.cfg, self.root, self.spec().get("testPaths") or [], snapshot)[1]
            allowed = self.step_context(step, attempt)["write_paths"]
            reverted += checks.m1_strays(self.cfg, self.root, self.paths, allowed, [(xy, p) for xy, p in snapshot if p not in reverted],
                                         exempt=specguard.spec_files(self.root), owned_extra=self.owned_artifacts(step))[1]
            if reverted:
                self.history(f"{step} attempt {attempt}: {status}; out-of-scope changes reverted: {', '.join(reverted)}")
            gitops.git(self.root, "add", "-A")
            if status == "UPSTREAM":
                return self.upstream(step, attempt, obj)
            return self.blocked(step, attempt, obj)
        if merge:
            findings += checks.l3_unmerged(self.root, conflicted)
        spec = self.spec()
        remaining = list(snapshot)
        if st.get("tests_frozen_at") and step != "SPEC-TO-TESTS":
            f2, r2 = checks.m2_frozen(self.cfg, self.root, spec.get("testPaths") or [], snapshot, merge_tree, conflicted)
            findings += f2
            remaining = [(xy, p) for xy, p in snapshot if p not in r2]
        allowed = self.step_context(step, attempt)["write_paths"]
        f1, r1 = checks.m1_strays(self.cfg, self.root, self.paths, allowed, remaining, merge_tree=merge_tree, exempt=specguard.spec_files(self.root),
                                  owned_extra=self.owned_artifacts(step))
        findings += f1
        unresolved = bool([f for f in findings if f["id"] == "L3"])
        if unresolved:
            gitops.abort_merge(self.root)
            self.history(f"{step} attempt {attempt}: L3, the merge is aborted; the next attempt re-establishes it")
        else:
            self.commit_work(step, attempt, merge)
            if merge:
                st["merge_pending"] = None
                st["step_starts"][step] = merge_tree  # the gate's diff starts at the automerge tree: the sibling's changes never appear in it
                self.history(f"{step} attempt {attempt}: merge commit made; later attempts are normal")
        artifact_errors = self.s1(step, spec)
        if artifact_errors:
            findings.append(checks.finding("S1", "\n".join(artifact_errors), "the artifact is missing or invalid", "write the artifact as the contract says"))
        if not artifact_errors and not unresolved and "M3" in pipeline.checks_for(step):
            findings += checks.m3_verify(self.cfg, self.harness, spec)
        if not [f for f in findings if f["blocking"]] and "M5" in pipeline.checks_for(step):
            findings += checks.m5_suite(self.cfg, self.harness)
        blocking = [f for f in findings if f.get("blocking")]
        nonblocking = [f for f in findings if not f.get("blocking")]
        for f in nonblocking:
            st["carried"].append(dict(f, source="mechanical"))
        if blocking:
            rel = f"{self.paths['findings']}/{step}-{attempt}.mechanical.json"
            self.write_findings(rel, {"verdict": "FAIL", "findings": findings, "source": "mechanical", "step": step, "attempt": attempt})
            for f in blocking:
                self.add_finding(step, f, "mechanical", attempt)
            st["failures"][step] = st["failures"].get(step, 0) + 1
            self.history(f"{step} attempt {attempt}: mechanical findings {', '.join(f['id'] for f in blocking)}")
            self.limit_check(step)
            return
        for k, e in st["findings_ledger"].items():
            if e.get("step") == step and e.get("source") != "gate" and e.get("status") in OPEN:
                e["status"] = "fixed"
        if merge:
            st["merge_pending"] = None
        st["step_commits"][step] = self.head()
        if step == "PLAN-TO-SPEC":
            self.w1(spec)
        gate = pipeline.gate_of(step)
        if status == "NEEDS-OWNER":
            st["pending_question"] = {"question": obj.get("question") or "(no question given)", "assumption": obj.get("assumption") or ""}
            if gate and self.gate_runs(gate):
                st["step"] = gate
                return
            if self.delegated():
                self.settle_question(f"{step} attempt {attempt}", "gate disabled, delegated")
                self.history(f"{step} attempt {attempt}: NEEDS-OWNER proceeds on the stated assumption (delegated)")
            else:
                self.raise_checkpoint("question", step, question=f"{st['pending_question']['question']} (assumption: {st['pending_question']['assumption'] or 'none'})")
                return
        if gate:
            st["step"] = gate
        else:
            self.accept_producer(step)
            self.complete(step)

    def settle_question(self, who, why):
        """The producer's open question stands on its assumption: one undefined line names who assumed what and why nobody ruled."""
        q = self.state["pending_question"]
        procs.append_text(self.abs(self.paths["undefined"]), f"- {who} assumed: {q.get('assumption') or '(none stated)'} (runner: {why}; question: {q['question']})\n")
        self.state["pending_question"] = None

    def e1(self, edits):
        """E1: spec-file edits are kept, `spec_edits` names the files that differ from base_commit, every new or changed diff goes
        to HISTORY, and the branch's baseline is accepted provisionally, so the guard in the permanent suite (M5, L2) is green
        until the owner re-accepts at the spec-edit checkpoint; the baseline files are not in the snapshot, so M1 never sees them."""
        st = self.state
        hashes = {path: procs.sha256_text(diff) for path, diff in edits.items()}
        known = st.get("spec_edit_hashes") or {}
        if hashes == known:
            return
        for path, diff in edits.items():
            if hashes[path] != known.get(path):
                self.history(f"SPEC EDIT {path}\n\n```diff\n{diff}\n```")
        for path in known:
            if path not in hashes:
                self.history(f"SPEC EDIT {path} undone: the file is back at base_commit")
        st["spec_edit_hashes"], st["spec_edits"], st["spec_edits_approved"] = hashes, sorted(hashes), False
        specguard.accept(self.root, f"round {self.id}: provisional, pending the owner's spec-edit checkpoint; edited: {', '.join(sorted(hashes)) or 'none'}")

    def commit_work(self, step, attempt, merge):
        self.commit(f"{step} attempt {attempt} work", push=False, merge=merge)

    def s1(self, step, spec):
        s = pipeline.step(step)
        if not s.artifact:
            return []
        path = self.abs(self.paths[s.artifact])
        if not os.path.exists(path):
            return [f"{self.paths[s.artifact]} missing"]
        if s.artifact == "postmortem":
            return [] if procs.read_text(path).strip() else [f"{self.paths['postmortem']} is empty"]
        try:
            obj = procs.read_json(path)
        except ValueError as exc:
            return [f"{self.paths[s.artifact]}: not JSON ({exc})"]
        if s.artifact == "agentsPlan":
            return checks.s1_agents_plan(self.cfg, obj, self.gate_runs, self.state["overrides"])
        if s.artifact == "spec":
            return checks.s1_spec(self.cfg, obj, self.harness, self.paths, self.state["budget_usd"], specguard.spec_files(self.root))
        if s.artifact == "suite":
            return checks.s2_suite(self.cfg, obj, self.root, self.harness, self.state["base_commit"], spec.get("testPaths") or [])
        return []

    def w1(self, spec):
        overlaps = landing.sibling_overlaps(self, spec)
        if overlaps:
            f = checks.finding("W1", "\n".join(overlaps), "a live sibling round declares an overlapping path", "coordinate with the sibling or narrow the paths", blocking=False)
            self.state["carried"].append(dict(f, source="mechanical"))
            self.state["sibling_paths"] = overlaps
            self.history("W1: overlapping paths with live siblings:\n" + "\n".join(overlaps))

    def upstream(self, step, attempt, obj):
        st = self.state
        target = obj.get("target")
        if target not in pipeline.earlier_producers(step):
            f = checks.finding("S1", str(target), "UPSTREAM must name an earlier producer step", "name one of " + ", ".join(pipeline.earlier_producers(step)))
            rel = f"{self.paths['findings']}/{step}-{attempt}.mechanical.json"
            self.write_findings(rel, {"verdict": "FAIL", "findings": [f], "source": "mechanical", "step": step, "attempt": attempt})
            self.add_finding(step, f, "mechanical", attempt)
            st["failures"][step] = st["failures"].get(step, 0) + 1
            self.limit_check(step)
            return
        f = checks.finding("U1", obj.get("notes") or "", f"{step} returned UPSTREAM: the artifact of {target} is wrong", "fix the contradiction quoted", source="upstream")
        self.reset_downstream(target)
        self.add_finding(target, f, "upstream", attempt)
        st["round_retries"] += 1
        st["step"] = target
        st["pending_question"] = None
        self.history(f"UPSTREAM from {step} attempt {attempt} to {target}")
        if target == "CHAT-TO-PLAN":
            self.raise_checkpoint("upstream-plan", target, question=obj.get("notes") or "the plan is wrong", artifact=self.paths["plan"])

    def blocked(self, step, attempt, obj):
        st = self.state
        f = checks.finding("B1", obj.get("narrow") or obj.get("notes") or "", f"{step} returned BLOCKED", "narrow the step as suggested", source="blocked")
        self.add_finding(step, f, "blocked", attempt)
        st["failures"][step] = st["failures"].get(step, 0) + 1
        self.raise_checkpoint("blocked", step, question=obj.get("narrow") or obj.get("notes") or "the step is blocked")

    def limit_check(self, producer):
        st = self.state
        if st["failures"].get(producer, 0) >= int(self.cfg["maxFailuresBeforeStop"]):
            self.raise_checkpoint("failure-limit", producer, question=f"{producer} failed {st['failures'][producer]} times (maxFailuresBeforeStop {self.cfg['maxFailuresBeforeStop']}); approve resets the count")

    def record_gate(self, step, attempt, obj):
        st = self.state
        producer = pipeline.producer_of(step)
        for key, ruling in (obj.get("rulings") or {}).items():
            e = st["findings_ledger"].get(key)
            if not e or e.get("step") != producer or e["status"] == "settled" or e["status"] == "withdrawn":
                self.flag(f"ruling on {key} ignored (unknown, settled or withdrawn)")
                continue
            e["ruling"] = {"status": ruling.get("status"), "quote": ruling.get("quote", "")}
            if ruling.get("status") == "upheld":
                e["upholds"] = e.get("upholds", 0) + 1
                e["status"] = "settled" if e["upholds"] >= 2 else "open"
            else:
                e["status"] = "withdrawn"
        for f in obj.get("findings") or []:
            self.add_finding(producer, f, "gate", attempt)
        jc = obj.get("judgment_calls") or {}
        suffix = f" (via runner, {step}-{attempt})"
        for key in ("defined", "undefined"):
            lines = [str(l).strip() for l in (jc.get(key) or []) if str(l).strip()]
            if lines:  # a gate that copied the file's format already ends its line with the suffix
                procs.append_text(self.abs(self.paths[key]), "".join(f"- {l}" + ("" if re.search(r"\(via runner, [^()]*\)$", l) else suffix) + "\n" for l in lines))
        rel = f"{self.paths['findings']}/{step}-{attempt}.json"
        self.write_findings(rel, obj)
        needs = obj.get("needs_owner") or {}
        if needs.get("status") == "upheld":
            q = st.get("pending_question") or {"question": needs.get("reason") or "the producer's question", "assumption": ""}
            st["step"] = producer
            self.raise_checkpoint("question", producer, question=f"{q['question']} (assumption: {q.get('assumption') or 'none'}; gate: {needs.get('reason', '')})")
            return
        if needs.get("status") == "withdrawn" and st.get("pending_question"):
            q = st["pending_question"]
            st["carried"].append({"id": "Q1", "quote": q["question"], "reason": needs.get("reason", ""), "suggestion": "assume: " + needs.get("reason", ""), "source": "gate"})
            procs.append_text(self.abs(self.paths["defined"]), f"- {step}-{attempt} withdrew the producer's question; assume: {needs.get('reason', '')} (via runner)\n")
            st["pending_question"] = None
        if st.get("pending_question") and needs.get("status") not in ("upheld", "withdrawn"):
            self.settle_question(producer, f"{step} attempt {attempt} gave no ruling")
            self.flag(f"{step} attempt {attempt}: no ruling on the producer's question; the assumption stands")
        if obj["verdict"] == "PASS":
            for f in obj.get("findings") or []:
                st["carried"].append({"id": f["id"], "quote": f["quote"], "reason": f["reason"], "suggestion": f.get("suggestion", ""), "source": "gate"})
            for f in obj.get("findings") or []:
                e = st["findings_ledger"].get(f["id"])
                if e:
                    e["status"] = "carried"
            self.accept_producer(producer)
            self.complete(step)
            return
        st["failures"][producer] = st["failures"].get(producer, 0) + 1
        st["step"] = producer
        self.limit_check(producer)

    # ---- owner commands ---------------------------------------------------
    def owner_command(self, command, quote, unverified=False, text=None, through=None, steps=None, reason=None, push=True):
        st = self.state
        if command not in ("override", "abandon") and st["status"] != "checkpoint":
            raise RunnerError(f"{command} needs a checkpoint; the round is {st['status']}", 2)
        if through and through not in pipeline.BY_NAME:
            raise RunnerError(f"--through names unknown step {through}", 2)
        cp = st.get("checkpoint") or {}
        verified = ownermod.verify_quote(self.owner_log, quote, cp.get("at") if st["status"] == "checkpoint" else None)
        if verified is False and not unverified:
            raise RunnerError(f"quote not found in the owner log after {cp.get('at')}: {quote!r} (pass --unverified to record it anyway)", 2)
        tag = "[via driver]" if verified else "[via driver, unverified]"
        ownermod.append_line(self.abs(self.paths["ownerLog"]), quote, tag=tag)
        if not verified:
            self.flag(f"{command}: quote recorded unverified ({'no owner log' if verified is None else 'not in the log'})", who="driver")
        self.history(f"RESUME {command} quote: {quote}")
        kind = cp.get("kind")
        if command == "override":
            self.override(steps or [])
            if st["status"] == "checkpoint" and cp.get("step") in st["overrides"]:
                self.resume()  # the checkpoint's own step is skipped; any other override is followed by approve
            elif st["status"] == "checkpoint":
                self.notes.append(f"overrides recorded; the checkpoint at {cp.get('step')} stands: approve to resume")
        elif command == "abandon":
            self.abandon(reason or quote, push)
            return self.done_payload(False), 0
        elif command == "answer":
            self.answer(kind, cp.get("step"), text or quote)
        elif command in ("approve", "delegate"):
            if command == "delegate":
                st["approval"] = dict(st.get("approval") or {}, mode="delegated", through=through, words=quote, at=procs.now(), source="driver")
            self.approve(kind, cp.get("step"), quote)
        self.save()
        self.commit(f"{command} at {kind or 'active'}", push)
        if st["status"] == "checkpoint":
            return self.checkpoint_payload(), 10
        return {"kind": "resumed", "round": self.id, "command": command, "status": st["status"], "step": st["step"], "spend": self.spend()}, 0

    def resume(self):
        self.state["status"], self.state["checkpoint"] = "active", None

    def approve(self, kind, step, quote):
        st = self.state
        if kind == "review":
            st["inputs_hash"]["PLAN"] = sha_of(self.abs(self.paths["plan"]))
            if st["inputs_hash"].get("SPEC"):
                st["inputs_hash"]["SPEC"] = self.spec_hash()
        elif kind == "failure-limit":
            st["failures"][step] = 0
        elif kind == "spec-edit":
            specguard.accept(self.root, f"round {self.id}: approved by the owner: {quote}")
            st["spec_edits_approved"] = True
        elif kind == "upstream-plan":
            plan_hash = sha_of(self.abs(self.paths["plan"]))
            if plan_hash == st["inputs_hash"].get("PLAN"):
                raise RunnerError("upstream-plan: edit PLAN.json first, then approve", 2)
            errors = schemas.validate(self.plan(), schemas.SCHEMAS["PLAN"], "PLAN")
            if errors:
                raise RunnerError("PLAN.json invalid: " + "; ".join(errors), 2)
            st["inputs_hash"]["PLAN"] = plan_hash
            st["attempts"]["CHAT-TO-PLAN"] = st["attempts"].get("CHAT-TO-PLAN", 0) + 1
            st["step"] = "CHAT-TO-PLAN-GATE"
            st["approval"] = dict(st.get("approval") or {"mode": "approved"}, words=quote, at=procs.now(), source="driver")
        elif kind == "approval":
            st["approval"] = dict(st.get("approval") or {"mode": "approved"}, words=quote, at=procs.now(), source="driver")
            if st["approval"].get("mode") not in ("approved", "delegated"):
                st["approval"]["mode"] = "approved"
        elif kind in ("question", "blocked"):
            self.answer(kind, step, "proceed on your stated assumption")
            return
        elif kind == "infra":
            if st.get("attempt_pending"):
                st["attempt_pending"]["infra"] = 0
        self.resume()

    def answer(self, kind, step, text):
        st = self.state
        producer = step
        if kind == "review":
            producer = pipeline.producer_of(step) if pipeline.step(step).kind == "gate" else step
        if pipeline.step(producer).kind not in ("producer", "code"):
            raise RunnerError(f"answer does not apply at {kind} ({step})", 2)
        f = checks.finding("O1", text, "the owner's answer", text, source="owner")
        self.add_finding(producer, f, "owner", st["attempts"].get(producer, 0) + 1)
        st["pending_question"] = None
        st["step"] = producer
        st["attempt_pending"] = None
        if kind == "review":
            st["step_commits"].pop(producer, None)
            gate = pipeline.gate_of(producer)
            if gate:
                st["step_commits"].pop(gate, None)
        self.history(f"owner answer to {producer}: {text}")
        self.resume()

    def override(self, steps):
        st = self.state
        current = pipeline.index(st["step"])
        for name in steps:
            if not pipeline.is_overridable(name):
                raise RunnerError(f"{name} cannot be overridden", 2)
            gate = pipeline.gate_of(name)
            if (gate or name) in st["step_commits"]:  # a producer is accepted by its gate, not by its clean commit
                raise RunnerError(f"{name} is already accepted", 2)
            if pipeline.index(name) < current:  # the producer ran and its gate has not judged the artifact yet
                raise RunnerError(f"{name} already ran; its gate {gate} is pending: override the gate instead", 2)
            if name not in st["overrides"]:
                st["overrides"].append(name)
        pending = st.get("attempt_pending")
        if pending and pending["step"] in st["overrides"]:  # its unrecorded work is discarded, never swept unchecked into this command's commit
            keep = [self.repo_rel(self.paths[k]) for k in ("state", "history", "ownerLog")]
            dirty = checks.dirty(self.root, exclude=keep)
            checks.revert(self.root, dirty)
            if dirty:
                self.history(f"override: unrecorded work of {pending['step']} attempt {pending['attempt']} discarded: {', '.join(p for _, p in dirty)}")
            st["attempt_pending"] = None
        self.history("override: " + ", ".join(steps))

    def abandon(self, reason, push=True):
        st = self.state
        if st.get("landed_at"):
            raise RunnerError("the round already landed; to skip the postmortem use override --steps POSTMORTEM", 2)
        if self.merging():
            gitops.abort_merge(self.root)
        st["status"], st["abandoned_at"], st["checkpoint"] = "abandoned", procs.now(), None
        st["merge_pending"] = st["resume_step"] = st["attempt_pending"] = None
        self.history(f"ABANDONED: {reason}")
        self.index_line("abandoned")
        self.save()
        self.commit("abandon", push=False)
        gitops.git(self.root, "tag", "-f", f"round/{self.id}-abandoned", check=False)
        if push:
            try:
                self.push()
                gitops.git(self.root, "push", "-f", "origin", f"refs/tags/round/{self.id}-abandoned", check=False)
            except RunnerError as exc:
                self.flag(str(exc))

    def finish(self):
        st = self.state
        st["status"], st["finished_at"], st["checkpoint"] = "finished", procs.now(), None
        self.index_line("landed" if st.get("landed_at") else "finished")

    def index_line(self, outcome):
        st = self.state
        row = {"id": self.rid, "quote_usd": st["budget_usd"], "spend": self.spend(), "attempts": st["attempts"], "failures": st["failures"],
               "round_retries": st["round_retries"], "judgment_calls": self.judgment_counts(), "outcome": outcome,
               "prose_commit": st["prose_commit"], "landed_at": st.get("landed_at"), "abandoned_at": st.get("abandoned_at")}
        procs.append_text(os.path.join(os.path.dirname(self.folder), "index.jsonl"), json.dumps(row, ensure_ascii=False) + "\n")

    # ---- read-only views ---------------------------------------------------
    def status_payload(self):
        st = self.state
        living = None  # the charge the diff from base_commit would book; once landed the booked living_usd is the figure
        if gitops.head(self.root) and not st.get("landed_at"):
            try:
                living = ledger.living_charge(self.cfg, self.root, st["base_commit"], "HEAD", self.spec().get("testPaths") or [])[0]
            except RunnerError:
                living = None
        return {"round": self.id, "status": st["status"], "step": st["step"], "attempt_pending": st.get("attempt_pending"),
                "checkpoint": st.get("checkpoint"), "attempts": st["attempts"], "failures": st["failures"], "round_retries": st["round_retries"],
                "spend": self.spend(), "living_preview_usd": living, "judgment_calls": self.judgment_counts(),
                "undefined_tail": self.undefined_tail(), "undefined_file": self.abs(self.paths["undefined"]),
                "hard_stop": ledger.hard_stop(self.cfg, st), "branch": st["branch"], "root": self.root, "spec_edits": st["spec_edits"]}

    def check_payload(self):
        st = self.state
        name = st["step"]
        s = pipeline.step(name)
        findings = []
        if s.kind == "landing":
            findings = landing.landing_check(self, mutate=False)[0]
        elif s.kind in ("producer", "code"):
            spec = self.spec()
            errors = self.s1(name, spec)
            if errors:
                findings.append(checks.finding("S1", "\n".join(errors), "the artifact is missing or invalid", "write the artifact as the contract says"))
            if "M3" in pipeline.checks_for(name):
                findings += checks.m3_verify(self.cfg, self.harness, spec)
            if "M5" in pipeline.checks_for(name):
                findings += checks.m5_suite(self.cfg, self.harness)
        return {"kind": "check", "round": self.id, "step": name, "findings": findings}


def st_base(r):
    return r.state["base_commit"][:12]


# ---- start and lookup ----------------------------------------------------------
def validate_plan(cfg, plan, through, overrides):
    errors = schemas.validate(plan, schemas.SCHEMAS["PLAN"], "PLAN")
    approval = plan.get("approval")
    if cfg.gate_enabled("CHAT-TO-PLAN-GATE") and not approval:  # --delegate overrides the mode, never the owner's word
        errors.append("PLAN: approval is required while CHAT-TO-PLAN-GATE is enabled (mode, words)")
    for name in overrides:
        if not pipeline.is_overridable(name):
            errors.append(f"PLAN: {name} cannot be overridden")
    if through and through not in pipeline.BY_NAME:
        errors.append(f"PLAN: through names unknown step {through}")
    for key, path in (plan.get("provided_artifacts") or {}).items():
        if key not in schemas.ARTIFACT_SCHEMA and key != "postmortem":
            errors.append(f"PLAN: provided_artifacts.{key} is not an artifact key")
        elif not os.path.exists(path):
            errors.append(f"PLAN: provided_artifacts.{key} file missing: {path}")
    return errors


def start(root, plan_path, budget=None, branch=None, no_branch=False, delegate=False, through=None, accept_spec=False,
          agent=None, unverified=False, push=True):
    cfg = configmod.load(root)
    files = specguard.spec_files(root)
    present = {f: os.path.exists(os.path.join(root, f)) for f in files}
    errors, _ = pipeline.lint(cfg, prompts.prose_names(cfg, root), present)
    if errors:
        raise RunnerError("lint: " + "; ".join(errors), 2)
    drift = specguard.check(root)
    if not drift["clean"] and not accept_spec:
        raise RunnerError("spec drift: " + specguard.summary(drift).replace("\n", "; ") + "; review, then `spec accept --note ...` or `start --accept-spec`", 3)
    try:
        plan = procs.read_json(plan_path)
    except (OSError, ValueError) as exc:
        raise RunnerError(f"plan unreadable: {exc}", 2)
    approval = dict(plan.get("approval") or {})
    overrides = list(approval.get("overrides") or [])
    errors = validate_plan(cfg, plan, through or approval.get("through"), overrides)
    if errors:
        raise RunnerError("; ".join(errors), 2)
    if agent and agent not in cfg.agents:
        raise RunnerError(f"--agent {agent} is not a roster key", 2)
    main_root = gitops.main_root(root)
    log = ownermod.log_path(main_root)
    words = approval.get("words")
    if words and os.path.exists(log):
        ok = ownermod.verify_quote(log, words, plan.get("presented_at"))
        if not ok and not unverified:
            raise RunnerError(f"approval words not found in the owner log after {plan.get('presented_at')}: {words!r} (pass --unverified to record them anyway)", 2)
    if not approval:
        approval = {"mode": "approved", "source": "gate-disabled"}
    if delegate:
        approval.update({"mode": "delegated", "through": through or approval.get("through")})
    approval.setdefault("source", "plan")
    if no_branch:
        if not procs.same_path(main_root, root):
            raise RunnerError(f"--no-branch runs in the main checkout only; {os.path.abspath(root)} is a linked worktree of {main_root}", 2)
        rid = (local_round_ids(cfg) or [0])[-1] + 1
        wt = os.path.abspath(root)
        branch_name = branch or gitops.current_branch(root) or "HEAD"
        mode = "no-branch"
    else:
        if not gitops.has_origin(root):
            raise RunnerError("no origin remote; use --no-branch for a single-checkout round", 2)
        if not gitops.git_ok(root, "check-ignore", "-q", cfg["worktreeDir"].rstrip("/") + "/probe"):
            raise RunnerError(f"worktreeDir {cfg['worktreeDir']} is not gitignored; add `{cfg['worktreeDir'].rstrip('/')}/` to .gitignore", 2)
        if not gitops.git_ok(root, "ls-remote", "--exit-code", "origin", "HEAD"):
            raise RunnerError("origin is not reachable (git ls-remote origin HEAD failed)", 1)
        gitops.git(root, "fetch", "-q", "origin")
        target = f"origin/{cfg['mainBranch']}"
        stale = checks.e1_spec_edits(root, target, files + [specguard.SPEC_YAML, specguard.BASELINE])
        if stale:
            raise RunnerError(f"spec files differ from {target}, which the round starts from: {', '.join(sorted(stale))}; "
                              "commit and push them first (or pull, when origin is ahead), or use --no-branch", 2)
        rid, branch_name = landing.claim(root, cfg, branch)
        wt = os.path.join(main_root, *cfg["worktreeDir"].strip("/").split("/"), f"round-{cfg.round_id(rid)}")
        if os.path.exists(wt) or gitops.branch_exists(root, branch_name):
            raise RunnerError(f"worktree {wt} or local branch {branch_name} already exists; the claim {branch_name} stays claimed, rerun start", 2)
        gitops.git(root, "worktree", "add", "-q", "-b", branch_name, wt, target)
        local = os.path.join(root, configmod.HARNESS_DIR, configmod.LOCAL_FILE)
        if os.path.exists(local):
            shutil.copyfile(local, os.path.join(wt, configmod.HARNESS_DIR, configmod.LOCAL_FILE))
        mode = "worktree"
    wcfg = configmod.load(wt)
    r = Round(wt, wcfg, rid)
    head = r.head()
    os.makedirs(r.folder, exist_ok=True)
    for key in ("prompts", "results", "findings"):
        folder = r.abs(r.paths[key])
        os.makedirs(folder, exist_ok=True)
        procs.write_text(os.path.join(folder, ".keep"), "")
    plan["round"] = rid
    procs.write_json(r.abs(r.paths["plan"]), plan)
    for key, path in (plan.get("provided_artifacts") or {}).items():
        shutil.copyfile(path, r.abs(r.paths[key]))
    for key in ("defined", "undefined"):
        procs.write_text(r.abs(r.paths[key]), HEADERS[key].format(id=r.id))
    previous = [row for row in r.index_rows()]
    since = [plan.get("presented_at")] + [previous[-1].get("landed_at") or previous[-1].get("abandoned_at")] if previous else [plan.get("presented_at")]
    since = [s for s in since if s]
    r.state = {
        "round": rid, "id": r.id, "branch": branch_name, "mode": mode, "created_at": procs.now(), "status": "active",
        "step": "CHAT-TO-PLAN-GATE", "attempt_pending": None, "attempts": {"CHAT-TO-PLAN": 1}, "failures": {}, "infra_errors": {},
        "round_retries": 0, "step_starts": {}, "step_commits": {}, "inputs_hash": {"PLAN": None, "SPEC": None},
        "budget_usd": float(budget if budget is not None else plan["quote_usd"]),
        "spend": {"entries": [], "agent_usd": 0.0, "driver_usd": 0.0, "owner_usd": 0.0, "living_usd": 0.0},
        "base_commit": head, "prose_commit": head, "approval": approval, "overrides": overrides, "checkpoint": None,
        "pending_question": None, "findings_ledger": {}, "carried": [], "tests_frozen_at": None,
        "merge_pending": None, "resume_step": None, "spec_edits": [], "hard_stop_raised": False, "round_limit_raised": False,
        "landed_at": None, "abandoned_at": None, "judgment_calls": {"defined": 0, "undefined": 0},
        "owner_since": min(since) if since else None, "agent_override": agent, "words_charged": {}, "undefined_at_checkpoint": 0,
    }
    r.state["inputs_hash"]["PLAN"] = sha_of(r.abs(r.paths["plan"]))
    procs.write_text(r.abs(r.paths["history"]), f"# Round {r.id}\n\nStarted {r.state['created_at']} on {branch_name}; quote ${r.state['budget_usd']}.\n\n")
    r.refresh_owner_slice()
    if words and not os.path.exists(log):
        r.flag("approval words recorded unverified: no owner log", who="driver")
    elif words and unverified:
        r.flag("approval words recorded unverified (--unverified)", who="driver")
    budgets = r.budgets()
    ledger.append(r.state, "CHAT-TO-PLAN", 1, max(budgets.get("CHAT-TO-PLAN", 0.0), 0.0), "agent-estimate", "planning in chat, estimated at its share")
    ledger.append(r.state, "CHAT-TO-PLAN", 1, wcfg["driverUsdPerStep"], "driver")
    plan_words = prompts.plan_text(plan)
    ledger.append(r.state, "CHAT-TO-PLAN", 1, ledger.word_cost(wcfg, "planCostPerWord", plan_words), "owner", f"{procs.words(plan_words)} plan words")
    r.state["words_charged"]["plan"] = True
    for w in wcfg.warnings:
        r.flag("config: " + w)
    if accept_spec:
        specguard.accept(wt, f"round {r.id}: accepted at start")
    r.save()
    gitops.git(wt, "add", "-A")
    gitops.git(wt, "commit", "-q", "--no-verify", "-m", f"round {r.id}: start")
    if mode == "worktree":
        proc = gitops.git_proc(wt, "push", "-u", "origin", branch_name)
        if not proc.ok:
            raise RunnerError(f"push of {branch_name} failed: {(proc.err or proc.out).strip()[-300:]}", 1)
    runner = os.path.join(wt, "harness", "src", "run.py")
    return {"round": rid, "id": r.id, "folder": r.paths["folder"], "branch": branch_name, "worktree": wt, "runner": runner,
            "record_hint": f"py -3.13 {procs.quoted(runner)} --root {procs.quoted(wt)} next", "warnings": r.notes}


def open_round(root, rid=None):
    cfg = configmod.load(root)
    if rid is None:
        branch = gitops.current_branch(root) or ""
        m = re.fullmatch(r"round/(\d+)", branch)
        if m:
            rid = int(m.group(1))
        else:
            open_ids = []
            for i in local_round_ids(cfg):
                path = cfg.abs_path(cfg.round_paths(i)["state"])
                if os.path.exists(path) and procs.read_json(path).get("status") not in ("finished", "abandoned"):
                    open_ids.append(i)
            if len(open_ids) == 1:
                rid = open_ids[0]
            elif not open_ids and local_round_ids(cfg):
                rid = local_round_ids(cfg)[-1]
            else:
                raise RunnerError("which round? pass --round N" + (f" (unfinished: {open_ids})" if open_ids else " (no rounds exist; run start)"), 2)
    r = Round(root, cfg, rid)
    if r.state is None:
        raise RunnerError(f"round {cfg.round_id(rid)} has no STATE.json under {r.folder}", 2)
    return r


def planning_contexts(cfg, root):
    """round.* and step.* for CHAT-TO-PLAN before any round exists."""
    dummy = Round(root, cfg, 0)
    rows = dummy.index_rows()
    history = [f"round {r.get('id')}: quoted {r.get('quote_usd')} actual {(r.get('spend') or {}).get('total_usd')} ({r.get('outcome')})" for r in rows][-5:]
    pms = []
    for row in rows:
        if row.get("outcome") == "landed":
            rel = cfg.round_paths(int(row["id"]))["postmortem"]
            if os.path.exists(cfg.abs_path(rel)):
                pms.append(rel)
    carry = list(cfg["carryForwardFiles"])
    round_ctx = prompts.empty_round_context(
        worktree=os.path.abspath(root), harness_root=cfg.harness_root,
        history="\n".join(history) or "none", postmortem_paths=pms[-int(cfg["postmortemFeedRounds"]):] or "none",
        todos=dummy.carry_text(carry[0]) if carry else "none", clarifications=dummy.carry_text(carry[1]) if len(carry) > 1 else "none",
        steps=prompts.step_table(cfg), runner=os.path.join(cfg.harness_root, "src", "run.py"))
    step_ctx = prompts.step_context(cfg, "CHAT-TO-PLAN", 1, cfg.round_paths(0), root, cfg.harness_root)
    return round_ctx, step_ctx, False
