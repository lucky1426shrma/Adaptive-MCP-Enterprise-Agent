from __future__ import annotations

import logging

from app.security.log_redaction import SecretRedactionFilter


def _make_record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1, msg="test message", args=(), exc_info=None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_redacts_field_named_api_key() -> None:
    record = _make_record(api_key="sk-real-secret-value")
    SecretRedactionFilter().filter(record)
    assert record.api_key == "***REDACTED***"


def test_redacts_field_named_token() -> None:
    record = _make_record(auth_token="real-token-value")
    SecretRedactionFilter().filter(record)
    assert record.auth_token == "***REDACTED***"


def test_redacts_field_named_password() -> None:
    record = _make_record(db_password="hunter2")
    SecretRedactionFilter().filter(record)
    assert record.db_password == "***REDACTED***"


def test_redacts_connection_string_field() -> None:
    record = _make_record(connection_string="postgresql://user:pass@host/db")
    SecretRedactionFilter().filter(record)
    assert record.connection_string == "***REDACTED***"


def test_redacts_case_insensitively() -> None:
    record = _make_record(API_KEY="secret")
    SecretRedactionFilter().filter(record)
    assert record.API_KEY == "***REDACTED***"


def test_does_not_redact_unrelated_fields() -> None:
    record = _make_record(event="request_completed", latency_ms=42.0, path="/health")
    SecretRedactionFilter().filter(record)
    assert record.event == "request_completed"
    assert record.latency_ms == 42.0
    assert record.path == "/health"


def test_does_not_redact_non_string_values_even_if_key_matches() -> None:
    # A numeric or dict value under a matching key name is left alone —
    # this filter only redacts string values, matching the documented
    # scope (it can't safely stringify arbitrary objects).
    record = _make_record(token_count=5)
    SecretRedactionFilter().filter(record)
    assert record.token_count == 5


def test_filter_always_returns_true_to_allow_the_record_through() -> None:
    record = _make_record(api_key="secret")
    assert SecretRedactionFilter().filter(record) is True


def test_standard_message_field_is_never_touched() -> None:
    record = _make_record()
    record.msg = "a message mentioning a token conceptually"
    SecretRedactionFilter().filter(record)
    assert record.msg == "a message mentioning a token conceptually"
