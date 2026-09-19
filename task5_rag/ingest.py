"""
One-time (or re-runnable) ingestion script: loads the 5 Meridian Estates
sample PDFs from Task 5 into the FAISS vector store so the RAG pipeline
has something to retrieve from.

The uploaded Task 5 project didn't include a pre-built index (FAISS index
files aren't meant to be committed to git), so this rebuilds it from the
same source PDFs.

Run once before testing RAG-dependent scenarios:
    python -m task5_rag.ingest
"""
import uuid
from pathlib import Path

from task5_rag.services.extraction import extract_text
from task5_rag.services.chunking import chunk_document
from task5_rag.services import vectorstore

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent / "sample_documents"


def ingest_all():
    pdf_files = sorted(SAMPLE_DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"[ingest] No PDFs found in {SAMPLE_DOCS_DIR}")
        return

    total_chunks = 0
    for pdf_path in pdf_files:
        document_id = str(uuid.uuid4())
        filename = pdf_path.name
        print(f"[ingest] Processing {filename}...")

        pages = extract_text(pdf_path, "pdf")
        if not pages:
            print(f"[ingest]   WARNING: no extractable text in {filename}, skipping")
            continue

        chunks = chunk_document(pages, document_id=document_id, document_name=filename)
        if not chunks:
            print(f"[ingest]   WARNING: no chunks produced for {filename}, skipping")
            continue

        vectorstore.add_chunks(chunks)
        total_chunks += len(chunks)
        print(f"[ingest]   Added {len(chunks)} chunks from {len(pages)} pages")

    print(f"[ingest] Done. Total chunks in vector store: {vectorstore.total_chunk_count()} "
          f"(added {total_chunks} this run)")


if __name__ == "__main__":
    ingest_all()
