# ADR-008: Ship as a PyPI package launched with `uvx`

**Date:** 2026-10-03  
**Status:** Accepted  
**Supersedes:** ADR-003

## Context
Phase 1 of ADR-007 makes the server installable by students with no developer background.
The original layout was a single `classroom-mcp/server.py` run by an explicitly pinned
interpreter (ADR-003). That required each user to install Python, install requirements into
the right interpreter, and hand-write an absolute path into their host config. That is the
exact failure ADR-003 was written to work around.

## Decision
- Restructure into an installable package, `src/classroom_mcp/`, with a `classroom-mcp`
  console script (`pyproject.toml`, hatchling build):
  - `server.py`: MCP tool definitions and dispatch only.
  - `classroom.py`: Classroom API calls, pagination, submission merge (ADR-004).
  - `formatting.py`: pure rendering helpers.
  - `auth.py`: sign-in and token storage (ADR-009).
  - `errors.py`: failure text (ADR-006).
  - `__main__.py`: CLI (`serve` default, `login`, `logout`, `status`).
- Publish to PyPI as `classroom-mcp`. The host config students paste is:
  `{"command": "uvx", "args": ["classroom-mcp"]}`.
  `uvx` provisions a suitable Python and an isolated environment on first launch, so there is
  no interpreter to choose or pin.
- Dependencies are ranges, not pins: `mcp>=1.30,<2` (the version tested), plus Google client
  libraries. `uv.lock` pins the development environment.
- `requires-python >= 3.11`: Google's API client ends support for 3.10 on 2026-10-04.
- Tool names, arguments and output text are unchanged by the restructure; `tests/` (pytest,
  offline fakes of the Classroom service) locks that in, plus an end-to-end test over the real
  stdio transport in a subprocess.
- Releases are manual (`uv build` + `uv publish`) until there is a reason to automate them.
  CI runs the tests on Windows, macOS and Linux.

## Consequences
- Students need exactly one prerequisite, `uv`, installed with a single copy-paste command.
- **All documented commands use `uvx --managed-python`** (added 2026-10-03, after 0.1.0). By
  default uv will build the tool environment on any system Python that satisfies
  `requires-python`. On the developer's machine it picked a version-manager shim
  (`C:\Python\shims\python3.13.exe`), producing a broken environment
  ("No Python at C:\Python\shims\python.exe"). Students' machines can have similar stubs
  (Microsoft Store aliases, pyenv shims). `--managed-python` makes uv use its own CPython,
  downloaded once (~25 MB), so the result no longer depends on what else is installed.
- ADR-003's interpreter pinning is obsolete. A GUI host may still not see `uvx` on PATH right
  after installing uv; the README documents using the full path in that case.
- `uvx` resolves the newest compatible dependencies at install time, not what was tested. The
  `<2` cap on `mcp` limits the blast radius; a bad upstream release would still surface first
  in users' hands. Mitigation if it happens: tighten the range and publish a patch release.
- The `mcp` 1.0.0 low-level `Server` API is kept (it still works on 1.30). Migrating to
  `FastMCP` is deferred: it would change no behaviour.
- The old `classroom-mcp/` folder is removed. Local development runs from the repo with
  `uv run classroom-mcp`.
