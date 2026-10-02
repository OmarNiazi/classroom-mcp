# Project State

## Current Status
Phase 1 of open-sourcing (ADR-007) is **released on PyPI** as `classroom-mcp`
(0.1.0 on 2026-10-03; 0.1.1 fixes the PyPI README). The server is an installable package
(`src/classroom_mcp/`) that students run with `uvx --managed-python classroom-mcp`,
using a shared bundled OAuth client and on-demand browser sign-in. The same three tools as
before, with identical output. 52 offline tests pass (run on Python 3.10 and 3.13); the
wheel builds and runs through `uvx`.

**Verified live (2026-10-03):** fresh on-demand sign-in over stdio. The first
`get_all_courses` call opened the browser, and the student finished within the 40 s wait, so the
call returned courses directly (16 s), no retry. Then all three tools ran against all 12 active
courses (36 calls, 0 errors). All three scopes were granted.

**Verified from PyPI:** `uvx --managed-python classroom-mcp` run from a neutral directory
connects over stdio in ~8 s and returns live data for all three tools. Without
`--managed-python`, uv built the environment on a broken Python shim on the dev machine (see
ADR-008), so every documented command now includes it.

**0.1.0's PyPI page has a garbled README** (a PowerShell encoding round-trip); fixed in 0.1.1.

## Last Implemented (2026-10-03)
- **One-command install** (ADR-010, 0.2.0): `classroom-mcp setup` finds Claude Desktop
  (incl. the Store build), Claude Code and Cursor, merges a `google-classroom` entry (backup
  first, never touches unparseable files, absolute `uvx` path), then signs in. `remove` undoes
  it. `install.ps1` / `install.sh` install uv and run setup. Verified against the real Claude
  Desktop config on the dev machine: the old `python server.py` entry was replaced, and other
  keys were preserved.
- **Package restructure** (ADR-008, supersedes ADR-003): `server.py` split into `server`,
  `classroom`, `formatting`, `auth`, `errors`, `__main__`. `pyproject.toml` (hatchling),
  `mcp>=1.30,<2`, Python >= 3.11. Old `classroom-mcp/` folder removed.
- **Auth rework** (ADR-009, amends ADR-002): bundled Desktop client
  (`client_config.json`, project `gcr-mcp`), token in `%LOCALAPPDATA%\classroom-mcp\`,
  sign-in starts on the first tool call (own loopback listener, since `run_local_server`
  prints to stdout), waits 40 s so the question can still be answered, rejects partial
  (granular-consent) grants, self-heals on revoked tokens. CLI `login` / `logout` / `status`.
  Scopes reduced to the three actually granted.
- **Tests:** formatting, submission merge, error text, the full sign-in state machine
  (simulated Google redirect), and an end-to-end stdio test including non-ASCII output.
- `mcp` 1.30 now wraps stdio in UTF-8 itself; the ADR-005 reconfigure stays as a backstop.
- README for non-developers, PRIVACY.md, SECURITY.md, MIT LICENSE, CI on 3 OSes.

## Tools Implemented
| Tool | Status |
|------|--------|
| get_all_courses | Done; verified live with the new auth |
| get_assessment_items | Done; verified live across 12 courses (incl. `only_pending`) |
| read_stream_announcements | Done; verified live across 12 courses |
| download_files | Blocked: needs `drive.readonly`, a restricted scope |

## Owner Actions Pending
1. Google Cloud Console, project `gcr-mcp` → Google Auth Platform: set Branding (app name,
   support email), make sure Data Access lists the three scopes, then **Audience → Publish app**
   (Testing → In production). Do **not** submit for verification yet.
2. ~~PyPI account + publish 0.1.0~~ done. Publish 0.1.1. Then replace the account-wide
   token with a project-scoped one.
3. Make the GitHub repo public (README/PRIVACY links point at it; GitHub Pages for the
   consent-screen home page and privacy policy).

## Known Issues / Notes
- **Unverified app:** students see Google's warning screen; 100 lifetime users until verified.
  Start verification (needs PRIVACY.md hosted + homepage) before nearing the cap.
- **School accounts** (especially under-18) often block unverified third-party apps. Not
  fixable in code; documented in README.
- `client_config.json` contains the client secret and **will be public**. That's intended
  (ADR-009), but GitHub secret scanning may flag it on push.
- Still 403 on the current scopes: `courseWorkMaterials.list`, `topics.list`, `students.list`,
  `teachers.list`, `userProfiles.get`.
- `get_all_courses` hardcodes `courseStates=["ACTIVE"]`; 29 archived courses are reachable.
- `download_files` would need `drive.readonly`, which Google classes as a *restricted* scope:
  much stricter verification (possibly a third-party security assessment). Out of reach for a
  public app for now.

## Next Step
Publish 0.2.0, push and make the repo public (the install one-liners are served from
raw.githubusercontent.com), then a friend test of the one-liner on a second machine and account.
After that: Phase 2 (mobile via
self-hosted HTTP, ADR-007), or the smaller wins (a `course_states` parameter, a cross-course
"what's due everywhere" tool).
