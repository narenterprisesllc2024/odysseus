#!/bin/bash
set -euo pipefail
# Resolve GitHub token from keylib
export GITHUB_PERSONAL_ACCESS_TOKEN=$(bash /opt/aionui/.claude/skills/api-keys-resolver/scripts/get-key.sh GITHUB_TOKEN)
exec /opt/aionui/.npm-global/bin/mcp-server-github
