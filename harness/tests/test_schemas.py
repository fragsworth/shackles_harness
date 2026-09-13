import json

from shackles import schemas

PLAN = {"presented_at": "2026-01-01T00:00:00Z", "quote_usd": 10, "summary": "s", "scope": ["a"], "validation": ["v"], "non_goals": []}


def test_validator_messages():
    v = lambda obj, schema: schemas.validate(obj, schema, "T")
    assert v(5, {"type": "str"}) == ["T: $ should be str, got int"]
    assert v(True, {"type": "int"}) == ["T: $ should be int, got bool"]
    assert v({"a": "x"}, {"type": "dict", "required": ["a", "b"]}) == ["T: $ missing required key b"]
    assert v({"a": "x"}, {"type": "dict", "properties": {"a": {"type": "str", "enum": ["y"]}}}) == ["T: a should be one of y, got 'x'"]
    assert v({"a": 0}, {"type": "dict", "properties": {"a": {"type": "number", "exclusiveMinimum": 0}}}) == ["T: a should be greater than 0, got 0"]
    assert v([], {"type": "list", "minItems": 1}) == ["T: $ should have at least 1 items, got 0"]
    assert v(["a", 2], {"type": "list", "items": {"type": "str"}}) == ["T: $[1] should be str, got int"]
    assert v({"x": 1}, {"type": "dict", "additionalProperties": False}) == ["T: $ has unknown key x"]
    assert v({"x": 1}, {"type": "dict", "additionalProperties": {"type": "str"}}) == ["T: x should be str, got int"]
    assert v("ab", {"type": ["str", "list"]}) == [] and v(3, {"type": ["str", "list"]}) == ["T: $ should be str or list, got int"]
    assert v("2026-01-01", {"type": "str", "pattern": r"Z$"}) == ["T: $ should match Z$, got '2026-01-01'"]


def test_plan_schema():
    assert schemas.validate(PLAN, schemas.SCHEMAS["PLAN"], "PLAN") == []
    bad = dict(PLAN, quote_usd=0, presented_at="yesterday")
    errors = schemas.validate(bad, schemas.SCHEMAS["PLAN"], "PLAN")
    assert "PLAN: quote_usd should be greater than 0, got 0" in errors
    assert any(e.startswith("PLAN: presented_at should match") for e in errors)
    assert schemas.validate(dict(PLAN, approval={"mode": "maybe"}), schemas.SCHEMAS["PLAN"], "PLAN") == \
        ["PLAN: approval.mode should be one of approved, delegated, got 'maybe'"]


def test_agents_plan_spec_suite_schemas():
    ap = {"round": 1, "agents": {"PLAN-AGENTS": "max"}, "shares": {"work": {"A": 1}, "gates": {}}}
    assert schemas.validate(ap, schemas.SCHEMAS["AGENTS_PLAN"], "AGENTS_PLAN") == []
    assert schemas.validate({"round": 1, "agents": {}, "shares": {"work": {}}}, schemas.SCHEMAS["AGENTS_PLAN"], "AGENTS_PLAN") == \
        ["AGENTS_PLAN: shares missing required key gates"]
    spec = {"round": 1, "summary": "s", "verify": ["py"], "implPaths": ["../src/"], "testPaths": [], "nonGoals": []}
    assert schemas.validate(spec, schemas.SCHEMAS["SPEC"], "SPEC") == []
    assert schemas.validate(dict(spec, implPaths=[], verify=3), schemas.SCHEMAS["SPEC"], "SPEC") == \
        ["SPEC: verify should be str or list, got int", "SPEC: implPaths should have at least 1 items, got 0"]
    assert schemas.validate(dict(spec, refactor=[{"what": "x"}]), schemas.SCHEMAS["SPEC"], "SPEC") == ["SPEC: refactor[0] missing required key budget_usd"]
    suite = {"round": 1, "keep": [], "archive": [], "notes": ""}
    assert schemas.validate(suite, schemas.SCHEMAS["SUITE"], "SUITE") == []
    assert schemas.validate({"round": 1}, schemas.SCHEMAS["SUITE"], "SUITE") == [
        "SUITE: $ missing required key keep", "SUITE: $ missing required key archive", "SUITE: $ missing required key notes"]


def test_result_and_findings_schemas():
    assert schemas.validate({"status": "DONE"}, schemas.SCHEMAS["RESULT"], "RESULT") == []
    assert schemas.validate({"status": "OK"}, schemas.SCHEMAS["RESULT"], "RESULT") == ["RESULT: status should be one of DONE, NEEDS-OWNER, UPSTREAM, BLOCKED, got 'OK'"]
    assert schemas.validate({"status": "DONE", "resolutions": {"F1": {"status": "maybe"}}}, schemas.SCHEMAS["RESULT"], "RESULT") == \
        ["RESULT: resolutions.F1.status should be one of fixed, disputed, deferred, got 'maybe'"]
    assert schemas.validate({"status": "DONE", "judgment_calls": {"defined": ["a line"], "undefined": 0}}, schemas.SCHEMAS["RESULT"], "RESULT") == [], \
        "a producer that answers in the gate's list shape is not an infrastructure error"
    assert schemas.validate({"status": "DONE", "judgment_calls": {"defined": "1"}}, schemas.SCHEMAS["RESULT"], "RESULT") == \
        ["RESULT: judgment_calls.defined should be int or list, got str"]
    f = {"verdict": "FAIL", "findings": [{"id": "F1", "quote": "q", "reason": "r", "suggestion": "s", "blocking": True}]}
    assert schemas.validate(f, schemas.SCHEMAS["FINDINGS"], "FINDINGS") == []
    assert schemas.validate({"verdict": "PASS", "findings": [{"id": "F1"}]}, schemas.SCHEMAS["FINDINGS"], "FINDINGS") == [
        "FINDINGS: findings[0] missing required key quote", "FINDINGS: findings[0] missing required key reason", "FINDINGS: findings[0] missing required key blocking"]
    assert schemas.validate({"verdict": "PASS", "findings": [], "needs_owner": {"status": "yes"}}, schemas.SCHEMAS["FINDINGS"], "FINDINGS") == \
        ["FINDINGS: needs_owner.status should be one of upheld, withdrawn, got 'yes'"]


