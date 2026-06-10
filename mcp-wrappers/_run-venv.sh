#!/bin/bash
# Generic venv runner for inside the Odysseus container.
#
# The host venvs have .venv/bin/python3 → /usr/bin/python3, which on the
# host is Python 3.12. Inside the container /usr/bin/python3 is Python 3.13
# (Debian trixie system Python). The Docker image's Python 3.12 lives at
# /usr/local/bin/python3. This script bridges the gap by:
#   1. Adding the venv's site-packages to PYTHONPATH
#   2. Exec'ing the server script with the container's Python 3.12
#
# Usage: _run-venv.sh <venv-dir> <server-script> [extra-args...]
set -euo pipefail

VENV="$1"; SCRIPT="$2"; shift 2

SITE="${VENV}/lib/python3.12/site-packages"
if [ ! -d "$SITE" ]; then
    echo "FATAL: site-packages not found at $SITE" >&2
    exit 1
fi

export PYTHONPATH="${SITE}${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/local/bin/python3 "$SCRIPT" "$@"
