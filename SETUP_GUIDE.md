# Citation Parser -- Complete Setup Guide for Lawyers

**You don't need to know coding.** Follow each step exactly as written. If you get stuck, show this guide to any engineering student or IT person -- they can get you running in 30 minutes.

---

## What You're Building

A system that runs on your personal computer (Mac, Windows, or Linux) and does this:

1. You find a judgment PDF on Manupatra, SCC Online, or LawFinder
2. You forward that PDF to a Telegram bot (your own private bot)
3. Your computer automatically reads the PDF and extracts: case name, court, petition type, disposition, ratio, acts and sections cited, judges, date, key quotes
4. Everything becomes searchable in your browser at `http://localhost:5757`
5. Next time you need that citation, you search your library instead of Manupatra

**All data stays on your machine. Nothing is uploaded to any cloud.**

---

## Before You Start

You need:

- A Mac, Windows PC, or Linux machine that stays on (or can be turned on when needed)
- An internet connection (only needed for initial setup and Telegram)
- A Telegram account (free, download from App Store or Play Store)
- About 30 minutes of time

---

## Part 1: Install Python

Python is the programming language this tool is built in. You need to install it once.

### On Mac

1. Open **Terminal** (press `Cmd + Space`, type "Terminal", press Enter)
2. Type this and press Enter:
   ```
   python3 --version
   ```
3. If you see something like `Python 3.12.0`, skip to Part 2
4. If you get an error, install Python:
   - Go to https://www.python.org/downloads/
   - Click the big yellow "Download Python" button
   - Open the downloaded file and follow the installer
   - Close Terminal and open it again
   - Type `python3 --version` to verify

### On Windows

1. Go to https://www.python.org/downloads/
2. Click "Download Python"
3. **IMPORTANT:** When the installer opens, check the box that says **"Add Python to PATH"**
4. Click "Install Now"
5. Open **Command Prompt** (press Windows key, type "cmd", press Enter)
6. Type `python --version` to verify

### On Linux (Ubuntu/Debian)

```
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

---

## Part 2: Download Citation Parser

### Option A: Using Git (Recommended)

If you have Git installed:

1. Open Terminal (Mac/Linux) or Command Prompt (Windows)
2. Navigate to where you want the folder:
   ```
   cd ~/Desktop
   ```
3. Download:
   ```
   git clone https://github.com/Wolfgangrush/Citation-Parcer.git
   cd Citation-Parcer
   ```

### Option B: Download as ZIP

1. Go to https://github.com/Wolfgangrush/Citation-Parcer
2. Click the green **"Code"** button
3. Click **"Download ZIP"**
4. Extract the ZIP file to your Desktop
5. Open Terminal and navigate to the folder:
   ```
   cd ~/Desktop/Citation-Parcer
   ```

---

## Part 3: Create Your Telegram Bot

This is your private bot that receives PDFs. Only you (and anyone you give the bot link to) can use it.

1. Open Telegram on your phone
2. Search for **@BotFather** (the official Telegram bot that creates other bots)
3. Send this message:
   ```
   /newbot
   ```
4. BotFather will ask for a name. Type something like:
   ```
   My Citations
   ```
5. BotFather will ask for a username. It must end in "bot". Type something like:
   ```
   mycitations_bot
   ```
   (If taken, try `mycitations123_bot` or similar)
6. BotFather will reply with a message containing your **bot token**. It looks like this:
   ```
   7197907660:AAGVCZiYSWQEyMOjZhlQ_1DzADwcdYFl8SU
   ```
7. **Copy this token.** You'll need it in the next step.

---

## Part 4: Choose Your AI Parser

The tool needs an AI to read judgment PDFs and extract structured data. You have two options:

### Option A: Ollama (Free, Runs Locally, Recommended)

Ollama runs an AI model on your own machine. No API key needed, no cost, fully private.

**Requirements:** Your machine needs at least 8 GB RAM (16 GB recommended).

1. Go to https://ollama.com and click **Download**
2. Install Ollama
3. Open Terminal and run:
   ```
   ollama pull llama3.2
   ```
   This downloads the AI model (about 2 GB). Wait for it to finish.
4. That's it -- Ollama will run automatically when needed.

### Option B: Google Gemini (Cloud API, Very Accurate)

Gemini is Google's AI. It's more accurate but sends your PDF text to Google's servers.

1. Go to https://aistudio.google.com/apikey
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the API key (looks like `AIzaSyC...`)
5. You'll enter this in the next step

---

## Part 5: Configure the System

1. In your Terminal, make sure you're in the Citation Parser folder:
   ```
   cd ~/Desktop/Citation-Parcer
   ```
2. Copy the example configuration:
   ```
   cp .env.example .env
   ```
3. Open the `.env` file in any text editor:
   - **Mac:** `open -e .env` (opens in TextEdit)
   - **Windows:** `notepad .env`
   - **Linux:** `nano .env`
4. Find this line and replace `your_bot_token_here` with your actual Telegram bot token:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```
   After editing it should look like:
   ```
   TELEGRAM_BOT_TOKEN=7197907660:AAGVCZiYSWQEyMOjZhlQ_1DzADwcdYFl8SU
   ```

