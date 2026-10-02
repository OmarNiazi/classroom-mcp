from datetime import datetime, timezone

from classroom_mcp.formatting import describe_materials, format_timestamp, parse_due, truncate


def local(dt):
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def test_parse_due_with_time_converts_utc_to_local():
    work = {"dueDate": {"year": 2026, "month": 10, "day": 5}, "dueTime": {"hours": 18, "minutes": 30}}
    due_utc, display = parse_due(work)
    assert due_utc == datetime(2026, 10, 5, 18, 30, tzinfo=timezone.utc)
    assert display == local(due_utc)


def test_parse_due_without_time_shows_date_only():
    work = {"dueDate": {"year": 2026, "month": 10, "day": 5}}
    due_utc, display = parse_due(work)
    assert due_utc == datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert display == "2026-10-05 (no time set)"


def test_parse_due_zero_valued_time_fields_are_omitted_by_google():
    # Midnight UTC arrives as an empty dueTime object, which is still a set time.
    work = {"dueDate": {"year": 2026, "month": 10, "day": 5}, "dueTime": {}}
    due_utc, display = parse_due(work)
    assert display == local(datetime(2026, 10, 5, tzinfo=timezone.utc))


def test_parse_due_without_date():
    assert parse_due({}) == (None, None)


def test_format_timestamp():
    assert format_timestamp("2026-09-21T08:15:00.123Z") == local(
        datetime(2026, 9, 21, 8, 15, 0, 123000, tzinfo=timezone.utc)
    )
    assert format_timestamp(None) == "unknown date"
    assert format_timestamp("not a date") == "not a date"


def test_describe_materials_names_each_kind():
    materials = [
        {"driveFile": {"driveFile": {"title": "Lab 3.pdf"}}},
        {"link": {"url": "https://example.com"}},
        {"link": {"url": "https://example.com", "title": "Reading"}},
        {"youtubeVideo": {"title": "Lecture"}},
        {"form": {}},
        {"somethingNew": {}},
    ]
    assert describe_materials(materials) == [
        "Lab 3.pdf",
        "https://example.com",
        "Reading",
        "Lecture",
        "Google Form",
    ]
    assert describe_materials(None) == []


def test_truncate_collapses_whitespace_and_cuts():
    assert truncate("a\n\n b   c") == "a b c"
    assert truncate("x" * 10, limit=4) == "xxxx..."
    assert truncate(None) == ""
