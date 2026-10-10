"""`mtab app`: the tab maker's page and its API on http://localhost:8765.

One Python process does it all, so running the app needs no Node.js: it serves the page
(the Next.js UI exported by `npm run build` into mtab/web/) and the JSON API the page
calls, and runs each tab as `python -m mtab.cli run <url> <flags>` in a child process,
one at a time (the GPU can't share). The child's timestamped `[HH:MM:SS]` lines become
the job's log and out/<song>/ its result.

The app downloads whatever link it's given, so it serves this machine only: it listens
on 127.0.0.1, and every API request is checked first (`refused`): the Host check blocks
DNS rebinding, the Origin check blocks other websites' pages posting to localhost.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent  # the app's folder: out/ and work/ live here
WEB = Path(__file__).resolve().parent / "web"  # the exported page (npm run build)
PORT = 8765

# The engine's melody stems: mtab/separate.py MELODY_STEMS (a test checks). Not imported
# from there, so the server starts without loading PyTorch.
MELODY_STEMS = ("vocals", "guitar", "piano", "other")

# The only files the page may fetch from a song's output folder.
FILES = {
    "tab.txt": "text/plain; charset=utf-8",
    "tab.musicxml": "application/vnd.recordare.musicxml+xml",
    "preview.wav": "audio/wav",
    "report.json": "application/json",
}

SONG_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
YOUTUBE = re.compile(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/")
# Same pattern as mtab/audio.py, so the song id here is the engine's folder name.
YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")
LOG_LINE = re.compile(r"^\[\d\d:\d\d:\d\d\] ")
LOCAL_HOST = re.compile(r"^(localhost|127\.0\.0\.1)(:\d+)?$")


class InputError(ValueError):
    """A bad link or option from the page: answered with 400 and its message."""


def video_id(url) -> str:
    """A YouTube video link -> its video id, or raises InputError."""
    u = str(url if url is not None else "").strip()
    if not YOUTUBE.match(u):
        raise InputError("paste a youtube.com or youtu.be link")
    m = YOUTUBE_ID.search(u)
    if not m:
        raise InputError("that YouTube link doesn't point at a video")
    return m.group(1)


def option_args(raw: dict | None) -> list[str]:
    """The page's options -> `mtab run` flags, or raises InputError. Separation and the
    pitch model aren't offered."""
    raw = raw or {}
    args: list[str] = []
    stem = raw.get("stem") or "auto"
    if stem != "auto" and stem not in MELODY_STEMS:
        raise InputError("bad stem")
    if stem != "auto":
        args += ["--stem", stem]
    if raw.get("key_change"):
        args.append("--key-change")

    def num(key, flag, ok):
        v = raw.get(key)
        if v in ("", None):
            return
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise InputError(f"bad {key}") from None
        if isinstance(v, bool) or n != n or not ok(n):
            raise InputError(f"bad {key}")
        args.extend([flag, str(int(n)) if n.is_integer() else str(n)])

    num("bpm", "--bpm", lambda v: 30 <= v <= 300)
    num("beats_per_bar", "--beats-per-bar", lambda v: v.is_integer() and 2 <= v <= 7)
    num("subdivision", "--grid", lambda v: v in (3, 4))
    return args


def _now() -> str:
    return time.strftime("%H:%M:%S")


def _spawn(cmd: list[str], cwd: Path, env: dict):
    return subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")


