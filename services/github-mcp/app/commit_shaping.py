"""Transforms raw GitHub REST API commit JSON into this server's
CommitSummary shape — pure logic, no I/O.

Split out from `github_client.py` specifically so it's unit-testable
without `httpx` installed.
"""

from __future__ import annotations

from typing import Any, Dict, List


def shape_commit(raw_commit: Dict[str, Any], files_changed: List[str]) -> Dict[str, Any]:
    """Map one GitHub API commit object (from `GET /repos/{o}/{r}/commits`)
    plus its separately-fetched file list into our CommitSummary dict.

    Truncates `sha` to 10 chars (a git short-sha, unambiguous in
    practice, much more readable in agent output than the full 40-char
    hash) and takes only the first line of the commit message (the
    summary line; full multi-line commit bodies aren't needed for the
    tool's purpose and would bloat every result).
    """
    commit = raw_commit.get("commit", {}) or {}
    message = commit.get("message") or ""
    first_line = message.splitlines()[0] if message else ""
    author = (commit.get("author") or {}).get("name") or "unknown"
    date = (commit.get("author") or {}).get("date") or ""

    return {
        "sha": raw_commit.get("sha", "")[:10],
        "message": first_line,
        "author": author,
        "date": date,
        "files_changed": files_changed,
    }
