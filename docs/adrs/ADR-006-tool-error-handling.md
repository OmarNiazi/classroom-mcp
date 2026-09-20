# ADR-006: Return tool failures as text content, not exceptions

**Date:** 2026-09-21  
**Status:** Accepted

## Context
Tool handlers can fail for reasons the student can act on (wrong course ID, missing argument,
a scope Google will not grant) and for reasons they cannot (network, token revoked). An MCP
handler can either raise — which the SDK turns into a JSON-RPC error — or return the failure
as ordinary `TextContent`.

A raised error reaches the model as a protocol-level failure with little usable detail. The
existing `get_all_courses` already returned errors as text; this ADR formalises that as the
rule and defines the message shape.

## Decision
Every handler catches its own failures and returns `TextContent`. `HttpError` is caught
separately from generic `Exception` so the HTTP status can be translated:

| Status | Message |
|---|---|
| 404 | "course not found. Check the course ID (use get_all_courses)." |
| 403 | "access denied by Google ... granted OAuth scopes do not cover this call." |
| other | the raw error |

Missing required arguments are validated before any API call and returned the same way.
All failures are also logged to stderr (per ADR-001) with the full exception.

`ValueError` for an unknown tool name is still **raised** — that is a host/protocol bug, not a
user-facing condition.

## Consequences
- The model sees actionable text and can self-correct — most usefully, a 404 tells it to go
  call `get_all_courses` rather than guessing another ID.
- The 403 message names scopes explicitly, because scope gaps are the most likely failure in
  this project (see `docs/project-state.md` on `download_files`).
- Tool calls "succeed" at the protocol level even when they fail semantically. A host that
  counts protocol errors will under-report failures; the stderr log is the source of truth.
- Verified against a bad course ID, a missing `course_id`, and a non-integer `limit` — each
  returns a clean message and the server stays up.
