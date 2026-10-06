# Project State

## Current Status (end of session 2026-10-03)
Phase 1 of open-sourcing (ADR-007) is **released and public**:

- **PyPI:** `classroom-mcp` 0.2.0 is the latest. 0.1.0 has a garbled PyPI README from a
  PowerShell encoding round-trip; 0.1.1 was built but never uploaded.
- **GitHub:** <https://github.com/OmarNiazi/classroom-mcp> is public. Private vulnerability
  reporting is on. CI (pytest + build on Windows/macOS/Linux, Python 3.11 and 3.13) is green.
- **GitHub Pages:** <https://omarniazi.github.io/classroom-mcp/> (README) and
  `/PRIVACY.html`, the URLs for the consent screen's App domain section.
- **Student install is one command:** `install.ps1` / `install.sh` (served raw from GitHub) install
  uv if missing, then run `uvx --managed-python classroom-mcp@latest setup`. That registers the
  server in Claude Desktop, Claude Code and Cursor, and signs in.

Same three tools, identical output. 73 offline tests.

### Verified
- **Live sign-in over stdio.** The first `get_all_courses` call opened the browser, the student
  finished within the 40 s wait, and the call returned courses directly (16 s), with no retry.
  Then all three tools ran against all 12 active courses (36 calls, 0 errors).
- **From PyPI.** `uvx --managed-python classroom-mcp` connects in ~8 s and returns live data.
- **Windows one-liner end to end in a sandbox** (no uv on PATH, isolated home and AppData). It
  installed uv, downloaded Python and the package, registered with Claude Desktop, and
  completed a real sign-in.
- **Hosted `install.ps1`** works both with and without `-NoProfile` (see ADR-010 on the
  line-by-line `iex` issue).

## Last Implemented (2026-10-07)
- **0.2.1: `setup` waits for Claude Desktop to be quit before editing its config.** Claude
  Desktop had silently reverted the 0.2.0 edit (it saves its in-memory config back while
  running), so on the dev machine it never launched the new entry. `setup` and `remove` now
  detect it running, ask the user to quit it from the tray, wait up to 5 minutes, then write. If
  it stays open, it's skipped and the other apps are still configured. Verified on the dev
  machine: after the fix Claude Desktop launched the `uvx` entry and served tool calls, and its
  own later config save kept the entry. Claude Desktop (Store build) logs are in
  `%LOCALAPPDATA%\Claude\Logs`.

## Earlier (2026-10-03)
- **Installer robustness:** `install.ps1` is one complete statement per line, with no blank
  lines and no trailing newline. On the dev machine, PowerShell 5.1 with profiles loaded made
  `irm | iex` run it line by line. The format is enforced by `tests/test_install_scripts.py`.
  The documented one-liner adds `-NoProfile`.
- **One-command install** (ADR-010, 0.2.0): `setup` / `remove` in `hosts.py`, with merge-only
  backed-up config edits and an absolute `uvx` path. Verified against the real Claude Desktop
  config.
- **Package + uvx distribution** (ADR-008, supersedes ADR-003), `--managed-python` everywhere.
- **Auth rework** (ADR-009, amends ADR-002): shared bundled client, token in
  `%LOCALAPPDATA%\classroom-mcp\`, sign-in on demand, partial-grant/revocation handling.
- README for non-developers, PRIVACY.md, SECURITY.md, MIT LICENSE.

## Tools Implemented
| Tool | Status |
|------|--------|
| get_all_courses | Done; verified live with the new auth |
| get_assessment_items | Done; verified live across 12 courses (incl. `only_pending`) |
| read_stream_announcements | Done; verified live across 12 courses |
| download_files | Blocked: needs `drive.readonly`, a restricted scope |

## Owner Actions Pending
1. **Google Auth Platform (project `gcr-mcp`):**
   - Confirm Audience shows **In production**.
   - Fill in App domain: home page `https://omarniazi.github.io/classroom-mcp/`, privacy
     `https://omarniazi.github.io/classroom-mcp/PRIVACY.html`, authorised domain
     `omarniazi.github.io`.
   - The "requires verification" banner is expected. Don't submit until nearing 100 users.
2. **PyPI:** replace the account-wide upload token with one scoped to `classroom-mcp`.
3. **Friend test:** run the one-liner on a second machine with a different Google account.
   Report the warning screen vs "Access blocked", personal vs school account, and any errors.

## Known Issues / Notes
- **Unverified app:** students see Google's warning screen; 100 lifetime users until verified.
- **School accounts** (especially under-18) often block unverified third-party apps. Not
  fixable in code; documented in README.
- The PyPI page for 0.2.0 shows the Windows one-liner without `-NoProfile`. It still works,
  because the fix is in the script. The next release picks up the current README.
- CI annotation: `actions/checkout@v4` and `astral-sh/setup-uv@v6` target the deprecated Node 20.
  Bump them when convenient.
- VS Code isn't auto-configured by `setup` (its user-level MCP config location has moved).
- Still 403 on the current scopes: `courseWorkMaterials.list`, `topics.list`, `students.list`,
  `teachers.list`, `userProfiles.get`.
- `get_all_courses` hardcodes `courseStates=["ACTIVE"]`; 29 archived courses are reachable.
- `download_files` would need `drive.readonly`, a *restricted* scope with much stricter
  verification. Out of reach for a public app for now.

## Next Step
Friend test of the one-liner. Then either the smaller wins (a `course_states` parameter, a
cross-course "what's due everywhere" tool, VS Code support in `setup`), or Phase 2 (mobile
via self-hosted HTTP, ADR-007).
