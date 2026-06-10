#!/bin/bash
set -euo pipefail
# Resolve Stripe key from keylib
KEY=$(bash /opt/aionui/.claude/skills/api-keys-resolver/scripts/get-key.sh STRIPE_SECRET_KEY)
exec /opt/aionui/.npm-global/bin/mcp --api-key="$KEY"
