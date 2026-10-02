"""A stand-in for the googleapiclient Classroom service: just enough of the
`service.courses().courseWork().list(...).execute()` chain, with paging."""

import json

import httplib2
from googleapiclient.errors import HttpError


def http_error(status, message="error"):
    resp = httplib2.Response({"status": str(status)})
    content = json.dumps({"error": {"code": status, "message": message}}).encode()
    return HttpError(resp, content)


class _Request:
    def __init__(self, response):
        self._response = response

    def execute(self):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class Endpoint:
    """A list() endpoint serving `pages` in order, linked by nextPageToken."""

    def __init__(self, *pages, error=None, **children):
        self.pages = list(pages) or [{}]
        self.error = error
        self.children = children
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            return _Request(self.error)
        token = kwargs.get("pageToken")
        index = 0 if token is None else int(token)
        response = dict(self.pages[index])
        if index + 1 < len(self.pages):
            response["nextPageToken"] = str(index + 1)
        return _Request(response)

    def __getattr__(self, name):
        children = self.__dict__.get("children", {})
        if name not in children:
            raise AttributeError(name)
        return lambda: children[name]


class FakeService:
    def __init__(self, courses=None, coursework=(), submissions=(), announcements=(), error=None):
        self.submissions = Endpoint(*submissions, error=error)
        self.coursework = Endpoint(*coursework, error=error, studentSubmissions=self.submissions)
        self.announcements = Endpoint(*announcements, error=error)
        self._courses = Endpoint(
            courses or {},
            error=error,
            courseWork=self.coursework,
            announcements=self.announcements,
        )

    def courses(self):
        return self._courses
