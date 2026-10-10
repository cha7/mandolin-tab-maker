import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from mtab import app
from mtab.app import InputError, Jobs, option_args, refused, static_file, video_id

YT = "https://www.youtube.com/watch?v=Xpkc-NU1KA0"


class FakeProc:
    """A stand-in for the engine's process: prints the given lines, exits with code."""

    def __init__(self, stdout=(), stderr=(), code=0):
        self.stdout, self.stderr, self.code = list(stdout), list(stderr), code

    def wait(self):
        return self.code


class FakeSpawn:
    def __init__(self):
        self.calls, self.procs = [], []

    def __call__(self, cmd, cwd, env):
        self.calls.append({"cmd": cmd, "cwd": cwd, "env": env})
        return self.procs.pop(0) if self.procs else FakeProc()


@pytest.fixture
def made(tmp_path):
    song = tmp_path / "out" / "abc123def45"
    song.mkdir(parents=True)
    summary = {"song_id": "abc123def45", "title": "Old tune", "overall": 0.7,
               "sections": {"high": 2, "medium": 1, "low": 1}}
    (song / "report.json").write_text(json.dumps({"summary": summary, "sections": []}))
    (song / "tab.txt").write_text("tab")
    (song / "secret.wav").write_text("not served")
    spawn = FakeSpawn()
    return tmp_path, spawn, Jobs(tmp_path, spawn=spawn, background=False)


def test_stems_match_the_engine():
    from mtab.separate import MELODY_STEMS
    assert app.MELODY_STEMS == MELODY_STEMS


def test_video_id_takes_youtube_video_links_only():
    assert video_id(YT) == "Xpkc-NU1KA0"
    assert video_id("https://youtu.be/Xpkc-NU1KA0?t=3") == "Xpkc-NU1KA0"
    assert video_id(" https://m.youtube.com/shorts/Xpkc-NU1KA0 ") == "Xpkc-NU1KA0"
    for bad in ["https://example.com/a.mp3", "file:///etc/passwd", "https://photos.google.com/photo/AF1Qip",
                "https://www.youtube.com/@channel", None]:
        with pytest.raises(InputError):
            video_id(bad)


def test_option_args_turn_the_page_options_into_flags():
    assert option_args({}) == []
    assert option_args({"stem": "vocals", "key_change": True, "bpm": "120", "beats_per_bar": "",
                        "subdivision": "3"}) == ["--stem", "vocals", "--key-change", "--bpm", "120", "--grid", "3"]
    for bad in [{"bpm": 9000}, {"bpm": "abc"}, {"stem": "drums"}, {"subdivision": 5}, {"beats_per_bar": 2.5},
                {"bpm": True}]:
        with pytest.raises(InputError):
            option_args(bad)


def test_runs_the_engine_for_a_link_and_follows_its_progress(made):
    root, spawn, jobs = made
    spawn.procs.append(FakeProc(["[12:00:01] audio: x\n", "[12:00:02] separating stems\n", "{\n", "tab\n"]))
    assert jobs.submit("https://youtu.be/Xpkc-NU1KA0", {"stem": "guitar"}) == "Xpkc-NU1KA0"
    assert jobs.status("Xpkc-NU1KA0")["status"] == "queued"
    assert jobs.run_next()
    call = spawn.calls[0]
    assert call["cmd"] == [sys.executable, "-m", "mtab.cli", "run", YT, "--stem", "guitar",
                           "--work", str(root / "work"), "--out", str(root / "out")]
    assert call["cwd"] == root and call["env"]["PYTHONUNBUFFERED"] == "1"
    st = jobs.status("Xpkc-NU1KA0")
    # Only the timestamped lines are the log (not the summary JSON or the tab printed at the end).
    assert st["log"] == ["[12:00:01] audio: x", "[12:00:02] separating stems"]
    assert st["status"] == "done"


def test_runs_one_song_at_a_time_and_reports_the_queue(made):
    _, spawn, jobs = made
    jobs.submit(YT)
    jobs.submit("https://youtu.be/aaaaaaaaaaa")
    jobs.submit(YT)  # already queued: not queued twice
    assert jobs.status("aaaaaaaaaaa")["position"] == 2
    spawn.procs.append(FakeProc(stderr=["Traceback...\n", "RuntimeError: no melody found\n"], code=1))
    jobs.run_next()
    assert jobs.status("Xpkc-NU1KA0") | {"log": []} == {"status": "error", "error": "RuntimeError: no melody found",
                                                         "log": [], "position": 0}
    assert jobs.status("aaaaaaaaaaa")["position"] == 1
    jobs.run_next()
    assert jobs.status("aaaaaaaaaaa")["status"] == "done"
    assert not jobs.run_next()


