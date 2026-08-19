"""Tests for PaymentFailureStatsInput validation.

Requires `pydantic` installed to execute — verify locally with
`pip install -r requirements-dev.txt && pytest`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import PaymentFailureStatsInput


def test_valid_range_passes() -> None:
    validated = PaymentFailureStatsInput(start_date="2026-08-01", end_date="2026-08-14")
    assert validated.start_date == "2026-08-01"
    assert validated.service is None


def test_optional_service_filter() -> None:
    validated = PaymentFailureStatsInput(
        start_date="2026-08-01", end_date="2026-08-02", service="payment-service"
    )
    assert validated.service == "payment-service"


def test_invalid_date_format_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PaymentFailureStatsInput(start_date="08/01/2026", end_date="2026-08-02")


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PaymentFailureStatsInput(start_date="2026-08-14", end_date="2026-08-01")


def test_range_exceeding_max_days_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PaymentFailureStatsInput(start_date="2026-01-01", end_date="2026-08-01")


def test_same_day_range_is_allowed() -> None:
    validated = PaymentFailureStatsInput(start_date="2026-08-01", end_date="2026-08-01")
    assert validated.start_date == validated.end_date


def test_overlong_service_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PaymentFailureStatsInput(start_date="2026-08-01", end_date="2026-08-01", service="x" * 101)
