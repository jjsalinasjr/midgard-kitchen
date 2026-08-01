"""Retrieval over the Codex (pgvector), exposed to the agent as a function tool.

Design-plan §4 + D9 + §9·S2. Uses the SYNC retrieval path (psycopg2) to sidestep
the known LlamaIndex async-Postgres / pgbouncer bug; the agent tool wraps
`consult_codex` in asyncio.to_thread so it never blocks the event loop.
"""

from __future__ import annotations

import logging

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding

from ..settings import Settings
from .ingest import build_vector_store

logger = logging.getLogger("midgard-kitchen.retrieve")

_retriever = None  # built once per process, reused across tool calls


def _get_retriever(settings: Settings):
    global _retriever
    if _retriever is None:
        index = VectorStoreIndex.from_vector_store(
            build_vector_store(settings),
            embed_model=OpenAIEmbedding(model=settings.embedding_model),
        )
        _retriever = index.as_retriever(similarity_top_k=settings.rag_top_k)
    return _retriever


def consult_codex(query: str, settings: Settings | None = None) -> str:
    """Synchronous top-k retrieval. Returns chapter-tagged passages as one string,
    ready to hand to the LLM (so Thor can answer AND cite the chapter)."""
    settings = settings or Settings()
    nodes = _get_retriever(settings).retrieve(query)
    if not nodes:
        return "The Codex holds no counsel on this matter."

    passages = []
    for n in nodes:
        chapter = n.metadata.get("chapter", "the Codex")
        passages.append(f"[{chapter}] {n.get_content().strip()}")
    return "\n\n".join(passages)
