"""Thin wrapper around the GitHub REST API for github-mcp.

Owns every outbound call to GitHub. `server.py`'s MCP tool never touches
`httpx` directly — it calls this class, which raises typed exceptions
(`app/github_exceptions.py`) that `server.py` maps to sanitized tool
responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.github_exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.span_helper import start_span

logger = logging.getLogger(__name__)


class GitHubClient:
    """Authenticated client for a small, read-only slice of the GitHub REST API."""

    def __init__(self, token: str, base_url: str = "https://api.github.com", timeout_seconds: float = 10.0) -> None:
        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN is not configured. github-mcp cannot call the GitHub API without it."
            )
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise GitHubAPIError(f"GitHub API request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"GitHub API request to {path} failed") from exc

        if response.status_code == 401:
            raise GitHubAuthError("GitHub API rejected the configured token (401).")
        if response.status_code == 404:
            raise GitHubNotFoundError(f"GitHub resource not found: {path}")
        if response.status_code == 403:
            # GitHub uses 403 for both "rate limited" and "forbidden" —
            # disambiguate via the rate-limit header rather than assuming.
            if response.headers.get("x-ratelimit-remaining") == "0":
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")
            raise GitHubAuthError("GitHub API returned 403 (insufficient token permissions).")
        if response.status_code >= 400:
            raise GitHubAPIError(f"GitHub API returned {response.status_code} for {path}")

        return response.json()

    async def list_commits(
        self, owner: str, repo: str, since: str, path: Optional[str], max_results: int
    ) -> List[Dict[str, Any]]:
        """List commits on the default branch, newest first, via GitHub's
        native `since`/`path` filters (not a client-side filter)."""
        with start_span("github.list_commits", {"repository": f"{owner}/{repo}", "max_results": max_results}):
            params: Dict[str, Any] = {"since": f"{since}T00:00:00Z", "per_page": max_results}
            if path:
                params["path"] = path

            data = await self._get(f"/repos/{owner}/{repo}/commits", params=params)
            return data[:max_results]

    async def get_commit_files(self, owner: str, repo: str, sha: str) -> List[str]:
        """Fetch the changed-file list for one commit.

        Note: this is a second request per commit (the list-commits
        endpoint doesn't include file details), so total request count
        for one tool call is `1 + len(commits)`, bounded by
        `max_results` (capped at 20 — see app/schemas.py).
        """
        with start_span("github.get_commit_files", {"repository": f"{owner}/{repo}", "sha": sha[:10]}):
            data = await self._get(f"/repos/{owner}/{repo}/commits/{sha}")
            files = data.get("files", []) or []
            return [f["filename"] for f in files if "filename" in f]

    async def ping(self) -> bool:
        """Cheap connectivity + auth check for the readiness endpoint."""
        try:
            await self._get("/rate_limit")
            return True
        except Exception:  # noqa: BLE001 - readiness must report, not raise
            logger.warning("github_ping_failed", extra={"event": "github_ping_failed"})
            return False
