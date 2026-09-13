"""Per-rung agent definitions under .claude/agents/, generated from the roster; the driver spawns them by name."""
import os

from . import procs

DIR = os.path.join(".claude", "agents")
GATE_BODY = ("You are a read-only gate of the shackles harness.\n"
             "Your entire instructions are the prompt file named in your task: read it first and follow it exactly.\n"
             "Write nothing, run nothing that changes files, and end with exactly the JSON object the prompt specifies and nothing else.\n")
PRODUCER_BODY = ("You are a producer step of the shackles harness.\n"
                 "Your entire instructions are the prompt file named in your task: read it first and follow it exactly.\n"
                 "Change files only under its WRITE_PATHS and the round folder, never run git commit, push, tag, reset, checkout, "
                 "clean, merge or rebase, and end with exactly the JSON object the prompt specifies and nothing else.\n")


def definition(cfg, kind, rung, entry):
    alias = cfg.model_alias(entry.get("model", ""))
    lines = ["---", f"name: shackles-{kind}-{rung}",
             f"description: {'Read-only gate' if kind == 'gate' else 'Producer step'} of the shackles harness at rung {rung} "
             f"({entry.get('model')}, effort {entry.get('effort')}); spawned by the driver with a prompt file as its task.",
             f"model: {alias}", f"effort: {entry.get('effort')}"]
    if kind == "gate":
        lines.append("tools: " + ", ".join(str(t) for t in cfg["gateToolFlags"][1:]))
    else:
        patterns = [str(p) for p in cfg["producerToolFlags"] if not str(p).startswith("--")]
        lines.append("disallowedTools: " + ", ".join(patterns))
    lines.append("---")
    return "\n".join(lines) + "\n\n" + (GATE_BODY if kind == "gate" else PRODUCER_BODY)


def expected(cfg):
    out = {}
    for rung, entry in cfg.agents.items():
        for kind in ("producer", "gate"):
            out[f"shackles-{kind}-{rung}.md"] = definition(cfg, kind, rung, entry)
    return out


def write(cfg, root):
    folder = os.path.join(root, DIR)
    written = []
    for name, text in expected(cfg).items():
        procs.write_text(os.path.join(folder, name), text)
        written.append(os.path.join(DIR, name).replace("\\", "/"))
    return written


def drift(cfg, root):
    folder = os.path.join(root, DIR)
    out = []
    for name, text in expected(cfg).items():
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            out.append(f"{name} missing (run agents --write)")
        elif procs.read_text(path) != text:
            out.append(f"{name} differs from the roster (run agents --write)")
    return out
