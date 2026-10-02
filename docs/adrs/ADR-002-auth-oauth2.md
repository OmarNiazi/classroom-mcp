# ADR-002: OAuth 2.0 with local token cache for authentication

**Date:** 2026-04-29  
**Status:** Accepted, amended by ADR-009 (shared bundled client, token in the user config dir,
sign-in on demand instead of at startup)

## Context
The Google Classroom API requires authentication on behalf of a specific user (the student).
Options considered:
1. OAuth 2.0 with `credentials.json` + `token.json` cache
2. Service account (requires domain-wide delegation — not available for personal accounts)
3. API key (not supported for user data endpoints)

## Decision
Use **OAuth 2.0 InstalledAppFlow** (`google-auth-oauthlib`).  
- `credentials.json` holds the OAuth client ID/secret (never committed to git).  
- On first run, `flow.run_local_server()` opens a browser for user consent and writes `token.json`.  
- On subsequent runs, `token.json` is loaded and refreshed automatically if expired.  
- Auth is triggered **eagerly at server startup** (not lazily on first tool call) so the browser
  flow completes before any MCP client interaction begins.

## Consequences
- First run requires a browser — cannot run fully headless on first auth.
- `credentials.json` and `token.json` must be in `.gitignore`.
- `OAUTHLIB_RELAX_TOKEN_SCOPE=1` is set at startup because Google silently drops
  `classroom.coursework.me.readonly` during consent (under investigation; see project-state.md).
- Token refresh is automatic; re-auth only needed if the refresh token is revoked.
