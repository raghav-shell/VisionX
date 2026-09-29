#!/bin/sh
set -eu

if [ -n "${VISIONSENTINEL_SEED_FILE:-}" ] && [ -f "$VISIONSENTINEL_SEED_FILE" ]; then
  python /opt/visionsentinel/scripts/seed_users.py "$VISIONSENTINEL_SEED_FILE"
fi

exec "$@"
