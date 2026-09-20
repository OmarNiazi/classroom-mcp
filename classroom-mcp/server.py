import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# MCP frames are UTF-8 JSON, but on Windows Python gives stdio the console
# codepage (cp1252 here). stdio_server wraps sys.stdin/sys.stdout directly, so a
# single non-Latin-1 character in course content -- an arrow, a curly quote, an
# emoji -- raises UnicodeEncodeError inside the transport writer and kills the
# whole server, not just the one tool call. Reconfigure before anything starts.
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]

BASE_DIR = Path(__file__).parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

# Google reports submission state as API enum names. NEW and CREATED both mean
# "assigned but nothing submitted" from the student's point of view.
SUBMISSION_STATE_LABELS = {
    "NEW": "Not turned in",
    "CREATED": "Not turned in",
    "TURNED_IN": "Turned in",
    "RETURNED": "Returned",
    "RECLAIMED_BY_STUDENT": "Reclaimed by you",
    "SUBMISSION_STATE_UNSPECIFIED": "Unknown",
}

NOT_SUBMITTED_STATES = {"NEW", "CREATED", "RECLAIMED_BY_STUDENT"}

DESCRIPTION_LIMIT = 400


def get_classroom_service():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("classroom", "v1", credentials=creds)


def paginate(request_fn, key):
    """Collect every page of a Classroom list call into a single list."""
    items = []
    page_token = None
    while True:
        response = request_fn(page_token)
        items.extend(response.get(key, []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return items


def parse_due(work):
    """Return (utc_datetime, display_string) or (None, None).

    Classroom splits a deadline across dueDate and dueTime and omits zero-valued
    fields. dueTime is UTC, so it is converted to local time for display.

    A missing dueTime key means the work has a due *date* with no time, which is
    not the same as midnight -- rendering the converted UTC midnight would invent
    a deadline hour the teacher never set, so only the date is shown.
    """
    due_date = work.get("dueDate")
    if not due_date:
        return None, None

    due_time = work.get("dueTime", {})
    due_utc = datetime(
        due_date["year"],
        due_date["month"],
        due_date["day"],
        due_time.get("hours", 0),
        due_time.get("minutes", 0),
        tzinfo=timezone.utc,
    )

    if "dueTime" not in work:
        return due_utc, due_utc.strftime("%Y-%m-%d") + " (no time set)"
    return due_utc, due_utc.astimezone().strftime("%Y-%m-%d %H:%M")


def format_timestamp(value):
    """Render an RFC 3339 Classroom timestamp in local time."""
    if not value:
        return "unknown date"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def describe_materials(materials):
    """Summarise attachments by name. Bytes need a Drive scope this server lacks."""
    names = []
    for material in materials or []:
        if "driveFile" in material:
            names.append(material["driveFile"]["driveFile"].get("title", "Untitled file"))
        elif "link" in material:
            names.append(material["link"].get("title") or material["link"].get("url", "Link"))
        elif "youtubeVideo" in material:
            names.append(material["youtubeVideo"].get("title", "YouTube video"))
        elif "form" in material:
            names.append(material["form"].get("title", "Google Form"))
    return names


def truncate(text, limit=DESCRIPTION_LIMIT):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def api_error_text(action, error):
    """Turn an HttpError into something the student can act on."""
    status = getattr(getattr(error, "resp", None), "status", None)
    if status == 404:
        return f"Error {action}: course not found. Check the course ID (use get_all_courses)."
    if status == 403:
        return (
            f"Error {action}: access denied by Google ({error}). "
            "This usually means the granted OAuth scopes do not cover this call."
        )
    return f"Error {action}: {error}"


server = Server("google-classroom")


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


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    arguments = arguments or {}

    if name == "get_all_courses":
        return await handle_get_all_courses()
    if name == "get_assessment_items":
        return await handle_get_assessment_items(
            arguments.get("course_id"),
            bool(arguments.get("only_pending", False)),
        )
    if name == "read_stream_announcements":
        return await handle_read_stream_announcements(
            arguments.get("course_id"),
            arguments.get("limit", 20),
        )
    raise ValueError(f"Unknown tool: {name}")


async def handle_get_all_courses() -> list[types.TextContent]:
    try:
        service = get_classroom_service()
        result = service.courses().list(studentId="me", courseStates=["ACTIVE"]).execute()
        courses = result.get("courses", [])

        if not courses:
            return [types.TextContent(type="text", text="No active courses found.")]

        lines = [f"Found {len(courses)} course(s):\n"]
        for c in courses:
            lines.append(f"- {c.get('name', 'Unnamed')} (ID: {c['id']})")
            if c.get("section"):
                lines[-1] += f" | Section: {c['section']}"
            if c.get("teacherGroupEmail"):
                lines[-1] += f" | Teacher group: {c['teacherGroupEmail']}"

        return [types.TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        log.error("get_all_courses failed: %s", e)
        return [types.TextContent(type="text", text=f"Error fetching courses: {e}")]


async def handle_get_assessment_items(course_id, only_pending) -> list[types.TextContent]:
    if not course_id:
        return [types.TextContent(type="text", text="Error: course_id is required.")]

    try:
        service = get_classroom_service()

        coursework = paginate(
            lambda token: service.courses()
            .courseWork()
            .list(courseId=course_id, pageSize=100, pageToken=token)
            .execute(),
            "courseWork",
        )

        if not coursework:
            return [types.TextContent(type="text", text="No coursework found for this course.")]

        # courseWorkId="-" fetches this student's submissions for every assignment
        # in the course in one paginated call, instead of one call per assignment.
        submissions = paginate(
            lambda token: service.courses()
            .courseWork()
            .studentSubmissions()
            .list(
                courseId=course_id,
                courseWorkId="-",
                userId="me",
                pageSize=100,
                pageToken=token,
            )
            .execute(),
            "studentSubmissions",
        )
        submission_by_work = {s["courseWorkId"]: s for s in submissions}

        # Undated work sorts last; otherwise soonest deadline first.
        def sort_key(work):
            due_utc, _ = parse_due(work)
            return (due_utc is None, due_utc or datetime.max.replace(tzinfo=timezone.utc))

        coursework.sort(key=sort_key)

        entries = []
        for work in coursework:
            submission = submission_by_work.get(work["id"], {})
            state = submission.get("state", "")

            if only_pending and state not in NOT_SUBMITTED_STATES:
                continue

            status = SUBMISSION_STATE_LABELS.get(state, "No submission record")
            if submission.get("late"):
                status += ", overdue" if state in NOT_SUBMITTED_STATES else ", late"

            if "assignedGrade" in submission:
                status += f", grade {submission['assignedGrade']}"
                if work.get("maxPoints"):
                    status += f"/{work['maxPoints']}"

            _, due_display = parse_due(work)
            header = f"- {work.get('title', 'Untitled')}"
            header += f" | Due: {due_display}" if due_display else " | No due date"
            header += f" | {status}"
            if work.get("maxPoints") and "assignedGrade" not in submission:
                header += f" | {work['maxPoints']} pts"

            entry = [header, f"  Type: {work.get('workType', 'UNSPECIFIED')} | ID: {work['id']}"]

            if work.get("description"):
                entry.append(f"  {truncate(work['description'])}")

            attachments = describe_materials(work.get("materials"))
            if attachments:
                entry.append(f"  Attachments: {', '.join(attachments)}")

            if work.get("alternateLink"):
                entry.append(f"  Link: {work['alternateLink']}")

            entries.append("\n".join(entry))

        if not entries:
            return [
                types.TextContent(
                    type="text",
                    text="No pending coursework - everything in this course is turned in.",
                )
            ]

        scope_note = " pending" if only_pending else ""
        heading = f"Found {len(entries)}{scope_note} item(s) of coursework:\n\n"
        return [types.TextContent(type="text", text=heading + "\n\n".join(entries))]

    except HttpError as e:
        log.error("get_assessment_items failed: %s", e)
        return [types.TextContent(type="text", text=api_error_text("fetching coursework", e))]
    except Exception as e:
        log.error("get_assessment_items failed: %s", e)
        return [types.TextContent(type="text", text=f"Error fetching coursework: {e}")]


async def handle_read_stream_announcements(course_id, limit) -> list[types.TextContent]:
    if not course_id:
        return [types.TextContent(type="text", text="Error: course_id is required.")]

    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20

    try:
        service = get_classroom_service()

        announcements = paginate(
            lambda token: service.courses()
            .announcements()
            .list(courseId=course_id, pageSize=100, pageToken=token)
            .execute(),
            "announcements",
        )

        if not announcements:
            return [
                types.TextContent(type="text", text="No announcements found for this course.")
            ]

        announcements.sort(key=lambda a: a.get("creationTime", ""), reverse=True)
        shown = announcements[:limit]

        entries = []
        for announcement in shown:
            entry = [f"- {format_timestamp(announcement.get('creationTime'))}"]

            text = " ".join((announcement.get("text") or "").split())
            entry.append(f"  {text}" if text else "  (no text)")

            attachments = describe_materials(announcement.get("materials"))
            if attachments:
                entry.append(f"  Attachments: {', '.join(attachments)}")

            if announcement.get("alternateLink"):
                entry.append(f"  Link: {announcement['alternateLink']}")

            entries.append("\n".join(entry))

        heading = f"Showing {len(shown)} of {len(announcements)} announcement(s), newest first:\n\n"
        return [types.TextContent(type="text", text=heading + "\n\n".join(entries))]

    except HttpError as e:
        log.error("read_stream_announcements failed: %s", e)
        return [types.TextContent(type="text", text=api_error_text("fetching announcements", e))]
    except Exception as e:
        log.error("read_stream_announcements failed: %s", e)
        return [types.TextContent(type="text", text=f"Error fetching announcements: {e}")]


async def main():
    # Trigger OAuth on startup so token.json is written before any tool is called.
    # Also validates credentials.json is present and correctly formatted.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_classroom_service)
    log.info("Auth OK - starting MCP server")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
