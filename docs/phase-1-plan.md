# Phase 1 Plan: Local install for any student (one-day scope)

Implements Phase 1 of [ADR-007](adrs/ADR-007-open-source-distribution-and-mobile.md).
Architecture diagram: [phase-1-architecture.svg](phase-1-architecture.svg).

## Goal
A student with no developer background goes from zero to asking their assistant about their
Classroom in three steps:

1. Install `uv` (one copy-paste command from the README).
2. Paste a config snippet into their MCP host (Claude Desktop, Claude Code, Cursor, VS Code...).
3. Ask a question, click the sign-in link, and approve in Google (clicking through the
   "unverified app" screen).

```json
{ "mcpServers": { "google-classroom": { "command": "uvx", "args": ["classroom-mcp"] } } }
```

## Decisions (2026-10-03)
| Topic | Decision |
|---|---|
| Google app | Reuse the existing `gcr-mcp` project and its Desktop OAuth client as the shared client. Publish it to **Production, unverified**: anyone can sign in after a warning screen, with a 100-user lifetime cap. Verification is deferred until that cap gets close. |
| Per-student Cloud projects | Rejected as the default. Google has no public API for creating the consent screen or a Desktop client, so it can't be scripted. Kept as an advanced override (`CLASSROOM_MCP_CLIENT_SECRETS`). |
| Distribution | PyPI, package name `classroom-mcp` (free as of 2026-10-03). Published manually with `uv publish`. |
| License | MIT |
| Python | >= 3.11 (Google's API client drops 3.10 on 2026-10-04). `uvx` supplies it. |

## Target layout
```
pyproject.toml                 # metadata, dependency ranges, `classroom-mcp` entry point
src/classroom_mcp/
  __init__.py
  __main__.py                  # CLI: (no args) = serve | login | logout | status
  server.py                    # MCP app + tool definitions (thin)
  classroom.py                 # Classroom API calls, pagination, submission merge
  formatting.py                # due dates, timestamps, materials, truncation
  auth.py                      # client config, token store, sign-in flow, refresh
  errors.py                    # HttpError / auth failures -> student-facing text
  client_config.json           # shared Desktop OAuth client (public by design)
tests/
.github/workflows/ci.yml       # pytest on Windows / macOS / Linux
LICENSE  README.md  PRIVACY.md  SECURITY.md
```
Tool names, arguments and output text stay identical.

## Milestones (in order)
1. **Restructure.** Split `server.py` into the package as a pure move. Add `pyproject.toml` and a
   pytest suite for the formatting, merge and error logic.
2. **Dependency check.** `uvx` installs the *latest* compatible versions, not the
   `mcp` 1.0.0 that's installed here. Run the tests and a stdio smoke test against the newest
   `mcp` 1.x and set the version ranges. The FastMCP migration is deferred: the low-level
   API still works and changing it costs time without changing behaviour.
3. **Auth rework.** This is the core work:
   - Bundled client config, with an env-var override.
   - Token stored in the per-user config dir (`platformdirs`).
   - **Sign-in on demand:** the server starts instantly. The first tool call without a token opens
     the browser in the background and returns a "sign in here, then ask again" message with the link.
   - The success page says "Connected, you can close this tab".
   - Self-heals when access is revoked (`invalid_grant`, then sign in again).
   - CLI: `login` / `logout` / `status`.
   - Minimal scopes (drop the never-granted `coursework.me.readonly`).
   - Cache the Classroom service per process.
4. **Docs.** README for non-developers, including the warning-screen walkthrough, a "my school blocks
   it" section and troubleshooting. Add LICENSE, PRIVACY.md and SECURITY.md. Add ADR-008 (packaging + `uvx`,
   supersedes ADR-003) and ADR-009 (shared unverified client + on-demand sign-in, amends ADR-002).
   Update `CLAUDE.md` and `project-state.md`.
5. **CI.** pytest on 3 OSes per push. Releasing stays manual.
6. **End-to-end check.** Build a wheel, run it via `uvx` from the local build with a fresh config
   dir, connect Claude Desktop, sign in, and exercise all 3 tools across the 12 courses.

## Your tasks (about 15 minutes, can run in parallel)
1. **Google Cloud Console**, project `gcr-mcp`, Google Auth Platform:
   - **Branding:** set the app name (e.g. "Classroom MCP"), support email and developer contact.
   - **Data Access:** make sure these scopes are listed: `classroom.courses.readonly`,
     `classroom.announcements.readonly` and `classroom.student-submissions.me.readonly`.
   - **Audience:** click **Publish app** (Testing to In production). Don't submit for
     verification.
2. **PyPI:** create an account at pypi.org with 2FA enabled, and create an API token when we
   are ready to publish.
3. Create a public GitHub repo for the project, or tell me the existing remote is the one to use.

## Deferred
- Google verification. This removes the warning screen and the 100-user cap.
- FastMCP migration, the one-click Claude Desktop extension, and automated PyPI release.
- Phase 2 (mobile via self-hosted HTTP).

## Known limits (documented, not solved)
- Many school-managed accounts, especially under-18 accounts, block unverified third-party apps.
  Google shows the block in the browser, and the README tells students to ask IT.
- The shared client secret will be public in the repo. This is standard for Desktop OAuth clients
  (Google treats it as non-confidential). GitHub secret scanning may flag it on push.
- Your current `token.json` isn't migrated. You sign in once more. During development your
  Claude Desktop config changes to `uv run --directory "D:\Misc Projects\GCR-MCP" classroom-mcp`.
