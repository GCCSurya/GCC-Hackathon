#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f dist/index.html ]]; then
  echo "Missing dist/index.html. Build the frontend before deploying."
  exit 1
fi

exec gunicorn \
  --chdir backend \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  app:app