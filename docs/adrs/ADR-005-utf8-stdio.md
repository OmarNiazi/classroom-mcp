# ADR-005: Force UTF-8 on stdio streams

**Date:** 2026-09-21  
**Status:** Accepted

## Context
Implementing `read_stream_announcements` surfaced a crash that killed the **entire server
process**, not just the failing tool call:

```
UnicodeEncodeError: 'charmap' codec can't encode character '→' in position 304
  File "mcp/server/stdio.py", line 75, in stdout_writer
    await stdout.write(json + "\n")
```

The trigger was an ordinary teacher announcement containing arrows:
`"Go to Edit → Preferences → Protocols → UDP/TCP"`.

Root cause: `mcp.server.stdio.stdio_server()` wraps `sys.stdin` / `sys.stdout` **directly**
(see its source — `anyio.wrap_file(sys.stdout)`). On Windows, Python gives those streams the
console codepage, which is `cp1252` on this machine. MCP frames are UTF-8 JSON, so any
character outside Latin-1 — an arrow, a curly quote, an em dash, an emoji — raises inside
the transport writer. The exception escapes the anyio task group and terminates the process.

This is not exotic input. Arrows and smart quotes appear routinely in Classroom announcements
and assignment descriptions, so the server would have died in normal use.

## Decision
Reconfigure the standard streams to UTF-8 at import time, before the transport starts:

```python
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
```

`stdin` is left **strict** — a decode error there means genuinely malformed protocol input and
should be loud. `stdout` and `stderr` use `errors="replace"` as a backstop: substituting one
character is always preferable to killing the server, and U+FFFD inside a JSON string value
keeps the frame structurally valid.

The `hasattr` guard covers stream objects that a host might substitute without `reconfigure`.

## Consequences
- Non-ASCII course content round-trips correctly — verified with arrows, en dashes, accented
  text and emoji.
- This must run **before** `stdio_server()` is entered. Placing it at module import time makes
  that ordering hard to break accidentally.
- Any future stdio-based MCP server on Windows needs the same treatment; this is a property of
  the SDK's transport, not of this server.
- **Update 2026-10-03:** `mcp` >= 1.30 wraps the protocol streams in UTF-8 itself, so the SDK
  no longer has this bug. The reconfigure is kept (now first thing in `__main__.main()`) for
  stderr logging and the CLI's own console output. `tests/test_stdio.py` checks non-ASCII
  output end to end over the real transport.
- ADR-001 already requires logging to stderr only. That still holds — this ADR only changes the
  encoding of those streams, not which stream is used.
