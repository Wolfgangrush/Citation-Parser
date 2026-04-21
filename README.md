# Legal Citation Manager

Local-first 24/7 system for receiving court judgment PDFs through Telegram, extracting citation metadata with AI, storing it in SQLite, searching/editing through a Flask dashboard, and exporting the library to Google Docs.

## Quick Start

```bash
cd ~/sccparser
./install_sccparser.sh
source ~/.zshrc
sccparser on
```

The system will now run 24/7. Send PDFs to your Telegram bot anytime from court!

## What It Does

- Receives text-based PDF judgments through a Telegram bot.
- Extracts text with `pdfplumber`.
- Parses metadata with Ollama locally by default.
- Supports `AI_PROVIDER=gemini` for Gemini API parsing.
- Supports `AI_PROVIDER=local_http` for a custom local parser endpoint.
- Supports `AI_PROVIDER=codex_cli` if the Codex CLI is configured on the Mac.
- Detects multiple citation formats:
  - **DigiLegal/SCC**: `# HEADNOTE #` format with acts referred, cases referred
  - **Law Finder**: `IMPORTANT` blocks with lettered subsections (A, B, C, D)
  - **High Court Orders**: Raw orders with `CORAM:`, `DATE:`, neutral citations
  - **Supreme Court Orders**: `2026 INSC 244` neutral citation format
  - **SCC Reporter**: `(2024) 10 SCC 456` or `2024 SCC OnLine SC 1234`
  - **Manupatra**: `Manu/SC/2024/123`, `Manu/PH/2024/456` (Delhi HC)
  - **Indian Kanoon**: `2024:SC:567`, `2024:BOM-NAG:123-DB` with URLs
- Detects near-duplicates using citation name, filename, court, year, judgment date, and case number.
- Stores structured records in local SQLite.
- Deletes PDFs after successful processing by default.
- Provides dashboard search, upload, view, edit, delete, and Google Docs export.
- Imports local bare Acts into SQLite and opens section text from clickable dashboard provision chips.

## Setup

```bash
cd ~/sccparser
./setup.sh
```

Edit `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
AI_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
BACKEND_PORT=5757
```

## Install Command (Recommended)

Run the installer to add the `sccparser` command to your terminal:

```bash
./install_sccparser.sh
source ~/.zshrc
```

## Running 24/7

Start everything:
```bash
sccparser on
# or: sccparser start
```

Stop everything:
```bash
sccparser off
# or: sccparser stop
```

Check status:
```bash
sccparser status
```

View logs:
```bash
sccparser logs        # Backend logs
sccparser bot-logs    # Telegram bot logs
```

Dashboard: `http://localhost:5757`

## Legacy Scripts (Still Work)

```bash
./start          # Start with health checks
./run_all.sh     # Simple start both services
./run_backend.sh # Backend only
./run_bot.sh     # Bot only
```

Dashboard:
```text
http://localhost:5757
```

## Bare Act Lookup

Put bare Act PDFs in the local `Bare Acts ` folder and import them:

```bash
.venv/bin/python import_bare_acts.py
```

The importer stores parsed section text in SQLite under `legal_provisions`. Dashboard section chips such as `IPC §409` and `CrPC §482` are clickable and open a small local popup. The local LLM is not used for this lookup.

## Google Docs Export

1. Create an OAuth desktop client in Google Cloud.
2. Enable Google Docs API and Google Drive API.
3. Download the OAuth JSON file.
4. Save it as `google_credentials.json` in this folder, or set `GOOGLE_DRIVE_CREDENTIALS_PATH` in `.env`.
5. Click `Export to Google Docs` in the dashboard or send `/export_google` to the bot.
6. Optional: set `GOOGLE_DOC_ID` to update an existing document instead of creating a new one.
7. Optional: set `AUTO_EXPORT_GOOGLE_DOCS=true` to export after every successful PDF ingestion.

The first export opens a browser auth flow and stores the token at `google_token.json`. For a 24x7 terminal workflow, run the first export manually once so the token exists before enabling automatic export.

## AI Provider Options

Gemini:

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-pro
```

Ollama:

```bash
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_NUM_CTX=32768
AI_MAX_CHARS=60000
HIGH_COURT_ORDER_USE_AI=false
```

Run Ollama separately:

```bash
ollama run llama3.2
```

Local HTTP:

```bash
AI_PROVIDER=local_http
LOCAL_AI_ENDPOINT=http://localhost:11434/api/legal-citation-parse
```

The endpoint must accept:

```json
{"filename": "case.pdf", "text": "...", "schema": {}}
```

and return the extracted citation JSON.

Codex CLI:

```bash
AI_PROVIDER=codex_cli
CODEX_CLI_COMMAND=codex
```

This requires a working local Codex CLI setup and is mainly useful as a fallback parser.

## Extracted Fields

- `citation_name`
- `court`
- `year`
- `petition_type`
- `case_number`
- `detected_format`
- `neutral_citation`
- `bench`
- `party_names`
- `appearances`
- `order_type`
- `directions`
- `next_hearing_date`
- `disposition`
- `cited_cases`
- `acts_referred`
- `headnote`
- `important_principles`
- `subsections`
- `brief_facts`
- `sections`
- `laws`
- `holding`
- `ratio`
- `headnotes`
- `key_quotes`
- `judges`
- `date_judgment`
- `tags`
- `notes`

## 24/7 Operation

The system is designed to run continuously:
- Auto-restart on crash (via launchd service)
- Health monitoring with `HEALTH_CHECK.sh`
- Log rotation to prevent disk bloat
- Works with Tailscale for remote access

### Auto-start on Boot (Optional)

To start SCC Parser automatically when your Mac boots:

```bash
# Copy the example plist and edit paths to match your machine
cp com.sccparser.service.plist.example com.sccparser.service.plist
# Edit com.sccparser.service.plist — replace /path/to/sccparser with your actual path

# Copy to LaunchAgents and load
cp com.sccparser.service.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sccparser.service.plist

# To unload later:
# launchctl unload ~/Library/LaunchAgents/com.sccparser.service.plist
```

### Periodic Health Check (Optional)

Add to crontab for automatic health checks:
```bash
# Edit crontab
crontab -e

# Add this line to check every 5 minutes and restart if needed:
*/5 * * * * ~/sccparser/HEALTH_CHECK.sh >> ~/sccparser/logs/healthcheck.log 2>&1
```

## Notes

- **Port**: Now uses `5757` to avoid conflicts with other services
- PDFs are deleted after successful ingestion by default. Set `DELETE_PDF_AFTER_PROCESSING=false` to keep them.
- Scanned PDFs are not supported in this MVP because you said your PDFs are text-based.
- The app binds to `127.0.0.1:5757` for localhost-only use. For network access, set `BACKEND_HOST=0.0.0.0` in `.env`.
