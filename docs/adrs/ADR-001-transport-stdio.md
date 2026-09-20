# ADR-001: Use stdio as the MCP transport

**Date:** 2026-04-29  
**Status:** Accepted

## Context
MCP servers can expose themselves over stdio (spawned as a subprocess by the host) or over
HTTP/SSE (a long-running network process). This server targets a single local user running
Claude Desktop on the same machine that has their Google credentials.

## Decision
Use **stdio** transport exclusively. The server is spawned on demand by Claude Desktop and
communicates via stdin/stdout JSON-RPC. No HTTP server is started.

## Consequences
- Simple deployment: no port management, no firewall rules, no service process to keep alive.
- Claude Desktop owns the process lifecycle — the server exits when the host disconnects.
- Logging must go to **stderr only**. Any stdout output corrupts the JSON-RPC stream.
- Not suitable for multi-user or remote access scenarios (acceptable for current scope).
