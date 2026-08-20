"""Exceptions for github-mcp's GitHub API client."""

from __future__ import annotations


class GitHubClientError(Exception):
    """Base class for all GitHub API client errors."""


class GitHubAuthError(GitHubClientError):
    """GitHub rejected the configured token, or the token lacks permission."""


class GitHubRateLimitError(GitHubClientError):
    """GitHub API rate limit exceeded."""


class GitHubNotFoundError(GitHubClientError):
    """The requested repository/resource doesn't exist or isn't visible to this token."""


class GitHubAPIError(GitHubClientError):
    """Any other GitHub API failure (timeout, 5xx, unexpected shape)."""
