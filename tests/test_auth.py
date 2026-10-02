import json
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from classroom_mcp import auth

# Bypass any system proxy: the listener is on loopback.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def redirect(url, **params):
    """Play the part of Google redirecting the browser back to the listener."""
    query = parse_qs(urlparse(url).query)
    target = query["redirect_uri"][0]
    params.setdefault("state", query["state"][0])
    with _opener.open(f"{target}?{urlencode(params)}", timeout=5) as response:
        return response.read().decode("utf-8")


@pytest.fixture
def google_grants(monkeypatch):
    """Make the code exchange succeed offline, granting the given scopes."""
    granted = {"scopes": list(auth.SCOPES)}

    def fake_fetch_token(self, **kwargs):
        assert kwargs["code"] == "good-code"
        self.oauth2session.token = {
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "Bearer",
            "expires_at": time.time() + 3600,
            "scope": granted["scopes"],
        }
        return self.oauth2session.token

    monkeypatch.setattr(Flow, "fetch_token", fake_fetch_token)
    return granted


def write_token(expired=False):
    expiry = datetime.now(timezone.utc).replace(tzinfo=None)
    expiry += timedelta(hours=-1 if expired else 1)
    creds = Credentials(
        "access",
        refresh_token="refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test-client",
        client_secret="test-secret",
        scopes=auth.SCOPES,
        expiry=expiry,
    )
    auth.save_token(creds)


def test_token_lives_in_config_dir(tmp_path):
    assert auth.token_path() == tmp_path / "config" / "token.json"


def test_no_token_means_not_signed_in():
    assert auth.current_credentials() is None


def test_saved_token_round_trips():
    write_token()
    creds = auth.current_credentials()
    assert creds is not None and creds.valid
    assert creds.refresh_token == "refresh"


def test_unreadable_token_is_ignored():
    auth.token_path().parent.mkdir(parents=True)
    auth.token_path().write_text("{not json", encoding="utf-8")
    assert auth.current_credentials() is None


def test_revoked_token_is_discarded(monkeypatch):
    write_token(expired=True)

    def refuse(self, request):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(Credentials, "refresh", refuse)
    assert auth.current_credentials() is None
    assert not auth.token_path().exists()


def test_expired_token_is_refreshed_and_saved(monkeypatch):
    write_token(expired=True)

    def renew(self, request):
        self.token = "renewed"
        self.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", renew)
    assert auth.current_credentials().token == "renewed"
    assert json.loads(auth.token_path().read_text())["token"] == "renewed"


def test_sign_in_starts_on_demand_and_opens_browser(isolated_auth):
    with pytest.raises(auth.SignInRequired) as raised:
        auth.ensure_credentials()
    url = raised.value.url
    assert url.startswith("https://accounts.google.com/o/oauth2/auth?")
    assert isolated_auth == [url]

    query = parse_qs(urlparse(url).query)
    assert query["redirect_uri"][0].startswith("http://127.0.0.1:")
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["code_challenge_method"] == ["S256"]
    assert set(query["scope"][0].split()) == set(auth.SCOPES)


def test_repeat_calls_join_the_same_sign_in(isolated_auth):
    urls = []
    for _ in range(2):
        with pytest.raises(auth.SignInRequired) as raised:
            auth.ensure_credentials()
        urls.append(raised.value.url)
    assert urls[0] == urls[1]
    assert len(isolated_auth) == 1  # one browser window, not two


def test_completed_sign_in_saves_token(google_grants):
    with pytest.raises(auth.SignInRequired) as raised:
        auth.ensure_credentials()
    page = redirect(raised.value.url, code="good-code")
    assert "Connected to Google Classroom" in page

    creds = auth.ensure_credentials()
    assert creds.refresh_token == "refresh"
    assert auth.token_path().exists()


def test_waiting_call_continues_once_sign_in_finishes(google_grants):
    attempt, _ = auth.start_sign_in()
    threading.Timer(0.3, redirect, args=(attempt.url,), kwargs={"code": "good-code"}).start()
    creds = auth.ensure_credentials(wait=5)
    assert creds.token == "access"


def test_cancelled_sign_in_is_reported_once_then_retried(isolated_auth):
    attempt, _ = auth.start_sign_in()
    page = redirect(attempt.url, error="access_denied")
    assert "Sign-in not completed" in page

    with pytest.raises(auth.SignInRequired) as raised:
        auth.ensure_credentials()
    assert "access wasn't allowed" in raised.value.reason
    assert raised.value.url != attempt.url  # a fresh attempt
    assert len(isolated_auth) == 2


def test_failure_during_wait_is_not_repeated(isolated_auth):
    attempt, _ = auth.start_sign_in()
    threading.Timer(0.3, redirect, args=(attempt.url,), kwargs={"error": "access_denied"}).start()
    with pytest.raises(auth.SignInRequired) as raised:
        auth.ensure_credentials(wait=5)
    assert raised.value.url is None  # the listener is closed; no dead link
    assert "access wasn't allowed" in raised.value.reason

    with pytest.raises(auth.SignInRequired) as raised:
        auth.ensure_credentials()
    assert raised.value.url is not None
    assert raised.value.reason is None


def test_unticked_permission_is_rejected(google_grants):
    google_grants["scopes"] = auth.SCOPES[:1]
    attempt, _ = auth.start_sign_in()
    page = redirect(attempt.url, code="good-code")
    assert "unticked" in page
    assert not auth.token_path().exists()
    assert "see your own coursework and grades" in attempt.error


def test_mismatched_state_is_rejected(google_grants):
    attempt, _ = auth.start_sign_in()
    redirect(attempt.url, code="good-code", state="forged")
    assert "didn't match" in attempt.error
    assert not auth.token_path().exists()


def test_listener_ignores_unrelated_requests(google_grants):
    attempt, _ = auth.start_sign_in()
    target = parse_qs(urlparse(attempt.url).query)["redirect_uri"][0]
    with pytest.raises(urllib.error.HTTPError):
        _opener.open(target + "favicon.ico", timeout=5)
    assert attempt.active
    redirect(attempt.url, code="good-code")
    assert attempt.creds is not None


def test_sign_out_revokes_and_deletes(monkeypatch):
    write_token()
    posted = {}

    class Ok:
        status_code = 200

    def fake_post(url, data, headers, timeout):
        posted.update(url=url, data=data)
        return Ok()

    monkeypatch.setattr(auth.requests, "post", fake_post)
    assert auth.sign_out() == (True, True)
    assert posted == {"url": auth.REVOKE_URL, "data": {"token": "refresh"}}
    assert not auth.token_path().exists()


def test_sign_out_when_signed_out():
    assert auth.sign_out() == (False, False)


def test_bundled_client_config_is_a_desktop_client(monkeypatch):
    monkeypatch.delenv(auth.CLIENT_SECRETS_ENV)
    config = auth.load_client_config()
    assert set(config) == {"installed"}
    assert config["installed"]["client_id"].endswith(".apps.googleusercontent.com")
