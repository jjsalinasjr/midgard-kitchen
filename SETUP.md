# Setup — Midgard Kitchen

## Prerequisites (accounts & keys)

| Service | Key(s) | Used for |
|---|---|---|
| **LiveKit Cloud** | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | media server + agent dispatch |
| **OpenAI** | `OPENAI_API_KEY` | LLM + RAG embeddings |
| **Deepgram** | `DEEPGRAM_API_KEY` | STT |
| **Cartesia** | `CARTESIA_API_KEY` | TTS |
| **Supabase** | `DATABASE_URL` (and enable the `vector` extension) | RAG vector store |

Use the **Session pooler** connection string from Supabase (IPv4-friendly, port 5432) and an alphanumeric DB password to avoid percent-encoding.

## 1. Backend (Python, `uv`)

```bash
cd backend
cp .env.example .env          # fill in the keys above
uv sync
```

**Ingest the Codex into pgvector (one-time):**
```bash
uv run python -m midgard_kitchen.rag.ingest
```
Expect `Parsed 13 chapters …` → embedding progress → `Ingestion complete.`

**Run the agent:**
```bash
# Terminal smoke test — local audio, no server needed:
uv run python -m midgard_kitchen.agent console

# Connected to LiveKit Cloud (required for the browser frontend):
uv run python -m midgard_kitchen.agent dev
```

## 2. Frontend (Next.js)

```bash
cd frontend
cp .env.example .env.local     # fill LIVEKIT_URL / API_KEY / API_SECRET
                               # (NEXT_PUBLIC_LIVEKIT_URL is NOT needed)
npm install
npm run dev
```
Open **http://localhost:3000**.

## Full local run

Two terminals, same LiveKit Cloud project on both sides:

```bash
# Terminal 1 — agent
cd backend  && uv run python -m midgard_kitchen.agent dev

# Terminal 2 — frontend
cd frontend && npm run dev
```
→ open `localhost:3000` → **Start Call** → talk to Thor → ask about the Codex or the weather → **End Call**.

## Configurable pipeline (optional)

Every provider/model is env-overridable — see `backend/.env.example`. Notable knobs:
`STT_MODEL`, `LLM_MODEL`, `TTS_MODEL`, `TTS_VOICE`, `TTS_SPEED`, `TTS_EMOTION`,
`EMBEDDING_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RAG_TOP_K`, `TURN_DETECTOR_VERSION`.
The agent's dispatch name is `LIVEKIT_AGENT_NAME` (default `midgard-kitchen`) — it must match on both backend and the frontend token route.

## Deployment (summary)

- **Frontend → Vercel:** import the repo with **Root Directory = `frontend`**, then set `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` and `ACCESS_CODE` (the shared "rune" reviewers enter — gates API costs on the public demo) as env vars, all server-side (no `NEXT_PUBLIC_`). Leave `ACCESS_CODE` unset locally to keep the gate open during development. Optionally set `NEXT_PUBLIC_SESSION_LIMIT_MIN` (default `10`) to cap how long a single call can run before it auto-disconnects.
- **Agent → LiveKit Cloud:** `lk agent create` from `backend/`, configuring the same provider keys + `DATABASE_URL` as secrets. (Run the ingestion step once so pgvector is populated.)
