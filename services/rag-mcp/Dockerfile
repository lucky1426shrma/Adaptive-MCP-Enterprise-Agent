# RAG MCP: hybrid retrieval (Qdrant + BM25 + BGE embeddings + cross-encoder
# reranker). This image is meaningfully heavier and slower to build than
# every other service in this project — sentence-transformers pulls in
# torch, and model weights (BGE + the reranker) download from the
# Hugging Face Hub on first container start, not at build time (see
# app/embeddings.py / app/reranker.py's docstrings). Budget real time
# for the first `docker compose up` of this service.
#
# VERIFICATION NOTE: like every other pip/npm-dependent piece of this
# project, this Dockerfile could not be built in the sandbox this
# project was authored in (no network access — see the root README).
# The CPU-only torch install below is a well-established technique,
# but verify the build completes cleanly on your machine before relying
# on it.

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch FIRST, explicitly, before requirements.txt.
# sentence-transformers depends on torch; the default PyPI wheel is
# CUDA-enabled and multiple gigabytes larger than necessary for a
# project that only ever runs embedding/reranking inference on CPU
# (this project has no GPU requirement anywhere — see the root README).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=3)" || exit 1

CMD ["python", "-m", "app.server"]
