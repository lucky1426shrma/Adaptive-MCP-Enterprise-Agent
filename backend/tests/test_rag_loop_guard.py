from __future__ import annotations

from app.agent.rag_loop_guard import is_repeat_query, rag_attempts_remaining


def test_attempts_remaining_full_budget_when_unused() -> None:
    assert rag_attempts_remaining([], max_attempts=3) == 3


def test_attempts_remaining_decreases_with_usage() -> None:
    assert rag_attempts_remaining(["q1", "q2"], max_attempts=3) == 1


def test_attempts_remaining_never_negative() -> None:
    assert rag_attempts_remaining(["q1", "q2", "q3", "q4"], max_attempts=3) == 0


def test_is_repeat_query_detects_exact_match() -> None:
    assert is_repeat_query("March incident", ["March incident"]) is True


def test_is_repeat_query_case_and_whitespace_insensitive() -> None:
    assert is_repeat_query("  march INCIDENT  ", ["March incident"]) is True


def test_is_repeat_query_false_for_different_query() -> None:
    assert is_repeat_query("March incident root cause", ["March incident"]) is False


def test_is_repeat_query_false_when_no_history() -> None:
    assert is_repeat_query("anything", []) is False
