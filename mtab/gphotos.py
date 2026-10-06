"""Google Photos, through the Photos Picker API: you choose a video in Google's own picker
window and we download it. (Google no longer lets apps fetch library items by ID or link,
so a pasted photos.google.com link can't be used directly.)

Needs an OAuth client (type "Web application") with the Photos Picker API enabled and
http://localhost:<port>/auth/google/callback as an authorized redirect URI. Its ID and
secret go in .env.local as GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET. Tokens are kept in
memory only: sign in again after restarting the server."""

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PICKER = "https://photospicker.googleapis.com/v1"
SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
ENV_FILE = Path(".env.local")


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    """KEY=VALUE lines from .env.local, overridden by real environment variables."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


class GooglePhotos:
    def __init__(self, port: int, env: dict[str, str] | None = None):
        env = load_env() if env is None else env
        self.client_id = env.get("GOOGLE_CLIENT_ID", "")
        self.client_secret = env.get("GOOGLE_CLIENT_SECRET", "")
        self.redirect_uri = f"http://localhost:{port}/auth/google/callback"
        self._state: set[str] = set()
        self._token: dict | None = None
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def signed_in(self) -> bool:
        return self._token is not None

    # --- sign-in ---

    def auth_url(self) -> str:
        state = secrets.token_urlsafe(24)
        self._state.add(state)
        return AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri,
            "response_type": "code", "scope": SCOPE, "state": state,
            "access_type": "offline", "prompt": "consent",
        })

    def finish_sign_in(self, code: str, state: str) -> None:
        if state not in self._state:
            raise PermissionError("sign-in expired or didn't start here; try again")
        self._state.discard(state)
        tok = _post_form(TOKEN_URL, {
            "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri, "grant_type": "authorization_code",
        })
        tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 60
        with self._lock:
            self._token = tok

    def _access_token(self) -> str:
        with self._lock:
            tok = self._token
            if tok is None:
                raise PermissionError("not signed in to Google Photos")
            if time.time() >= tok["expires_at"]:
                if not tok.get("refresh_token"):
                    self._token = None
                    raise PermissionError("Google sign-in expired; sign in again")
                new = _post_form(TOKEN_URL, {
                    "refresh_token": tok["refresh_token"], "client_id": self.client_id,
                    "client_secret": self.client_secret, "grant_type": "refresh_token",
                })
                tok.update(new)
                tok["expires_at"] = time.time() + int(new.get("expires_in", 3600)) - 60
            return tok["access_token"]

    # --- picker ---

    def new_session(self) -> dict:
        """{id, pickerUri, pollingConfig}. Open pickerUri for the user."""
        s = self._api("POST", f"{PICKER}/sessions", body={})
        # /autoclose closes Google's picker window once the choice is made.
        s["pickerUri"] = s["pickerUri"].rstrip("/") + "/autoclose"
        return s

    def session(self, session_id: str) -> dict:
        return self._api("GET", f"{PICKER}/sessions/{urllib.parse.quote(session_id)}")

    def picked_video(self, session_id: str) -> dict:
        """The first video picked in a session: {id, filename, mimeType, baseUrl}."""
        page = None
        while True:
            q = {"sessionId": session_id, "pageSize": 100}
            if page:
                q["pageToken"] = page
            r = self._api("GET", f"{PICKER}/mediaItems?" + urllib.parse.urlencode(q))
            for item in r.get("mediaItems", []):
                f = item.get("mediaFile", {})
                if item.get("type") == "VIDEO" or f.get("mimeType", "").startswith("video/"):
                    return {"id": item["id"], "filename": f.get("filename", "video"),
                            "mimeType": f.get("mimeType", ""), "baseUrl": f["baseUrl"]}
            page = r.get("nextPageToken")
            if not page:
                raise ValueError("no video in what was picked; choose a video, not a photo")

    def end_session(self, session_id: str) -> None:
        try:
            self._api("DELETE", f"{PICKER}/sessions/{urllib.parse.quote(session_id)}")
        except Exception:  # noqa: BLE001 - sessions expire on their own anyway
            pass

    def download(self, base_url: str, dest: Path) -> Path:
        """Downloads the video file itself (baseUrl + "=dv")."""
        req = urllib.request.Request(base_url + "=dv",
                                     headers={"Authorization": f"Bearer {self._access_token()}"})
        tmp = dest.with_suffix(dest.suffix + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.replace(dest)
        return dest

    def _api(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Google Photos {e.code}: {_error_message(e)}") from None
        return json.loads(raw) if raw else {}


def _post_form(url: str, fields: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(),
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Google sign-in failed: {_error_message(e)}") from None


def _error_message(e: urllib.error.HTTPError) -> str:
    try:
        d = json.loads(e.read())
        err = d.get("error")
        if isinstance(err, dict):
            return err.get("message", str(err))
        return d.get("error_description") or str(err)
    except Exception:  # noqa: BLE001
        return e.reason
