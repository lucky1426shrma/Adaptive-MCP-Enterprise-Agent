from __future__ import annotations

import json

from app.llm.exceptions import LLMResponseError
from app.llm.openrouter_format import message_to_openrouter, parse_tool_calls, tool_to_openrouter
from app.llm.schemas import ChatMessage, ChatRole, ToolCall, ToolDefinition


def test_system_message_conversion() -> None:
    msg = ChatMessage(role=ChatRole.system, content="You are helpful.")
    assert message_to_openrouter(msg) == {"role": "system", "content": "You are helpful."}


def test_user_message_conversion() -> None:
    msg = ChatMessage(role=ChatRole.user, content="Why did failures increase?")
    converted = message_to_openrouter(msg)
    assert converted["role"] == "user"
    assert converted["content"] == "Why did failures increase?"


def test_assistant_message_with_tool_calls_conversion() -> None:
    msg = ChatMessage(
        role=ChatRole.assistant,
        content=None,
        tool_calls=[ToolCall(id="c1", name="rag__search_knowledge", arguments={"query": "x", "top_k": 3})],
    )
    converted = message_to_openrouter(msg)

    assert converted["role"] == "assistant"
    assert converted["tool_calls"][0]["id"] == "c1"
    assert converted["tool_calls"][0]["type"] == "function"
    assert converted["tool_calls"][0]["function"]["name"] == "rag__search_knowledge"
    assert json.loads(converted["tool_calls"][0]["function"]["arguments"]) == {"query": "x", "top_k": 3}


def test_tool_result_message_conversion() -> None:
    msg = ChatMessage(
        role=ChatRole.tool, tool_call_id="c1", name="rag__search_knowledge", content='{"results": []}'
    )
    converted = message_to_openrouter(msg)
    assert converted == {
        "role": "tool",
        "tool_call_id": "c1",
        "name": "rag__search_knowledge",
        "content": '{"results": []}',
    }


def test_tool_result_message_with_no_content_becomes_empty_string() -> None:
    msg = ChatMessage(role=ChatRole.tool, tool_call_id="c1", name="x", content=None)
    converted = message_to_openrouter(msg)
    assert converted["content"] == ""


def test_tool_definition_conversion() -> None:
    tool = ToolDefinition(
        name="rag__search_knowledge",
        description="Search the knowledge base.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    converted = tool_to_openrouter(tool)

    assert converted["type"] == "function"
    assert converted["function"]["name"] == "rag__search_knowledge"
    assert converted["function"]["description"] == "Search the knowledge base."
    assert converted["function"]["parameters"]["properties"]["query"]["type"] == "string"


def test_parse_tool_calls_returns_none_for_empty() -> None:
    assert parse_tool_calls(None) is None
    assert parse_tool_calls([]) is None


def test_parse_tool_calls_parses_json_arguments() -> None:
    raw = [{"id": "c1", "function": {"name": "rag__search_knowledge", "arguments": '{"query": "x"}'}}]
    parsed = parse_tool_calls(raw)

    assert parsed is not None
    assert parsed[0].id == "c1"
    assert parsed[0].name == "rag__search_knowledge"
    assert parsed[0].arguments == {"query": "x"}


def test_parse_tool_calls_handles_multiple_calls() -> None:
    raw = [
        {"id": "c1", "function": {"name": "rag__search_knowledge", "arguments": '{"query": "a"}'}},
        {"id": "c2", "function": {"name": "db__get_payment_failure_stats", "arguments": '{"start_date": "2026-08-01"}'}},
    ]
    parsed = parse_tool_calls(raw)
    assert len(parsed) == 2
    assert parsed[1].name == "db__get_payment_failure_stats"


def test_parse_tool_calls_defaults_missing_arguments_to_empty_dict() -> None:
    raw = [{"id": "c1", "function": {"name": "x", "arguments": ""}}]
    parsed = parse_tool_calls(raw)
    assert parsed[0].arguments == {}


def test_parse_tool_calls_raises_on_malformed_json() -> None:
    raw = [{"id": "c1", "function": {"name": "x", "arguments": "{not valid json"}}]
    try:
        parse_tool_calls(raw)
        raise AssertionError("expected LLMResponseError")
    except LLMResponseError:
        pass


def test_parse_tool_calls_raises_on_non_object_arguments() -> None:
    raw = [{"id": "c1", "function": {"name": "x", "arguments": "[1, 2, 3]"}}]
    try:
        parse_tool_calls(raw)
        raise AssertionError("expected LLMResponseError")
    except LLMResponseError:
        pass


def test_parse_tool_calls_handles_dict_arguments() -> None:
    raw = [{"id": "c1", "function": {"name": "rag__search_knowledge", "arguments": {"query": "x"}}}]
    parsed = parse_tool_calls(raw)
    assert parsed is not None
    assert parsed[0].arguments == {"query": "x"}


def test_parse_tool_calls_handles_markdown_fenced_json() -> None:
    raw = [
        {
            "id": "c1",
            "function": {
                "name": "rag__search_knowledge",
                "arguments": '```json\n{"query": "markdown test"}\n```',
            },
        }
    ]
    parsed = parse_tool_calls(raw)
    assert parsed is not None
    assert parsed[0].arguments == {"query": "markdown test"}


def test_parse_tool_calls_generates_id_when_missing() -> None:
    raw = [{"function": {"name": "x", "arguments": '{"a": 1}'}}]
    parsed = parse_tool_calls(raw)
    assert parsed is not None
    assert parsed[0].id.startswith("call_0")

