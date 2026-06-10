#!/bin/bash
set -euo pipefail
# Rewrite localhost → host.docker.internal
export LETTA_BASE="${LETTA_BASE:-http://host.docker.internal:8283}"
export LETTA_SERVER_PASSWORD="${LETTA_SERVER_PASSWORD:-stol4oUN5u2xvpzDESLVZSHMNkdw2wAR}"
export SOVI_AGENT_ID="${SOVI_AGENT_ID:-agent-43a4358a-2b35-4059-92e8-34dc7b6a19f1}"
export LETTA_TIMEOUT_S="${LETTA_TIMEOUT_S:-240}"

exec /app/mcp-wrappers/_run-venv.sh \
    /opt/aionui/services/mcp-letta/.venv \
    /opt/aionui/services/mcp-letta/server.py
