import os

import pytest

import fixtures
from shackles import config as configmod
from shackles import contract, doctor, pipeline, prompts, render

CONTEXT = {"project": {"budget": 100, "gates": {"A-GATE": 0, "B-GATE": 1}, "f": 0.1, "g": 12.5, "h": 10.0, "t": True,
                       "n": None, "l": ["a", 1], "d": {"k": "v"}, "name": "verbatim  text"},
           "round": {"id": "0001", "steps": [{"step": "X"}]},
           "step": {"name": "S", "retry_cost": 3.5}}


def make(prose=None, plumbing=None, kind="producer", step="PLAN-AGENTS", gate=None, note=None, sentence=None, ctx=None):
    prose, plumbing = prose or {}, plumbing if plumbing is not None else {"producer": "PROC {{ step.name }}", "gate": "GATE {{ step.name }}"}
    return render.Renderer(prose.get, plumbing.get, ctx or CONTEXT, kind, step, gate, note, sentence)


def test_grammar_and_dotted_lookups():
    r = make()
    assert r.render("{{ project.budget }}|{{project.budget}}|{{  round.id  }}|{{ project.gates.B-GATE }}|{{ round.steps.0.step }}") == "100|100|0001|1|X"
    assert r.render("{{ nodot }}") == "[unresolved: nodot]" and r.unresolved == ["nodot"]


def test_value_formatting():
    r = make()
    assert r.render("{{ project.f }} {{ project.g }} {{ project.h }} {{ project.t }} {{ project.n }} {{ project.l }} {{ project.d }} {{ project.name }}") == \
        '0.1 12.5 10 true none ["a",1] {"k":"v"} verbatim  text'


def test_unresolved_marker_collected_never_raises():
    r = make()
    out = r.render("a {{ project.missing }} b {{ nowhere.x }} c {{ prose.NOPE }} d {{ plumbing.NOPE }}")
    assert out == "a [unresolved: project.missing] b [unresolved: nowhere.x] c [unresolved: prose.NOPE] d [unresolved: plumbing.NOPE]"
    assert r.unresolved == ["project.missing", "nowhere.x", "prose.NOPE", "plumbing.NOPE"]


def test_prose_include_renders_once_per_document():
    r = make(prose={"A": "[A {{ prose.B }} {{ prose.B }}]", "B": "b-text"})
    assert r.render("{{ prose.A }}{{ prose.B }}") == "[A b-text ]"
    assert r.rendered == {"A", "B"}


def test_cycle_and_depth():
    r = make(prose={"A": "a{{ prose.B }}", "B": "b{{ prose.A }}"})
    assert r.render("{{ prose.A }}") == "ab[cycle: A]"
    chain = {f"P{i}": f"{i}{{{{ prose.P{i + 1} }}}}" for i in range(12)}
    r = make(prose=chain)
    out = r.render("{{ prose.P0 }}")
    assert "[depth: P" in out and any("depth" in w for w in r.warnings)


def test_process_instructions_by_kind_and_step_extra():
    plumbing = {"producer": "PROC {{ step.name }}", "gate": "GATE {{ step.name }}", "PLAN-AGENTS": "EXTRA {{ round.id }}"}
    r = make(plumbing=plumbing)
    assert r.render("{{ plumbing.PROCESS-INSTRUCTIONS }}") == "PROC S\nEXTRA 0001" and r.process_rendered
    r = make(plumbing=plumbing, kind="gate", step="PLAN-AGENTS-GATE")
    assert r.render("{{ plumbing.PROCESS-INSTRUCTIONS }}") == "GATE S"
    r = make(plumbing={"CHAT-TO-PLAN": "CHAT {{ round.id }}"}, kind="plan", step="CHAT-TO-PLAN")
    assert r.render("{{ plumbing.PROCESS-INSTRUCTIONS }}") == "CHAT 0001"
    r = make(plumbing={"producer": "P", "X": "other {{ step.name }}"})
    assert r.render("{{ plumbing.X }}") == "other S"


def test_gate_prose_embed_mode():
    prose = {"COMMON": "common-text", "PLAN-AGENTS-GATE": "gate-head {{ prose.COMMON }} {{ plumbing.PROCESS-INSTRUCTIONS }} {{ plumbing.GATE-PROSE }} {{ step.retry_cost }} tail"}
    r = make(prose=prose, gate="PLAN-AGENTS-GATE")
    out = r.render("{{ prose.COMMON }} | {{ plumbing.GATE-PROSE }}")
    assert out == "common-text | gate-head    3.5 tail"
    assert not r.process_rendered
    r = make(prose=prose, gate="PLAN-AGENTS-GATE", note=render.DISABLED_NOTE)
    assert r.render("{{ plumbing.GATE-PROSE }}").startswith(render.DISABLED_NOTE + "\ngate-head common-text")
    r = make(prose=prose, sentence="mechanical sentence")
    assert r.render("{{ plumbing.GATE-PROSE }}") == "mechanical sentence"
    r = make(prose={}, gate="MISSING-GATE")
    assert r.render("{{ plumbing.GATE-PROSE }}") == "[unresolved: prose.MISSING-GATE]"


def test_assemble_raw_header_and_missing_process_token():
    r = make(prose={}, plumbing={"producer": "PROC {{ step.name }}"})
    out = render.assemble("HEAD {{ project.budget }} {{ plumbing.PROCESS-INSTRUCTIONS }}", "body {{ project.budget }}", r)
    assert out == "HEAD {{ project.budget }} {{ plumbing.PROCESS-INSTRUCTIONS }}\n\nbody 100\n\nPROC S\n"
    assert any("appended" in w for w in r.warnings)
    r = make(prose={}, plumbing={"producer": "PROC"})
    out = render.assemble("H", "body {{ plumbing.PROCESS-INSTRUCTIONS }}", r)
    assert out == "H\n\nbody PROC\n" and not r.warnings


