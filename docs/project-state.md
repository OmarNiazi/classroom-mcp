# Project State

## Current Status
Three tools live and verified against real Classroom data: `get_all_courses`,
`get_assessment_items`, `read_stream_announcements`. Auth working, MCP server connected
to Claude Desktop.

## Last Implemented
- `get_assessment_items` — coursework for a course with the student's own submission
  status merged in (turned in / overdue / grade), sorted by due date. `only_pending` filter.
- `read_stream_announcements` — announcement stream, newest first, with attachment names.
- **Fixed a server-killing crash:** non-Latin-1 characters in course content (arrows, curly
  quotes, emoji) raised `UnicodeEncodeError` inside the MCP stdio writer and terminated the
  whole process. stdio is now forced to UTF-8 — see ADR-005.
- Due dates with no `dueTime` now render as date-only instead of inventing a converted
  UTC-midnight hour.

## Tools Implemented
| Tool | Status |
|------|--------|
| get_all_courses | Done, verified in Claude Desktop |
| get_assessment_items | Done, verified against all 12 active courses |
| read_stream_announcements | Done, verified against all 12 active courses |
| download_files | Blocked — needs a Drive scope (see below) |

## Scope Findings (resolved 2026-09-21)
Confirmed via Google's tokeninfo endpoint what is actually granted:

- **Granted:** `classroom.courses.readonly`, `classroom.announcements.readonly`,
  `classroom.student-submissions.me.readonly`
- **Silently dropped:** `classroom.coursework.me.readonly` — still never granted.

**This is no longer blocking.** `classroom.courses.readonly` covers `courseWork.list`,
`courseWork.get`, and `studentSubmissions.list`, all verified working. The dropped scope
is cosmetic; `OAUTHLIB_RELAX_TOKEN_SCOPE=1` remains in place. Likely cause if ever worth
chasing: the scope is not registered on the OAuth consent screen in Google Cloud Console,
and Google only grants what is listed there.

Still 403 on the current grant, if ever needed:
`courseWorkMaterials.list`, `topics.list`, `students.list`, `teachers.list`,
`userProfiles.get` (so announcement authors cannot be resolved to names).

## Known Issues / Notes
- **`download_files` needs a new scope.** Every attachment seen is a `driveFile`; Classroom
  returns metadata only (id, title, `alternateLink`) and the bytes live in Drive. There is
  no Drive scope in `SCOPES` at all — this was never requested, and Drive returns
  `403 insufficientPermissions`. `alternateLink` is a browser URL requiring interactive
  login, so it is not a workaround. The only scope that works is `drive.readonly`, which
  grants read access to the **entire** Drive, not just Classroom attachments
  (`drive.file` covers only app-created files). Adding it means deleting `token.json` and
  re-consenting, since the refresh token is bound to the granted scope set. Privacy call
  to be made before implementing.
- **Not a git repository, and no `.gitignore`.** `credentials.json` (client secret) and
  `token.json` (live refresh token) sit unprotected in `classroom-mcp/`. CLAUDE.md says
  "never commit" but nothing enforces it — `git init && git add .` would commit both.
- ADR-003's premise looks stale: `python -V` now resolves to 3.13.7, same as
  `C:\Python313`. The pinned path in `claude_desktop_config.json` is still correct and
  harmless, but the 3.14 conflict it works around may no longer exist.
- `mcp` is pinned at 1.0.0; newer SDKs have a considerably nicer decorator API.
- `get_all_courses` hardcodes `courseStates=["ACTIVE"]`. There are **29 archived courses**
  reachable on the current grant if past-semester material is ever wanted.

## Next Step
Decide on `download_files`: accept the `drive.readonly` privacy tradeoff and re-consent,
or defer. If deferring, the obvious smaller wins are a `course_states` parameter on
`get_all_courses` and a cross-course "what's due everywhere" tool.
