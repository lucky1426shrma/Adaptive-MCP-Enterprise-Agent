# Backend: FastAPI + LangGraph agent + MCP client.
#
# Lightweight relative to rag-mcp (no ML weights) — this image should
# build quickly. See services/rag-mcp/Dockerfile for why THAT one is
# very different.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Simple stdlib-only healthcheck — no curl/wget in python:slim by default.
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
