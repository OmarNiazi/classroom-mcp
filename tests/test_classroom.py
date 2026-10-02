from classroom_mcp import classroom
from fakes import FakeService


def work(id, title, day=None, **extra):
    item = {"id": id, "title": title, "workType": "ASSIGNMENT", **extra}
    if day is not None:
        item["dueDate"] = {"year": 2026, "month": 10, "day": day}
    return item


def test_list_courses():
    service = FakeService(
        courses={
            "courses": [
                {"id": "1", "name": "Networks", "section": "B", "teacherGroupEmail": "t@x.edu"},
                {"id": "2"},
            ]
        }
    )
    text = classroom.list_courses(service)
    assert text.startswith("Found 2 course(s):")
    assert "- Networks (ID: 1) | Section: B | Teacher group: t@x.edu" in text
    assert "- Unnamed (ID: 2)" in text
    assert service.courses().calls == [{"studentId": "me", "courseStates": ["ACTIVE"]}]


def test_list_courses_empty():
    assert classroom.list_courses(FakeService()) == "No active courses found."


def test_assessment_items_merges_submissions_and_sorts_by_due_date():
    service = FakeService(
        coursework=[
            {"courseWork": [work("a", "Undated"), work("b", "Later", day=20, maxPoints=10)]},
            {"courseWork": [work("c", "Sooner", day=5, maxPoints=100)]},
        ],
        submissions=[
            {
                "studentSubmissions": [
                    {"courseWorkId": "b", "state": "TURNED_IN", "late": True},
                    {"courseWorkId": "c", "state": "CREATED", "late": True},
                ]
            }
        ],
    )
    text = classroom.list_assessment_items(service, "course-1", only_pending=False)

    assert text.startswith("Found 3 item(s) of coursework:")
    order = [text.index(title) for title in ("Sooner", "Later", "Undated")]
    assert order == sorted(order)
    assert "Sooner | Due: 2026-10-05 (no time set) | Not turned in, overdue | 100 pts" in text
    assert "Later | Due: 2026-10-20 (no time set) | Turned in, late | 10 pts" in text
    assert "Undated | No due date | No submission record" in text

    # Both list calls paginated, and submissions came from one wildcard query.
    assert len(service.coursework.calls) == 2
    assert service.submissions.calls[0]["courseWorkId"] == "-"
    assert service.submissions.calls[0]["userId"] == "me"


def test_assessment_items_grade_rendering():
    service = FakeService(
        coursework=[{"courseWork": [work("g", "Quiz", day=1, maxPoints=20)]}],
        submissions=[{"studentSubmissions": [{"courseWorkId": "g", "state": "RETURNED", "assignedGrade": 17}]}],
    )
    text = classroom.list_assessment_items(service, "c", only_pending=False)
    assert "Quiz | Due: 2026-10-01 (no time set) | Returned, grade 17/20" in text
    assert "pts" not in text


def test_assessment_items_only_pending():
    service = FakeService(
        coursework=[{"courseWork": [work("done", "Done", day=1), work("todo", "Todo", day=2)]}],
        submissions=[
            {
                "studentSubmissions": [
                    {"courseWorkId": "done", "state": "TURNED_IN"},
                    {"courseWorkId": "todo", "state": "RECLAIMED_BY_STUDENT"},
                ]
            }
        ],
    )
    text = classroom.list_assessment_items(service, "c", only_pending=True)
    assert text.startswith("Found 1 pending item(s) of coursework:")
    assert "Todo" in text and "Done" not in text


def test_assessment_items_all_turned_in():
    service = FakeService(
        coursework=[{"courseWork": [work("x", "X", day=1)]}],
        submissions=[{"studentSubmissions": [{"courseWorkId": "x", "state": "TURNED_IN"}]}],
    )
    text = classroom.list_assessment_items(service, "c", only_pending=True)
    assert text == "No pending coursework - everything in this course is turned in."


def test_assessment_items_details():
    service = FakeService(
        coursework=[
            {
                "courseWork": [
                    work(
                        "d",
                        "Essay",
                        description="Write   about\nnetworks",
                        materials=[{"driveFile": {"driveFile": {"title": "Brief.docx"}}}],
                        alternateLink="https://classroom.google.com/c/1/a/d",
                    )
                ]
            }
        ]
    )
    text = classroom.list_assessment_items(service, "c", only_pending=False)
    assert "  Type: ASSIGNMENT | ID: d" in text
    assert "  Write about networks" in text
    assert "  Attachments: Brief.docx" in text
    assert "  Link: https://classroom.google.com/c/1/a/d" in text


def test_assessment_items_no_coursework():
    text = classroom.list_assessment_items(FakeService(), "c", only_pending=False)
    assert text == "No coursework found for this course."


def test_announcements_newest_first_with_limit():
    service = FakeService(
        announcements=[
            {
                "announcements": [
                    {"creationTime": "2026-09-01T10:00:00Z", "text": "Old"},
                    {"creationTime": "2026-09-03T10:00:00Z", "text": "Newest → arrows"},
                ]
            },
            {"announcements": [{"creationTime": "2026-09-02T10:00:00Z", "text": ""}]},
        ]
    )
    text = classroom.list_announcements(service, "c", limit=2)
    assert text.startswith("Showing 2 of 3 announcement(s), newest first:")
    assert "Newest → arrows" in text
    assert "(no text)" in text
    assert "Old" not in text


def test_announcements_empty():
    assert classroom.list_announcements(FakeService(), "c", 20) == "No announcements found for this course."
