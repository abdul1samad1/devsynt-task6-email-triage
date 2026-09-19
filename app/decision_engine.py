"""
Decision Engine: takes a ParsedEmail + its Classification and executes the
correct action. This is the only place that "decides" anything — and even
here, the AI never makes a hiring/business/scheduling decision, it only
routes to the human who should.
"""
from app import discord_notifier, email_client, logger, rag
from app.classifier import Classification
from app.config import config
from app.email_client import ParsedEmail


def handle_email(parsed: ParsedEmail, classification: Classification):
    category = classification.category
    rag_used = False
    response_sent = ""
    forwarded_to = ""
    discord_status = "not_sent"
    action_taken = ""
    status = "success"
    error = ""

    try:
        if category in ("general_query", "sales_inquiry") and not classification.requires_human:
            action_taken, response_sent, rag_used = _handle_rag_query(parsed)

        elif category == "job_application":
            email_client.forward_email(config.HR_EMAIL, parsed, note="New job application — see below.")
            discord_notifier.notify_hr(parsed.sender_name, parsed.sender, parsed.subject)
            forwarded_to = config.HR_EMAIL
            discord_status = "sent"
            action_taken = "forward_and_notify (HR)"

        elif category in ("project_related", "internal_communication", "complaint"):
            email_client.forward_email(
                config.MANAGER_EMAIL, parsed,
                note=f"Routed as '{category}'. {classification.reasoning}"
            )
            discord_notifier.notify_manager(
                parsed.sender_name, parsed.sender, parsed.subject, category, classification.reasoning
            )
            forwarded_to = config.MANAGER_EMAIL
            discord_status = "sent"
            action_taken = "forward_and_notify (Manager)"

        elif category == "meeting_request":
            suggested_reply = _draft_meeting_reply(parsed)
            discord_notifier.notify_meeting(parsed.sender_name, parsed.sender, parsed.subject, suggested_reply)
            discord_status = "sent"
            action_taken = "notify_human (meeting — awaiting confirmation)"

        elif category == "urgent_request":
            discord_notifier.notify_urgent(parsed.sender_name, parsed.sender, parsed.subject, classification.reasoning)
            discord_status = "sent"
            action_taken = "immediate_human_notification (urgent)"

        elif category == "promotional":
            action_taken = "archived (promotional)"

        elif category == "spam":
            action_taken = "moved_to_spam"

        else:  # "other" or anything unmapped -> safe default: human review
            email_client.forward_email(
                config.MANAGER_EMAIL, parsed,
                note="Unclassified / uncertain email — routed for human review."
            )
            discord_notifier.notify_manager(
                parsed.sender_name, parsed.sender, parsed.subject, "other", classification.reasoning
            )
            forwarded_to = config.MANAGER_EMAIL
            discord_status = "sent"
            action_taken = "forward_and_notify (fallback -> Manager)"

    except Exception as e:  # noqa: BLE001 - we want to log any failure, not crash the run
        status = "error"
        error = str(e)
        action_taken = action_taken or "failed"

    logger.log_email(
        message_id=parsed.message_id,
        thread_id=parsed.thread_id,
        sender=parsed.sender,
        subject=parsed.subject,
        category=category,
        priority=classification.priority,
        ai_decision=classification.reasoning,
        action_taken=action_taken,
        rag_used=rag_used,
        response_sent=response_sent,
        forwarded_to=forwarded_to,
        discord_status=discord_status,
        status=status,
        error=error,
    )


def _handle_rag_query(parsed: ParsedEmail) -> tuple[str, str, bool]:
    """Run the query through Task 5's RAG pipeline. Escalate on low confidence
    or no-answer instead of ever fabricating a response."""
    result = rag.answer_query(parsed.body)

    if not result.found_in_kb or result.confidence < config.RAG_CONFIDENCE_THRESHOLD:
        email_client.forward_email(
            config.MANAGER_EMAIL, parsed,
            note="RAG could not confidently answer this from the knowledge base — routed for human review."
        )
        discord_notifier.notify_manager(
            parsed.sender_name, parsed.sender, parsed.subject,
            "general_query", "No confident answer found in knowledge base."
        )
        return "escalated_low_confidence -> Manager", "", True

    reply_body = (
        f"{result.answer}\n\n"
        f"— This is an automated reply based on our knowledge base."
    )
    email_client.send_reply(parsed.sender, parsed.subject, reply_body, in_reply_to=parsed.message_id)
    return "rag_reply_sent", reply_body, True


def _draft_meeting_reply(parsed: ParsedEmail) -> str:
    """A simple templated suggestion — a human approves/edits before sending."""
    return (
        f"Hi {parsed.sender_name or 'there'}, thanks for reaching out. "
        f"I'll check availability and confirm a time shortly."
    )
