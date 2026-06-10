#!/bin/bash
set -euo pipefail
# Coolify needs credentials from the shared env file
set -a; source /opt/aionui/.env; set +a
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/coolify-mcp/.venv \
    /opt/aionui/mcp-servers/coolify-mcp/server.py
