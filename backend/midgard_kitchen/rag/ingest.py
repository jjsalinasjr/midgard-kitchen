"""Offline ingestion: the Codex PDF -> chapter-tagged chunks -> Supabase pgvector.

Design-plan §4 + D6/D7/D8. Splits Mrs. Beeton's Book of Household Management into
per-chapter documents (so every chunk carries its chapter), then LlamaIndex chunks
them, embeds with OpenAI, and upserts into pgvector. Re-running is idempotent — it
drops and rebuilds the table, so you can freely re-tune chunking.

Run (from backend/):
    uv run python -m midgard_kitchen.rag.ingest
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv
from pypdf import PdfReader

from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

from ..settings import Settings

load_dotenv(".env")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("midgard-kitchen.ingest")

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "beeton.pdf"
SOURCE_NAME = "Mrs. Beeton's Book of Household Management, Vol. 1"

# Chapter headings look like "CHAPTER I." / "CHAPTER X4." at the start of a line.
_CHAPTER_RE = re.compile(r"^\s*CHAPTER\s+([IVXLCDM0-9]+)\b\.?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_MIN_CHAPTER_CHARS = 400  # drops table-of-contents fragments / stray headings


def pg_params(database_url: str) -> dict:
    """Parse a Postgres URL into discrete params (percent-decoding user/password)."""
    u = urlparse(database_url)
    return {
        "host": u.hostname,
        "port": u.port or 5432,
        "database": (u.path or "/postgres").lstrip("/") or "postgres",
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
    }


def build_vector_store(settings: Settings) -> PGVectorStore:
    p = pg_params(settings.database_url)
    return PGVectorStore.from_params(
        host=p["host"],
        port=p["port"],
        database=p["database"],
        user=p["user"],
        password=p["password"],
        table_name=settings.vector_table,
        embed_dim=settings.embed_dim,
    )


def _reset_table(settings: Settings) -> None:
    """Drop the vector table so re-ingestion doesn't accumulate duplicate rows."""
    import psycopg2

    p = pg_params(settings.database_url)
    conn = psycopg2.connect(
        host=p["host"], port=p["port"], dbname=p["database"], user=p["user"], password=p["password"]
    )
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS data_{settings.vector_table}")
        logger.info("Cleared existing table data_%s (fresh ingest).", settings.vector_table)
    finally:
        conn.close()


def load_chapter_documents(pdf_path: Path) -> list[Document]:
    reader = PdfReader(str(pdf_path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)

    matches = list(_CHAPTER_RE.finditer(text))
    # Dedup by chapter label, keeping the longest body — the table of contents and
    # the real chapter both match "CHAPTER I"; the real one has far more text.
    by_label: dict[str, tuple[str, str]] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end].strip()
        label = f"CHAPTER {m.group(1).upper()}"
        title = (m.group(2) or "").strip().rstrip(".")
        if label not in by_label or len(body) > len(by_label[label][1]):
            by_label[label] = (title, body)

    docs: list[Document] = []
    for label, (title, body) in by_label.items():
        if len(body) < _MIN_CHAPTER_CHARS:
            continue
        docs.append(
            Document(
                text=body,
                metadata={
                    "source": SOURCE_NAME,
                    "chapter": label,
                    "chapter_title": title or label,
                },
                # Keep "source" out of the embedded/LLM text — it's identical on
                # every chunk and would only dilute the signal.
                excluded_embed_metadata_keys=["source"],
                excluded_llm_metadata_keys=["source"],
            )
        )

    if not docs:  # fallback: chapter detection failed -> ingest the whole book
        logger.warning("No chapters detected; ingesting the whole book as one document.")
        docs = [Document(text=text, metadata={"source": SOURCE_NAME, "chapter": "Full text"})]

    return docs


def ingest(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Codex PDF not found at {DATA_PATH}")

    logger.info("Loading and splitting %s ...", DATA_PATH.name)
    docs = load_chapter_documents(DATA_PATH)
    logger.info("Parsed %d chapters: %s", len(docs), [d.metadata.get("chapter") for d in docs])

    _reset_table(settings)
    storage_context = StorageContext.from_defaults(vector_store=build_vector_store(settings))

    logger.info("Embedding + upserting into pgvector (table data_%s) ...", settings.vector_table)
    VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        embed_model=OpenAIEmbedding(model=settings.embedding_model),
        transformations=[SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)],
        show_progress=True,
    )
    logger.info("Ingestion complete. The Codex is inscribed.")


if __name__ == "__main__":
    ingest()
