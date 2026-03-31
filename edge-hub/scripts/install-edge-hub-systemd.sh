#!/usr/bin/env bash
# Install systemd service so Edge Hub starts on boot (Linux / Raspberry Pi with Docker).
# Usage:
#   chmod +x scripts/install-edge-hub-systemd.sh
#   export EDGE_HUB_DIR="$HOME/GDT_Edge/edge-hub"   # or your path
#   export HUB_USER="$USER"
#   ./scripts/install-edge-hub-systemd.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EDGE_HUB_DIR="${EDGE_HUB_DIR:-$ROOT}"
HUB_USER="${HUB_USER:-$USER}"
UNIT_SRC="$(dirname "$0")/systemd/gdt-edge-hub.service"
UNIT_DST="/etc/systemd/system/gdt-edge-hub.service"

if [[ ! -f "$EDGE_HUB_DIR/docker-compose.dist.yml" ]]; then
  echo "EDGE_HUB_DIR must contain docker-compose.dist.yml (got: $EDGE_HUB_DIR)" >&2
  exit 1
fi

if ! id -u "$HUB_USER" >/dev/null 2>&1; then
  echo "User $HUB_USER does not exist." >&2
  exit 1
fi

if ! groups "$HUB_USER" | grep -q '\bdocker\b'; then
  echo "User $HUB_USER should be in the docker group: sudo usermod -aG docker $HUB_USER" >&2
  exit 1
fi

EDGE_HUB_DIR="$(cd "$EDGE_HUB_DIR" && pwd)"

tmp="$(mktemp)"
sed -e "s|REPLACE_USER|$HUB_USER|g" -e "s|REPLACE_EDGE_HUB_DIR|$EDGE_HUB_DIR|g" "$UNIT_SRC" >"$tmp"
sudo cp "$tmp" "$UNIT_DST"
rm -f "$tmp"

sudo systemctl daemon-reload
sudo systemctl enable gdt-edge-hub.service
sudo systemctl start gdt-edge-hub.service

echo "Installed. Status: sudo systemctl status gdt-edge-hub.service"
echo "Logs:    journalctl -u gdt-edge-hub.service -f"
