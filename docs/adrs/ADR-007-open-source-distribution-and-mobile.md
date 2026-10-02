# ADR-007: Open-source distribution, shared OAuth client, and mobile via self-hosted remote

**Date:** 2026-10-02  
**Status:** Accepted for Phase 1 (implemented by ADR-008, ADR-009); Phase 2 proposed

## Context
The server currently runs over stdio (ADR-001) with the developer's own `credentials.json` and
`token.json` (ADR-002). The goal is now a public GitHub project that any student can use, with
setup simple enough for non-developers, including students on mobile.

Three constraints shape the options:
1. **stdio cannot reach phones.** A mobile app cannot spawn a local process. Mobile access
   requires a remote HTTPS endpoint (MCP Streamable HTTP).
2. **Bring-your-own-credentials is not simple.** Asking each student to create a Google Cloud
   project, configure a consent screen and download `credentials.json` will lose most users.
3. **Hosting everyone's tokens is a liability.** A central multi-user service would store
   refresh tokens for student accounts (possibly minors), triggering security, FERPA/COPPA/GDPR
   and ongoing-cost burdens a hobby project should not take on.

## Decision
Distribute as **local-first, with a shared OAuth client and tokens kept on each student's
machine**, and treat mobile as a separate, later, self-hosted mode.

### Phase 1 - Local install (desktop hosts)
- Ship a single shared OAuth **client ID** (Desktop-app type) with the project. Register it
  once and put it through Google's OAuth app verification for the Classroom scopes.
- Students sign in via the browser on first run. `token.json` is stored in a per-user config
  directory (not the repo folder) and never leaves the machine.
- Package for one-step install: publish to PyPI so setup is `uvx classroom-mcp`, plus a
  one-click Claude Desktop extension bundle. README shows a copy-paste config for other hosts.
- stdio remains the default transport. ADR-001 stays in force for this mode.

### Phase 2 - Self-hosted remote (mobile and web)
- Add an optional Streamable HTTP mode, off by default, for **single-user personal
  deployment**: one student deploys their own instance (one-click deploy button), signs in
  once, and adds the URL as a custom connector in their MCP-capable app.
- Each instance holds exactly one user's token. There is no shared multi-user server operated
  by the project. This amends ADR-001: HTTP is permitted as an opt-in mode, never the default.
- Needs its own OAuth redirect URI, so a deployer may need their own OAuth client; document
  this honestly as the "advanced" path.
- Verify that connectors configured on the web reach the mobile app before documenting it as
  supported.

### Explicitly not doing
- A central hosted service that stores other users' Google tokens.
- Requesting `drive.readonly` by default. File download, if added, is a separate opt-in
  scope with its own consent.

## Consequences
- Students get a "click, sign in, done" desktop experience; the project holds no user data.
- Verification is deferred (decided 2026-10-03, see `docs/phase-1-plan.md`): the shared client
  ships **in production but unverified**, so students click through an "unverified app" warning
  and the app is capped at 100 lifetime users. Verification (privacy policy, homepage, review)
  is required to lift both, and should start before the cap is near. Per-student Cloud projects
  were rejected as the default because the consent screen and Desktop client cannot be created
  via any public API, so setup cannot be scripted.
- Some school Google Workspace domains block third-party apps; those students cannot sign in
  regardless of packaging. Document this.
- Mobile is real but second-class: more setup, one deployment per student, and dependent on
  third-party app support for remote MCP connectors.
- Code changes: move token storage to a user config dir, build the API client from explicitly
  supplied credentials rather than module-level files, pin dependencies, and migrate off
  `mcp` 1.0.0 to an SDK version with HTTP transport support.
- Open-source hygiene: LICENSE, SECURITY.md (how to report token-handling issues), and a
  privacy statement that data stays local.
