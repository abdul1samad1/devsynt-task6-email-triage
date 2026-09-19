"""
SQLite-backed logging and duplicate protection.

Every processed email gets one row: sender, subject, category, priority,
AI decision, action taken, whether RAG was used, response sent, forwarded-to,
Discord status, timestamp, and error/status. message_id is UNIQUE so the
same email can never be processed twice even if IMAP re-delivers it.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    thread_id TEXT,
    sender TEXT,
    subject TEXT,
    category TEXT,
    priority TEXT,
    ai_decision TEXT,
    action_taken TEXT,
    rag_used INTEGER,
    response_sent TEXT,
    forwarded_to TEXT,
    discord_status TEXT,
    status TEXT,
    error TEXT,
    processed_at TEXT
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def already_processed(message_id: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM email_log WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None


def log_email(
    message_id: str,
    thread_id: str,
    sender: str,
    subject: str,
    category: str,
    priority: str,
    ai_decision: str,
    action_taken: str,
    rag_used: bool,
    response_sent: str = "",
    forwarded_to: str = "",
    discord_status: str = "not_sent",
    status: str = "success",
    error: str = "",
):
    with _conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO email_log
               (message_id, thread_id, sender, subject, category, priority,
                ai_decision, action_taken, rag_used, response_sent,
                forwarded_to, discord_status, status, error, processed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                message_id, thread_id, sender, subject, category, priority,
                ai_decision, action_taken, int(rag_used), response_sent,
                forwarded_to, discord_status, status, error,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def recent_logs(limit: int = 50):
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM email_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
