# ADR-010: `setup` registers the server in the user's AI apps

**Date:** 2026-10-03  
**Status:** Accepted

## Context
After ADR-008/009, installing still meant hand-editing a JSON config file in the right
place for each app, with an exact command line. In practice that was the step most likely to go
wrong: wrong file, broken JSON, wrong path, macOS GUI apps not seeing `~/.local/bin`. It was
also the step the owner found unacceptable for non-developers.

## Decision
Add `classroom-mcp setup` and `classroom-mcp remove`, plus one-line install scripts.

**`setup`** (in `hosts.py`):
- Finds supported apps by their config directories:
  - **Claude Desktop:** `%APPDATA%\Claude`, the Microsoft Store build's
    `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude`,
    `~/Library/Application Support/Claude`, `$XDG_CONFIG_HOME/Claude`.
  - **Cursor:** `~/.cursor`.
  - **Claude Code:** the `claude` CLI on PATH, registering via `claude mcp add --scope user`
    rather than editing `~/.claude.json`, which Claude Code owns.
- Merges a single `google-classroom` entry into `mcpServers`. Every other key and server is
  preserved; the file is backed up to `<name>.classroom-mcp.bak` before any write; writes are
  atomic, UTF-8 without BOM. BOM-prefixed or empty files are accepted.
- **Never rewrites a file it can't parse** (invalid JSON, non-object, `mcpServers` not an
  object). It reports "skipped" and prints the manual command instead.
- Registers `uvx` by **absolute path** (`shutil.which`), with `--managed-python classroom-mcp`,
  so apps launched from the Start menu or Dock don't depend on PATH.
- Idempotent: re-running reports "already set up" and doesn't touch the file. An older entry
  (e.g. the pre-package `python server.py`) is replaced.
- Then runs the same sign-in as `login`, in the terminal, before any app launches the server.
- `--client claude-desktop|claude-code|cursor` limits it to particular apps.

**`remove`** deletes only the `google-classroom` entry (same safety rules); `logout` remains the
separate step that revokes Google access.

**Install scripts:** `install.ps1` / `install.sh` at the repo root, fetched from
`raw.githubusercontent.com`. They install uv if missing (the uv installer runs in a child
process so it can't end the script), put `~/.local/bin` on PATH for the current session, and run
`uvx --managed-python classroom-mcp@latest setup`.

VS Code is not auto-configured yet; its user-level MCP config location has moved between
releases, and writing a file it ignores would report a false success. It's covered by the
manual instructions.

## Consequences
- Student setup is one pasted command plus restarting the app.
- The tool now writes to other applications' config files. Mitigated by merge-only edits,
  backups, refusing to touch unparseable files, and an explicit `remove`.
- If an app is running and later rewrites its config from memory, the entry could be lost.
  Re-running `setup` is safe; the README says to fully quit the app afterwards.
- The one-liners depend on the GitHub repo being public, and on the package names on
  PyPI/GitHub not changing.
- Config locations are app implementation details and can change; each one is a single
  entry in `json_hosts()` and covered by tests.