5. **If using Ollama** (free, local), make sure these lines say:
   ```
   AI_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2
   ```

6. **If using Gemini** (cloud), change these lines:
   ```
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_actual_gemini_api_key
   ```

7. Save the file and close the editor.

---

## Part 6: Run Setup

1. In Terminal, run:
   ```
   chmod +x setup.sh start run_all.sh run_backend.sh run_bot.sh
   ./setup.sh
   ```
   This installs all required packages. Wait for "Setup complete."

2. **On Windows**, run this instead:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

---

## Part 7: Start the System

```
./start
```

You should see:
```
Starting backend...
Starting Telegram bot...
Dashboard: http://localhost:5757
```

**Open your browser and go to:** http://localhost:5757

You should see the Citation Manager dashboard. If you see it, the system is working.

### On Windows

Open two separate Command Prompt windows:

**Window 1 (Backend):**
```
.venv\Scripts\python backend.py
```

**Window 2 (Bot):**
```
.venv\Scripts\python telegram_bot.py
```

---

## Part 8: Test It

1. Open Telegram on your phone
2. Search for your bot (the username you created, like `@mycitations_bot`)
3. Send `/start` -- the bot should reply with a welcome message
4. Find any judgment PDF (from Manupatra, SCC Online, or your downloads)
5. Send that PDF to your bot
6. The bot will reply with:
   ```
   Received filename.pdf. Processing...
   ```
7. After 10-30 seconds (depending on your AI provider), it will reply with the extracted data:
   ```
   Citation saved.
   Case name: State v. Rahul Kumar
   Case number: APEAL 456/2024
   Year: 2024
   Type: Criminal Appeal
   Court: Bombay High Court
   ```
8. Go to http://localhost:5757 in your browser -- you should see the citation card

---

## Daily Use

### Sending Citations

Whenever you find a useful judgment:
1. Download the PDF from Manupatra / SCC Online / LawFinder
2. Open Telegram
3. Send the PDF to your bot
4. Done. It's in your library.

**From court:** If you have a PDF on your phone, forward it directly to the bot from WhatsApp or your file manager.

### Searching Your Library

1. Open http://localhost:5757
2. Use the search bar to search by:
   - Case name ("State v. Rahul Kumar")
   - Legal topic ("anticipatory bail")
   - Section reference ("Section 439" or "IPC 302")
   - Ratio or holding text ("bail is rule jail is exception")
   - Any text from the original PDF
3. Use filters:
   - **Case type:** Filter by Appeals, Bail Applications, Writ Petitions, etc.
   - **Section:** Find cases citing a specific section
   - **Year:** Show only recent cases

### Understanding the Dashboard Cards

Each citation card shows:

- **Result badge (top):** Allowed, Dismissed, Partly Allowed, Disposed Of, or Needs Review
- **Plea:** What the petitioner/appellant was asking for
- **Grounds:** Why the court allowed/dismissed (the ratio)
- **Case type badge:** WP (Writ Petition), APEAL (Criminal Appeal), BA (Bail Application), etc.
- **Court badge:** Which court decided
- **Year badge:** When decided
- **Key Provisions:** Clickable section references (e.g., "IPC S302") -- click to read the actual section text

### Editing a Citation

If the AI got something wrong:
1. Click **Edit** on the citation card
2. Fix any field (case name, disposition, ratio, etc.)
3. Click **Save**

### Uploading from Browser

You can also upload PDFs directly from your computer:
1. Go to http://localhost:5757
2. Click **Choose File** and select a PDF
3. Click **Upload PDF**

---

## Keeping It Running

### Starting and Stopping

**Start:**
```
./start
```

**Stop:** Press `Ctrl + C` in the terminal where it's running.

### Making It Run Automatically (Mac Only)

If you want Citation Parser to start automatically when your Mac turns on:

1. Copy the example service file:
   ```
   cp com.sccparser.service.plist.example com.sccparser.service.plist
   ```
2. Open it in a text editor:
   ```
   open -e com.sccparser.service.plist
   ```
3. Replace every `/path/to/sccparser` with the actual path to your folder.
   For example, if the folder is on your Desktop:
   ```
   /Users/yourname/Desktop/Citation-Parcer
   ```
   (Replace `yourname` with your Mac username. To find it, type `whoami` in Terminal.)
4. Save the file
5. Run:
   ```
   cp com.sccparser.service.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.sccparser.service.plist
   ```

Now it starts automatically on boot.

---

## Accessing From Your Phone (Advanced)

If you want to search your library from your phone (not just send PDFs):

### Using Tailscale (Recommended)

Tailscale creates a secure private network between your devices.

1. Install Tailscale on your Mac/PC: https://tailscale.com
2. Install Tailscale on your phone
3. Sign in with the same account on both
4. On your computer, change this line in `.env`:
   ```
   BACKEND_HOST=0.0.0.0
   ```
