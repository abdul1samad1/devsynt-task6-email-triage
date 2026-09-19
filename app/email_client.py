"""
Email intake and dispatch.

- fetch_unseen_emails(): pulls new emails via IMAP, parses sender/subject/
  body/thread-id/attachments, and cleans quoted replies & signatures.
- send_reply() / forward_email(): SMTP send helpers used by the decision engine.

IMAP/SMTP were chosen over the Gmail API to avoid an OAuth setup step —
the task spec explicitly allows IMAP. Swap this module out if you'd rather
use the Gmail API or Microsoft Graph; nothing else in the project needs to change.
"""
import email
import imaplib
import re
import smtplib
from dataclasses import dataclass, field
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from app.config import config


@dataclass
class ParsedEmail:
    message_id: str
    thread_id: str
    sender: str
    sender_name: str
    subject: str
    body: str
    raw_body: str
    timestamp: str
    attachments: list = field(default_factory=list)  # list of (filename, bytes)


def _decode(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            decoded += text.decode(enc or "utf-8", errors="ignore")
        else:
            decoded += text
    return decoded


def _clean_body(text: str) -> str:
    """Strip quoted replies, signatures, and tracking noise from a plain-text body."""
    if not text:
        return ""
    # Cut off at common "On ... wrote:" quote markers
    text = re.split(r"\nOn .{0,80} wrote:\n", text)[0]
    text = re.split(r"\n-{2,}\s*Original Message\s*-{2,}\n", text, flags=re.IGNORECASE)[0]
    # Drop lines that are quoted replies (start with '>')
    lines = [ln for ln in text.split("\n") if not ln.strip().startswith(">")]
    text = "\n".join(lines)
    # Cut common signature separator
    text = text.split("\n-- \n")[0]
    return text.strip()


def _extract_body_and_attachments(msg) -> tuple[str, list]:
    body = ""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if content_type == "text/plain" and "attachment" not in disposition:
                charset = part.get_content_charset() or "utf-8"
                body += part.get_payload(decode=True).decode(charset, errors="ignore")
            elif "attachment" in disposition:
                filename = _decode(part.get_filename())
                if filename:
                    attachments.append((filename, part.get_payload(decode=True)))
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(charset, errors="ignore")
    return body, attachments


def fetch_unseen_emails(limit: int = 20) -> list[ParsedEmail]:
    """Connect via IMAP and return parsed, unread emails (marks them as seen)."""
    results: list[ParsedEmail] = []

    with imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT) as imap:
        imap.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        imap.select("INBOX")

        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return results

        ids = data[0].split()[-limit:]  # cap how many we pull per run
        for msg_id in ids:
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw_msg = email.message_from_bytes(msg_data[0][1])

            message_id = raw_msg.get("Message-ID", f"<no-id-{msg_id.decode()}>")
            thread_id = raw_msg.get("References") or raw_msg.get("In-Reply-To") or message_id
            sender_full = _decode(raw_msg.get("From", ""))
            sender_match = re.search(r"<(.+?)>", sender_full)
            sender_email = sender_match.group(1) if sender_match else sender_full
            sender_name = sender_full.split("<")[0].strip().strip('"')

            subject = _decode(raw_msg.get("Subject", "(no subject)"))
            timestamp = raw_msg.get("Date", "")

            raw_body, attachments = _extract_body_and_attachments(raw_msg)
            clean = _clean_body(raw_body)

            results.append(ParsedEmail(
                message_id=message_id,
                thread_id=thread_id,
                sender=sender_email,
                sender_name=sender_name,
                subject=subject,
                body=clean,
                raw_body=raw_body,
                timestamp=timestamp,
                attachments=attachments,
            ))
    return results


def _smtp_send(msg: MIMEMultipart):
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        server.send_message(msg)


def send_reply(to_address: str, subject: str, body: str, in_reply_to: Optional[str] = None):
    """Send an automated RAG-generated reply, threaded to the original message."""
    msg = MIMEMultipart()
    msg["From"] = config.EMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.attach(MIMEText(body, "plain"))
    _smtp_send(msg)


def forward_email(to_address: str, parsed: ParsedEmail, note: str = ""):
    """Forward an email (with attachments) to HR/Manager, with an optional note on top."""
    msg = MIMEMultipart()
    msg["From"] = config.EMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = f"Fwd: {parsed.subject}"

    body = f"{note}\n\n--- Forwarded message ---\nFrom: {parsed.sender_name} <{parsed.sender}>\n" \
           f"Subject: {parsed.subject}\n\n{parsed.body}"
    msg.attach(MIMEText(body, "plain"))

    for filename, content in parsed.attachments:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    _smtp_send(msg)
