from __future__ import annotations

from app.commit_shaping import shape_commit


def test_shapes_basic_commit() -> None:
    raw = {
        "sha": "abcdef1234567890",
        "commit": {
            "message": "Increase payment gateway connection pool size\n\nLonger body text here.",
            "author": {"name": "Alice Example", "date": "2026-03-15T09:00:00Z"},
        },
    }
    shaped = shape_commit(raw, ["src/payments/gateway_client_config.py"])

    assert shaped["sha"] == "abcdef1234"
    assert shaped["message"] == "Increase payment gateway connection pool size"
    assert shaped["author"] == "Alice Example"
    assert shaped["date"] == "2026-03-15T09:00:00Z"
    assert shaped["files_changed"] == ["src/payments/gateway_client_config.py"]


def test_sha_is_truncated_to_ten_characters() -> None:
    raw = {"sha": "0123456789abcdef0123456789abcdef01234567", "commit": {"message": "msg"}}
    shaped = shape_commit(raw, [])
    assert shaped["sha"] == "0123456789"
    assert len(shaped["sha"]) == 10


def test_only_first_line_of_message_is_kept() -> None:
    raw = {"sha": "abc", "commit": {"message": "First line\nSecond line\nThird line"}}
    shaped = shape_commit(raw, [])
    assert shaped["message"] == "First line"


def test_missing_author_falls_back_to_unknown() -> None:
    raw = {"sha": "abc", "commit": {"message": "msg"}}
    shaped = shape_commit(raw, [])
    assert shaped["author"] == "unknown"


def test_empty_message_does_not_raise() -> None:
    raw = {"sha": "abc", "commit": {"message": ""}}
    shaped = shape_commit(raw, [])
    assert shaped["message"] == ""


def test_missing_commit_key_does_not_raise() -> None:
    raw = {"sha": "abc"}
    shaped = shape_commit(raw, [])
    assert shaped["message"] == ""
    assert shaped["author"] == "unknown"


def test_no_files_changed_is_empty_list() -> None:
    raw = {"sha": "abc", "commit": {"message": "msg"}}
    shaped = shape_commit(raw, [])
    assert shaped["files_changed"] == []
