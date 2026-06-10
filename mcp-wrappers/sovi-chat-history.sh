#!/bin/bash
set -euo pipefail
exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/projects/sovereign-memory-bridge/.venv \
    /opt/aionui/projects/sovereign-memory-bridge/mcp_server.py
