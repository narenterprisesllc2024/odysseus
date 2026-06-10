#!/bin/bash
set -euo pipefail
# Resolve API key from keylib
if [[ -z "${POSTIZ_API_KEY:-}" ]]; then
    KEY_RESOLVER="/opt/aionui/.claude/skills/api-keys-resolver/scripts/get-key.sh"
    if [[ -x "${KEY_RESOLVER}" ]] || [[ -r "${KEY_RESOLVER}" ]]; then
        POSTIZ_API_KEY="$(bash "${KEY_RESOLVER}" POSTIZ_API_KEY 2>/dev/null)" || true
    fi
    export POSTIZ_API_KEY="${POSTIZ_API_KEY:-}"
fi
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/postiz-mcp/.venv \
    /opt/aionui/mcp-servers/postiz-mcp/server.py