def test_loads_a_song_made_before_unless_asked(made):
    _, spawn, jobs = made
    assert jobs.submit("https://youtu.be/abc123def45") == "abc123def45"
    assert not jobs.queue
    st = jobs.status("abc123def45")
    assert st["status"] == "done" and st["tab"] == "tab"
    jobs.submit("https://youtu.be/abc123def45", rerun=True)
    jobs.run_next()
    assert "re-running" in jobs.status("abc123def45")["log"][0]


def test_lists_songs_and_serves_only_their_listed_files(made):
    _, _, jobs = made
    assert [(r["song_id"], r["title"]) for r in jobs.history()] == [("abc123def45", "Old tune")]
    assert jobs.file("abc123def45", "tab.txt") == (b"tab", "text/plain; charset=utf-8")
    assert jobs.file("abc123def45", "secret.wav") is None
    assert jobs.file("..", "tab.txt") is None
    assert jobs.file("abc123def45", "__class__") is None
    assert jobs.status("nothing-here")["status"] == "unknown"


def test_refused_allows_this_machine_only():
    h = lambda **kw: {k.capitalize(): v for k, v in kw.items()}
    assert refused("GET", h(host="localhost:8765")) is None
    assert refused("POST", h(host="127.0.0.1:8765", origin="http://127.0.0.1:8765")) is None
    assert refused("POST", h(host="localhost:8765")) is None  # curl: no Origin
    # Other host names (DNS rebinding) and other sites' pages.
    assert refused("GET", h(host="evil.example"))[0] == 403
    assert refused("GET", h(host="localhost.evil.example:8765"))[0] == 403
    assert refused("POST", h(host="localhost:8765", origin="https://evil.example"))[0] == 403
    assert refused("POST", h(host="localhost:8765", origin="http://localhost:9999"))[0] == 403
    # npm run dev: the Next dev server's page, only when asked for.
    dev = ("http://localhost:3000",)
    assert refused("POST", h(host="localhost:8765", origin="http://localhost:3000"), dev) is None


def test_static_file_stays_inside_the_page(tmp_path):
    web = tmp_path / "web"
    (web / "_next").mkdir(parents=True)
    (web / "index.html").write_text("home")
    (web / "_next" / "a.js").write_text("js")
    (tmp_path / "secret.txt").write_text("no")
    assert static_file("/", web) == (web / "index.html").resolve()
    assert static_file("/index", web) == (web / "index.html").resolve()
    assert static_file("/_next/a.js", web) == (web / "_next" / "a.js").resolve()
    for bad in ["/../secret.txt", "/%2e%2e/secret.txt", "/nope"]:
        assert static_file(bad, web) is None


def test_the_server_answers_the_page_and_the_api(made):
    root, _, jobs = made
    web = root / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>home</h1>")
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.make_handler(jobs, web))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def req(path, data=None, headers=None):
        r = urllib.request.Request(base + path, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    try:
        assert req("/") == (200, b"<h1>home</h1>")
        status, body = req("/api/history")
        assert status == 200 and json.loads(body)[0]["song_id"] == "abc123def45"
        assert req("/api/files/abc123def45/tab.txt") == (200, b"tab")
        assert req("/api/files/abc123def45/secret.wav")[0] == 404
        assert req("/api/jobs/abc123def45")[0] == 200
        assert req("/api/history", headers={"Host": "evil.example"})[0] == 403
        post = lambda body, ctype="application/json", **h: req("/api/jobs", body, {"Content-Type": ctype, **h})
        assert post(json.dumps({"url": "https://youtu.be/aaaaaaaaaaa"}).encode()) == (202, b'{"song_id": "aaaaaaaaaaa"}')
        assert post(b"url=x", "application/x-www-form-urlencoded")[0] == 415
        assert post(b"{", )[0] == 400
        assert post(json.dumps({"url": "https://example.com"}).encode())[0] == 400
        assert post(b"{}", Origin="https://evil.example")[0] == 403
    finally:
        server.shutdown()
        server.server_close()


def test_the_built_page_is_committed():
    # People who install the app never run `npm run build`: mtab/web/ is what they get.
    assert (app.WEB / "index.html").is_file(), "run `npm run build` and commit mtab/web/"
