"""Env-driven provider/model configuration.

This is where the "configurable STT/LLM/TTS/VAD" requirement lives
(design-plan D14). Every provider/model choice is read from the environment,
so swapping a provider or model is a one-line env change — never a code edit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_list(key: str, default: list[str]) -> list[str]:
    raw = os.getenv(key, "")
    if not raw:
        return default
    return [s.strip() for s in raw.split(",") if s.strip()]


@dataclass
class Settings:
    agent_name: str = field(default_factory=lambda: _env("AGENT_NAME", "midgard-kitchen"))

    # STT
    stt_provider: str = field(default_factory=lambda: _env("STT_PROVIDER", "deepgram"))
    stt_model: str = field(default_factory=lambda: _env("STT_MODEL", "nova-3"))
    stt_language: str = field(default_factory=lambda: _env("STT_LANGUAGE", "en"))
    # Keyterm prompting (nova-3) — boosts recognition of the story's proper nouns
    # so STT stops hearing "Thor" as "Four".
    stt_keyterms: list[str] = field(
        default_factory=lambda: _env_list(
            "STT_KEYTERMS", ["Thor", "Codex", "Midgard", "Asgard", "Beeton", "Odinson", "Valhalla"]
        )
    )

    # LLM
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "openai"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "gpt-4o-mini"))

    # TTS
    tts_provider: str = field(default_factory=lambda: _env("TTS_PROVIDER", "cartesia"))
    tts_model: str = field(default_factory=lambda: _env("TTS_MODEL", "sonic-3"))
    tts_voice: str = field(default_factory=lambda: _env("TTS_VOICE", ""))  # Cartesia voice id (e.g. Johan)
    # Expressiveness controls (Cartesia sonic-3) — dial these to make Thor boom.
    tts_speed: float = field(default_factory=lambda: _env_float("TTS_SPEED", 1.0))    # >1 = faster / more energetic
    tts_volume: float = field(default_factory=lambda: _env_float("TTS_VOLUME", 1.0))  # >1 = louder / more present
    tts_emotion: str = field(default_factory=lambda: _env("TTS_EMOTION", ""))         # e.g. "excited" (sonic-3, beta)

    # Turn detection — LiveKit audio turn detector.
    # Blank = auto (full "v1" on LiveKit Cloud, local "v1-mini" fallback);
    # set "v1-mini" to force fully-local operation.
    turn_detector_version: str = field(default_factory=lambda: _env("TURN_DETECTOR_VERSION", ""))

    # RAG — LlamaIndex ingestion → Supabase pgvector (design-plan §4).
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", ""))
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", "text-embedding-3-small"))
    embed_dim: int = field(default_factory=lambda: _env_int("EMBED_DIM", 1536))  # 3-small=1536, 3-large=3072
    chunk_size: int = field(default_factory=lambda: _env_int("CHUNK_SIZE", 512))
    chunk_overlap: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP", 64))
    vector_table: str = field(default_factory=lambda: _env("VECTOR_TABLE", "codex"))  # stored as data_codex
    rag_top_k: int = field(default_factory=lambda: _env_int("RAG_TOP_K", 5))
