#!/bin/bash
set -euo pipefail
# Load Mem0 service token
ENV_FILE="/opt/aionui/projects/mem0-service/.env"
if [[ ! -r "${ENV_FILE}" ]]; then
    echo "FATAL: ${ENV_FILE} not readable" >&2
    exit 1
fi
set -a; source "${ENV_FILE}"; set +a
# Rewrite localhost → host.docker.internal
export MEM0_BASE_URL="${MEM0_BASE_URL:-http://host.docker.internal:8767}"
export MEM0_DEFAULT_USER="${MEM0_DEFAULT_USER_ID:-nate}"

exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/.claude/mcp-servers/sovi-memory/.venv \
    /opt/aionui/.claude/mcp-servers/sovi-memory/server.py
