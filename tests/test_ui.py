import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from mtab import ui
from mtab.gphotos import GooglePhotos


class FakeGoogle(GooglePhotos):
    """Google Photos with the network calls replaced."""

    def __init__(self, port):
        super().__init__(port, env={"GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "s"})
        self._token = {"access_token": "t", "expires_at": 1e12}
        self.ended = []

    def new_session(self):
        return {"id": "sess1", "pickerUri": "https://photos.google.com/picker/x/autoclose",
                "pollingConfig": {"pollInterval": "2s"}}

    def session(self, session_id):
        return {"mediaItemsSet": True}

    def picked_video(self, session_id):
        return {"id": "media-1", "filename": "Jam_at_the_ranch.MP4", "mimeType": "video/mp4",
                "baseUrl": "https://example.invalid/base"}

    def download(self, base_url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"video")
        return dest

    def end_session(self, session_id):
        self.ended.append(session_id)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    runs = []

    def fake_run(source, opts, work, out, log, song_id):
        runs.append((source, song_id, (work / song_id / "title.txt").read_text()
                     if (work / song_id / "title.txt").exists() else None))

    monkeypatch.setattr(ui.pipeline, "run", fake_run)
    song = tmp_path / "out" / "abc123"
    song.mkdir(parents=True)
    (song / "tab.txt").write_text("tab")
    (song / "secret.wav").write_text("not served")
    jobs = ui.Jobs(tmp_path / "work", tmp_path / "out")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.BaseHTTPRequestHandler)
    google = FakeGoogle(srv.server_port)
    srv.RequestHandlerClass = ui.make_handler(jobs, google, srv.server_port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{srv.server_port}", "jobs": jobs, "runs": runs,
           "google": google}
    srv.shutdown()


def request(url, body=None, headers=None, method=None, raw=False):
    data = None
    h = dict(headers or {})
    if body is not None:
        data = body if raw else json.dumps(body).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(url, body, **kw):
    code, raw = request(url, body, **kw)
    return code, json.loads(raw)


def wait_for(cond, timeout=5):
    import time
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_page_and_allowed_files(app):
    assert request(app["url"] + "/")[0] == 200
    assert request(app["url"] + "/files/abc123/tab.txt") == (200, b"tab")


def test_only_listed_files_are_served(app):
    u = app["url"]
    assert request(u + "/files/abc123/secret.wav")[0] == 404
    assert request(u + "/files/..%2F..%2Fetc/passwd")[0] == 404
    assert request(u + "/files/../abc123/tab.txt")[0] == 404


def test_rejects_other_sites(app):
    u = app["url"]
    yt = {"url": "https://www.youtube.com/watch?v=Xpkc-NU1KA0"}
    assert post(u + "/api/jobs", yt, headers={"Origin": "https://evil.example"})[0] == 403
    assert request(u + "/", headers={"Host": "evil.example:80"})[0] == 403
    # A form-style post (no preflight) is refused too.
    assert request(u + "/api/jobs", b"url=x", raw=True,
                   headers={"Content-Type": "text/plain"})[0] == 415


def test_rejects_non_youtube_and_bad_options(app):
    u = app["url"] + "/api/jobs"
    assert post(u, {"url": "https://example.com/a.mp3"})[0] == 400
    assert post(u, {"url": "file:///etc/passwd"})[0] == 400
    code, j = post(u, {"url": "https://photos.google.com/photo/AF1QipM6a9"})
    assert code == 400 and "Pick from Google Photos" in j["error"]
    yt = "https://www.youtube.com/watch?v=Xpkc-NU1KA0"
    assert post(u, {"url": yt, "options": {"bpm": 9000}})[0] == 400
    assert post(u, {"url": yt, "options": {"stem": "drums"}})[0] == 400
    assert post(u, {"url": yt, "options": {"subdivision": 5}})[0] == 400


def test_upload_then_make(app):
    u = app["url"]
    hdr = {"Content-Type": "application/octet-stream", "X-Filename": "My%20Song.mp4"}
    code, raw = request(u + "/api/upload", b"fake video bytes", raw=True, headers=hdr)
    assert code == 200
    up = json.loads(raw)
    assert up["title"] == "My Song" and up["upload"].endswith(".mp4")
    assert (app["jobs"].uploads / up["upload"]).read_bytes() == b"fake video bytes"
    code, j = post(u + "/api/jobs", {"upload": up["upload"], "title": up["title"]})
    assert code == 202 and j["song_id"].startswith("up-")
    assert wait_for(lambda: app["runs"])
    source, sid, title = app["runs"][0]
    assert source.endswith(up["upload"]) and sid == j["song_id"] and title == "My Song"


def test_upload_rejects_bad_files(app):
    u = app["url"] + "/api/upload"
    bad = {"Content-Type": "application/octet-stream", "X-Filename": "notes.exe"}
    assert request(u, b"x", raw=True, headers=bad)[0] == 400
    assert post(app["url"] + "/api/jobs", {"upload": "../../etc/passwd"})[0] == 400


def test_google_pick_flow(app):
    u = app["url"]
    st = json.loads(request(u + "/api/google")[1])
    assert st == {"configured": True, "signed_in": True,
                  "redirect_uri": f"{u.replace('127.0.0.1', 'localhost')}/auth/google/callback"}
    code, s = post(u + "/api/google/session", {})
    assert code == 200 and s["id"] == "sess1" and s["pollSeconds"] == 2
    assert json.loads(request(u + "/api/google/session/sess1")[1]) == {"mediaItemsSet": True}
    code, j = post(u + "/api/jobs", {"google_session": "sess1"})
    assert code == 202 and j["song_id"].startswith("gp-")
    assert wait_for(lambda: app["runs"])
    source, sid, title = app["runs"][0]
    assert source.endswith(".mp4") and title == "Jam at the ranch"
    assert app["google"].ended == ["sess1"]


def test_sign_in_redirects_to_google(app):
    app["google"]._token = None
    req = urllib.request.Request(app["url"] + "/auth/google")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    try:
        urllib.request.build_opener(NoRedirect).open(req)
    except urllib.error.HTTPError as e:
        loc = e.headers["Location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "photospicker.mediaitems.readonly" in loc and "state=" in loc
    # A callback with a state we never issued is refused.
    try:
        urllib.request.build_opener(NoRedirect).open(
            app["url"] + "/auth/google/callback?code=x&state=forged")
    except urllib.error.HTTPError as e:
        assert e.headers["Location"].startswith("/#google-error=")


def test_options_parse():
    o = ui._options({"options": {"stem": "vocals", "key_change": True, "bpm": "120",
                                 "beats_per_bar": "", "subdivision": "3"}})
    assert (o.stem, o.key_change, o.bpm, o.beats_per_bar, o.subdivision) == \
        ("vocals", True, 120.0, None, 3)
    assert o.separate is True
