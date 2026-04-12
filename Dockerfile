# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY EvoScientist/pm/frontend/package*.json ./
RUN npm ci --silent
COPY EvoScientist/pm/frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --extra pm --no-dev --frozen

# Copy project source
COPY . .

# Overlay the freshly-built frontend dist
COPY --from=frontend-builder /frontend/dist ./EvoScientist/pm/frontend/dist

# Install the package itself
RUN uv pip install -e . --no-deps

EXPOSE 7860 8001

CMD ["uv", "run", "EvoSci", "dashboard", "--host", "0.0.0.0", "--no-open"]
