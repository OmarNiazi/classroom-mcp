# ADR-009: Shared unverified OAuth client, per-user token, sign-in on demand

**Date:** 2026-10-03  
**Status:** Accepted  
**Amends:** ADR-002

## Context
ADR-002 had each installation bring its own `credentials.json`, sign in eagerly at server
startup, and keep `token.json` next to the code. For a public, open-source install
(ADR-007 Phase 1) each of those is a problem:

- Creating a Google Cloud project, consent screen and Desktop client is far too technical for
  most students. Google exposes no public API for creating the consent screen or a Desktop
  OAuth client, so it cannot be scripted for them.
- Eager sign-in blocks server startup on a browser interaction; hosts can time out waiting.
- `google_auth_oauthlib`'s `run_local_server()` prints the sign-in URL to **stdout**, which is
  the MCP protocol channel (ADR-001).
- A token next to the code doesn't exist in a `uvx`-managed install, and would be per-version.

## Decision
**One shared client.** The project's Desktop-app OAuth client (Cloud project `gcr-mcp`) ships
inside the package as `client_config.json`. Google treats Desktop client secrets as
non-confidential, since every installed copy must carry them. `CLASSROOM_MCP_CLIENT_SECRETS=<path>`
overrides it for forks and anyone who wants their own client.

**Unverified, in production.** Google app verification is deferred (see ADR-007). Students see
Google's "hasn't verified this app" screen and click through; the app is capped at 100 lifetime
users until verified. Testing mode was rejected: it needs every user's email added by hand and
expires sign-ins every 7 days.

**Minimal scopes.** `classroom.courses.readonly`, `classroom.announcements.readonly`,
`classroom.student-submissions.me.readonly`. The never-granted
`classroom.coursework.me.readonly` is dropped; `courses.readonly` already covers coursework.

**Token per user, outside the code.** Stored at `platformdirs.user_config_dir("classroom-mcp")`
(`%LOCALAPPDATA%\classroom-mcp\token.json` on Windows), written atomically, mode 0600 on POSIX.
`CLASSROOM_MCP_CONFIG_DIR` overrides the directory.

**Sign-in on demand.** The server starts with no auth. When a tool call finds no usable token:
1. A sign-in attempt starts: a one-shot HTTP listener on `127.0.0.1:<random port>` (our own,
   not `run_local_server`, so nothing reaches stdout), with PKCE, `access_type=offline` and
   `prompt=consent` (so a refresh token is issued even for a returning account). The browser
   is opened automatically.
2. The tool call waits up to 40 s (under common 60 s host timeouts) for it to finish. If it
   does, the original question is answered with no retry needed.
3. Otherwise it returns instructions with the sign-in link, the unverified-app click-through,
   and the school-admin caveat. Repeat calls join the same attempt; only one browser window.
4. The listener closes after success, failure, or 5 minutes. A failed attempt's reason is
   reported once; the next call starts a fresh attempt.

**Granular consent is checked.** Google lets users untick individual permissions.
`OAUTHLIB_RELAX_TOKEN_SCOPE` stays set so oauthlib returns the token instead of raising, and the
granted scopes are compared against the required ones; a partial grant is rejected with a
message naming what was unticked, and no token is saved.

**Self-healing.** A refresh that fails with `RefreshError` (revoked, expired, client changed),
at load time or mid-call, deletes the token and falls back to on-demand sign-in.

**CLI.** `classroom-mcp login` (foreground sign-in), `logout` (revoke with Google, best
effort, then delete), `status`.

## Consequences
- A student's whole setup is: install, paste config, click sign in. No Cloud project, no files.
- Tokens never leave the student's machine; the project operates no server.
- The shared client secret is public in the repository. Anyone could reuse the client ID in
  their own app, which would show this project's name on their consent screen. That is the
  accepted cost for every open-source desktop OAuth app; Google's mitigation is verification,
  and the 100-user cap is per client, so abuse could consume it.
- Many school-managed Google accounts, especially under-18 accounts, block unverified
  third-party apps. Google shows the block in the browser; the flow simply never completes.
  Nothing in code can work around it; the README and sign-in message say to ask IT.
- The sign-in listener is a transient HTTP server bound to loopback. It is not an MCP transport;
  ADR-001's stdio-only rule for the protocol still holds.
- Existing installs' `token.json` files are not migrated; one fresh sign-in is needed.
