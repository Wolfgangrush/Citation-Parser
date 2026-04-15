#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p logs
.venv/bin/python3 backend.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

sleep 2
.venv/bin/python3 telegram_bot.py > logs/telegram_bot.log 2>&1 &
BOT_PID=$!
echo "Telegram bot PID: $BOT_PID"
echo "Dashboard: http://localhost:5757"
echo "Logs: logs/backend.log and logs/telegram_bot.log"

trap 'kill "$BACKEND_PID" "$BOT_PID" 2>/dev/null || true' INT TERM EXIT
wait
