import asyncio
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5757").rstrip("/")
PDF_STORAGE = Path(os.getenv("PDF_STORAGE_PATH", "./pdfs_received"))
PDF_STORAGE.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Legal Citation Manager\n\n"
        "Send a text-based court judgment PDF. I will extract metadata, save it locally, "
        f"delete the temporary PDF after processing, and make it searchable at {BACKEND_URL}.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/stats - Library statistics\n"
        "/export_google - Export library to Google Docs"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        response = requests.get(f"{BACKEND_URL}/api/stats", timeout=20)
        response.raise_for_status()
        data = response.json()
        await update.message.reply_text(
            "Library Statistics\n\n"
            f"Total citations: {data.get('total_citations', 0)}\n"
            f"Applications: {data.get('application_count', 0)}\n"
            f"Petitions: {data.get('petition_count', 0)}\n"
            f"Appeals: {data.get('appeal_count', 0)}\n"
            f"Other case types: {data.get('other_type_count', 0)}\n\n"
            f"Dashboard: {BACKEND_URL}"
        )
    except Exception as exc:
        await update.message.reply_text(f"Could not fetch stats: {exc}")


async def export_google(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Starting Google Docs export...")
    try:
        response = requests.post(f"{BACKEND_URL}/api/export/google", timeout=240)
        data = response.json()
        if response.ok:
            await update.message.reply_text(
                f"Google Docs export complete.\n"
                f"Citations exported: {data.get('count', 0)}\n"
                f"{data.get('url')}"
            )
        else:
            await update.message.reply_text(
                f"Google export needs setup: {data.get('error')}\n{data.get('setup', '')}"
            )
    except Exception as exc:
        await update.message.reply_text(f"Google export failed: {exc}")


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    if not document:
        await update.message.reply_text("Please send a PDF file.")
        return

    if document.mime_type != "application/pdf" and not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Only PDF files are accepted.")
        return

    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text("File too large. Maximum size is 50MB.")
        return

    await update.message.reply_text(f"Received {document.file_name}. Processing...")

    temp_path = PDF_STORAGE / f"telegram_{document.file_unique_id}_{document.file_name}"
    try:
        telegram_file = await context.bot.get_file(document.file_id)
        await telegram_file.download_to_drive(str(temp_path))

        with temp_path.open("rb") as handle:
            response = requests.post(
                f"{BACKEND_URL}/api/upload",
                files={"pdf": (document.file_name, handle, "application/pdf")},
                data={"filename": document.file_name},
                timeout=900,
            )

        data = response.json()
        if response.status_code == 201:
            await update.message.reply_text(
                "Citation saved.\n\n"
                f"{data.get('citation_name', 'Unknown')}\n"
                f"Case number: {data.get('case_number') or 'N/A'}\n"
                f"Year: {data.get('year') or 'N/A'}\n"
                f"Type: {data.get('petition_type') or 'N/A'}\n"
                f"Court: {data.get('court') or 'N/A'}\n\n"
                f"Dashboard: {BACKEND_URL}"
            )
        elif response.status_code == 409:
            existing = data.get("existing", {})
            await update.message.reply_text(
                "Near-duplicate detected. Not added.\n\n"
                f"Existing: {existing.get('citation_name', 'Unknown')}\n"
                f"Year: {existing.get('year') or 'N/A'}\n"
                f"Court: {existing.get('court') or 'N/A'}"
            )
        else:
            await update.message.reply_text(f"Processing failed: {data.get('error', response.text)}")
    except Exception as exc:
        await update.message.reply_text(f"Processing error: {exc}")
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> None:
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_bot_token_here":
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured in .env")

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("export_google", export_google))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("Telegram bot listening for PDFs.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
