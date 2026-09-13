"""Structural checks of the owner's spec: files present, gates and prose names line up, every prompt renders.
No test here asserts on any sentence of the owner's prose."""
import os

import yaml

from shackles import config as configmod
from shackles import doctor, pipeline, prompts, specguard

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))


def test_every_listed_spec_file_exists_and_loads():
    files = specguard.spec_files(REPO_ROOT)
    assert files, "spec.yaml lists no files"
    for rel in files:
        path = os.path.join(REPO_ROOT, rel)
        assert os.path.exists(path), rel
        text = open(path, encoding="utf-8").read()
        if rel.endswith((".yaml", ".yml")):
            assert isinstance(yaml.safe_load(text), dict), rel
        else:
            assert text.strip(), rel


def test_pipeline_gates_match_the_gates_map_in_order():
    cfg = configmod.load(REPO_ROOT)
    keys = [k for k in cfg.gates if k in pipeline.gates()]
    assert keys == pipeline.gates()
    assert set(cfg.gates) == set(pipeline.gates())


def test_prose_files_map_to_steps_and_every_step_has_prose():
    cfg = configmod.load(REPO_ROOT)
    names = prompts.prose_names(cfg, REPO_ROOT)
    for name in names:
        assert pipeline.prose_owner(name) is not None, f"prose file {name} maps to no pipeline step"
    for s in pipeline.PIPELINE:
        expected = pipeline.prose_file(s.name)
        if expected:
            assert expected in names, expected


def test_roster_keys_referenced_exist():
    cfg = configmod.load(REPO_ROOT)
    for key in ("maxAgent", "gateAgent", "systemTestAgent"):
        assert cfg[key] in cfg.agents, key
    for rung, entry in cfg.agents.items():
        for field in ("model", "effort", "inputUsdPerMTok", "outputUsdPerMTok", "spawnCost"):
            assert field in entry, (rung, field)


def test_lint_is_clean_on_the_real_repository():
    cfg = configmod.load(REPO_ROOT)
    present = {f: os.path.exists(os.path.join(REPO_ROOT, f)) for f in specguard.spec_files(REPO_ROOT)}
    errors, _ = pipeline.lint(cfg, prompts.prose_names(cfg, REPO_ROOT), present)
    assert errors == []


def test_every_prompt_renders_without_unresolved_tokens():
    cfg = configmod.load(REPO_ROOT)
    waived = doctor.waivers(REPO_ROOT)
    rendered = doctor.render_all(cfg, REPO_ROOT)
    header = prompts.agents_md(cfg, REPO_ROOT)
    for name, r in rendered.items():
        assert r.get("error") is None, (name, r.get("error"))
        unresolved = [t for t in r["unresolved"] if t not in waived]
        assert unresolved == [], (name, unresolved)
        body = r["text"][len(header):]
        assert "{{" not in body, name
