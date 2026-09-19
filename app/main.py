"""
Entry point. Exposes a small FastAPI app (consistent with the Task 5
dashboard) so you can:
  - trigger a manual inbox scan for demoing test scenarios (POST /process-inbox)
  - view the processed-email log (GET /logs)
  - run it continuously as a background poller (python -m app.main)
"""
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import decision_engine, logger
from app.classifier import classify_email
from app.config import config
from app.email_client import fetch_unseen_emails

app = FastAPI(title="DevSynt Task 6 — Email Triage & RAG Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_inbox_once() -> int:
    """Fetch unseen emails, classify + route each, skipping already-logged
    message IDs (duplicate protection). Returns count processed.

    Each email is handled in its own try/except: IMAP marks a message as
    read the moment it's fetched, so if we let one bad email (e.g. a
    transient 503 from Gemini) raise all the way up, it would already be
    marked read but never logged -- effectively lost, with no retry.
    Catching per-email keeps the batch going and guarantees every fetched
    email gets at least an error log row."""
    emails = fetch_unseen_emails()
    processed = 0
    for parsed in emails:
        if logger.already_processed(parsed.message_id):
            continue
        try:
            classification = classify_email(parsed.sender, parsed.subject, parsed.body)
            decision_engine.handle_email(parsed, classification)
        except Exception as e:  # noqa: BLE001
            print(f"[process_inbox] failed on {parsed.message_id}: {e}")
            logger.log_email(
                message_id=parsed.message_id,
                thread_id=parsed.thread_id,
                sender=parsed.sender,
                subject=parsed.subject,
                category="other",
                priority="high",
                ai_decision="classification/routing raised an exception",
                action_taken="failed",
                rag_used=False,
                status="error",
                error=str(e),
            )
        processed += 1
    return processed


@app.post("/process-inbox")
def process_inbox_endpoint():
    count = process_inbox_once()
    return {"processed": count}


@app.get("/logs")
def get_logs(limit: int = 50):
    return {"logs": logger.recent_logs(limit)}


@app.get("/health")
def health():
    return {"status": "ok"}


def _poll_loop():
    while True:
        try:
            count = process_inbox_once()
            if count:
                print(f"[poller] processed {count} email(s)")
        except Exception as e:  # noqa: BLE001
            print(f"[poller] error: {e}")
        time.sleep(config.POLL_INTERVAL_SECONDS)


@app.on_event("startup")
def start_background_poller():
    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=False)
