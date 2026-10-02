# classroom-mcp installer for Windows.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OmarNiazi/classroom-mcp/main/install.ps1 | iex"
#
# Installs uv if it's missing (it runs classroom-mcp; no Python install needed),
# adds classroom-mcp to the AI apps it finds (Claude Desktop, Claude Code, Cursor),
# then opens Google sign-in. Undo with: uvx --managed-python classroom-mcp remove

if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    # A child process, so the uv installer can't end this script early.
    powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
    Write-Host "uv didn't install, or this window can't see it yet." -ForegroundColor Yellow
    Write-Host "Close PowerShell, open a new window, and run the same command again." -ForegroundColor Yellow
    return
}

uvx --managed-python classroom-mcp@latest setup
