"""Tests for tool input validation.

Requires `pydantic` installed to execute — see the top-level README for
why that isn't possible in this sandbox; verify locally with
`pip install -r requirements-dev.txt && pytest`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import SearchKnowledgeInput


def test_valid_input_passes() -> None:
    validated = SearchKnowledgeInput(query="March payment incident", top_k=5)
    assert validated.query == "March payment incident"
    assert validated.top_k == 5


def test_default_top_k_is_five() -> None:
    validated = SearchKnowledgeInput(query="anything")
    assert validated.top_k == 5


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchKnowledgeInput(query="", top_k=5)


def test_overlong_query_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchKnowledgeInput(query="x" * 501, top_k=5)


@pytest.mark.parametrize("top_k", [0, -1, 21, 1000])
def test_top_k_out_of_range_is_rejected(top_k: int) -> None:
    with pytest.raises(ValidationError):
        SearchKnowledgeInput(query="valid query", top_k=top_k)


@pytest.mark.parametrize("top_k", [1, 20])
def test_top_k_boundary_values_are_accepted(top_k: int) -> None:
    validated = SearchKnowledgeInput(query="valid query", top_k=top_k)
    assert validated.top_k == top_k
