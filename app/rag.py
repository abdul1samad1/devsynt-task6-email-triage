"""
Bridge into the Task 5 RAG pipeline (reused, not rebuilt, per the task spec).
Task 5's code lives in task5_rag/ at the project root and is called directly
here via a plain Python import -- no second server needed.

Task 5's rag.answer_question() already implements the hallucination
guardrail: it returns its NOT_FOUND_PHRASE with empty sources whenever
nothing relevant is retrieved, or when the model itself couldn't answer
from the retrieved context. We treat "sources non-empty" as our
found_in_kb / confidence signal here, since that guardrail already did
the real work of deciding whether the answer is trustworthy.
"""
from dataclasses import dataclass

from task5_rag.services.rag import answer_question as _task5_answer_question


@dataclass
class RagResult:
    answer: str
    sources: list[str]
    confidence: float  # 0.0-1.0 -- used to decide whether to escalate to a human
    found_in_kb: bool


def answer_query(question: str) -> RagResult:
    answer_text, sources = _task5_answer_question(question)

    found_in_kb = bool(sources)
    confidence = 1.0 if found_in_kb else 0.0

    source_names = [s["document_name"] for s in sources] if sources else []

    return RagResult(
        answer=answer_text,
        sources=source_names,
        confidence=confidence,
        found_in_kb=found_in_kb,
    )
