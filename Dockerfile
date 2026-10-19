# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=ghcr.io/astral-sh/uv:python3.11-trixie-slim@sha256:7936cc6625ca04cafa6ecc3c2881ddfe90a747c55c74480cd4ac6ffad6a5af1e

# ---------- Frontend (React SPA) ----------
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY gazzali/frontend/package*.json ./
RUN npm ci --silent
COPY gazzali/frontend/ ./
RUN npm run build

# ---------- Runtime ----------
# The Python environment is installed in ONE stage, deliberately.
#
# The earlier layout built the virtualenv in a separate stage and then copied it in
# whole. Because the project is reinstalled on every build (see --reinstall-package
# below), that copy's 164 MB / ~8000 files were re-created and re-exported on every
# source change, which measured as the slowest part of a deploy: 22s to copy, then
# 67s exporting layers and 33s unpacking, against 4s of actual building when nothing
# changed. Installing into the runtime image directly leaves the dependency layer
# cached and only the application code to export.
FROM ${BASE_IMAGE} AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tini curl \
    && rm -rf /var/lib/apt/lists/*

ARG UID=1000
ARG GID=1000
RUN groupadd --gid ${GID} gazzali \
    && useradd --uid ${UID} --gid ${GID} --create-home --shell /bin/bash gazzali

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GAZZALI_WORKSPACE_DIR=/workspace \
    GAZZALI_DATA_DIR=/home/gazzali/.gazzali

WORKDIR /src

# Dependencies on their own layer: editing application code must not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# The SPA is served from the installed package, so dist must be in place before the
# project is installed — the wheel carries it (see package-data in pyproject.toml).
COPY gazzali/ ./gazzali/
COPY --from=frontend-builder /frontend/dist ./gazzali/frontend/dist

# --reinstall-package: uv otherwise reuses the wheel it cached for the project on
# a previous build, so newly added modules never reach site-packages.
# /src is build input only — the package is installed non-editable, so removing it in
# this same layer keeps the source tree out of the image.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --reinstall-package gazzali \
    && rm -rf /src

RUN mkdir -p /workspace /home/gazzali/.gazzali \
    && chown -R ${UID}:${GID} /workspace /home/gazzali

USER gazzali
WORKDIR /workspace

LABEL org.opencontainers.image.title="Gazzali" \
      org.opencontainers.image.description="Gazzali research management platform (API, SPA, AI runner)." \
      org.opencontainers.image.licenses="Apache-2.0"

EXPOSE 7860 8001

ENTRYPOINT ["tini", "--", "python", "-m", "gazzali"]
CMD ["--host", "0.0.0.0"]
