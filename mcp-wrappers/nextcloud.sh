#!/bin/bash
set -euo pipefail
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/nextcloud-mcp/.venv \
    /opt/aionui/mcp-servers/nextcloud-mcp/server.py
