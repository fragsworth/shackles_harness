import os

import pytest
import yaml

from shackles import config
from shackles.gitops import RunnerError


def make(tmp_path, project=None, local=None, roster=None):
    h = tmp_path / "harness"
    h.mkdir(exist_ok=True)
    if project is not None:
        (h / "project.yaml").write_text(project if isinstance(project, str) else yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    if local is not None:
        (h / "local.yaml").write_text(yaml.safe_dump(local, sort_keys=False), encoding="utf-8")
    if roster is not None:
        (h / "subAgents.yaml").write_text(yaml.safe_dump({"agents": roster}, sort_keys=False), encoding="utf-8")
    return config.load(str(tmp_path))


ROSTER = {"max": {"model": "m-max", "effort": "max", "spawnCost": 0.2}, "low": {"model": "m-low", "effort": "low", "spawnCost": 0.02}}


def test_layering_and_sources(tmp_path):
    cfg = make(tmp_path, project={"budget": 10, "pushAttempts": 2}, local={"pushAttempts": 7, "claudePath": "x"}, roster=ROSTER)
    assert cfg["budget"] == 10 and cfg.sources["budget"] == "project.yaml"
    assert cfg["pushAttempts"] == 7 and cfg.sources["pushAttempts"] == "local.yaml"
    assert cfg["claudePath"] == "x"
    assert cfg["infraRetries"] == 3 and cfg.sources["infraRetries"] == "default"


def test_every_key_defaults_when_project_is_empty(tmp_path):
    cfg = make(tmp_path, project="", roster=ROSTER)
    for key in config.DEFAULTS:
        assert cfg[key] == config.DEFAULTS[key]
    assert not (cfg.warnings and "missing" in cfg.warnings[0] and "project.yaml" in cfg.warnings[0])


def test_missing_project_file_warns_and_defaults(tmp_path):
    cfg = make(tmp_path, roster=ROSTER)
    assert cfg["mainBranch"] == "main"
    assert any("project.yaml missing" in w for w in cfg.warnings)


def test_unknown_keys_kept(tmp_path):
    cfg = make(tmp_path, project={"ownerExtra": 5}, roster=ROSTER)
    assert cfg["ownerExtra"] == 5 and cfg.sources["ownerExtra"] == "project.yaml"


def test_type_mismatch_is_a_usage_error_naming_the_key(tmp_path):
    with pytest.raises(RunnerError) as exc:
        make(tmp_path, project={"pushAttempts": "five"}, roster=ROSTER)
    assert "pushAttempts" in str(exc.value) and exc.value.code == 2


def test_id_width_from_the_n_run(tmp_path):
    cfg = make(tmp_path, project={"roundPaths": {"folder": "archives/rounds/NNN/"}}, roster=ROSTER)
    assert cfg.id_width == 3 and cfg.round_id(7) == "007" and cfg.round_folder(7) == "archives/rounds/007"
    cfg = make(tmp_path, project={"roundPaths": {"folder": "rounds/r-NNNNN"}}, roster=ROSTER)
    assert cfg.round_folder(12) == "rounds/r-00012"
    cfg = make(tmp_path, project={"roundPaths": {"folder": "rounds/plain/"}}, roster=ROSTER)
    assert cfg.id_width == 4 and cfg.round_folder(1) == "archives/rounds/0001"
    assert any("N-run" in w for w in cfg.warnings)


def test_round_paths_fill_missing_entries(tmp_path):
    cfg = make(tmp_path, project={"roundPaths": {"folder": "archives/rounds/NNNN/", "artifacts": {"plan": "P.json"}}}, roster=ROSTER)
    paths = cfg.round_paths(3)
    assert paths["plan"] == "archives/rounds/0003/P.json"
    assert paths["state"] == "archives/rounds/0003/STATE.json"
    assert paths["prompts"] == "archives/rounds/0003/PROMPTS"
    assert any("roundPaths.runner.state missing" in w for w in cfg.warnings)


def test_gates_coercion_and_order(tmp_path):
    cfg = make(tmp_path, project={"gates": {"B-GATE": 1, "A-GATE": 0, "C-GATE": 2}}, roster=ROSTER)
    assert list(cfg.gates) == ["B-GATE", "A-GATE", "C-GATE"]
    assert cfg.gates == {"B-GATE": True, "A-GATE": False, "C-GATE": True}
    assert cfg.gate_enabled("MISSING-GATE") is False
    assert any("C-GATE" in w for w in cfg.warnings)


def test_roster_fallbacks_warn(tmp_path):
    cfg = make(tmp_path, project={"maxAgent": "max"}, roster=ROSTER)
    assert cfg.rung("low")[0] == "low"
    assert cfg.rung("nope")[0] == "max" and any("nope" in w for w in cfg.warnings)
    cfg = make(tmp_path, project={"maxAgent": "gone"}, roster=ROSTER)
    assert cfg.rung("nope")[0] == "max" and any("first roster key" in w for w in cfg.warnings)
    assert any("maxAgent 'gone'" in w for w in cfg.warnings)


def test_repo_relative_paths_allow_parent_but_not_escape(tmp_path):
    cfg = make(tmp_path, project={}, roster=ROSTER)
    assert cfg.repo_rel("../src/") == "src"
    assert cfg.repo_rel("src/") == "harness/src"
    assert cfg.repo_rel("archives/rounds/0001/SPEC.json") == "harness/archives/rounds/0001/SPEC.json"
    with pytest.raises(RunnerError):
        cfg.repo_rel("../../outside")
    assert not os.path.isabs(cfg.repo_rel("docs/"))


def test_bom_and_crlf_project_file(tmp_path):
    text = "﻿budget: 42\r\nmainBranch: trunk\r\n"
    cfg = make(tmp_path, project=text, roster=ROSTER)
    assert cfg["budget"] == 42 and cfg["mainBranch"] == "trunk"


def test_model_alias(tmp_path):
    cfg = make(tmp_path, project={}, roster=ROSTER)
    assert cfg.model_alias("claude-fable-5-1") == "fable"
    assert cfg.model_alias("other") == "other"
