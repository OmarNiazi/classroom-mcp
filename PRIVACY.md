# Privacy Policy

_Last updated: 2026-10-03_

classroom-mcp is open-source software that runs entirely on your own computer. This policy
explains what Google data it uses and where that data goes.

## What it accesses
When you sign in, you grant read-only access to:

| Google permission | Used for |
|---|---|
| `classroom.courses.readonly` | Listing your classes and their assignments |
| `classroom.announcements.readonly` | Reading teacher announcements |
| `classroom.student-submissions.me.readonly` | Your own submission status and grades |

It cannot create, change or delete anything in your Google account, and it can't see other
students' work or grades.

## Where your data goes
- **Your sign-in** (an OAuth token) is saved only in your user folder on your computer. It isn't
  sent to the project's authors or to any third party.
- **Your Classroom data** is fetched directly from Google by the program on your computer
  and passed to the AI app you connected it to (for example Claude Desktop), only when you
  ask a question that needs it. What that app does with it is governed by that app's own
  privacy policy.
- **The project runs no servers** and collects no analytics, telemetry or logs. The authors
  never receive any of your data.

## Google API Services User Data Policy
classroom-mcp's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements. Data is used only to answer your requests, is not
transferred to anyone else, is not used for advertising, and is not used to train AI models
by this project.

## Removing access
- Run `uvx --managed-python classroom-mcp logout` to revoke access with Google and delete the
  saved sign-in, or
- remove the app at <https://myaccount.google.com/permissions> and delete the folder
  shown by `uvx --managed-python classroom-mcp status`.

## Contact
Questions or concerns: open an issue at <https://github.com/OmarNiazi/classroom-mcp/issues>.
