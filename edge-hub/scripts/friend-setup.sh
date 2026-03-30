#!/usr/bin/env bash
# Run on the Pi/Linux box: uses a pre-published image (no git build).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== GDT Edge Hub — install from registry ==="
echo ""

if ! command -v docker &>/dev/null; then
  echo "Install Docker first: https://docs.docker.com/engine/install/debian/"
  exit 1
fi

COMPOSE=(docker compose)
if ! docker compose version &>/dev/null; then
  COMPOSE=(docker-compose)
fi

if [[ -f .env ]]; then
  # shellcheck source=/dev/null
  set -a
  source .env
  set +a
fi

if [[ -z "${GDT_EDGE_IMAGE:-}" ]]; then
  read -r -p "Full image name (e.g. ghcr.io/yourname/gdt-edge-hub:latest): " GDT_EDGE_IMAGE
fi

if [[ -z "${GDT_EDGE_IMAGE:-}" ]]; then
  echo "GDT_EDGE_IMAGE is required."
  exit 1
fi

echo "Using image: $GDT_EDGE_IMAGE"
read -r -p "Console API base URL (https://...): " API_URL
read -r -s -p "API key (Bearer): " API_KEY
echo ""
read -r -p "Serial device [/dev/ttyUSB0]: " SERIAL_IN
SERIAL_IN=${SERIAL_IN:-/dev/ttyUSB0}

cat > .env <<EOF
GDT_EDGE_IMAGE=${GDT_EDGE_IMAGE}
GDT_CONSOLE_API_BASE_URL=${API_URL}
GDT_CONSOLE_API_KEY=${API_KEY}
GDT_SERIAL_DEVICE=${SERIAL_IN}
SERIAL_DEVICE=${SERIAL_IN}
GDT_PORT=8756
EOF

echo ""
echo "Pulling image..."
"${COMPOSE[@]}" -f docker-compose.dist.yml pull

echo "Starting..."
"${COMPOSE[@]}" -f docker-compose.dist.yml up -d

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "Open: http://${IP:-this-machine}:8756"
echo "Logs: ${COMPOSE[*]} -f docker-compose.dist.yml logs -f"
