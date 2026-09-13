"""The {{ ns.key }} engine: prose includes once per document, plumbing blocks, dotted context lookups."""
import json
import re

TOKEN = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")
MAX_DEPTH = 8
MISSING = object()
DISABLED_NOTE = ("(This gate is disabled this round: a DONE that passes the mechanical checks is accepted. "
                 "The standard below still applies.)")
KIND_FILES = {"producer": "producer", "code": "producer", "gate": "gate", "plan": None}


def fmt(value):
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = repr(value)
        return text[:-2] if text.endswith(".0") else text
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def lookup(context, ns, key):
    node = context.get(ns, MISSING)
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return MISSING
    return node


class Renderer:
    """One document: `prose(name)` and `plumbing(name)` return text or None; `context` holds the namespaces."""

    def __init__(self, prose, plumbing, context, kind, step_name, gate_name=None, gate_note=None, gate_sentence=None):
        self.prose, self.plumbing, self.context = prose, plumbing, context
        self.kind, self.step_name, self.gate_name = kind, step_name, gate_name
        self.gate_note, self.gate_sentence = gate_note, gate_sentence
        self.rendered, self.stack, self.unresolved, self.warnings = set(), [], [], []
        self.process_rendered = False

    def miss(self, token):
        self.unresolved.append(token)
        return f"[unresolved: {token}]"

    def render(self, text, depth=0, embed=False):
        def sub(match):
            token = match.group(1)
            ns, _, key = token.partition(".")
            if ns == "prose":
                return self.prose_token(key, depth, embed)
            if ns == "plumbing":
                return self.plumbing_token(key, depth, embed)
            if ns in self.context and key:
                value = lookup(self.context, ns, key)
                return self.miss(token) if value is MISSING else fmt(value)
            return self.miss(token)
        return TOKEN.sub(sub, text)

    def prose_token(self, name, depth, embed):
        if name in self.stack:
            return f"[cycle: {name}]"
        if depth >= MAX_DEPTH:
            self.warnings.append(f"include depth exceeded at prose.{name}")
            return f"[depth: {name}]"
        if name in self.rendered:
            return ""
        text = self.prose(name)
        if text is None:
            return self.miss(f"prose.{name}")
        self.rendered.add(name)
        self.stack.append(name)
        try:
            return self.render(text, depth + 1, embed)
        finally:
            self.stack.pop()

    def process_block(self, depth):
        parts = []
        base = KIND_FILES.get(self.kind)
        if base:
            text = self.plumbing(base)
            if text is not None:
                parts.append(self.render(text, depth + 1))
        extra = self.plumbing(self.step_name)
        if extra is not None:
            parts.append(self.render(extra, depth + 1))
        self.process_rendered = True
        return "\n".join(p.rstrip("\n") for p in parts)

    def gate_prose(self, depth):
        if self.gate_sentence:
            return self.gate_sentence
        text = self.prose(self.gate_name) if self.gate_name else None
        if text is None:
            return self.miss(f"prose.{self.gate_name}") if self.gate_name else ""
        body = self.render(text, depth + 1, embed=True)
        return (self.gate_note + "\n" + body) if self.gate_note else body

    def plumbing_token(self, name, depth, embed):
        if name == "PROCESS-INSTRUCTIONS":
            return "" if embed else self.process_block(depth)
        if name == "GATE-PROSE":
            return "" if embed else self.gate_prose(depth)
        text = self.plumbing(name)
        if text is None:
            return self.miss(f"plumbing.{name}")
        return self.render(text, depth + 1, embed)


def assemble(header, prose_text, renderer):
    """A prompt: the raw header (AGENTS.md), a blank line, the rendered prose, the process block appended if absent."""
    body = renderer.render(prose_text)
    if not renderer.process_rendered:
        renderer.warnings.append("prose has no plumbing.PROCESS-INSTRUCTIONS token; the block was appended")
        body = body.rstrip("\n") + "\n\n" + renderer.process_block(0)
    return header.rstrip("\n") + "\n\n" + body.rstrip("\n") + "\n"
