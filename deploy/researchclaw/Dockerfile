# AutoResearchClaw worker: runs ARC pipelines for the PM (internal network only).
FROM python:3.12-slim

ARG ARC_COMMIT=be4ba47
RUN apt-get update && apt-get install -y --no-install-recommends git tini \
    && rm -rf /var/lib/apt/lists/*

# ARC itself, pinned (it moves fast; we integrate only through its CLI and files).
RUN git clone https://github.com/aiming-lab/AutoResearchClaw /opt/arc \
    && git -C /opt/arc checkout ${ARC_COMMIT} \
    && pip install --no-cache-dir /opt/arc fastapi uvicorn pytest httpx

# The experiments' own Python, with pip so ARC can add packages (CPU only).
RUN python -m venv /opt/expvenv \
    && /opt/expvenv/bin/pip install --no-cache-dir numpy pandas scipy scikit-learn \
       statsmodels matplotlib seaborn \
    && /opt/expvenv/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN useradd --create-home --uid 1001 arc && mkdir -p /runs && chown arc /runs
WORKDIR /app
COPY worker.py test_worker.py ./
USER arc
ENV ARC_RUNS_DIR=/runs ARC_DATASETS_DIR=/datasets ARC_EXPERIMENT_PYTHON=/opt/expvenv/bin/python

EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health')"
ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8100"]
