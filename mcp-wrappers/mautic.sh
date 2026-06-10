#!/bin/bash
set -euo pipefail
# Load Mautic credentials from shared env
set -a; source /opt/aionui/.env; set +a
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/mautic-mcp/.venv \
    /opt/aionui/mcp-servers/mautic-mcp/server.py
