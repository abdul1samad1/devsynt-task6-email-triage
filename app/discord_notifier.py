"""Send formatted Discord notifications via channel-specific webhooks."""
import requests

from app.config import config


def _post(webhook_url: str, content: str):
    if not webhook_url:
        print(f"[discord] No webhook configured — would have sent:\n{content}")
        return
    try:
        requests.post(webhook_url, json={"content": content}, timeout=10)
    except requests.RequestException as e:
        print(f"[discord] Failed to send notification: {e}")


def notify_hr(sender_name: str, sender_email: str, subject: str, position_hint: str = ""):
    content = (
        f"🔔 **New Job Application**\n"
        f"Candidate: {sender_name} | Email: {sender_email}\n"
        f"Subject: {subject}\n"
        f"{'Position hint: ' + position_hint if position_hint else ''}\n"
        f"The application has been forwarded to HR."
    )
    _post(config.DISCORD_WEBHOOK_HR, content)


def notify_manager(sender_name: str, sender_email: str, subject: str, category: str, reasoning: str):
    content = (
        f"📋 **{category.replace('_', ' ').title()}**\n"
        f"From: {sender_name} <{sender_email}>\n"
        f"Subject: {subject}\n"
        f"Note: {reasoning}\n"
        f"Forwarded to Manager."
    )
    _post(config.DISCORD_WEBHOOK_MANAGER, content)


def notify_urgent(sender_name: str, sender_email: str, subject: str, reasoning: str):
    content = (
        f"🚨 **URGENT — Immediate attention required**\n"
        f"From: {sender_name} <{sender_email}>\n"
        f"Subject: {subject}\n"
        f"Why: {reasoning}"
    )
    _post(config.DISCORD_WEBHOOK_URGENT, content)


def notify_meeting(sender_name: str, sender_email: str, subject: str, suggested_reply: str):
    content = (
        f"📅 **Meeting Request — needs confirmation**\n"
        f"From: {sender_name} <{sender_email}>\n"
        f"Subject: {subject}\n"
        f"Suggested reply (not sent yet):\n> {suggested_reply}"
    )
    _post(config.DISCORD_WEBHOOK_MANAGER, content)
