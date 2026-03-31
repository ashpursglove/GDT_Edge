#!/usr/bin/env bash
# From the edge-hub folder: start containers (if needed) and open the UI in the default browser.
# Use on a Pi with a desktop, or adjust BROWSER_URL for another machine.

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f docker-compose.dist.yml ]]; then
  docker compose -f docker-compose.dist.yml up -d
elif [[ -f docker-compose.yml ]]; then
  docker compose up -d
else
  echo "No docker-compose file found in $(pwd)" >&2
  exit 1
fi

# Wait briefly for the HTTP server inside the container
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8756/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

BROWSER_URL="${BROWSER_URL:-http://127.0.0.1:8756}"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$BROWSER_URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$BROWSER_URL" || true
else
  echo "Open in a browser: $BROWSER_URL"
fi
