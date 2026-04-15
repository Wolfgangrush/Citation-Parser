#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/python3 telegram_bot.py
