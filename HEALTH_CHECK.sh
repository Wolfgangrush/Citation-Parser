#!/usr/bin/env bash
# Health Check Script for SCC Parser
# Run this periodically to ensure services are running

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_URL="${SCCPARSER_URL:-http://localhost:5757}"

# Check if backend is responding
if curl -sSf "$BACKEND_URL/api/stats" > /dev/null 2>&1; then
    echo "✓ Backend is healthy"
    exit 0
else
    echo "✗ Backend is not responding"
    # Attempt to restart
    if [ -x "$SCRIPT_DIR/sccparser" ]; then
        echo "Attempting to restart..."
        "$SCRIPT_DIR/sccparser" restart
    fi
    exit 1
fi
