import asyncio

import pytest
from google.auth.exceptions import RefreshError

from classroom_mcp import auth, server
from fakes import FakeService, http_error


def call(name, arguments=None):
    return asyncio.run(server.dispatch(name, arguments))


@pytest.fixture
def signed_in(monkeypatch):
    """Skip auth and serve the given fake service."""
    holder = {"service": FakeService()}
    monkeypatch.setattr(server.auth, "ensure_credentials", lambda wait=0: object())
    monkeypatch.setattr(server, "_service_for", lambda creds: holder["service"])
    return holder


def test_tools_are_listed_unchanged():
    tools = asyncio.run(server.list_tools())
    assert [t.name for t in tools] == [
        "get_all_courses",
        "get_assessment_items",
        "read_stream_announcements",
    ]


def test_missing_course_id_is_reported_without_calling_google(monkeypatch):
    monkeypatch.setattr(server, "_run", lambda *a: pytest.fail("should not reach Google"))
    assert call("get_assessment_items", {}) == "Error: course_id is required."
    assert call("read_stream_announcements", {"course_id": ""}) == "Error: course_id is required."


def test_unknown_tool_raises():
    with pytest.raises(ValueError):
        call("nope")


@pytest.mark.parametrize("given, used", [(None, 20), ("abc", 20), (0, 1), (500, 100), ("7", 7)])
def test_announcement_limit_is_clamped(signed_in, given, used):
    signed_in["service"] = FakeService(
        announcements=[{"announcements": [{"creationTime": f"2026-09-{d:02d}T00:00:00Z"} for d in range(1, 29)]}]
    )
    args = {"course_id": "c"}
    if given is not None:
        args["limit"] = given
    text = call("read_stream_announcements", args)
    assert text.startswith(f"Showing {min(used, 28)} of 28")


def test_tool_returns_data(signed_in):
    signed_in["service"] = FakeService(courses={"courses": [{"id": "1", "name": "Networks"}]})
    assert "Networks (ID: 1)" in call("get_all_courses")


def test_not_found_is_actionable(signed_in):
    signed_in["service"] = FakeService(error=http_error(404))
    text = call("get_assessment_items", {"course_id": "bad"})
    assert text == "Error fetching coursework: course not found. Check the course ID (use get_all_courses)."


def test_forbidden_mentions_scopes(signed_in):
    signed_in["service"] = FakeService(error=http_error(403, "Insufficient Permission"))
    text = call("read_stream_announcements", {"course_id": "c"})
    assert text.startswith("Error fetching announcements: access denied by Google")
    assert "OAuth scopes" in text


def test_unexpected_error_is_text(signed_in):
    signed_in["service"] = FakeService(error=RuntimeError("network down"))
    assert call("get_all_courses") == "Error fetching courses: network down"


def test_sign_in_needed_returns_instructions(monkeypatch):
    def need_sign_in(wait=0):
        raise auth.SignInRequired("https://accounts.google.com/o/oauth2/auth?x=1")

    monkeypatch.setattr(server.auth, "ensure_credentials", need_sign_in)
    text = call("get_all_courses")
    assert "https://accounts.google.com/o/oauth2/auth?x=1" in text
    assert "Advanced" in text
    assert "IT admin" in text


def test_failed_sign_in_says_ask_again(monkeypatch):
    def failed(wait=0):
        raise auth.SignInRequired(None, "access wasn't allowed.")

    monkeypatch.setattr(server.auth, "ensure_credentials", failed)
    text = call("get_all_courses")
    assert "access wasn't allowed" in text
    assert "Ask again" in text


def test_revoked_mid_session_restarts_sign_in(monkeypatch):
    calls = []

    def ensure(wait=0):
        calls.append(wait)
        if len(calls) == 1:
            return object()
        raise auth.SignInRequired("https://accounts.google.com/o/oauth2/auth?again=1")

    forgotten = []
    monkeypatch.setattr(server.auth, "ensure_credentials", ensure)
    monkeypatch.setattr(server.auth, "forget_credentials", lambda: forgotten.append(True))
    monkeypatch.setattr(server, "_service_for", lambda creds: FakeService(error=RefreshError("invalid_grant")))

    text = call("get_all_courses")
    assert forgotten == [True]
    assert "no longer accepts the saved sign-in" in text
    assert "again=1" in text
