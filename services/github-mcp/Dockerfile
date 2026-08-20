# GitHub MCP: real GitHub API integration, repository allow-listed.
# Lightweight image.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health', timeout=3)" || exit 1

CMD ["python", "-m", "app.server"]
