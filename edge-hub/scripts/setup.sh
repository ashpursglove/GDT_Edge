#!/usr/bin/env bash
# Friendly installer for Raspberry Pi / Linux (Docker + Docker Compose plugin required).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== GDT Edge Hub — setup ==="
echo ""

if ! command -v docker &>/dev/null; then
  echo "Docker is not installed. On Raspberry Pi OS, install Docker Engine, then re-run this script."
  echo "See: https://docs.docker.com/engine/install/debian/"
  exit 1
fi

if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
  echo "Docker Compose is not available. Install the Docker Compose plugin."
  exit 1
fi

COMPOSE=(docker compose)
if ! docker compose version &>/dev/null; then
  COMPOSE=(docker-compose)
fi

echo "Enter values from your site operator (GDT Console / Vercel)."
read -r -p "Console API base URL (https://...): " API_URL
read -r -s -p "API key (Bearer / ingest key): " API_KEY
echo ""
read -r -p "Serial device path [/dev/ttyUSB0]: " SERIAL_IN
SERIAL_IN=${SERIAL_IN:-/dev/ttyUSB0}

if [[ ! -e "$SERIAL_IN" ]]; then
  echo "Warning: $SERIAL_IN does not exist yet. Plug in the USB-RS485 adapter and check:"
  echo "  ls -l /dev/ttyUSB* /dev/serial/by-id/"
fi

cat > .env <<EOF
GDT_CONSOLE_API_BASE_URL=${API_URL}
GDT_CONSOLE_API_KEY=${API_KEY}
GDT_SERIAL_DEVICE=${SERIAL_IN}
SERIAL_DEVICE=${SERIAL_IN}
GDT_PORT=8756
EOF

echo ""
echo "Building and starting container..."
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "Done. Open in a browser:"
echo "  http://${IP:-this-machine}:8756"
echo ""
echo "Useful commands:"
echo "  ${COMPOSE[*]} logs -f"
echo "  ${COMPOSE[*]} down"
