"""
Wrapper around Google's current Gemini SDK ("google-genai") for two things:
1. Generating embeddings for chunks and questions (gemini-embedding-001)
2. Generating grounded answers from retrieved context (gemini-flash-latest)

Note: the older `google-generativeai` package and the `text-embedding-004` /
`gemini-2.0-flash` models it commonly used have both been retired by Google.
This uses the current, actively maintained `google-genai` SDK and models.
"""
from typing import List
from google import genai
from google.genai import types
from task5_rag.config import GEMINI_API_KEY, MODEL_NAME, EMBEDDING_MODEL_NAME, EMBEDDING_DIM

_client = genai.Client(api_key=GEMINI_API_KEY)

NOT_FOUND_PHRASE = "I couldn't find that information in the uploaded documents."

SYSTEM_INSTRUCTION = f"""You are a customer-facing assistant that answers questions ONLY using the
CONTEXT provided below, which was retrieved from the user's uploaded documents.

Rules:
- Base your answer strictly on the CONTEXT. Do not use outside/general knowledge.
- If the CONTEXT does not contain enough information to answer, respond with exactly:
  "{NOT_FOUND_PHRASE}"
- Do not guess, assume, or fabricate any fact, number, name, or policy not present in the CONTEXT.
- Be concise and directly answer the question when the CONTEXT supports it.
- If the CONTEXT partially answers the question, answer what you can and note what's missing,
  rather than fabricating the rest.
"""

_TASK_TYPE_MAP = {
    "retrieval_document": "RETRIEVAL_DOCUMENT",
    "retrieval_query": "RETRIEVAL_QUERY",
}


def embed_text(text: str, task_type: str = "retrieval_document") -> List[float]:
    """task_type: 'retrieval_document' for chunks, 'retrieval_query' for questions."""
    result = _client.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIM,
            task_type=_TASK_TYPE_MAP.get(task_type, "RETRIEVAL_DOCUMENT"),
        ),
    )
    return list(result.embeddings[0].values)


def embed_batch(texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
    return [embed_text(t, task_type=task_type) for t in texts]


def generate_answer(question: str, context_chunks: List[str]) -> str:
    if not context_chunks:
        return NOT_FOUND_PHRASE

    context_block = "\n\n---\n\n".join(context_chunks)
    prompt = f"{SYSTEM_INSTRUCTION}\n\nCONTEXT:\n{context_block}\n\nQUESTION:\n{question}\n\nANSWER:"

    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return (response.text or "").strip() or NOT_FOUND_PHRASE
