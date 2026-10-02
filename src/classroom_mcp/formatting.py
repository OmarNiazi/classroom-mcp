"""Pure rendering helpers: Classroom API shapes in, display strings out."""

from datetime import datetime, timezone

DESCRIPTION_LIMIT = 400


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
