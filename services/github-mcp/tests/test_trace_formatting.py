from __future__ import annotations

from app.trace_formatting import format_span_id, format_trace_id


def test_format_trace_id_pads_to_32_hex_chars() -> None:
    assert format_trace_id(1) == "0" * 31 + "1"
    assert len(format_trace_id(1)) == 32


def test_format_trace_id_full_128_bit_value() -> None:
    max_128_bit = (2**128) - 1
    formatted = format_trace_id(max_128_bit)
    assert formatted == "f" * 32


def test_format_trace_id_zero() -> None:
    assert format_trace_id(0) == "0" * 32


def test_format_span_id_pads_to_16_hex_chars() -> None:
    assert format_span_id(1) == "0" * 15 + "1"
    assert len(format_span_id(1)) == 16


def test_format_span_id_full_64_bit_value() -> None:
    max_64_bit = (2**64) - 1
    assert format_span_id(max_64_bit) == "f" * 16


def test_format_span_id_zero() -> None:
    assert format_span_id(0) == "0" * 16
