"""Hand-written validation of every JSON the runner reads or writes; emitted as JSON Schema for --json-schema."""
import json
import re

from . import contract

TYPES = {"str": str, "int": int, "number": (int, float), "bool": bool, "list": list, "dict": dict}
JSON_TYPES = {"str": "string", "int": "integer", "number": "number", "bool": "boolean", "list": "array", "dict": "object"}


def _isa(value, tname):
    if tname == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if tname == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[tname])


def validate(obj, schema, name, path=""):
    """["NAME: <path> <problem>", ...]; empty when valid."""
    errors = []
    where = path or "$"
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else list(types)
        if not any(_isa(obj, t) for t in types):
            return [f"{name}: {where} should be {' or '.join(types)}, got {type(obj).__name__}"]
    if "enum" in schema and obj not in schema["enum"]:
        return [f"{name}: {where} should be one of {', '.join(map(str, schema['enum']))}, got {obj!r}"]
    if "minimum" in schema and isinstance(obj, (int, float)) and obj < schema["minimum"]:
        errors.append(f"{name}: {where} should be at least {schema['minimum']}, got {obj}")
    if "exclusiveMinimum" in schema and isinstance(obj, (int, float)) and obj <= schema["exclusiveMinimum"]:
        errors.append(f"{name}: {where} should be greater than {schema['exclusiveMinimum']}, got {obj}")
    if "pattern" in schema and isinstance(obj, str) and not re.search(schema["pattern"], obj):
        errors.append(f"{name}: {where} should match {schema['pattern']}, got {obj!r}")
    if isinstance(obj, dict):
        for key in schema.get("required", []):
            if key not in obj:
                errors.append(f"{name}: {where} missing required key {key}")
        props = schema.get("properties", {})
        for key, value in obj.items():
            if key in props:
                errors += validate(value, props[key], name, f"{path}.{key}" if path else key)
            elif "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
                errors += validate(value, schema["additionalProperties"], name, f"{path}.{key}" if path else key)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{name}: {where} has unknown key {key}")
    if isinstance(obj, list):
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errors.append(f"{name}: {where} should have at least {schema['minItems']} items, got {len(obj)}")
        if "items" in schema:
            for i, item in enumerate(obj):
                errors += validate(item, schema["items"], name, f"{where}[{i}]")
    return errors


STR, INT, NUM, BOOL = {"type": "str"}, {"type": "int"}, {"type": "number"}, {"type": "bool"}
STR_LIST = {"type": "list", "items": STR}

