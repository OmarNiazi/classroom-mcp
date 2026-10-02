# classroom-mcp installer for Windows:
#   powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OmarNiazi/classroom-mcp/main/install.ps1 | iex"
# Installs uv if missing (it runs classroom-mcp; no Python install needed), adds classroom-mcp to the
# AI apps it finds (Claude Desktop, Claude Code, Cursor), then opens Google sign-in.
# Undo with: uvx --managed-python classroom-mcp remove
# Keep every statement on ONE line, with no blank lines and no trailing newline: some Windows
# PowerShell 5.1 setups make `iex` run the downloaded text line by line (tests/test_install_scripts.py).
if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) { Write-Host "Installing uv..."; powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"; $env:Path = "$env:USERPROFILE\.local\bin;$env:Path" }
if (Get-Command uvx -ErrorAction SilentlyContinue) { uvx --managed-python classroom-mcp@latest setup } else { Write-Host "uv didn't install, or this window can't see it yet. Close PowerShell, open a new window, and run the same command again." -ForegroundColor Yellow }