# RAG MCP

Knowledge-retrieval MCP server. Exposes exactly one tool,
`search_knowledge`, over **Streamable HTTP** at `/mcp`. This service
owns all retrieval mechanics (chunking happens offline at ingestion;
dense + BM25 + fusion + rerank happen per-query); callers never touch
Qdrant or BM25 directly.

## Pipeline

```
Query
  │
  ├─► Dense search (Qdrant, BGE embeddings)
  ├─► Sparse search (BM25)
  │
  ▼
Reciprocal Rank Fusion
  │
  ▼
Cross-encoder rerank (cross-encoder/ms-marco-MiniLM-L-6-v2)
  │
  ▼
Top-K evidence chunks, each with document_id / title / source / chunk_id / score
```

## Setup

```bash
cd services/rag-mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

## Ingest the sample documents

Required before the server can return real results — without this,
`search_knowledge` responds with an empty result set (BM25 index empty,
Qdrant collection empty).

```bash
python -m scripts.ingest --docs-dir data/sample_docs
```

This downloads BGE embedding weights from Hugging Face on first run
(one-time, then cached locally) and writes to local on-disk Qdrant plus
`data/index/chunks.jsonl`.

## Run the server

```bash
python app/server.py
# or: uvicorn app.server:app --host 0.0.0.0 --port 8001
```

```bash
curl http://localhost:8001/health
curl http://localhost:8001/health/ready
```

## Verify the MCP wiring itself

The FastMCP-inside-Starlette mounting pattern (see the docstring at the
top of `app/server.py`) is the one part of this service I could not
execute-test in the environment I built it in (no network access).
Verify it actually works on your machine:

```bash
python -m scripts.smoke_test_client
```

Expected output: the tool list includes `search_knowledge`, followed by
a JSON result with `results`, `dense_candidates`, `sparse_candidates`,
`reranked`. If this hangs or errors, check the mounting/lifespan note
in `app/server.py` against your installed `mcp` package version's docs.

## Tests

```bash
pytest -v
```

`test_chunking.py`, `test_fusion.py`, and `test_retrieval_pipeline.py`
are dependency-light (pure Python / fakes) and were actually executed
during development, not just syntax-checked. `test_schemas.py` and
`test_auth.py` need `pydantic`/`starlette`/`httpx` installed to run.

## Known limitations (Phase 3)

- Ingestion is a manual CLI step, not automated or scheduled.
- No incremental/delta ingestion — re-running `scripts/ingest.py`
  re-embeds every document in `data/sample_docs`.
- No retrieval quality metrics computed yet — `evaluation/datasets/rag_eval_seed.jsonl`
  exists but Phase 12 is what actually runs it.
- `enable_reranker=False` falls back to fused-RRF order; that path is
  wired but not yet A/B evaluated against reranked output.
