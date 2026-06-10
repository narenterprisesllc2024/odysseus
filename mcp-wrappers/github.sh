#!/bin/bash
set -euo pipefail
# Resolve GitHub token: keylib first, then fall back to env var
export GITHUB_PERSONAL_ACCESS_TOKEN=$(bash /opt/aionui/.claude/skills/api-keys-resolver/scripts/get-key.sh GITHUB_TOKEN 2>/dev/null) || \
    export GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_TOKEN:-}"
exec /opt/aionui/.npm-global/bin/mcp-server-github
