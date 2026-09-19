"""
Ties retrieval and generation together, and applies the hallucination guardrail:
if nothing retrieved is actually relevant to the question, we short-circuit to the
"not found" response instead of asking the LLM to answer from weak/no context.
"""
from typing import List, Dict, Tuple
from task5_rag.config import TOP_K
from task5_rag.services import vectorstore
from task5_rag.services.gemini_client import generate_answer, NOT_FOUND_PHRASE

# Chroma returns cosine distance (lower = more similar) when using default embeddings.
# Anything above this is treated as "not actually relevant" -- tune based on testing.
RELEVANCE_DISTANCE_THRESHOLD = 0.65


def answer_question(question: str) -> Tuple[str, List[Dict]]:
    hits = vectorstore.query(question, top_k=TOP_K)

    relevant_hits = [
        h for h in hits
        if h["distance"] is None or h["distance"] <= RELEVANCE_DISTANCE_THRESHOLD
    ]

    if not relevant_hits:
        return NOT_FOUND_PHRASE, []

    context_chunks = [h["text"] for h in relevant_hits]
    answer = generate_answer(question, context_chunks)

    # If the model itself decided it couldn't answer, don't attach sources --
    # showing sources next to a "not found" answer is misleading.
    if NOT_FOUND_PHRASE.lower() in answer.lower():
        return answer, []

    sources = [{
        "document_name": h["document_name"],
        "document_id": h["document_id"],
        "page": h["page"],
        "chunk_id": h["chunk_id"],
    } for h in relevant_hits]

    return answer, sources
