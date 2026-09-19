"""
Standalone config for the reused Task 5 RAG pipeline, kept separate from
Task 6's own app/config.py so the two don't collide.

Reads the same GEMINI_API_KEY from the shared .env (python-dotenv merges
whatever's already loaded), and updates model names to gemini-3.6-flash,
which is what you confirmed working during Task 6 testing today
(gemini-2.0-flash was retired; gemini-flash-latest was hitting persistent
503s at time of testing).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("RAG_MODEL_NAME", "gemini-3.6-flash")
EMBEDDING_MODEL_NAME = os.getenv("RAG_EMBEDDING_MODEL_NAME", "gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "768"))

CHROMA_DIR = Path(os.getenv("RAG_VECTOR_DIR", BASE_DIR.parent / "data" / "chroma"))

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))
TOP_K = int(os.getenv("RAG_TOP_K", "5"))

CHROMA_DIR.mkdir(parents=True, exist_ok=True)

if not GEMINI_API_KEY:
    print("[WARN] GEMINI_API_KEY is not set. Set it in your .env file before making requests.")
