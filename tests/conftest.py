import json

import pytest

from classroom_mcp import auth

FAKE_CLIENT = {
    "installed": {
        "client_id": "test-client.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


@pytest.fixture(autouse=True)
def isolated_auth(tmp_path, monkeypatch):
    """Every test gets an empty config dir, a fake OAuth client, no real browser,
    and fresh module state, so nothing touches the developer's real sign-in."""
    client_file = tmp_path / "client.json"
    client_file.write_text(json.dumps(FAKE_CLIENT), encoding="utf-8")
    monkeypatch.setenv(auth.CONFIG_DIR_ENV, str(tmp_path / "config"))
    monkeypatch.setenv(auth.CLIENT_SECRETS_ENV, str(client_file))

    opened = []
    monkeypatch.setattr(auth.webbrowser, "open", lambda url, new=0: opened.append(url) or True)
    monkeypatch.setattr(auth, "_creds", None)
    monkeypatch.setattr(auth, "_sign_in", None)
    yield opened
    if auth._sign_in is not None:
        auth._sign_in.done.set()  # let the listener thread exit
