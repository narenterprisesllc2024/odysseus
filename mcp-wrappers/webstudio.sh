#!/bin/bash
set -euo pipefail
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/webstudio-mcp/.venv \
    /opt/aionui/mcp-servers/webstudio-mcp/server.py