class Jobs:
    """The job queue, the songs made before, and their output files. The HTTP handler
    calls these, never the engine directly."""

    def __init__(self, root: Path = ROOT, spawn=_spawn, background: bool = True):
        self.out = Path(root) / "out"
        self.work = Path(root) / "work"
        self.root = Path(root)
        self.spawn = spawn
        self.background = background
        self.state: dict[str, dict] = {}  # id -> {status, log, error}
        self.queue: list[dict] = []  # [{id, url, args}]
        self.running: dict | None = None
        self.lock = threading.Condition()
        if background:
            threading.Thread(target=self._worker, daemon=True).start()

    def _report(self, sid: str) -> Path:
        return self.out / sid / "report.json"

    def submit(self, url, options=None, rerun: bool = False) -> str:
        """Queues a tab for a YouTube link. Returns the song id; a song already made (or in
        progress) isn't queued again unless rerun is set."""
        sid = video_id(url)
        args = option_args(options)
        with self.lock:
            cur = self.state.get(sid)
            if cur and cur["status"] in ("queued", "running"):
                return sid
            if not rerun and not cur and self._report(sid).exists():
                return sid  # the page loads it
            self.state[sid] = {"status": "queued", "log": [], "error": None}
            self.queue.append({"id": sid, "url": f"https://www.youtube.com/watch?v={sid}", "args": args})
            self.lock.notify()
        return sid

    def _worker(self) -> None:
        while True:
            with self.lock:
                while not self.queue:
                    self.lock.wait()
            self.run_next()

    def run_next(self) -> bool:
        """Runs the next queued job to the end (the worker thread's loop; tests call it
        directly). False when nothing was queued."""
        with self.lock:
            if not self.queue:
                return False
            job = self.running = self.queue.pop(0)
            st = self.state[job["id"]]
            st["status"] = "running"

        def log(line: str) -> None:
            print(line, flush=True)
            with self.lock:
                st["log"].append(line)

        if self._report(job["id"]).exists():
            log(f"[{_now()}] re-running (cached steps are reused)")
        cmd = [sys.executable, "-m", "mtab.cli", "run", job["url"], *job["args"],
               "--work", str(self.work), "--out", str(self.out)]
        # Unbuffered, so progress shows as it happens; UTF-8, so Windows' console encoding
        # can't break a log line.
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        error = None
        try:
            proc = self.spawn(cmd, self.root, env)
            tail: list[str] = []

            def drain_stderr():
                for line in proc.stderr:
                    sys.stderr.write(line)
                    tail.append(line)
                    del tail[:-50]

            t = threading.Thread(target=drain_stderr, daemon=True)
            t.start()
            for line in proc.stdout:
                line = line.rstrip("\r\n")
                if LOG_LINE.match(line):
                    log(line)
            code = proc.wait()
            t.join(timeout=5)
            if code != 0:
                # The traceback's last line, e.g. "RuntimeError: no melody found".
                last = [x.strip() for x in tail if x.strip()]
                error = last[-1] if last else f"the engine stopped (exit {code})"
        except OSError as e:
            error = str(e)
        with self.lock:
            st.update({"status": "error", "error": error} if error else {"status": "done"})
            self.running = None
        return True

    def status(self, sid: str) -> dict:
        with self.lock:
            cur = self.state.get(sid)
            st = {**cur, "log": list(cur["log"])} if cur else {}
            position = next((i + 1 for i, j in enumerate(self.queue) if j["id"] == sid), 0)
        report = self._report(sid)
        if not st:
            st = {"status": "done" if report.exists() else "unknown", "log": []}
        if st["status"] == "done" and report.exists():
            st["report"] = json.loads(report.read_text(encoding="utf-8"))
            st["tab"] = (self.out / sid / "tab.txt").read_text(encoding="utf-8")
        st["position"] = position if st["status"] == "queued" else 0
        return st

    def history(self) -> list[dict]:
        if not self.out.exists():
            return []
        rows = []
        for d in self.out.iterdir():
            report = self._report(d.name)
            if not (SONG_ID.match(d.name) and report.exists()):
                continue
            s = json.loads(report.read_text(encoding="utf-8"))["summary"]
            rows.append({"song_id": s["song_id"], "title": s.get("title"), "overall": s.get("overall"),
                         "sections": s["sections"], "made": report.stat().st_mtime * 1000})
        return sorted(rows, key=lambda r: r["made"], reverse=True)

    def file(self, sid: str, name: str) -> tuple[bytes, str] | None:
        """One of FILES from a song's output folder, or None."""
        if not SONG_ID.match(sid) or name not in FILES:
            return None
        f = self.out / sid / name
        return (f.read_bytes(), FILES[name]) if f.is_file() else None


