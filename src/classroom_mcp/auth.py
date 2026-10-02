"""Google sign-in for one student, started on demand (ADR-009).

The server starts without credentials. The first tool call that needs Google
starts a sign-in: a loopback HTTP listener on 127.0.0.1 waits for Google's
redirect while the student approves access in their browser. The resulting
token is stored in the per-user config directory, never in the repo.

google_auth_oauthlib's run_local_server() is deliberately not used: it prints
the sign-in URL to stdout, which is the MCP protocol channel, and it blocks the
caller until the browser comes back.
"""

import html
import json
import logging
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import platformdirs
import requests
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Google's granular consent lets the student untick individual permissions, so
# the granted scope set can legitimately differ from the requested one. Without
# this, oauthlib raises instead of returning the token; the shortfall is
# checked explicitly in _SignIn._complete().
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

log = logging.getLogger(__name__)

APP_NAME = "classroom-mcp"
CLIENT_SECRETS_ENV = "CLASSROOM_MCP_CLIENT_SECRETS"
CONFIG_DIR_ENV = "CLASSROOM_MCP_CONFIG_DIR"

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]

# What each scope means to a student, for the "you unticked a box" message.
SCOPE_DESCRIPTIONS = {
    SCOPES[0]: "see your Classroom classes",
    SCOPES[1]: "see class announcements",
    SCOPES[2]: "see your own coursework and grades",
}

SIGN_IN_TIMEOUT_SECONDS = 300
REVOKE_URL = "https://oauth2.googleapis.com/revoke"


class SignInRequired(Exception):
    """No usable credentials.

    `url` is the in-progress sign-in to finish, or None when the last attempt
    just failed (`reason` says why) and the next call should start a new one.
    """

    def __init__(self, url, reason=None):
        super().__init__(reason or "Sign-in required")
        self.url = url
        self.reason = reason


# --- Storage -----------------------------------------------------------------


def config_dir():
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override)
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))


def token_path():
    return config_dir() / "token.json"


def load_client_config():
    """The shared OAuth client bundled with the package, unless overridden.

    This is a Desktop-app client: Google treats its secret as non-confidential
    because every installed copy necessarily ships it.
    """
    override = os.environ.get(CLIENT_SECRETS_ENV)
    if override:
        return json.loads(Path(override).read_text(encoding="utf-8"))
    bundled = resources.files(__package__).joinpath("client_config.json")
    return json.loads(bundled.read_text(encoding="utf-8"))


def load_token():
    path = token_path()
    if not path.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(path), SCOPES)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        log.warning("Ignoring unreadable token file %s: %s", path, e)
        return None


def save_token(creds):
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(creds.to_json(), encoding="utf-8")
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def delete_token():
    try:
        token_path().unlink()
    except FileNotFoundError:
        pass


# --- Browser sign-in ---------------------------------------------------------


def _page(title, body):
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:32rem;margin:15vh auto;"
        "padding:0 1rem;line-height:1.5;color:#222}h1{font-size:1.4rem}</style>"
        f"</head><body><h1>{html.escape(title)}</h1><p>{html.escape(body)}</p></body></html>"
    )


