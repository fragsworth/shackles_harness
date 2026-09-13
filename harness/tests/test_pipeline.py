import copy

import pytest

import fixtures
from shackles import config as configmod
from shackles import pipeline


def cfg_with(gates=None, **over):
    data = copy.deepcopy(configmod.DEFAULTS)
    if gates is not None:
        data["gates"] = gates
    data.update(over)
    return configmod.Config("r/harness", data, {}, [], fixtures.ROSTER)


ALL_PROSE = [pipeline.prose_file(s.name) for s in pipeline.PIPELINE if pipeline.prose_file(s.name)] + \
    ["COMMON-PROJECT.txt", "COMMON-ROUND.txt", "COMMON-OVERVIEW.txt", "COMMON-GATE.txt"]


def test_lookups():
    assert pipeline.NAMES[0] == "CHAT-TO-PLAN" and pipeline.NAMES[-1] == "POSTMORTEM-GATE"
    assert pipeline.producer_of("PLAN-AGENTS-GATE") == "PLAN-AGENTS" and pipeline.producer_of("CHAT-TO-PLAN-GATE") == "CHAT-TO-PLAN"
    assert pipeline.gate_of("PLAN-AGENTS") == "PLAN-AGENTS-GATE" and pipeline.gate_of("CLEANUP") is None
    assert pipeline.gate_of("CHAT-TO-PLAN") == "CHAT-TO-PLAN-GATE"
    assert pipeline.next_after("CLEANUP") == "LANDING" and pipeline.next_after("POSTMORTEM-GATE") is None
    assert pipeline.earlier_producers("SPEC-TO-TESTS") == ["CHAT-TO-PLAN", "PLAN-AGENTS", "PLAN-TO-SPEC"]
    assert pipeline.index("LANDING") == 13
    assert pipeline.producers() == ["CHAT-TO-PLAN", "PLAN-AGENTS", "PLAN-TO-SPEC", "SPEC-TO-TESTS", "SPEC-TO-IMPLEMENTATION",
                                    "TESTS-TO-SUITE", "CLEANUP", "POSTMORTEM"]
    assert pipeline.gates() == list(configmod.DEFAULTS["gates"])
    assert pipeline.llm_gates() == pipeline.gates()[1:]
    assert pipeline.is_overridable("CLEANUP") and not pipeline.is_overridable("LANDING") and not pipeline.is_overridable("NOPE")
    with pytest.raises(KeyError):
        pipeline.step("NOPE")


def test_prose_file_mapping():
    assert pipeline.prose_file("PLAN-AGENTS") == "PLAN-AGENTS-OVERVIEW.txt"
    assert pipeline.prose_file("PLAN-AGENTS-GATE") == "PLAN-AGENTS-GATE.txt"
    assert pipeline.prose_file("LANDING") is None and pipeline.prose_file("CHAT-TO-PLAN-GATE") is None
    assert pipeline.prose_owner("COMMON-X.txt") == "COMMON" and pipeline.prose_owner("CLEANUP-OVERVIEW.txt") == "CLEANUP"
    assert pipeline.prose_owner("LANDING-OVERVIEW.txt") is None and pipeline.prose_owner("REVIEW-GATE.txt") is None
    assert pipeline.prose_owner("notes.md") is None


def test_checks_for():
    assert pipeline.checks_for("PLAN-AGENTS") == ["M0", "M4", "E1", "S1"]
    assert pipeline.checks_for("SPEC-TO-IMPLEMENTATION", merge_attempt=True)[-1] == "L3"
    assert pipeline.checks_for("PLAN-AGENTS-GATE") == [] and pipeline.checks_for("LANDING") == ["L1", "L2"]
    for ids in (s.checks for s in pipeline.PIPELINE):
        assert all(i in pipeline.CHECKS for i in ids)


def test_lint_clean():
    errors, warnings = pipeline.lint(cfg_with(), ALL_PROSE, {"a": True})
    assert errors == [] and warnings == []


def test_lint_gate_missing_from_map_is_a_warning_and_unknown_gate_an_error():
    gates = dict(configmod.DEFAULTS["gates"])
    gates.pop("SPEC-TO-TESTS-GATE")
    gates["REVIEW-GATE"] = 1
    errors, warnings = pipeline.lint(cfg_with(gates=gates), ALL_PROSE, {})
    assert errors == ["gates.REVIEW-GATE names no pipeline gate"]
    assert warnings == ["gate SPEC-TO-TESTS-GATE absent from gates (disabled)"]


def test_lint_reordered_map():
    gates = dict(configmod.DEFAULTS["gates"])
    items = list(gates.items())
    items[1], items[2] = items[2], items[1]
    errors, _ = pipeline.lint(cfg_with(gates=dict(items)), ALL_PROSE, {})
    assert errors and errors[0].startswith("gates keys are not in pipeline order")


def test_lint_prose_files():
    errors, warnings = pipeline.lint(cfg_with(), ALL_PROSE + ["EXTRA.txt"], {})
    assert warnings == ["unknown prose file EXTRA.txt"] and not errors
    errors, _ = pipeline.lint(cfg_with(), [p for p in ALL_PROSE if p != "CLEANUP-OVERVIEW.txt"], {})
    assert errors == ["step CLEANUP has no prose CLEANUP-OVERVIEW.txt: restore it or override the step"]
    gates = dict(configmod.DEFAULTS["gates"], **{"POSTMORTEM-GATE": 1})
    _, warnings = pipeline.lint(cfg_with(gates=gates), [p for p in ALL_PROSE if p != "POSTMORTEM-GATE.txt"], {})
    assert warnings == ["gate POSTMORTEM-GATE is enabled but POSTMORTEM-GATE.txt is missing (disabled)"]


def test_lint_roster_checkpoints_artifacts_and_spec_files():
    errors, warnings = pipeline.lint(cfg_with(gateAgent="nope", checkpointsAfter=["NOPE"]), ALL_PROSE, {"harness/x": False})
    assert "gateAgent 'nope' is not a roster key" in errors and "spec file missing: harness/x" in errors
    assert "checkpointsAfter names unknown step NOPE" in warnings
    rp = copy.deepcopy(configmod.DEFAULTS["roundPaths"])
    rp["artifacts"].pop("suite")
    _, warnings = pipeline.lint(cfg_with(roundPaths=rp), ALL_PROSE, {})
    assert "roundPaths.artifacts.suite missing (default used)" in warnings
