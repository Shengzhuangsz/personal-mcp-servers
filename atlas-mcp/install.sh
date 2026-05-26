#!/usr/bin/env bash
# atlas-mcp MCP — one-shot installer
#
# Usage:
#   cd atlas-mcp && ./install.sh
#
# What it does:
#   1. Creates .env from .env.example if missing
#   2. Opens .env in your $EDITOR for you to fill in credentials
#   3. Registers the server with Claude Code via `claude mcp add`
#   4. Verifies the registration

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "==> atlas-mcp installer"
echo "    target: $HERE"
echo

# 1. .env
if [[ ! -f .env ]]; then
    if [[ ! -f .env.example ]]; then
        echo "ERROR: .env.example not found in $HERE" >&2
        exit 1
    fi
    cp .env.example .env
    echo "✓ Created .env from .env.example"
    NEW_ENV=1
else
    echo "✓ .env already exists, leaving it alone"
    NEW_ENV=0
fi

# 2. open editor (skip if non-interactive or .env was already there)
if [[ "$NEW_ENV" == "1" && -t 0 && -t 1 ]]; then
    echo
    echo "→ Opening .env in ${EDITOR:-nano} so you can fill in credentials."
    echo "  Save and close to continue."
    read -r -p "  Press Enter to open editor (or Ctrl-C to skip)... "
    "${EDITOR:-nano}" .env
fi

# 3. sanity-check that creds are filled
if grep -qE "^PG_LARK_APP_ID=cli_xxxxxxxxxxxxxxxx" .env 2>/dev/null; then
    echo
    echo "WARNING: .env still contains placeholder values."
    echo "  Edit $HERE/.env before the server will work."
fi

# 4. register with Claude Code
if ! command -v claude >/dev/null 2>&1; then
    echo
    echo "WARNING: 'claude' CLI not found in PATH."
    echo "  After installing Claude Code, run:"
    echo "    claude mcp add atlas-mcp -s user -- python3 $HERE/server.py"
    exit 0
fi

echo
echo "==> Registering with Claude Code..."
if claude mcp list 2>/dev/null | grep -q "^atlas-mcp:"; then
    echo "✓ atlas-mcp already registered, skipping"
else
    claude mcp add atlas-mcp -s user -- python3 "$HERE/server.py"
    echo "✓ Registered"
fi

echo
echo "==> Verifying..."
claude mcp list 2>&1 | grep "atlas-mcp" || true

echo
echo "Done. Restart Claude Code to load the new MCP server."
