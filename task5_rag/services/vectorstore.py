"""
FAISS-based vector store. Chunk embeddings are generated via Gemini
(gemini_client.py) and stored here with the required metadata: document name,
document ID, page number, chunk ID.

FAISS only stores vectors + integer IDs, so metadata is kept alongside in a
JSON sidecar file, keyed by the same integer ID used in the FAISS index.

Note: swapped in for ChromaDB because chroma-hnswlib has no prebuilt Windows
wheel on PyPI and requires a full C++ build toolchain to compile from source.
FAISS ships genuine prebuilt wheels for Windows/Mac/Linux, so no compiler is
needed to install it.
"""
import json
import threading
from pathlib import Path
from typing import List, Dict

import numpy as np
import faiss

from task5_rag.config import CHROMA_DIR as VECTOR_DIR, EMBEDDING_DIM
from task5_rag.services.gemini_client import embed_text, embed_batch

_INDEX_PATH = VECTOR_DIR / "index.faiss"
_META_PATH = VECTOR_DIR / "metadata.json"
_lock = threading.Lock()


def _new_index():
    # IndexFlatL2 wrapped in IndexIDMap so we can add/remove by our own integer IDs.
    return faiss.IndexIDMap(faiss.IndexFlatL2(EMBEDDING_DIM))


def _load_meta() -> Dict:
    if _META_PATH.exists():
        with open(_META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"next_id": 1, "chunks": {}}  # chunks: {str(int_id): {chunk_id, text, document_id, document_name, page}}


def _save_meta(meta: Dict):
    with open(_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def _load_index():
    if _INDEX_PATH.exists():
        return faiss.read_index(str(_INDEX_PATH))
    return _new_index()


def _save_index(index):
    faiss.write_index(index, str(_INDEX_PATH))


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    return vectors / norms


def add_chunks(chunks: List[Dict]):
    """chunks: list of {chunk_id, text, document_id, document_name, page}"""
    if not chunks:
        return

    with _lock:
        index = _load_index()
        meta = _load_meta()

        texts = [c["text"] for c in chunks]
        embeddings = np.array(embed_batch(texts, task_type="retrieval_document"), dtype="float32")
        embeddings = _normalize(embeddings)

        int_ids = []
        for c in chunks:
            int_id = meta["next_id"]
            meta["next_id"] += 1
            meta["chunks"][str(int_id)] = {
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "document_id": c["document_id"],
                "document_name": c["document_name"],
                "page": c["page"],
            }
            int_ids.append(int_id)

        index.add_with_ids(embeddings, np.array(int_ids, dtype="int64"))

        _save_index(index)
        _save_meta(meta)


def delete_document_chunks(document_id: str):
    with _lock:
        index = _load_index()
        meta = _load_meta()

        ids_to_remove = [
            int(int_id) for int_id, entry in meta["chunks"].items()
            if entry["document_id"] == document_id
        ]
        if not ids_to_remove:
            return

        index.remove_ids(np.array(ids_to_remove, dtype="int64"))
        for int_id in ids_to_remove:
            del meta["chunks"][str(int_id)]

        _save_index(index)
        _save_meta(meta)


def query(question: str, top_k: int = 5) -> List[Dict]:
    """Returns list of {text, document_id, document_name, page, chunk_id, distance}."""
    with _lock:
        index = _load_index()
        meta = _load_meta()

    if index.ntotal == 0:
        return []

    query_embedding = np.array([embed_text(question, task_type="retrieval_query")], dtype="float32")
    query_embedding = _normalize(query_embedding)

    k = min(top_k, index.ntotal)
    distances, ids = index.search(query_embedding, k)

    hits = []
    for dist, int_id in zip(distances[0], ids[0]):
        if int_id == -1:
            continue
        entry = meta["chunks"].get(str(int_id))
        if not entry:
            continue
        hits.append({
            "chunk_id": entry["chunk_id"],
            "text": entry["text"],
            "document_id": entry["document_id"],
            "document_name": entry["document_name"],
            "page": entry["page"],
            "distance": float(dist),
        })
    return hits


def total_chunk_count() -> int:
    meta = _load_meta()
    return len(meta["chunks"])
