#!/bin/bash
set -euo pipefail
# Resolve Stripe key: keylib first, then fall back to env var
# (env var is set via docker-compose env_file from shared.env)
KEY=$(bash /opt/aionui/.claude/skills/api-keys-resolver/scripts/get-key.sh STRIPE_SECRET_KEY 2>/dev/null) || KEY="${STRIPE_SECRET_KEY:-}"
if [ -n "$KEY" ]; then
    exec /opt/aionui/.npm-global/bin/mcp --api-key="$KEY"
else
    # Let the binary try its own env-var lookup (STRIPE_SECRET_KEY)
    exec /opt/aionui/.npm-global/bin/mcp
fi
