# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

After reading this file, read `docs/project-state.md` for the current project state and last implemented change.

---

## Project Overview

A Google Classroom MCP server built with the Python MCP SDK. The server exposes Google Classroom data over **stdio** (not HTTP), so hosts like Claude Desktop can spawn the process on demand.

The current scope covers **student-facing functionality** only.

---

## Planned Student Tools

| Tool | Description | Status |
|------|-------------|--------|
| Get all courses | List all courses the authenticated student is enrolled in | Complete |
| Get assessment items | Retrieve coursework/assignments for a given course | Complete |
| Read stream announcements | Read the announcement stream for a given course | Complete |
| Download files | Download attachments from announcements and assignments | Blocked (needs Drive scope) |

---

## Repository Layout

```
pyproject.toml                # package metadata; `classroom-mcp` console script
src/classroom_mcp/
├── __main__.py               # CLI: serve (default) | setup | remove | login | logout | status
├── hosts.py                  # setup/remove: register in Claude Desktop, Claude Code, Cursor
├── server.py                 # MCP tool definitions + dispatch (thin)
├── classroom.py              # Classroom API calls, pagination, submission merge
├── formatting.py             # pure rendering helpers
├── auth.py                   # shared client, token store, on-demand sign-in
├── errors.py                 # failure text returned to the model
└── client_config.json        # shared Desktop OAuth client (public by design, ADR-009)
tests/                        # pytest; offline fakes + stdio end-to-end
install.ps1, install.sh       # one-line installers (uv + `classroom-mcp setup`), served raw from GitHub
```

```
docs/
├── project-state.md          # Current project snapshot + last implemented item
├── phase-1-plan.md           # Open-source Phase 1 plan + decisions
├── phase-1-architecture.svg  # Architecture diagram
└── adrs/                     # Architectural Decision Records
```

The student's sign-in is stored outside the repo, in the per-user config dir
(`%LOCALAPPDATA%\classroom-mcp\token.json` on Windows). Never commit tokens.

---

## Dev Setup

```bash
uv sync
uv run pytest
uv run classroom-mcp          # serve over stdio; first tool call starts browser sign-in
uv run classroom-mcp status   # where the sign-in is saved
```

Students run it with `uvx --managed-python classroom-mcp` from PyPI (ADR-008). Publish with
`uv build && uv publish` (owner's PyPI token).

When rewriting files from PowerShell 5.1, never use `Get-Content`/`Set-Content` round-trips on
UTF-8 files: they decode as ANSI and re-encode with a BOM (this garbled the 0.1.0 PyPI README).

The server communicates over **stdio**. Do not add an HTTP/SSE transport layer.

---

## Architecture Notes

- **Transport:** stdio only — the MCP host spawns the `classroom-mcp` process. Nothing but
  protocol frames may reach stdout. The sign-in's loopback listener is not a transport (ADR-009).
- **Auth:** OAuth 2.0 with the bundled shared client; sign-in starts on the first tool call that
  needs it (ADR-009). Scopes are read-only: `classroom.courses.readonly`,
  `classroom.announcements.readonly`, `classroom.student-submissions.me.readonly`.
- **ADR discipline:** Any significant design decision (auth approach, tool naming, error handling strategy, etc.) must be recorded as an ADR under `docs/adrs/` before or alongside implementation.
- **project-state.md** is the living document — update it whenever a tool is added or a meaningful change lands.
