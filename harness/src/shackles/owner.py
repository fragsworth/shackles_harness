"""The owner log: hook line format, the round's slice, quote verification."""
import os

from . import procs

LOG_REL = os.path.join("harness", "OWNER.log")


def escape(message):
    return message.replace("\\", "\\\\").replace("\n", "\\n")


def unescape(text):
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            out.append("\n" if text[i + 1] == "n" else text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def normalize(text):
    return " ".join((text or "").split())


def is_envelope(prompt, prefixes):
    return prompt.lstrip().startswith(tuple(prefixes))


def parse_line(line):
    if "\t" not in line:
        return None
    ts, _, message = line.rstrip("\n").partition("\t")
    return (ts, message) if len(ts) == 20 and ts.endswith("Z") else None


def read_log(path):
    if not path or not os.path.exists(path):
        return None
    return [p for p in (parse_line(l) for l in procs.read_text(path).splitlines()) if p]


def log_path(main_root):
    return os.path.join(main_root, LOG_REL)


def append_line(path, message, at=None, tag=None):
    line = f"{at or procs.now()}\t{tag + chr(9) if tag else ''}{escape(message)}\n"
    procs.append_text(path, line)
    return line


def slice_since(path, since, prefixes=()):
    """Log lines dated at or after `since` (all when since is None), envelopes filtered."""
    lines = read_log(path) or []
    out = []
    for ts, message in lines:
        if since and ts < since:
            continue
        if prefixes and is_envelope(unescape(message), prefixes):
            continue
        out.append(f"{ts}\t{message}")
    return out


def verify_quote(path, quote, after):
    """True when the whitespace-normalized quote occurs in a line dated at or after `after`; None without a log."""
    lines = read_log(path)
    if lines is None:
        return None
    wanted = normalize(quote)
    for ts, message in lines:
        if after and ts < after:
            continue
        if wanted and wanted in normalize(unescape(message)):
            return True
    return False
