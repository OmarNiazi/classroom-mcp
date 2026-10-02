"""MCP surface: tool definitions and dispatch. Logic lives in classroom.py."""

import asyncio
import logging
import threading

import mcp.server.stdio
import mcp.types as types
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server import Server

from . import auth, classroom
from .errors import api_error_text, sign_in_text

log = logging.getLogger(__name__)

# How long a tool call holds on while the student finishes a sign-in it just
# started, so the original question gets answered without asking again. Kept
# under common host request timeouts (60s).
SIGN_IN_WAIT_SECONDS = 40

server = Server("google-classroom")

# The Classroom client sits on httplib2, which is not thread-safe, and tool
# calls run in worker threads. One student, one call at a time is plenty.
_api_lock = threading.Lock()
_service = None
_service_creds = None


def _service_for(creds):
    global _service, _service_creds
    if _service is None or creds is not _service_creds:
        _service = build("classroom", "v1", credentials=creds, cache_discovery=False)
        _service_creds = creds
    return _service


def _run(action, fetch):
    """Authenticate, then run `fetch(service)`. Always returns text (ADR-006)."""
    try:
        creds = auth.ensure_credentials(wait=SIGN_IN_WAIT_SECONDS)
        with _api_lock:
            return fetch(_service_for(creds))
    except auth.SignInRequired as e:
        return sign_in_text(e.url, e.reason)
    except RefreshError as e:
        log.warning("%s: Google rejected the saved sign-in: %s", action, e)
        auth.forget_credentials()
        try:
            auth.ensure_credentials()
        except auth.SignInRequired as s:
            return sign_in_text(s.url, "Google no longer accepts the saved sign-in.")
        return f"Error {action}: Google rejected the saved sign-in. Please ask again."
    except HttpError as e:
        log.error("%s failed: %s", action, e)
        return api_error_text(action, e)
    except Exception as e:
        log.exception("%s failed", action)
        return f"Error {action}: {e}"


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_all_courses",
            description="List all courses the authenticated student is enrolled in.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="get_assessment_items",
            description=(
                "List coursework/assignments for a course, each annotated with the "
                "student's own submission status (turned in, not turned in, overdue, "
                "grade). Sorted by due date, soonest first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "course_id": {
                        "type": "string",
                        "description": "Course ID, as returned by get_all_courses.",
                    },
                    "only_pending": {
                        "type": "boolean",
                        "description": "If true, return only work that has not been turned in.",
                        "default": False,
                    },
                },
                "required": ["course_id"],
            },
        ),
        types.Tool(
            name="read_stream_announcements",
            description=(
                "Read the announcement stream for a course, newest first, "
                "including any attachment names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "course_id": {
                        "type": "string",
                        "description": "Course ID, as returned by get_all_courses.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum announcements to return (default 20, max 100).",
                        "default": 20,
                    },
                },
                "required": ["course_id"],
            },
        ),
    ]


def _clamp_limit(limit):
    try:
        return max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        return 20


async def dispatch(name, arguments):
    """Resolve a tool call to its text result. Raises only for unknown tools."""
    arguments = arguments or {}

    if name == "get_all_courses":
        return await asyncio.to_thread(_run, "fetching courses", classroom.list_courses)

    if name == "get_assessment_items":
        course_id = arguments.get("course_id")
        if not course_id:
            return "Error: course_id is required."
        only_pending = bool(arguments.get("only_pending", False))
        return await asyncio.to_thread(
            _run,
            "fetching coursework",
            lambda service: classroom.list_assessment_items(service, course_id, only_pending),
        )

    if name == "read_stream_announcements":
        course_id = arguments.get("course_id")
        if not course_id:
            return "Error: course_id is required."
        limit = _clamp_limit(arguments.get("limit", 20))
        return await asyncio.to_thread(
            _run,
            "fetching announcements",
            lambda service: classroom.list_announcements(service, course_id, limit),
        )

    raise ValueError(f"Unknown tool: {name}")


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=await dispatch(name, arguments))]


async def serve():
    # No auth at startup: the host gets a responsive server immediately, and
    # sign-in starts from the first tool call that needs it (ADR-009).
    log.info("classroom-mcp starting on stdio (token: %s)", auth.token_path())
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
