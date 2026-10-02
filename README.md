# classroom-mcp

Let your AI assistant read your **Google Classroom**: your classes, what's due (and whether
you've turned it in), and your teachers' announcements.

> "What do I still have to hand in this week?"
> "Did my networks teacher post anything about the exam?"
> "Which assignments am I late on, across all my classes?"

It works with any app that supports MCP servers, such as Claude Desktop, Claude Code, Cursor
and VS Code. It's **read-only**: it can't submit work, post, or change anything.

---

## Install (one command)

**On Windows:** open **Command Prompt** or **PowerShell** and paste:
```powershell
powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OmarNiazi/classroom-mcp/main/install.ps1 | iex"
```

**On a Mac or Linux** (not Windows): open **Terminal** and paste:
```sh
curl -LsSf https://raw.githubusercontent.com/OmarNiazi/classroom-mcp/main/install.sh | sh
```
If Windows says *"'sh' is not recognized"*, you pasted the Mac command. Use the Windows one above.

It adds itself to Claude Desktop, Claude Code and Cursor (whichever you have), then opens your
browser to sign in with Google:

1. Choose the Google account you use for Classroom.
2. Google will say **"Google hasn't verified this app"**. This is expected for a new
   open-source project. Click **Advanced**, then **Go to classroom-mcp (unsafe)**.
3. **Leave every box ticked** and click **Continue**. Every permission is read-only.

Then **fully quit and reopen your AI app** (on Windows, quit from the system tray; on Mac,
press Cmd+Q) and ask *"What do I still have to hand in this week?"*

That's it. You stay signed in on this computer.

**What the command does:** it installs [uv](https://docs.astral.sh/uv/) if you don't have it (uv
runs this server with its own copy of Python, so you don't install Python yourself), then runs
`uvx --managed-python classroom-mcp setup`. Before changing an app's settings file, `setup` saves
a backup next to it, and it only adds a `google-classroom` entry. Your other settings are left
alone.

### Other apps, or doing it by hand
If you already have uv, you can run the setup step on its own:
```sh
uvx --managed-python classroom-mcp setup
```
For an MCP app that `setup` doesn't know about (e.g. VS Code), add a server with command
`uvx` and arguments `--managed-python classroom-mcp`. For VS Code that's `.vscode/mcp.json`:
```json
{ "servers": { "google-classroom": { "command": "uvx", "args": ["--managed-python", "classroom-mcp"] } } }
```
If you skip the sign-in, it starts automatically the first time you ask a question.

### Uninstall
```sh
uvx --managed-python classroom-mcp remove   # take it out of your AI apps
uvx --managed-python classroom-mcp logout   # revoke Google access and delete your sign-in
```

---

## What it can see

| Can | Can't |
|---|---|
| Your active classes | Submit, unsubmit or edit anything |
| Assignments, due dates, points, attachment names | See classmates' work or grades |
| **Your own** submission status and grades | Download attachment files (planned) |
| Teacher announcements | Post or comment |

Tools exposed to the assistant: `get_all_courses`, `get_assessment_items`
(with an `only_pending` filter), `read_stream_announcements`.

## Privacy
Everything runs on **your computer**. Your Google sign-in is saved only in your user folder
(`%LOCALAPPDATA%\classroom-mcp\` on Windows, `~/Library/Application Support/classroom-mcp/` on
macOS, `~/.config/classroom-mcp/` on Linux). There's no server run by this project, and no
analytics. Your Classroom data goes from Google to your app, and nowhere else. Your AI app's own
privacy terms apply to what you ask it. Full details are in [PRIVACY.md](https://github.com/OmarNiazi/classroom-mcp/blob/main/PRIVACY.md).

## Signing out / switching accounts
```sh
uvx --managed-python classroom-mcp logout   # revokes access with Google and deletes the saved sign-in
uvx --managed-python classroom-mcp login    # sign in again, now
uvx --managed-python classroom-mcp status   # are you signed in, and where it's saved
```
You can also remove access anytime at <https://myaccount.google.com/permissions>.

## Troubleshooting

**"My school blocks this app" / "Access blocked" / "admin_policy_enforced"**
Your school's Google Workspace doesn't allow unverified third-party apps. This is common
for school-managed accounts, especially for students under 18. Only your school's IT admin
can allow it. A personal Google account that's enrolled in your classes will work.

**The app says it can't find `uvx`, or the server fails to start**
Apps opened from the Start menu or Dock don't always see newly installed tools. Restart your
computer, or put the full path in `"command"` instead of `uvx`:
- Windows: `"C:\\Users\\<you>\\.local\\bin\\uvx.exe"` (in JSON, backslashes are doubled)
- macOS: `"/Users/<you>/.local/bin/uvx"`
- Linux: `"/home/<you>/.local/bin/uvx"`

**The browser didn't open.** The assistant's reply includes the sign-in link; open it yourself.

**I unticked a permission.** You'll be asked to sign in again. Leave all boxes ticked.

**It worked before, now it asks me to sign in again.** You (or your school) removed its
access, or the sign-in expired. Just sign in again.

## Phones
Not yet. Phone apps can't launch programs on your phone, so this needs a hosted version. A
self-hosted option is planned. For now, use a computer.

## Known limits
- Until Google verifies the app, you'll see the warning screen, and it's limited to the first
  100 users.
- Only **active** classes are listed.
- Attachment files can't be downloaded yet (that needs access to your whole Google Drive).

---

## Development
```sh
git clone https://github.com/OmarNiazi/classroom-mcp && cd classroom-mcp
uv sync
uv run pytest
uv run classroom-mcp          # run the server from source (stdio)
```
Point a host at your checkout with
`"command": "uv", "args": ["run", "--directory", "/path/to/classroom-mcp", "classroom-mcp"]`.

| Environment variable | Purpose |
|---|---|
| `CLASSROOM_MCP_CLIENT_SECRETS` | Path to your own OAuth client JSON (Desktop app type) instead of the bundled one |
| `CLASSROOM_MCP_CONFIG_DIR` | Store the sign-in somewhere else (e.g. a second account) |

Design decisions are recorded in [`docs/adrs/`](https://github.com/OmarNiazi/classroom-mcp/tree/main/docs/adrs). Start with
[`docs/project-state.md`](https://github.com/OmarNiazi/classroom-mcp/blob/main/docs/project-state.md).

## License
[MIT](https://github.com/OmarNiazi/classroom-mcp/blob/main/LICENSE)
