#!/bin/bash
set -euo pipefail
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/services/mcp-claude-accounts/.venv \
    /opt/aionui/services/mcp-claude-accounts/server.py
