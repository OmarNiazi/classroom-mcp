# ADR-003: Pin explicit Python interpreter path in Claude Desktop config

**Date:** 2026-04-29  
**Status:** Superseded by ADR-008 (`uvx` provisions the interpreter; nothing to pin)

## Context
The machine has multiple Python versions on PATH (3.11, 3.13, 3.14). Claude Desktop resolves
`python` to whichever version appears first in its inherited PATH — which turned out to be
Python 3.14. Dependencies (`mcp`, `google-auth-oauthlib`, etc.) were installed under Python 3.13,
causing `ModuleNotFoundError: No module named 'google'` at server startup.

## Decision
Specify the **absolute path** to the correct Python interpreter in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-classroom": {
      "command": "C:\\Python313\\python.exe",
      "args": ["D:\\Misc Projects\\GCR-MCP\\classroom-mcp\\server.py"]
    }
  }
}
```

## Consequences
- Server reliably uses the interpreter where dependencies are installed.
- If the Python 3.13 installation moves, the config must be updated manually.
- Alternative (install deps into 3.14 or use a venv) deferred — acceptable for now given
  single-developer setup.