class _SignIn:
    """One browser sign-in attempt, served from a background thread."""

    def __init__(self, client_config):
        self.done = threading.Event()
        self.creds = None
        self.error = None
        self.error_reported = False

        session = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                params = parse_qs(urlparse(self.path).query)
                if "code" not in params and "error" not in params:
                    self.send_response(404)  # favicon and other noise
                    self.end_headers()
                    return
                title, body = session._complete(params)
                payload = _page(title, body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                log.debug("sign-in listener: " + format, *args)

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._server.timeout = 1
        redirect_uri = f"http://127.0.0.1:{self._server.server_port}/"
        self.flow = InstalledAppFlow.from_client_config(
            client_config, SCOPES, redirect_uri=redirect_uri
        )
        # prompt=consent makes Google issue a refresh token even if this
        # account approved the app before (e.g. after a local logout).
        self.url, self._state = self.flow.authorization_url(prompt="consent")
        self._thread = threading.Thread(target=self._serve, name="classroom-mcp-sign-in", daemon=True)

    def start(self, open_browser=True):
        self._thread.start()
        if open_browser:
            try:
                webbrowser.open(self.url, new=1)
            except Exception as e:  # no browser available; the URL is still returned
                log.warning("Could not open a browser: %s", e)
        return self

    def wait(self, seconds):
        """Block up to `seconds`; True once the attempt has finished either way."""
        return self.done.wait(seconds)

    @property
    def active(self):
        return not self.done.is_set()

    def _serve(self):
        deadline = time.monotonic() + SIGN_IN_TIMEOUT_SECONDS
        try:
            while not self.done.is_set() and time.monotonic() < deadline:
                self._server.handle_request()
        finally:
            self._server.server_close()
            if not self.done.is_set():
                self.error = "the sign-in window was open too long without finishing."
                self.done.set()

    def _complete(self, params):
        try:
            if "error" in params:
                if params["error"][0] == "access_denied":
                    self.error = "access wasn't allowed (the sign-in was cancelled or declined)."
                else:
                    self.error = f"Google returned an error: {params['error'][0]}."
                return "Sign-in not completed", "Close this tab and ask your assistant again to retry."

            if params.get("state", [None])[0] != self._state:
                self.error = "the sign-in response didn't match this attempt."
                return "Sign-in not completed", "Close this tab and ask your assistant again to retry."

            self.flow.fetch_token(code=params["code"][0])
            granted = self.flow.oauth2session.token.get("scope") or []
            if isinstance(granted, str):
                granted = granted.split()
            missing = [s for s in SCOPES if s not in granted]
            if missing:
                needed = ", ".join(SCOPE_DESCRIPTIONS[s] for s in missing)
                self.error = (
                    f"some permissions were left unticked ({needed}). "
                    "Sign in again and leave every box ticked."
                )
                return "Almost there", (
                    "Some permissions were left unticked, so Classroom can't be read yet. "
                    "Close this tab, ask your assistant again, and leave every box ticked."
                )

            creds = self.flow.credentials
            save_token(creds)
            self.creds = creds
            return "Connected to Google Classroom", (
                "You can close this tab and go back to your assistant."
            )
        except Exception as e:
            log.error("Sign-in failed: %s", e)
            self.error = f"Google rejected the sign-in ({e})."
            return "Sign-in failed", "Close this tab and ask your assistant again to retry."
        finally:
            self.done.set()


# --- Public API --------------------------------------------------------------

_lock = threading.Lock()
_creds = None
_sign_in = None


def current_credentials():
    """Valid credentials from memory or disk (refreshing if needed), else None."""
    global _creds
    with _lock:
        if _creds is None:
            _creds = load_token()
        creds = _creds
        if creds is None:
            return None
        if creds.valid:
            return creds
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                save_token(creds)
                return creds
            except RefreshError as e:
                # Revoked in the Google account, expired, or the client changed.
                log.warning("Saved sign-in no longer works, discarding it: %s", e)
        _creds = None
        delete_token()
        return None


def forget_credentials():
    """Drop credentials that Google has stopped accepting."""
    global _creds
    with _lock:
        _creds = None
        delete_token()


def start_sign_in(open_browser=True):
    """Return the in-progress sign-in, or start a new one.

    Returns (attempt, previous_error): previous_error explains why the last
    finished attempt didn't produce credentials, so it can be shown once.
    """
    global _sign_in
    with _lock:
        if _sign_in is not None and _sign_in.active:
            return _sign_in, None
        previous_error = None
        if _sign_in is not None and not _sign_in.error_reported:
            previous_error = _sign_in.error
        _sign_in = _SignIn(load_client_config()).start(open_browser=open_browser)
        return _sign_in, previous_error


def ensure_credentials(wait=0.0):
    """Valid credentials, or raise SignInRequired with a URL to finish sign-in.

    When a sign-in has to start, waits up to `wait` seconds for the student to
    finish it so the original request can continue without being asked again.
    """
    creds = current_credentials()
    if creds is not None:
        return creds

    attempt, previous_error = start_sign_in()
    if wait:
        attempt.wait(wait)
    if not attempt.done.is_set():
        raise SignInRequired(attempt.url, previous_error)

    if attempt.creds is not None:
        creds = current_credentials()
        if creds is not None:
            return creds
    # Finished without credentials. Its listener is closed, so there is no
    # link to hand out; the next call starts a fresh attempt.
    attempt.error_reported = True
    raise SignInRequired(None, attempt.error)


def sign_out():
    """Revoke the saved grant with Google (best effort) and delete it locally.

    Returns (had_token, revoked).
    """
    global _creds
    with _lock:
        creds = _creds or load_token()
        _creds = None
        revoked = False
        if creds is not None:
            token = creds.refresh_token or creds.token
            try:
                response = requests.post(
                    REVOKE_URL,
                    data={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10,
                )
                revoked = response.status_code == 200
            except requests.RequestException as e:
                log.warning("Could not reach Google to revoke access: %s", e)
        delete_token()
        return creds is not None, revoked
