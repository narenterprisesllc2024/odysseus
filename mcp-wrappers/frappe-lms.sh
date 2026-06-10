#!/bin/bash
set -euo pipefail
# Load Frappe credentials from shared env
if [[ -f /opt/aionui/.env ]]; then
    set -a; source /opt/aionui/.env; set +a
fi
# Defaults matching the host run.sh
export FRAPPE_API_KEY="${FRAPPE_API_KEY:-fdca734684f34ad}"
export FRAPPE_API_SECRET="${FRAPPE_API_SECRET:-e4a0004f533ec78}"
# Rewrite localhost → host.docker.internal for container networking
export FRAPPE_LMS_URL="${FRAPPE_LMS_URL:-http://host.docker.internal:3570}"
export FRAPPE_LMS_SITE="${FRAPPE_LMS_SITE:-learn.mysoviai.com}"

exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/mcp-servers/frappe-lms-mcp/.venv \
    /opt/aionui/mcp-servers/frappe-lms-mcp/server.py
