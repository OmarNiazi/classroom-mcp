#!/bin/sh
# classroom-mcp installer for macOS and Linux.
#
#   curl -LsSf https://raw.githubusercontent.com/OmarNiazi/classroom-mcp/main/install.sh | sh
#
# Installs uv if it's missing (it runs classroom-mcp; no Python install needed),
# adds classroom-mcp to the AI apps it finds (Claude Desktop, Claude Code, Cursor),
# then opens Google sign-in. Undo with: uvx --managed-python classroom-mcp remove
set -eu

if ! command -v uvx >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
    export PATH
fi

if ! command -v uvx >/dev/null 2>&1; then
    echo "uv didn't install, or this terminal can't see it yet."
    echo "Open a new terminal and run the same command again."
    exit 1
fi

uvx --managed-python classroom-mcp@latest setup
