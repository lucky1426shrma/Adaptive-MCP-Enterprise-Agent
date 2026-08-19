"""Manual smoke test: connect to the running RAG MCP server as a real
MCP client over Streamable HTTP, list its tools, and call search_knowledge.

This exists specifically to verify the FastMCP mounting/lifespan wiring
in `app/server.py` against whatever `mcp` SDK version you actually have
installed (see the caveat in that file) — run this after starting the
server and after running `scripts/ingest.py` at least once.

Usage:
    python -m scripts.smoke_test_client
"""

from __future__ import annotations

import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
    url = os.environ.get("RAG_MCP_SMOKE_TEST_URL", "http://localhost:8001/mcp/")
    token = os.environ.get("RAG_MCP_SMOKE_TEST_TOKEN", "dev-local-only-change-me")
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Connecting to {url} ...")
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools discovered:", [t.name for t in tools.tools])

            result = await session.call_tool(
                "search_knowledge", {"query": "March payment incident root cause", "top_k": 3}
            )
            print("search_knowledge result:")
            for block in result.content:
                print(getattr(block, "text", block))


if __name__ == "__main__":
    asyncio.run(main())
