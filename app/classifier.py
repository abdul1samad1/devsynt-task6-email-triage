"""
AI Classification: intent + priority + recommended action.

Uses the google-genai SDK (same as Task 5, avoids the retired
google-generativeai / text-embedding-004 issue you already hit).

Gemini's newer models have been hitting frequent, well-documented 503
"high demand" errors across many users recently. To keep the pipeline
reliable despite that, this module retries with backoff and falls back
through a short list of models before giving up.
"""
import json
import re
import time
from dataclasses import dataclass

from google import genai
from google.genai import errors as genai_errors

from app.config import config

_client = genai.Client(api_key=config.GEMINI_API_KEY)

# Try the configured model first, then fall back through these if it's
# unavailable. Keeps the pipeline working even during a Gemini outage on
# one specific model.
FALLBACK_MODELS = [config.GEMINI_MODEL, "gemini-2.5-flash", "gemini-flash-latest"]

CATEGORIES = [
    "general_query", "sales_inquiry", "job_application", "project_related",
    "internal_communication", "meeting_request", "urgent_request",
    "complaint", "promotional", "spam", "other",
]

PRIORITIES = ["low", "medium", "high", "critical"]

CLASSIFY_PROMPT = """You are an email triage classifier for a real-estate company's inbox.

Classify the email below into exactly one category, a priority, and whether it
requires a human to handle it. Categories:
{categories}

Priorities: {priorities}

Rules:
- job_application: any resume/CV submission or "I'm applying for..." → priority high, requires_human true
- project_related / internal_communication: client updates, requirements, deadlines, scope changes, anything needing managerial approval → requires_human true
- meeting_request: calls, interviews, demos, scheduling asks → requires_human true
- urgent_request: outages, security concerns, payment issues, angry/escalated clients → priority critical, requires_human true
- complaint: dissatisfaction that isn't critical/urgent → priority high, requires_human true
- promotional: marketing/ads FROM other companies TO us → requires_human false. Be conservative — if in doubt, do NOT classify as promotional.
- spam: unsolicited junk, phishing, irrelevant → requires_human false
- general_query / sales_inquiry: a question a knowledge base about the company could plausibly answer → requires_human false (RAG will attempt it; if RAG has low confidence, the app escalates separately)
- other: anything that doesn't fit → requires_human true

Respond with ONLY raw JSON, no markdown fences, in this exact shape:
{{"category": "...", "priority": "...", "requires_human": true/false, "reasoning": "one short sentence"}}

Email:
From: {sender}
Subject: {subject}
Body:
{body}
"""


@dataclass
class Classification:
    category: str
    priority: str
    requires_human: bool
    reasoning: str


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _generate_with_resilience(prompt: str) -> str:
    """Try each model in FALLBACK_MODELS, retrying transient errors
    (503/429) with short backoff before moving to the next model."""
    last_error = None

    for model in FALLBACK_MODELS:
        for attempt in range(3):
            try:
                response = _client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.candidates[0].content.parts[0].text
            except genai_errors.ServerError as e:
                # 503 "high demand" — transient, worth a short retry
                last_error = e
                time.sleep(2 * (attempt + 1))
            except genai_errors.ClientError as e:
                # e.g. 404 model not found / 429 quota — no point retrying
                # this same model, move straight to the next fallback
                last_error = e
                break
        # exhausted retries for this model (or hit a non-retryable client
        # error) -- try the next model in the fallback list

    raise last_error


def classify_email(sender: str, subject: str, body: str) -> Classification:
    prompt = CLASSIFY_PROMPT.format(
        categories=", ".join(CATEGORIES),
        priorities=", ".join(PRIORITIES),
        sender=sender,
        subject=subject,
        body=body[:6000],  # keep prompt bounded
    )

    raw_text = _generate_with_resilience(prompt)
    cleaned = _strip_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fail safe: if the model returns something unparseable, always
        # escalate to a human rather than silently dropping the email.
        return Classification(
            category="other",
            priority="high",
            requires_human=True,
            reasoning="Classifier returned unparseable output; routed to human for safety.",
        )

    category = data.get("category", "other")
    if category not in CATEGORIES:
        category = "other"
    priority = data.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"

    return Classification(
        category=category,
        priority=priority,
        requires_human=bool(data.get("requires_human", True)),
        reasoning=data.get("reasoning", ""),
    )