def refused(method: str, headers, allowed_origins=()) -> tuple[int, str] | None:
    """None when the request is allowed, else (status, error)."""
    host = headers.get("Host") or ""
    origin = headers.get("Origin")
    ok = bool(LOCAL_HOST.match(host)) and (
        method in ("GET", "HEAD") or origin is None or origin == f"http://{host}" or origin in allowed_origins)
    return None if ok else (403, "forbidden")


def static_file(path: str, web: Path = WEB) -> Path | None:
    """The exported page's file for a URL path, or None. Never leaves web/."""
    rel = unquote(path).lstrip("/")
    base = web.resolve()
    for cand in (rel or "index.html", f"{rel}.html", f"{rel}/index.html"):
        f = (base / cand).resolve()
        if f.is_relative_to(base) and f.is_file():
            return f
    return None


def make_handler(jobs: Jobs, web: Path = WEB, allowed_origins=()):
    class Handler(BaseHTTPRequestHandler):
        server_version = "mtab"

        def log_message(self, fmt, *args):  # the job log is the useful output; keep requests quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def _guard(self) -> bool:
            r = refused(self.command, self.headers, allowed_origins)
            if r:
                self._json(r[0], {"error": r[1]})
            return r is None

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith("/api/"):
                if not self._guard():
                    return
                parts = path.split("/")[2:]
                if parts == ["history"]:
                    return self._json(200, jobs.history())
                if len(parts) == 2 and parts[0] == "jobs":
                    sid = unquote(parts[1])
                    if not SONG_ID.match(sid):
                        return self._json(404, {"error": "not found"})
                    return self._json(200, jobs.status(sid))
                if len(parts) == 3 and parts[0] == "files":
                    f = jobs.file(unquote(parts[1]), unquote(parts[2]))
                    return self._send(200, *f) if f else self._json(404, {"error": "not found"})
                return self._json(404, {"error": "not found"})
            if not LOCAL_HOST.match(self.headers.get("Host") or ""):
                return self._json(403, {"error": "forbidden"})
            f = static_file(path, web)
            if f:
                ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
                    ctype += "; charset=utf-8"
                # Built files under _next/ have hashed names; pages are always revalidated.
                cache = "public, max-age=31536000, immutable" if path.startswith("/_next/static/") else "no-cache"
                return self._send(200, f.read_bytes(), ctype, cache)
            if not (web / "index.html").exists():
                return self._send(500, b"The page isn't built: run `npm run build`.", "text/plain; charset=utf-8")
            missing = web / "404.html"
            body = missing.read_bytes() if missing.exists() else b"Not found"
            self._send(404, body, "text/html; charset=utf-8")

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self._guard():
                return
            if path != "/api/jobs":
                return self._json(404, {"error": "not found"})
            # JSON only: a form post from another page can't send this type without a preflight.
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json(415, {"error": "expected JSON"})
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 65536)
                body = json.loads(self.rfile.read(length) or b"null")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._json(400, {"error": "bad JSON"})
            try:
                sid = jobs.submit(body.get("url"), body.get("options"), bool(body.get("rerun")))
            except InputError as e:
                return self._json(400, {"error": str(e)})
            self._json(202, {"song_id": sid})

    return Handler


def _already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/history", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def serve(port: int = PORT, open_browser: bool = True, dev: bool = False) -> int:
    url = f"http://localhost:{port}"
    # `npm run dev`: the Next dev server on :3000 forwards /api here.
    origins = ("http://localhost:3000", "http://127.0.0.1:3000") if dev else ()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(Jobs(), allowed_origins=origins))
    except OSError:
        if _already_running(url):
            print(f"Mandolin Tab Maker is already running: {url}")
            if open_browser:
                webbrowser.open(url)
            return 0
        print(f"Port {port} is in use by another program. Try: mtab app --port {port + 1}", file=sys.stderr)
        return 1
    print(f"Mandolin Tab Maker is running at {url}", flush=True)
    print("Keep this window open while you use it. Close it (or press Ctrl+C) to stop.", flush=True)
    if open_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
