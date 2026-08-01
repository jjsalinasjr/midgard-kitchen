# syntax=docker/dockerfile:1

# uv-based Python image — LiveKit's recommended base for uv projects.
ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1

# --- Build stage: install dependencies from the lockfile ---
FROM base AS build
RUN apt-get update && apt-get install -y \
    gcc g++ python3-dev \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Copy manifests first for layer caching, then sync from the lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked
COPY . .

# --- Production stage ---
FROM base
ARG UID=10001
RUN adduser --disabled-password --gecos "" --home "/app" --shell "/sbin/nologin" --uid "${UID}" appuser
WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app
USER appuser

# LiveKit Cloud injects LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET at
# runtime; the other secrets (OPENAI/DEEPGRAM/CARTESIA/DATABASE_URL) come from
# LiveKit Cloud secrets. "start" runs the worker in production mode.
CMD ["uv", "run", "python", "-m", "midgard_kitchen.agent", "start"]
