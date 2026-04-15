#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir -p pdfs_received templates logs instance exports "Bare Acts "
chmod +x start run_backend.sh run_bot.sh run_all.sh phone_url.sh 2>/dev/null || true

echo "Setup complete."
echo "Edit .env with TELEGRAM_BOT_TOKEN and GEMINI_API_KEY."
echo "Run everything: ./start"
