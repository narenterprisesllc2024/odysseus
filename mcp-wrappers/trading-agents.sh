#!/bin/bash
set -euo pipefail
# Rewrite localhost → host.docker.internal
export TA_API_URL="${TA_API_URL:-http://host.docker.internal:25809}"
export TA_TIMEOUT_S="${TA_TIMEOUT_S:-300}"

exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/services/mcp-trading-agents/.venv \
    /opt/aionui/services/mcp-trading-agents/server.py
