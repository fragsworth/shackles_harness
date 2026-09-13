"""The documents: INDEX aliases resolve, every command and config key is documented, the definitions match the roster."""
import os
import re

import fixtures
from shackles import agentdefs, cli, config as configmod

REPO_ROOT = fixtures.REPO_ROOT
HARNESS = os.path.join(REPO_ROOT, "harness")


def read(rel):
    return open(os.path.join(HARNESS, rel), encoding="utf-8").read()


def test_index_aliases_resolve():
    lines = [l for l in read("INDEX.md").splitlines() if " -> " in l]
    assert len(lines) >= 12
    for line in lines:
        aliases, _, targets = line.partition(" -> ")
        assert aliases.strip() and all(a.strip() for a in aliases.split(","))
        for target in targets.split(","):
            path = os.path.join(HARNESS, *target.strip().split("/"))
            assert os.path.exists(path), target


def test_every_cli_command_is_documented():
    parser = cli.build_parser()
    commands = [a for a in parser._subparsers._group_actions[0].choices]
    text = read("docs/DRIVER.md") + read("docs/PROCESS.md")
    for command in commands:
        assert re.search(rf"`{re.escape(command)}\b", text) or f"`{command}" in text, command


def test_every_defaults_key_appears_in_process_md():
    text = read("docs/PROCESS.md")
    for key in configmod.DEFAULTS:
        assert f"`{key}`" in text, key


def test_line_limits_and_one_sentence_per_line():
    assert len(read("docs/PROCESS.md").splitlines()) <= 200
    assert len(read("docs/DRIVER.md").splitlines()) <= 80
    assert len(read("docs/TESTING.md").splitlines()) <= 80
    assert len(read("INDEX.md").splitlines()) <= 40
    assert len(open(os.path.join(REPO_ROOT, "CLAUDE.md"), encoding="utf-8").read().splitlines()) <= 3


def test_agent_definitions_committed_and_hook_configured():
    cfg = configmod.load(REPO_ROOT)
    assert agentdefs.drift(cfg, REPO_ROOT) == []
    from shackles import doctor
    assert doctor.hook_configured(REPO_ROOT)


def test_carry_forward_files_exist_with_one_header_line():
    for rel in configmod.DEFAULTS["carryForwardFiles"]:
        text = read(rel)
        assert text.splitlines()[0].startswith("# ")
