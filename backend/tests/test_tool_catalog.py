from __future__ import annotations

from app.agent.tool_catalog import ToolCatalog


class _FakeToolInfo:
    def __init__(self, name, description=None, input_schema=None):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {}


class _FakeClient:
    def __init__(self, tools, raise_on_list=False):
        self._tools = tools
        self._raise = raise_on_list

    async def list_tools(self):
        if self._raise:
            raise RuntimeError("server down")
        return self._tools


class _FakeRegistry:
    def __init__(self, clients):
        self._clients = clients

    def all(self):
        return dict(self._clients)

    def get(self, name):
        return self._clients.get(name)


def test_catalog_starts_empty() -> None:
    catalog = ToolCatalog()
    assert catalog.is_empty
    assert catalog.tools == []


async def test_refresh_prefixes_tool_names_with_server() -> None:
    catalog = ToolCatalog()
    clients = {"rag": _FakeClient([_FakeToolInfo("search_knowledge", "desc")])}
    await catalog.refresh(_FakeRegistry(clients))

    assert not catalog.is_empty
    assert [t.name for t in catalog.tools] == ["rag__search_knowledge"]


async def test_refresh_carries_description_and_schema() -> None:
    catalog = ToolCatalog()
    clients = {
        "rag": _FakeClient([_FakeToolInfo("search_knowledge", "desc", {"type": "object", "properties": {"query": {}}})])
    }
    await catalog.refresh(_FakeRegistry(clients))

    tool = catalog.tools[0]
    assert tool.description == "desc"
    assert "query" in tool.parameters["properties"]


async def test_resolve_maps_back_to_server_and_original_name() -> None:
    catalog = ToolCatalog()
    clients = {"db": _FakeClient([_FakeToolInfo("get_payment_failure_stats")])}
    await catalog.refresh(_FakeRegistry(clients))

    server, tool_name = catalog.resolve("db__get_payment_failure_stats")
    assert server == "db"
    assert tool_name == "get_payment_failure_stats"


async def test_resolve_unknown_tool_raises_key_error() -> None:
    catalog = ToolCatalog()
    await catalog.refresh(_FakeRegistry({}))
    try:
        catalog.resolve("nonexistent__tool")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


async def test_unreachable_server_is_skipped_not_fatal() -> None:
    catalog = ToolCatalog()
    clients = {
        "rag": _FakeClient([_FakeToolInfo("search_knowledge")]),
        "github": _FakeClient([], raise_on_list=True),
    }
    await catalog.refresh(_FakeRegistry(clients))

    assert [t.name for t in catalog.tools] == ["rag__search_knowledge"]


async def test_multiple_servers_produce_distinct_prefixed_names() -> None:
    catalog = ToolCatalog()
    clients = {
        "rag": _FakeClient([_FakeToolInfo("search_knowledge")]),
        "db": _FakeClient([_FakeToolInfo("get_payment_failure_stats")]),
    }
    await catalog.refresh(_FakeRegistry(clients))

    assert sorted(t.name for t in catalog.tools) == [
        "db__get_payment_failure_stats",
        "rag__search_knowledge",
    ]


async def test_refresh_replaces_previous_catalog_entirely() -> None:
    catalog = ToolCatalog()
    await catalog.refresh(_FakeRegistry({"rag": _FakeClient([_FakeToolInfo("search_knowledge")])}))
    assert len(catalog.tools) == 1

    await catalog.refresh(_FakeRegistry({}))  # all servers gone
    assert catalog.is_empty
    try:
        catalog.resolve("rag__search_knowledge")
        raise AssertionError("expected KeyError after refresh cleared stale routes")
    except KeyError:
        pass
