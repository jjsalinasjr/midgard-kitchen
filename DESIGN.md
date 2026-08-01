# Design Document — Midgard Kitchen

This document lays out the plan, design decisions, and assumptions for the project. For *what the system does* and *how it works end-to-end*, see the [README](./README.md).

## Goal

A real-time, voice-first **RAG agent that addresses a genuine personal problem** — eating well on whole, real food to stay strong — delivered through a strong character: **Thor**, a warrior god who must keep his physique even in mortal life. The agent holds a natural spoken conversation, retrieves precise answers from a large reference book, and takes a live external action, all in character.

## Build plan (stages)

The build proceeds through six stages, each **verified locally before the next**. Guiding principle: *get a working end-to-end conversation first, then deepen each layer, then deploy* — never build on an unverified layer.

1. **Scaffold** — a monorepo (`backend/` Python + `frontend/` Next.js), env-driven configuration, provider accounts (LiveKit Cloud, OpenAI, Deepgram, Cartesia, Supabase), and pinned dependencies.
2. **Voice pipeline** — the Thor persona plus a configurable STT–LLM–TTS pipeline (Deepgram / OpenAI / Cartesia) with Silero VAD and the LiveKit audio turn detector. Verify in the terminal (`console` mode) before building any UI.
3. **RAG** — ingest the reference PDF into a vector store with chapter-aware chunking, and expose retrieval to the agent as a function tool. Verify retrieval accuracy directly, then through the agent.
4. **Narrative tool + polish** — a live-weather "read the skies" tool; STT keyterm boosting for the story's proper nouns; graceful degradation on both tools.
5. **Frontend** — a browser client with Start/End controls, a live transcript, an agent-state visualizer, and explicit agent dispatch via the token endpoint.
6. **Deploy + harden** — frontend to Vercel, agent to LiveKit Cloud (always-on); an access-code gate and a session cap to bound cost on the public demo.

## Design decisions & assumptions

### Trade-offs & limitations
- **Tool-call latency** — surfacing RAG as a tool adds one LLM round-trip on knowledge questions. A deliberate trade: it keeps retrieval off the hot path and gives a natural "let me consult the tome" beat; mitigable with a spoken status update.
- **PDF artifacts** — the public-domain transcription occasionally inserts spaces mid-word. Embeddings and the LLM tolerate it, but retrieved snippets can look slightly ragged.
- **Single volume** — only Volume 1 of the source book is ingested; self-consistent, since answers are grounded in the shipped PDF.
- **Preemptive generation** can fire a tool twice for one turn (idempotent, harmless) — a latency optimization kept on deliberately.

### Hosting assumptions
- **Frontend → Vercel** (serverless: the static app + the token endpoint).
- **Agent → LiveKit Cloud** managed compute — an always-on containerized worker, built from `backend/Dockerfile` and deployed with `lk agent create`. The same image runs on **AWS EC2/ECS** unchanged: the agent is a worker that connects *outbound* to LiveKit Cloud, so no inbound load balancer, ports, or TLS are required.
- **Vector store → Supabase** (managed Postgres + pgvector).
- Assumes free/hobby tiers, which comfortably cover a demo. The public demo is **access-gated** (a shared code checked at the token endpoint — no token → no room → no agent → no cost) and **session-capped** (auto-disconnect after N minutes) to bound API spend.

### RAG assumptions
- **Vector DB:** Supabase **pgvector** — managed, always-on, persistent; one fewer vendor than Pinecone/Chroma, with the vectors living in Postgres. Not committed as a file; reproducible from the shipped PDF via one ingestion command (`python -m midgard_kitchen.rag.ingest`).
- **Framework:** **LlamaIndex** for loading, chunking, embedding, and retrieval.
- **Chunking strategy:** the PDF is first split into **per-chapter documents** (each chunk inherits a `chapter` metadata tag), then chunked with `SentenceSplitter` at **512 / 64**. The chapter tags are what let the agent answer "what does the chapter on X say about Y" precisely, rather than returning a loosely-related passage.
- **Embeddings:** OpenAI `text-embedding-3-small` (1536-d) — strong for prose, inexpensive.
- **Retrieval:** semantic **top-k = 5**, returning chapter-tagged passages. Runs on the **synchronous** client (psycopg2) to avoid a known LlamaIndex async/pgbouncer issue, wrapped in `asyncio.to_thread` so it never blocks the agent's event loop.

### LiveKit agent design
- **Configurable pipeline** — discrete STT/LLM/TTS/VAD plugins, each selected by environment variable (`settings.py`), rather than a monolithic realtime model. Provider keys are the project's own.
- **Audio turn detector** — LiveKit's built-in audio end-of-turn model (the text model is deprecated), paired with Silero VAD, for natural turn-taking and interruptions.
- **RAG as a function tool** (not the every-turn `on_user_turn_completed` hook) — retrieval fires only when the model decides it's needed, keeping it off the hot path and in-character.
- **Explicit dispatch** — the browser's access token carries a `RoomConfiguration` naming the agent, so it joins on demand rather than into every room.
- **Graceful degradation** — both tools catch failures and return an in-character apology, so a provider outage never breaks the conversation.

## Key decisions at a glance

| Decision | Chosen | Over | Why |
|---|---|---|---|
| Media server | LiveKit Cloud | Self-hosting | Zero-ops managed SFU; self-hosting is the highest-risk WebRTC task |
| Vector store | Supabase pgvector | Pinecone / Chroma / FAISS | Managed, persistent, one fewer vendor; vectors live in Postgres |
| RAG framework | LlamaIndex | LangChain / from-scratch | Best PDF loaders + metadata-aware node parsing |
| Pipeline | Discrete plugins (env-selectable) | Monolithic realtime model | Configurable STT/LLM/TTS/VAD; provider keys are ours |
| RAG delivery | Function tool | `on_user_turn_completed` | Off the hot path; fires only when needed; in-narrative |
| Turn detection | Audio turn detector | Deprecated text model | Built-in, higher accuracy |
| Voice | Archetype voice + persona writing | Cloning a real actor | ToS + right-of-publicity (public demo) |
