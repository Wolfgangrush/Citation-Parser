#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PORT="$(grep -E '^BACKEND_PORT=' .env | tail -n 1 | cut -d= -f2)"
PORT="${PORT:-5757}"

if command -v tailscale >/dev/null 2>&1; then
  IP="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
  if [ -n "$IP" ]; then
    echo "Open this on your phone:"
    echo "http://$IP:$PORT"
    exit 0
  fi
fi

echo "Could not read Tailscale IP automatically."
echo "Run: tailscale ip -4"
echo "Then open: http://<that-ip>:$PORT"
