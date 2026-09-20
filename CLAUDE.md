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
classroom-mcp/
├── credentials.json      # OAuth 2.0 client credentials (never commit)
├── token.json            # Auto-generated on first auth run (never commit)
├── server.py             # MCP server entry point
└── requirements.txt      # Python dependencies
```

```
docs/
├── project-state.md      # Current project snapshot + last implemented item
└── adrs/                 # Architectural Decision Records
```

---

## Dev Setup

```bash
cd classroom-mcp
pip install -r requirements.txt
python server.py           # First run triggers OAuth browser flow; token.json is written
```

The server communicates over **stdio**. Do not add an HTTP/SSE transport layer.

---

## Architecture Notes

- **Transport:** stdio only — the MCP host spawns and communicates with `server.py` directly.
- **Auth:** OAuth 2.0 via `credentials.json` / `token.json`. The Google Classroom API scopes needed are read-only for the current student tools.
- **ADR discipline:** Any significant design decision (auth approach, tool naming, error handling strategy, etc.) must be recorded as an ADR under `docs/adrs/` before or alongside implementation.
- **project-state.md** is the living document — update it whenever a tool is added or a meaningful change lands.
