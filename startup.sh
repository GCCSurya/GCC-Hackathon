#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f dist/index.html ]]; then
  echo "Missing dist/index.html. Build the frontend before deploying."
  exit 1
fi

# Keep one worker: incidents, timeline, and active scenario are in-process state.
# Do not use WEB_CONCURRENCY until that state is shared across workers.
exec gunicorn \
  --chdir backend \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  app:app