def test_json_schema_and_describe():
    js = schemas.json_schema("RESULT")
    assert js["type"] == "object" and js["properties"]["status"]["enum"][0] == "DONE"
    assert schemas.json_schema("SPEC")["properties"]["verify"]["type"] == ["string", "array"]
    assert schemas.json_schema("FINDINGS")["properties"]["findings"]["items"]["required"] == ["id", "quote", "reason", "blocking"]
    text = schemas.describe("SUITE")
    assert text.startswith("JSON object with round (int, required); keep (list, required): test files")


def test_extract_json():
    assert schemas.extract_json('{"status": "DONE"}') == {"status": "DONE"}
    assert schemas.extract_json('Sure.\n```json\n{"verdict": "PASS", "findings": []}\n```\nthanks') == {"verdict": "PASS", "findings": []}
    assert schemas.extract_json('I decided {"a": 1} and then {"status": "DONE", "notes": "x {y}"} done') == {"status": "DONE", "notes": "x {y}"}
    assert schemas.extract_json("no json here {{{") is None
    assert schemas.extract_json('﻿{"status": "DONE"}') == {"status": "DONE"}
    assert schemas.extract_json('text {"other": 1}') == {"other": 1}


def test_extract_json_prefers_the_top_level_object_over_nested_ones():
    """A nested object with its own status key (a resolution, a ruling, needs_owner) never wins over the message's object."""
    producer = {"status": "DONE", "notes": "n", "resolutions": {"F1": {"status": "fixed", "reason": "r"}, "F2": {"status": "disputed", "reason": "d"}}}
    assert schemas.extract_json("Here is my final message:\n\n" + json.dumps(producer) + "\n\nThanks.") == producer
    gate = {"verdict": "PASS", "findings": [], "rulings": {"F2": {"status": "withdrawn", "quote": "q"}}, "needs_owner": {"status": "upheld", "reason": "x"}}
    assert schemas.extract_json("Verdict below.\n" + json.dumps(gate) + "\nDone.") == gate
    assert schemas.extract_json('earlier {"status": "UPSTREAM"} and finally {"status": "DONE"} then a summary {"files": 3}') == {"status": "DONE"}
    assert schemas.extract_json('{"a": {"status": "nested only"}}') == {"a": {"status": "nested only"}}, "the top-level object is the message"


def norm(obj, withdrawn=(), next_id=1):
    return schemas.normalize_findings(json.loads(json.dumps(obj)), "X-GATE", 2, next_id, set(withdrawn), 20)


def test_normalize_verdict_authoritative_both_ways():
    obj, notes = norm({"verdict": "PASS", "findings": [{"id": "F1", "quote": "q", "reason": "r", "blocking": True}]})
    assert obj["findings"][0]["blocking"] is False and obj["verdict"] == "PASS"
    assert notes == ["PASS with blocking findings F1: set non-blocking (the verdict is authoritative)"]
    obj, notes = norm({"verdict": "FAIL", "findings": [{"id": "F1", "quote": "q", "reason": "r", "suggestion": "s", "blocking": False}]})
    assert obj["verdict"] == "FAIL" and obj["findings"][0]["blocking"] is False
    assert notes == ["FAIL without a blocking finding: findings kept as given (the verdict is authoritative)"]
    obj, notes = norm({"verdict": "FAIL", "findings": []})
    assert notes == ["FAIL without any finding (the verdict is authoritative)"]


def test_normalize_ids_suggestion_withdrawn_and_truncation():
    obj, notes = norm({"verdict": "FAIL", "findings": [
        {"id": "F3", "quote": "a" * 30, "reason": "r", "blocking": True},
        {"id": "F3", "quote": "b", "reason": "r", "suggestion": "s", "blocking": False},
        {"id": "", "quote": "c", "reason": "r", "blocking": False},
        {"id": "F1", "quote": "old  quote", "reason": "r", "blocking": True}]}, withdrawn=["old quote"], next_id=3)
    ids = [f["id"] for f in obj["findings"]]
    assert ids == ["F3", "X-GATE-2.F3", "X-GATE-2.F0"]
    assert obj["findings"][0]["suggestion"] == "(none given)" and len(obj["findings"][0]["quote"]) == 20
    assert "finding X-GATE-2.F1 re-raises a withdrawn finding; dropped" in notes
    assert "finding id F3 renamed X-GATE-2.F3" in notes and "quote of F3 truncated to 20 chars" in notes
    obj, notes = norm({"verdict": "FAIL", "findings": [{"id": "F1", "quote": "q", "reason": "r", "blocking": True}]}, next_id=4)
    assert obj["findings"][0]["id"] == "X-GATE-2.F1"


def test_state_schema_requires_every_key():
    errors = schemas.validate({"round": 1}, schemas.SCHEMAS["STATE"], "STATE")
    assert "STATE: $ missing required key attempt_pending" in errors and len(errors) > 20
