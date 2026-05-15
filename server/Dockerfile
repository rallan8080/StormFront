# syntax=docker/dockerfile:1.7

# ---- builder ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps (bcrypt may need a C toolchain on some platforms).
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN pip install --prefix=/install .

# ---- runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system app \
 && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ---- dev (testing / local development) ----
#
# Extends runtime with the [dev] extras (pytest, ruff, mypy, etc.) and bakes
# the test suite in. Selected by docker-compose.override.yml via
# `build.target: dev`. Production builds use `target: runtime` (see base
# docker-compose.yml).
FROM runtime AS dev

USER root

COPY pyproject.toml ./
COPY --chown=app:app tests ./tests

# Install the dev tooling directly rather than via ".[dev]" — pip will sometimes
# skip extras processing when the main package is already installed at the
# same version, which would silently leave pytest out. Keep these pins in
# sync with the `dev` extras in pyproject.toml. Chown /app so the app user
# can write its pip cache for any ad-hoc installs at exec time.
RUN pip install --no-cache-dir \
        "pytest>=8.3" \
        "pytest-asyncio>=0.24" \
        "httpx>=0.27" \
        "ruff>=0.7" \
        "mypy>=1.13" \
 && chown app:app /app

USER app
