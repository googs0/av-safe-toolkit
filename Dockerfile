# syntax=docker/dockerfile:1

# Small, secure base
FROM python:3.11-slim AS runtime

# Defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Minimal OS deps (no compilers: rely on wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first for better build cache
COPY pyproject.toml README.md LICENSE ./

# Copy source (adjust if your layout changes)
COPY avsafe_descriptors ./avsafe_descriptors
COPY docs ./docs
COPY tests ./tests

# Install package; include 'signing' extra for Ed25519 support
RUN pip install --upgrade pip \
 && pip install --no-cache-dir ".[signing]"

# Run as non-root
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

# App runtime env (can be overridden at runtime/compose)
ENV AVSAFE_STRICT_CRYPTO=1

EXPOSE 8000

# Allow PORT/worker overrides via env; defaults are sensible
CMD ["sh","-c","uvicorn avsafe_descriptors.server.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-2}"]
