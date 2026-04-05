FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install all dependencies (pm extra required for FastAPI/uvicorn)
RUN uv sync --extra pm --no-dev --frozen

# Copy the rest of the project
COPY . .

# Install the package itself
RUN uv pip install -e . --no-deps

# Expose PM dashboard and runner service ports
EXPOSE 7860 8001

# Run the dashboard with host 0.0.0.0 so it's accessible outside the container
CMD ["uv", "run", "EvoSci", "dashboard", "--host", "0.0.0.0", "--no-open"]