SCHEMAS = {
    "PLAN": {
        "type": "dict", "required": ["presented_at", "quote_usd", "summary", "scope", "validation", "non_goals"],
        "properties": {
            "presented_at": {"type": "str", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", "doc": "UTC timestamp when the plan was shown"},
            "quote_usd": {"type": "number", "exclusiveMinimum": 0, "doc": "the quote in dollars"},
            "summary": dict(STR, doc="one paragraph, plain English"),
            "scope": dict(STR_LIST, doc="what the round builds"),
            "validation": dict(STR_LIST, doc="how the owner will see it works"),
            "non_goals": dict(STR_LIST, doc="what the round will not do"),
            "assumptions": dict(STR_LIST, doc="what was decided without asking"),
            "todos": {"type": "dict", "doc": "accepted TODO items by id"},
            "approval": {"type": "dict", "required": ["mode"], "properties": {
                "mode": {"type": "str", "enum": ["approved", "delegated"]}, "through": STR,
                "overrides": STR_LIST, "words": STR, "source": STR}, "doc": "the owner's word, verbatim"},
            "owner_words": STR_LIST,
            "provided_artifacts": {"type": "dict", "additionalProperties": STR, "doc": "artifact key -> path, for overridden producers"},
            "round": INT,
        },
    },
    "AGENTS_PLAN": {
        "type": "dict", "required": ["round", "agents", "shares"],
        "properties": {
            "round": INT,
            "agents": {"type": "dict", "additionalProperties": STR, "doc": "STEP -> rung for every producer step"},
            "shares": {"type": "dict", "required": ["work", "gates"], "properties": {
                "work": {"type": "dict", "additionalProperties": NUM, "doc": "STEP -> fraction of the work budget"},
                "gates": {"type": "dict", "additionalProperties": NUM, "doc": "producer STEP -> fraction of the gates budget"}}},
            "gateAgents": {"type": "dict", "additionalProperties": STR, "doc": "GATE -> rung"},
            "subAgents": {"type": "dict", "additionalProperties": INT, "doc": "STEP -> simultaneous sub-agents allowed"},
            "notes": STR,
        },
    },
    "SPEC": {
        "type": "dict", "required": ["round", "summary", "verify", "implPaths", "testPaths", "nonGoals"],
        "properties": {
            "round": INT,
            "summary": STR,
            "verify": {"type": ["str", "list"], "doc": "the verify command, run from HARNESS"},
            "verifyTimeoutSeconds": NUM,
            "implPaths": {"type": "list", "items": STR, "minItems": 1, "doc": "HARNESS-relative paths the implementation may change"},
            "testPaths": {"type": "list", "items": STR, "doc": "HARNESS-relative paths the tests may change"},
            "nonGoals": dict(STR_LIST, doc="the plan's non-goals, carried verbatim"),
            "refactor": {"type": "list", "items": {"type": "dict", "required": ["what", "budget_usd"],
                                                    "properties": {"what": STR, "budget_usd": NUM}}, "doc": "refactor items within maxRefactorOverhead"},
            "testPlan": STR,
        },
    },
    "SUITE": {
        "type": "dict", "required": ["round", "keep", "archive", "notes"],
        "properties": {"round": INT, "keep": dict(STR_LIST, doc="test files that join the permanent suite"),
                       "archive": dict(STR_LIST, doc="test files moved to the round's tests-archive/"),
                       "notes": STR, "raise_with_owner": dict(STR_LIST, doc="middle grounds worth flagging")},
    },
    "RESULT": {
        "type": "dict", "required": ["status"],
        "properties": {
            "status": {"type": "str", "enum": list(contract.STATUSES)},
            "notes": STR, "question": STR, "assumption": STR, "target": STR, "narrow": STR,
            "resolutions": {"type": "dict", "additionalProperties": {"type": "dict", "required": ["status"], "properties": {
                "status": {"type": "str", "enum": list(contract.RESOLUTIONS)}, "reason": STR}}},
            "judgment_calls": {"type": "dict", "properties": {"defined": {"type": ["int", "list"]}, "undefined": {"type": ["int", "list"]}},
                               "doc": "counts; a gate-shaped list of lines is tolerated"},
        },
    },
    "FINDINGS": {
        "type": "dict", "required": ["verdict", "findings"],
        "properties": {
            "verdict": {"type": "str", "enum": list(contract.VERDICTS)},
            "findings": {"type": "list", "items": {"type": "dict", "required": ["id", "quote", "reason", "blocking"], "properties": {
                "id": STR, "quote": STR, "reason": STR, "suggestion": STR, "blocking": BOOL}}},
            "rulings": {"type": "dict", "additionalProperties": {"type": "dict", "required": ["status"], "properties": {
                "status": {"type": "str", "enum": list(contract.RULINGS)}, "quote": STR}}},
            "needs_owner": {"type": "dict", "required": ["status"], "properties": {
                "status": {"type": "str", "enum": list(contract.RULINGS)}, "reason": STR}},
            "notes": STR,
            "judgment_calls": {"type": "dict", "properties": {"defined": STR_LIST, "undefined": STR_LIST}},
            "source": STR, "step": STR, "attempt": INT,
        },
    },
    "STATE": {
        "type": "dict",
        "required": ["round", "id", "branch", "mode", "created_at", "status", "step", "attempt_pending", "attempts",
                     "failures", "infra_errors", "round_retries", "step_starts", "step_commits", "inputs_hash",
                     "budget_usd", "spend", "base_commit", "prose_commit", "approval", "overrides", "checkpoint",
                     "pending_question", "findings_ledger", "last_findings", "carried", "tests_frozen_at",
                     "merge_pending", "resume_step", "spec_edits", "hard_stop_raised", "round_limit_raised",
                     "landed_at", "abandoned_at", "main_before", "judgment_calls", "runner_commit"],
        "properties": {
            "round": INT, "id": STR, "branch": STR, "mode": {"type": "str", "enum": ["worktree", "no-branch"]},
            "status": {"type": "str", "enum": ["active", "checkpoint", "finished", "abandoned"]},
            "attempts": {"type": "dict", "additionalProperties": INT}, "failures": {"type": "dict", "additionalProperties": INT},
            "infra_errors": {"type": "dict", "additionalProperties": INT}, "round_retries": INT,
            "budget_usd": NUM, "overrides": STR_LIST, "spec_edits": STR_LIST,
            "hard_stop_raised": BOOL, "round_limit_raised": BOOL,
            "spend": {"type": "dict", "required": ["entries", "agent_usd", "driver_usd", "owner_usd", "living_usd"]},
            "judgment_calls": {"type": "dict", "required": ["defined", "undefined"]},
        },
    },
}

ARTIFACT_SCHEMA = {"plan": "PLAN", "agentsPlan": "AGENTS_PLAN", "spec": "SPEC", "suite": "SUITE"}


def json_schema(name):
    def convert(node):
        out = {}
        t = node.get("type")
        if t:
            out["type"] = [JSON_TYPES[x] for x in t] if isinstance(t, list) else JSON_TYPES[t]
        for key in ("required", "enum", "minimum", "exclusiveMinimum", "minItems", "pattern"):
            if key in node:
                out[key] = node[key]
        if "properties" in node:
            out["properties"] = {k: convert(v) for k, v in node["properties"].items()}
        if "items" in node:
            out["items"] = convert(node["items"])
        if isinstance(node.get("additionalProperties"), dict):
            out["additionalProperties"] = convert(node["additionalProperties"])
        elif node.get("additionalProperties") is False:
            out["additionalProperties"] = False
        return out
    return convert(SCHEMAS[name])


def describe(name):
    """One line per property: the contract an agent gets in its prompt."""
    schema = SCHEMAS[name]
    required = set(schema.get("required", []))
    parts = []
    for key, node in schema.get("properties", {}).items():
        t = node.get("type")
        t = "|".join(t) if isinstance(t, list) else t
        if "enum" in node:
            t = "|".join(map(str, node["enum"]))
        text = f"{key} ({t}{', required' if key in required else ''})"
        if node.get("doc"):
            text += f": {node['doc']}"
        parts.append(text)
    return "JSON object with " + "; ".join(parts)


def extract_json(text):
    """The whole message; else the last ``` fence; else the last balanced top-level {...}."""
    text = text.strip()
    if text.startswith("﻿"):
        text = text[1:]
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    fences = re.findall(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.S)
    for fence in reversed(fences):
        try:
            obj = json.loads(fence)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    decoder = json.JSONDecoder()
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in reversed(starts):
        try:
            obj, end = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(obj, dict) and ("status" in obj or "verdict" in obj):
            return obj
    for start in starts:
        try:
            obj, end = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def normalize_findings(obj, gate, attempt, next_id, withdrawn_quotes, max_chars):
    """Apply the gate's verdict as authoritative and tidy the findings; returns (obj, notes)."""
    notes = []
    findings = obj.get("findings") or []
    seen = set()
    for f in findings:
        fid = str(f.get("id") or "")
        if not re.fullmatch(r"F\d+", fid) or fid in seen or int(fid[1:]) < next_id:
            new = f"{gate}-{attempt}.{fid or 'F0'}"
            k = 1
            while new in seen:
                k += 1
                new = f"{gate}-{attempt}.{fid or 'F0'}.{k}"
            notes.append(f"finding id {fid or '(none)'} renamed {new}")
            f["id"] = new
        seen.add(f["id"])
        if not f.get("suggestion"):
            f["suggestion"] = "(none given)"
        if len(f.get("quote") or "") > max_chars:
            f["quote"] = f["quote"][:max_chars]
            notes.append(f"quote of {f['id']} truncated to {max_chars} chars")
    kept = []
    for f in findings:
        if " ".join((f.get("quote") or "").split()) in withdrawn_quotes and withdrawn_quotes:
            notes.append(f"finding {f['id']} re-raises a withdrawn finding; dropped")
            continue
        kept.append(f)
    obj["findings"] = kept
    blocking = [f["id"] for f in kept if f.get("blocking")]
    if obj["verdict"] == "PASS" and blocking:
        for f in kept:
            f["blocking"] = False
        notes.append(f"PASS with blocking findings {', '.join(blocking)}: set non-blocking (the verdict is authoritative)")
    elif obj["verdict"] == "FAIL" and not blocking and kept:
        notes.append("FAIL without a blocking finding: findings kept as given (the verdict is authoritative)")
    elif obj["verdict"] == "FAIL" and not kept:
        notes.append("FAIL without any finding (the verdict is authoritative)")
    return obj, notes
