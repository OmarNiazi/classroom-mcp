# ADR-004: Merge student submission state into coursework results

**Date:** 2026-09-21  
**Status:** Accepted

## Context
The Classroom API models an assignment and a student's progress on it as two separate
resources: `courses.courseWork` (title, due date, points, attachments) and
`courses.courseWork.studentSubmissions` (turned in / not, late flag, assigned grade).

A student asking "what do I still owe this course?" needs both. Options considered:
1. `get_assessment_items` returns coursework only; add a second tool for submission state.
2. `get_assessment_items` returns coursework with each item's submission state merged in.

Option 1 forces the MCP host to make two calls and correlate them by `courseWorkId`,
which burns tokens and invites the model to mismatch IDs.

## Decision
Merge. `get_assessment_items` issues **two** API calls and joins them in the server:
- `courseWork.list` for the assignments,
- `studentSubmissions.list` with `courseWorkId="-"`, which returns this student's
  submissions for *every* assignment in the course in one paginated call.

Results are sorted by due date (soonest first, undated last), and each line carries a
human-readable status derived from `state` + `late` + `assignedGrade`.

An `only_pending` boolean filters to work in `NEW`, `CREATED`, or `RECLAIMED_BY_STUDENT`.

## Consequences
- Cost is two API calls per invocation regardless of assignment count — the `"-"` wildcard
  avoids the N+1 pattern of one submission call per assignment.
- Google's `state` enum is translated for humans: `NEW` and `CREATED` both render as
  "Not turned in", since the distinction is an internal Classroom detail.
- `late` is rendered as "overdue" for un-submitted work and "late" for submitted work —
  the same flag means different things to a student depending on submission state.
- The `assignedGrade` rendering path is **not exercised by any live course data** — no
  submission in the account carries a grade. It is covered by a stubbed test only.
- A caller who wants raw coursework without submission lookup cannot opt out. Acceptable:
  no current use case needs it.