def test_fmt_of_artifact_text_never_expands():
    ctx = dict(CONTEXT, step=dict(CONTEXT["step"], previous="msg with {{ project.budget }} inside"))
    r = make(ctx=ctx)
    assert r.render("{{ step.previous }}") == "msg with {{ project.budget }} inside"


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory):
    root = str(tmp_path_factory.mktemp("spec"))
    fixtures.write_spec(root, gates={"PLAN-AGENTS-GATE": 1, "SPEC-TO-TESTS-GATE": 1})
    return root


def test_every_fixture_prompt_renders_with_the_contract_lines(fixture_repo):
    cfg = configmod.load(fixture_repo)
    rendered = doctor.render_all(cfg, fixture_repo)
    assert set(rendered) == {s.name for s in pipeline.PIPELINE if s.kind in pipeline.AGENT_KINDS + ("plan",)}
    header = prompts.agents_md(cfg, fixture_repo)
    for name, r in rendered.items():
        assert r.get("error") is None and r["unresolved"] == [], (name, r)
        text = r["text"]
        assert text.startswith(header.rstrip("\n") + "\n\n")
        body = text[len(header):]
        assert "{{" not in body, name
        keys = contract.parse(text)
        assert keys["STEP"] == name
        if name == "CHAT-TO-PLAN":
            assert keys["KIND"] == "plan"
            continue
        kind = pipeline.step(name).kind
        assert keys["KIND"] == ("gate" if kind == "gate" else "producer")
        assert keys["ATTEMPT"] == "1" and keys["ROUND"] == "0001"
        assert os.path.isabs(keys["WORKTREE"]) and os.path.isabs(keys["HARNESS"]) and os.path.isabs(keys["RESULT_FILE"])
        assert text.count("PROCESS INSTRUCTIONS (mechanical") == 1
        if kind == "gate":
            assert "DIFF_FILE" in keys and "WRITE_PATHS" not in keys
        else:
            assert "WRITE_PATHS" in keys and "FROZEN_PATHS" in keys and "MERGE_IN_PROGRESS" in keys


def test_fixture_gate_prose_note_follows_the_gate_flag(fixture_repo):
    cfg = configmod.load(fixture_repo)
    rendered = doctor.render_all(cfg, fixture_repo)
    assert render.DISABLED_NOTE not in rendered["PLAN-AGENTS"]["text"]
    assert render.DISABLED_NOTE in rendered["PLAN-TO-SPEC"]["text"]
    assert prompts.CHAT_GATE_SENTENCE in rendered["CHAT-TO-PLAN"]["text"]
    assert "PLAN-AGENTS-GATE: fixture gate prose." in rendered["PLAN-AGENTS"]["text"]


def test_step_table_reports_the_approval_gate_as_not_running():
    data = dict(configmod.DEFAULTS, gates={"CHAT-TO-PLAN-GATE": 1, "PLAN-AGENTS-GATE": 1})
    cfg = configmod.Config(os.path.join("r", "harness"), data, {}, [], fixtures.ROSTER)
    rows = {row["step"]: row for row in prompts.step_table(cfg, overrides=["PLAN-AGENTS"])}
    assert rows["CHAT-TO-PLAN"]["gate"] == "CHAT-TO-PLAN-GATE" and rows["CHAT-TO-PLAN"]["gate_runs"] is False, "mechanical: no agent, no gate share"
    assert rows["PLAN-AGENTS"]["gate_runs"] is False and rows["PLAN-AGENTS"]["overridden"] is True
    rows = {row["step"]: row for row in prompts.step_table(cfg)}
    assert rows["PLAN-AGENTS"]["gate_runs"] is True and rows["CLEANUP"]["gate"] is None and rows["CLEANUP"]["gate_runs"] is False


def test_step_context_write_paths_and_inputs():
    cfg = configmod.Config(os.path.join("r", "harness"), dict(configmod.DEFAULTS), {}, [], fixtures.ROSTER)
    paths = cfg.round_paths(2)
    spec = {"implPaths": ["../src/"], "testPaths": ["../tests/"], "verify": ["x"]}
    impl = prompts.step_context(cfg, "SPEC-TO-IMPLEMENTATION", 3, paths, "wt", "h", spec=spec, frozen=True, conflicts=["../src/a.py"], merge=True)
    assert impl["write_paths"] == ["../src/", "../src/a.py", paths["folder"]] and impl["frozen_paths"] == ["../tests/"]
    assert impl["conflicts"] == ["../src/a.py"] and "L3" in impl["checks"] and impl["artifact"] == "a diff under WRITE_PATHS"
    cleanup = prompts.step_context(cfg, "CLEANUP", 1, paths, "wt", "h", spec=spec)
    assert cleanup["write_paths"] == ["../src/", "src/", "docs/", "tests/", "INDEX.md", paths["folder"]]
    gate = prompts.step_context(cfg, "SPEC-TO-TESTS-GATE", 2, paths, "wt", "h", spec=spec)
    assert gate["diff_file"].endswith("SPEC-TO-TESTS-GATE-2.diff") and gate["write_paths"] == []
    assert paths["results"] + "/SPEC-TO-TESTS-2.json" in gate["inputs"]
    pm = prompts.step_context(cfg, "POSTMORTEM", 1, paths, "wt", "h")
    assert pm["write_paths"] == [paths["folder"], "docs/TODO.md", "docs/CLARIFICATIONS.md"]
    assert paths["history"] in pm["inputs"] and "docs/TODO.md" in pm["inputs"]
