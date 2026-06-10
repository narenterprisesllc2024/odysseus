#!/bin/bash
set -euo pipefail
# Load broker service token
ENV_FILE="/opt/aionui/projects/mem0-service/.env"
if [[ ! -r "${ENV_FILE}" ]]; then
    echo "FATAL: ${ENV_FILE} not readable" >&2
    exit 1
fi
set -a; source "${ENV_FILE}"; set +a
# Rewrite localhost → host.docker.internal
export BROKER_BASE_URL="${BROKER_BASE_URL:-http://host.docker.internal:8768}"

exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/.claude/mcp-servers/decision-broker/.venv \
    /opt/aionui/.claude/mcp-servers/decision-broker/server.py
