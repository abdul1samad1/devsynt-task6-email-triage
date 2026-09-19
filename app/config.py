"""
Central configuration for the Email Triage & RAG Assistant.
All values are loaded from environment variables (see .env.example).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Email (IMAP for reading, SMTP for sending) ---
    IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # use an app password, not your real password

    # Mailbox to route into (HR / Manager inboxes). For the demo these can
    # just be other addresses you control, or the same inbox with a label.
    HR_EMAIL = os.getenv("HR_EMAIL")
    MANAGER_EMAIL = os.getenv("MANAGER_EMAIL")

    # --- Gemini (same model choice as Task 5, avoids the retired-model issue) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    # --- Discord webhooks (one per channel) ---
    DISCORD_WEBHOOK_HR = os.getenv("DISCORD_WEBHOOK_HR")
    DISCORD_WEBHOOK_MANAGER = os.getenv("DISCORD_WEBHOOK_MANAGER")
    DISCORD_WEBHOOK_URGENT = os.getenv("DISCORD_WEBHOOK_URGENT")

    # --- Logging DB ---
    DB_PATH = os.getenv("DB_PATH", "email_triage.db")

    # --- Polling ---
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

    # --- RAG confidence threshold below which we escalate to a human ---
    RAG_CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "0.55"))


config = Config()
