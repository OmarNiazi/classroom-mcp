"""Classroom API calls and their text rendering.

Every function takes a built Classroom service and returns the text a tool
hands back to the model. API errors propagate; the server layer turns them into
student-facing messages (ADR-006).
"""

from datetime import datetime, timezone

from .formatting import describe_materials, format_timestamp, parse_due, truncate

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


def list_courses(service):
    result = service.courses().list(studentId="me", courseStates=["ACTIVE"]).execute()
    courses = result.get("courses", [])

    if not courses:
        return "No active courses found."

    lines = [f"Found {len(courses)} course(s):\n"]
    for c in courses:
        lines.append(f"- {c.get('name', 'Unnamed')} (ID: {c['id']})")
        if c.get("section"):
            lines[-1] += f" | Section: {c['section']}"
        if c.get("teacherGroupEmail"):
            lines[-1] += f" | Teacher group: {c['teacherGroupEmail']}"

    return "\n".join(lines)


def list_assessment_items(service, course_id, only_pending):
    coursework = paginate(
        lambda token: service.courses()
        .courseWork()
        .list(courseId=course_id, pageSize=100, pageToken=token)
        .execute(),
        "courseWork",
    )

    if not coursework:
        return "No coursework found for this course."

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
        return "No pending coursework - everything in this course is turned in."

    scope_note = " pending" if only_pending else ""
    heading = f"Found {len(entries)}{scope_note} item(s) of coursework:\n\n"
    return heading + "\n\n".join(entries)


def list_announcements(service, course_id, limit):
    announcements = paginate(
        lambda token: service.courses()
        .announcements()
        .list(courseId=course_id, pageSize=100, pageToken=token)
        .execute(),
        "announcements",
    )

    if not announcements:
        return "No announcements found for this course."

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
    return heading + "\n\n".join(entries)
