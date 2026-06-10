#!/bin/bash
set -euo pipefail
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/ghost-mcp/.venv \
    /opt/aionui/mcp-servers/ghost-mcp/server.py
