#!/bin/bash
set -euo pipefail
# Rewrite localhost → host.docker.internal
export OPENBB_BASE="${OPENBB_BASE:-http://host.docker.internal:25811}"

exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/services/mcp-openbb/.venv \
    /opt/aionui/services/mcp-openbb/server.py
