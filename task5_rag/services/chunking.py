"""
Splits extracted page text into overlapping chunks suitable for embedding.
Each chunk carries the metadata required by the task spec: document name,
document ID, page number, and chunk ID.
"""
import uuid
from typing import List, Dict, Tuple
from task5_rag.config import CHUNK_SIZE, CHUNK_OVERLAP


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Simple sliding-window character chunker that tries to break on sentence/paragraph
    boundaries where possible, so chunks don't cut off mid-sentence."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            # try to break at the last sentence boundary within this window
            window = text[start:end]
            last_break = max(window.rfind(". "), window.rfind("\n"))
            if last_break > chunk_size * 0.5:  # only use it if it's not too early
                end = start + last_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(end - overlap, start + 1)

    return chunks


def chunk_document(
    pages: List[Tuple[int, str]],
    document_id: str,
    document_name: str,
) -> List[Dict]:
    """
    pages: list of (page_number, page_text)
    Returns a list of chunk dicts: {chunk_id, text, document_id, document_name, page}
    """
    all_chunks = []
    for page_number, page_text in pages:
        pieces = split_text(page_text)
        for piece in pieces:
            all_chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "text": piece,
                "document_id": document_id,
                "document_name": document_name,
                "page": page_number,
            })
    return all_chunks
