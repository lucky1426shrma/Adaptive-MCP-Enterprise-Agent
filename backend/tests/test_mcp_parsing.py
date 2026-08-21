from __future__ import annotations

from types import SimpleNamespace

from app.mcp.parsing import parse_tool_result_content


def _block(text):
    return SimpleNamespace(text=text)


def _result(content):
    return SimpleNamespace(content=content)


def test_valid_json_dict_is_parsed() -> None:
    result = _result([_block('{"query": "x", "results": []}')])
    data, raw = parse_tool_result_content(result)
    assert data == {"query": "x", "results": []}
    assert raw == '{"query": "x", "results": []}'


def test_empty_content_list_returns_none_none() -> None:
    result = _result([])
    assert parse_tool_result_content(result) == (None, None)


def test_missing_content_attribute_returns_none_none() -> None:
    result = SimpleNamespace()  # no .content at all
    assert parse_tool_result_content(result) == (None, None)


def test_block_with_no_text_returns_none_none() -> None:
    result = _result([_block(None)])
    assert parse_tool_result_content(result) == (None, None)


def test_non_json_text_falls_back_to_raw_text() -> None:
    result = _result([_block("plain text response, not JSON")])
    data, raw = parse_tool_result_content(result)
    assert data is None
    assert raw == "plain text response, not JSON"


def test_json_list_is_not_treated_as_structured_data() -> None:
    # Our tools always return a dict; a JSON array should fall back to
    # raw text rather than being (incorrectly) treated as `data`.
    result = _result([_block("[1, 2, 3]")])
    data, raw = parse_tool_result_content(result)
    assert data is None
    assert raw == "[1, 2, 3]"


def test_only_first_content_block_is_used() -> None:
    result = _result([_block('{"first": true}'), _block('{"second": true}')])
    data, _ = parse_tool_result_content(result)
    assert data == {"first": True}
