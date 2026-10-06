"""A local web page that drives the pipeline: a YouTube link, an uploaded file, or a video
picked from Google Photos in, the tab out.

Standard library only. Listens on 127.0.0.1 and refuses requests from other sites' pages
(Host and Origin checks): it downloads what it's given and holds a Google sign-in."""

import hashlib
import json
import queue
import re
import secrets
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import audio, pipeline
from .gphotos import GooglePhotos
from .separate import MELODY_STEMS

STATIC = Path(__file__).parent / "static"
# The only files the page may fetch from a song's output folder.
FILES = {
    "tab.txt": "text/plain; charset=utf-8",
    "tab.musicxml": "application/vnd.recordare.musicxml+xml",
    "preview.wav": "audio/wav",
    "report.json": "application/json",
}
MEDIA_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".3gp", ".mp3", ".m4a", ".wav",
             ".flac", ".ogg", ".opus", ".aac"}
MAX_UPLOAD = 4 << 30  # 4 GB
_YOUTUBE = re.compile(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/")
_GOOGLE_PHOTOS = re.compile(r"^https?://(photos\.google\.com|photos\.app\.goo\.gl)/")
_SONG_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_UPLOAD_ID = re.compile(r"^[0-9a-f]{16}\.[a-z0-9]{2,4}$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


class Jobs:
    """Runs one song at a time (the GPU can't share) and remembers each song's progress."""

    def __init__(self, work: Path, out: Path):
        self.work, self.out = work, out
        self.uploads = work / "uploads"
        self.state: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.queue: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, source: str, opts: pipeline.Options, rerun: bool, sid: str | None = None,
               title: str | None = None, prepare=None) -> tuple[str, bool]:
        """Queues a song. `prepare(log)`, if given, runs first in the worker (e.g. a
        download) and returns the source to use. Returns (song id, whether it was queued)."""
        sid = sid or audio.song_id(source)
        with self.lock:
            cur = self.state.get(sid)
            if cur and cur["status"] in ("queued", "running"):
                return sid, False
            if not rerun and (self.out / sid / "report.json").exists() and not cur:
                return sid, False  # already made; the page loads it
            self.state[sid] = {"status": "queued", "log": [], "error": None}
        if title:
            (self.work / sid).mkdir(parents=True, exist_ok=True)
            (self.work / sid / "title.txt").write_text(title)
        self.queue.put((sid, source, opts, prepare))
        return sid, True

    def status(self, sid: str) -> dict:
        with self.lock:
            st = dict(self.state.get(sid) or {})
        report = self.out / sid / "report.json"
        if not st:
            st = {"status": "done" if report.exists() else "unknown", "log": []}
        if st["status"] == "done" and report.exists():
            st["report"] = json.loads(report.read_text())
            st["tab"] = (self.out / sid / "tab.txt").read_text()
        st["position"] = self._position(sid) if st["status"] == "queued" else 0
        return st

    def history(self) -> list[dict]:
        rows = []
        for report in self.out.glob("*/report.json"):
            s = json.loads(report.read_text())["summary"]
            rows.append({"song_id": s["song_id"], "title": s["title"],
                         "overall": s["overall"], "sections": s["sections"],
                         "made": report.stat().st_mtime})
        return sorted(rows, key=lambda r: -r["made"])

    def save_upload(self, stream, length: int, filename: str) -> str:
        """Streams an upload to work/uploads/<content hash>.<ext>; returns that name."""
        ext = Path(filename).suffix.lower()
        if ext not in MEDIA_EXT:
            raise ValueError(f"unsupported file type {ext or '(none)'}; use a video or audio file")
        if not 0 < length <= MAX_UPLOAD:
            raise ValueError("file is empty or over 4 GB")
        self.uploads.mkdir(parents=True, exist_ok=True)
        tmp = self.uploads / f"tmp-{secrets.token_hex(8)}"
        h = hashlib.sha256()
        left = length
        try:
            with open(tmp, "wb") as f:
                while left:
                    chunk = stream.read(min(left, 1 << 20))
                    if not chunk:
                        raise ValueError("upload was cut off")
                    h.update(chunk)
                    f.write(chunk)
                    left -= len(chunk)
            name = h.hexdigest()[:16] + ext
            tmp.replace(self.uploads / name)
        finally:
            tmp.unlink(missing_ok=True)
        return name

    def _position(self, sid: str) -> int:
        with self.queue.mutex:
            ids = [item[0] for item in self.queue.queue]
        return ids.index(sid) + 1 if sid in ids else 0

    def _worker(self):
        while True:
            sid, source, opts, prepare = self.queue.get()
            self._set(sid, status="running")

            def log(msg, sid=sid):
                line = f"[{time.strftime('%H:%M:%S')}] {msg}"
                print(line, flush=True)
                with self.lock:
                    self.state[sid]["log"].append(line)

            try:
                if prepare:
                    source = prepare(log)
                if (self.out / sid / "report.json").exists():
                    log("re-running (cached steps are reused)")
                pipeline.run(source, opts, self.work, self.out, log=log, song_id=sid)
                self._set(sid, status="done")
            except Exception as e:  # noqa: BLE001 - report any failure to the page
                traceback.print_exc()
                self._set(sid, status="error", error=f"{type(e).__name__}: {e}")

    def _set(self, sid, **kw):
        with self.lock:
            self.state[sid].update(kw)


def _options(body: dict) -> pipeline.Options:
    """Options from the page, validated. Separation and the CREPE model aren't offered."""
    raw = body.get("options") or {}

    def num(key, cast, ok):
        v = raw.get(key)
        if v in ("", None):
            return None
        v = cast(v)
        if not ok(v):
            raise ValueError(f"bad {key}")
        return v

    stem = raw.get("stem") or "auto"
    if stem not in ("auto",) + MELODY_STEMS:
        raise ValueError("bad stem")
    return pipeline.Options(
        stem=stem,
        key_change=bool(raw.get("key_change")),
        bpm=num("bpm", float, lambda v: 30 <= v <= 300),
        beats_per_bar=num("beats_per_bar", int, lambda v: 2 <= v <= 7),
        subdivision=num("subdivision", int, lambda v: v in (3, 4)),
    )


def _clean_title(name: str) -> str:
    return re.sub(r"\s+", " ", Path(name).stem.replace("_", " ")).strip()[:120] or "Untitled"


def make_handler(jobs: Jobs, google: GooglePhotos, port: int):
    hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
    origins = {f"http://{h}" for h in hosts}

    def picked_job(session_id: str, opts, rerun: bool) -> str:
        item = google.picked_video(session_id)
        sid = "gp-" + hashlib.sha256(item["id"].encode()).hexdigest()[:12]
        ext = Path(item["filename"]).suffix.lower()
        dest = jobs.uploads / (sid + (ext if ext in MEDIA_EXT else ".mp4"))

        def prepare(log):
            if not dest.exists():
                log(f"downloading {item['filename']} from Google Photos")
                google.download(item["baseUrl"], dest)
            google.end_session(session_id)
            return str(dest)

        sid, queued = jobs.submit(str(dest), opts, rerun, sid=sid,
                                  title=_clean_title(item["filename"]), prepare=prepare)
        if not queued:
            google.end_session(session_id)
        return sid

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal for pipeline progress
            pass

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj):
            self._send(code, json.dumps(obj).encode(), "application/json")

        def _redirect(self, url: str):
            self._send(302, b"", "text/plain", {"Location": url})

        def _trusted(self) -> bool:
            """Only this page, opened from this machine. Blocks DNS rebinding (Host) and
            other websites posting to localhost (Origin)."""
            if self.headers.get("Host") not in hosts:
                self._json(403, {"error": "forbidden"})
                return False
            origin = self.headers.get("Origin")
            if self.command == "POST" and origin is not None and origin not in origins:
                self._json(403, {"error": "forbidden"})
                return False
            return True

        def do_GET(self):
            if not self._trusted():
                return
            path, _, query = self.path.partition("?")
            if path == "/":
                return self._send(200, (STATIC / "index.html").read_bytes(),
                                  "text/html; charset=utf-8")
            if path == "/api/history":
                return self._json(200, jobs.history())
            if path == "/api/google":
                return self._json(200, {"configured": google.configured,
                                        "signed_in": google.signed_in,
                                        "redirect_uri": google.redirect_uri})
            if path == "/auth/google":
                if not google.configured:
                    return self._json(400, {"error": "Google Photos isn't set up"})
                return self._redirect(google.auth_url())
            if path == "/auth/google/callback":
                q = urllib.parse.parse_qs(query)
                try:
                    if "error" in q:
                        raise RuntimeError(q["error"][0])
                    google.finish_sign_in(q.get("code", [""])[0], q.get("state", [""])[0])
                except Exception as e:  # noqa: BLE001 - shown on the page
                    return self._redirect("/#google-error=" + urllib.parse.quote(str(e)))
                return self._redirect("/#google-ready")
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "jobs"] and _SONG_ID.match(parts[2]):
                return self._json(200, jobs.status(parts[2]))
            if len(parts) == 4 and parts[:3] == ["api", "google", "session"] \
                    and _SESSION_ID.match(parts[3]):
                try:
                    s = google.session(parts[3])
                except Exception as e:  # noqa: BLE001
                    return self._json(502, {"error": str(e)})
                return self._json(200, {"mediaItemsSet": bool(s.get("mediaItemsSet"))})
            if len(parts) == 3 and parts[0] == "files" and _SONG_ID.match(parts[1]) \
                    and parts[2] in FILES:
                f = jobs.out / parts[1] / parts[2]
                if f.exists():
                    return self._send(200, f.read_bytes(), FILES[parts[2]])
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._trusted():
                return
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            n = int(self.headers.get("Content-Length") or 0)
            if self.path == "/api/upload":
                # A custom header plus a non-form type means browsers preflight it, so
                # other sites can't send it at all.
                name = urllib.parse.unquote(self.headers.get("X-Filename") or "")
                if ctype != "application/octet-stream" or not name:
                    return self._json(400, {"error": "bad upload"})
                try:
                    upload = jobs.save_upload(self.rfile, n, name)
                except ValueError as e:
                    return self._json(400, {"error": str(e)})
                return self._json(200, {"upload": upload, "title": _clean_title(name)})
            if ctype != "application/json":
                return self._json(415, {"error": "expected JSON"})
            try:
                body = json.loads(self.rfile.read(min(n, 10_000)) or b"{}")
            except json.JSONDecodeError as e:
                return self._json(400, {"error": str(e)})
            if self.path == "/api/google/session":
                try:
                    s = google.new_session()
                except Exception as e:  # noqa: BLE001
                    return self._json(502, {"error": str(e)})
                interval = str(s.get("pollingConfig", {}).get("pollInterval", "3s"))
                return self._json(200, {"id": s["id"], "pickerUri": s["pickerUri"],
                                        "pollSeconds": max(1.0, float(interval.rstrip("s")))})
            if self.path != "/api/jobs":
                return self._json(404, {"error": "not found"})
            try:
                opts = _options(body)
                rerun = bool(body.get("rerun"))
                if body.get("upload"):
                    upload = str(body["upload"])
                    if not _UPLOAD_ID.match(upload) or not (jobs.uploads / upload).exists():
                        raise ValueError("upload not found; upload the file again")
                    sid, _ = jobs.submit(str(jobs.uploads / upload), opts, rerun,
                                         sid="up-" + upload.split(".")[0],
                                         title=str(body.get("title") or "")[:120] or None)
                elif body.get("google_session"):
                    session_id = str(body["google_session"])
                    if not _SESSION_ID.match(session_id):
                        raise ValueError("bad session")
                    sid = picked_job(session_id, opts, rerun)
                else:
                    url = str(body.get("url", "")).strip()
                    if _GOOGLE_PHOTOS.match(url):
                        raise ValueError("Google Photos links only open when you're signed "
                                         "in; use “Pick from Google Photos” instead")
                    if not _YOUTUBE.match(url):
                        raise ValueError("paste a youtube.com or youtu.be link")
                    sid, _ = jobs.submit(url, opts, rerun)
            except (ValueError, TypeError) as e:
                return self._json(400, {"error": str(e)})
            except (PermissionError, RuntimeError) as e:
                return self._json(502, {"error": str(e)})
            self._json(202, {"song_id": sid})

    return Handler


def serve(port: int, work: Path, out: Path) -> None:
    jobs = Jobs(work, out)
    google = GooglePhotos(port)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(jobs, google, port))
    print(f"Mandolin tab maker: http://localhost:{port}  (Ctrl+C to stop)", flush=True)
    if not google.configured:
        print("  Google Photos: off (set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in "
              ".env.local to turn it on)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
