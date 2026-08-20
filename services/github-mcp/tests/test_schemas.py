"""Tests for SearchRecentCommitsInput validation.

Requires `pydantic` installed to execute — verify locally with
`pip install -r requirements-dev.txt && pytest`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import SearchRecentCommitsInput


def test_valid_input_passes() -> None:
    validated = SearchRecentCommitsInput(repository="myorg/payment-service", since="2026-08-01")
    assert validated.repository == "myorg/payment-service"
    assert validated.path_filter is None


def test_optional_path_filter() -> None:
    validated = SearchRecentCommitsInput(
        repository="myorg/payment-service", since="2026-08-01", path_filter="src/payments/"
    )
    assert validated.path_filter == "src/payments/"


def test_invalid_date_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchRecentCommitsInput(repository="myorg/payment-service", since="not-a-date")


@pytest.mark.parametrize(
    "repository",
    ["no-slash-here", "/leading-slash/repo", "trailing-slash/", ""],
)
def test_malformed_repository_is_rejected(repository: str) -> None:
    with pytest.raises(ValidationError):
        SearchRecentCommitsInput(repository=repository, since="2026-08-01")


def test_overlong_path_filter_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchRecentCommitsInput(
            repository="myorg/payment-service", since="2026-08-01", path_filter="x" * 301
        )
