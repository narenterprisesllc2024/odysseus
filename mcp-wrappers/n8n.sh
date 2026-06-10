#!/bin/bash
set -euo pipefail
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/n8n-mcp/.venv \
    /opt/aionui/mcp-servers/n8n-mcp/server.py
