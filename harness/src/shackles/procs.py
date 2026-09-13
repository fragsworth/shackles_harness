"""Process, file and time helpers shared by every module; Windows first."""
import datetime
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time

WINDOWS = os.name == "nt"
TS = "%Y-%m-%dT%H:%M:%SZ"


class Completed:
    def __init__(self, code, out, err, timed_out=False):
        self.code, self.out, self.err, self.timed_out = code, out, err, timed_out

    @property
    def ok(self):
        return self.code == 0 and not self.timed_out


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime(TS)


def parse_ts(text):
    return datetime.datetime.strptime(text, TS).replace(tzinfo=datetime.timezone.utc)


def hours_between(start, end):
    return (parse_ts(end) - parse_ts(start)).total_seconds() / 3600.0


def child_env(scrub=(), extra=None, base=None):
    env = dict(os.environ if base is None else base)
    for key in scrub:
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env.update(extra or {})
    return env


def kill_tree(proc):
    if WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.kill()


def run(argv, cwd, env=None, timeout=None, stdin_text=None):
    proc = subprocess.Popen(
        [str(a) for a in argv], cwd=cwd, env=env,
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        start_new_session=not WINDOWS)
    try:
        out, err = proc.communicate(stdin_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        out, err = proc.communicate()
        return Completed(-1, out or "", err or "", True)
    return Completed(proc.returncode, out or "", err or "")


def normalize_text(text):
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return normalize_text(f.read())


def read_bytes_normalized(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_file(path):
    return hashlib.sha256(read_bytes_normalized(path)).hexdigest()


def sha256_text(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def write_text(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    for i in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1 * (i + 1))
    os.replace(tmp, path)


def append_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_json(path):
    return json.loads(read_text(path))


def dumps(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write_json(path, obj):
    write_text(path, dumps(obj))


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))


def _onexc(func, path, exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path):
    if os.path.exists(path):
        shutil.rmtree(path, onexc=_onexc)


def posix(path):
    return path.replace("\\", "/")


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def under(path, prefix):
    """True when posix path `path` is `prefix` or lies under it (by parts, so src/ never matches src2/)."""
    from pathlib import PurePosixPath
    p, q = PurePosixPath(posix(path)).parts, PurePosixPath(posix(prefix)).parts
    return len(p) >= len(q) and p[:len(q)] == q


def words(text):
    return len(text.split())
