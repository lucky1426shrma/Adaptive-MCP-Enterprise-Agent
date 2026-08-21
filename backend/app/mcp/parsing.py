"""Parses MCP tool-call result content.

Deliberately dependency-free (stdlib only, duck-typed input) so it's
unit testable without the `mcp` SDK installed — see
`backend/tests/test_mcp_parsing.py`, which actually runs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


class _ContentBlockLike(Protocol):
    text: Optional[str]


class _ToolCallResultLike(Protocol):
    content: List[_ContentBlockLike]


def parse_tool_result_content(result: _ToolCallResultLike) -> Tuple[Optional[dict], Optional[str]]:
    """Extract structured data (if JSON) and raw text from an MCP tool result.

    Every MCP tool in this project (`search_knowledge`,
    `get_payment_failure_stats`, `search_recent_commits`) returns a
    Python dict, which FastMCP serializes into a single text content
    block containing JSON. This function extracts that JSON if present,
    and always preserves the raw text as a fallback — a parsing
    mismatch (e.g. a future tool that returns plain text) degrades to
    readable text rather than raising.

    Returns:
        (parsed_dict_or_None, raw_text_or_None)
    """
    content = getattr(result, "content", None) or []
    if not content:
        return None, None

    first_block = content[0]
    text = getattr(first_block, "text", None)
    if text is None:
        return None, None

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.debug("mcp_tool_result_not_json", extra={"event": "mcp_tool_result_not_json"})
        return None, text

    if isinstance(data, dict):
        return data, text
    return None, text
