# streamer-toolbox Product C 純文字 AI 問答 — GCP backend image（不含 STT / ffmpeg）
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY packages ./packages
COPY config ./config
COPY tools/streamer-config-gui ./tools/streamer-config-gui

RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "python", "-m", "app.main"]