5. Restart the system
6. Run `./phone_url.sh` to get the URL
7. Open that URL on your phone's browser

### Using Same Wi-Fi Network

1. Change `.env`:
   ```
   BACKEND_HOST=0.0.0.0
   ```
2. Find your computer's local IP:
   - **Mac:** System Settings > Wi-Fi > Details > IP Address (usually `192.168.x.x`)
3. On your phone, open: `http://192.168.x.x:5757`

---

## Google Docs Export (Optional)

Export your entire library to a Google Doc for printing or sharing:

1. Go to Google Cloud Console: https://console.cloud.google.com
2. Create a new project
3. Enable "Google Docs API" and "Google Drive API"
4. Create OAuth credentials (Desktop application)
5. Download the JSON file
6. Save it as `google_credentials.json` in the Citation Parser folder
7. Click "Export to Google Docs" in the dashboard
8. A browser window will open for Google sign-in (first time only)

---

## Importing Bare Acts (Optional)

If you have PDFs of bare Acts (IPC, CrPC, CPC, BNS, BNSS, BSA, etc.), you can import them so the dashboard shows clickable section text:

1. Put bare Act PDFs in the `Bare Acts ` folder (note the space after "Acts")
2. Run:
   ```
   .venv/bin/python import_bare_acts.py
   ```
3. Now when a citation references "IPC S302" or "CrPC S482", you can click it in the dashboard to read the actual section text

The following Acts are supported out of the box:
- Indian Penal Code (IPC)
- Code of Criminal Procedure (CrPC)
- Code of Civil Procedure (CPC)
- Bharatiya Nyaya Sanhita (BNS)
- Bharatiya Nagarik Suraksha Sanhita (BNSS)
- Bharatiya Sakshya Adhiniyam (BSA)
- Indian Evidence Act
- Specific Relief Act
- Representation of the People Act
- Maharashtra Co-operative Societies Act
- Maharashtra Zilla Parishads and Panchayat Samitis Act

---

## Supported PDF Formats

The system recognizes and extracts from these legal database formats:

| Source | What Gets Extracted |
|--------|-------------------|
| **DigiLegal / SCC Online** | Headnote, acts referred, cases referred, full structured data |
| **Law Finder** | Important principles, lettered subsections (A, B, C, D), brief facts |
| **High Court Orders** | Neutral citation, CORAM, appearances, operative directions |
| **Supreme Court Orders** | INSC neutral citation, party names, judges from signature blocks |
| **SCC Reporter** | SCC citation format, e.g. (2024) 10 SCC 456 |
| **Manupatra** | Manu citation format, e.g. Manu/SC/2024/123 |
| **Indian Kanoon** | Neutral citations, Indian Kanoon URLs |
| **Generic PDFs** | Best-effort extraction of all available fields |

---

## Troubleshooting

### "Backend failed to start"

- Check if port 5757 is already in use: `lsof -i :5757`
- Check the log: `cat logs/backend.log`

### Bot doesn't respond

- Check if the bot is running: look for "Telegram bot listening" in the terminal
- Check the token in `.env` matches what BotFather gave you
- Check the log: `cat logs/telegram_bot.log`

### "Could not extract enough text from this PDF"

- The PDF is likely scanned (an image, not text). This tool only works with text-based PDFs from legal databases.
- PDFs downloaded from Manupatra, SCC Online, and LawFinder are text-based and will work.

### AI extraction is slow

- **Ollama:** First run is slow (loading the model). Subsequent PDFs are faster.
- **Gemini:** Usually processes in 10-15 seconds.

### "GEMINI_API_KEY is not configured"

- Open `.env` and add your Gemini API key
- Make sure `AI_PROVIDER=gemini` is set

### "Ollama request failed"

- Make sure Ollama is installed and running: `ollama list`
- Pull the model if missing: `ollama pull llama3.2`

### Dashboard shows wrong data

- Click **Edit** on any citation to fix it manually
- Your corrections are saved permanently

---

## Uninstalling

To remove Citation Parser:
1. Stop the system (`Ctrl + C` or `sccparser off`)
2. Delete the folder
3. If you set up auto-start, run:
   ```
   launchctl unload ~/Library/LaunchAgents/com.sccparser.service.plist
   rm ~/Library/LaunchAgents/com.sccparser.service.plist
   ```

Your SQLite database (in the `instance/` folder) contains all your citations. Back it up before deleting if you want to keep your data.

---

## Privacy and Security

- All citations are stored in a local SQLite database on your machine
- PDFs are deleted after processing by default (configurable)
- The dashboard runs on localhost -- only accessible from your machine unless you explicitly change `BACKEND_HOST`
- If using Ollama: AI processing happens entirely on your machine
- If using Gemini: PDF text is sent to Google's API for parsing (the extracted data is still stored locally)
- No analytics, no telemetry, no data collection

---

## Getting Help

- Open an issue on GitHub: https://github.com/Wolfgangrush/Citation-Parcer/issues
- Include the error message and which step you're on
