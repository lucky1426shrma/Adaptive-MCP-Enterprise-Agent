from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.data_generation import (
    ALL_STATUSES,
    MARCH_INCIDENT_END,
    MARCH_INCIDENT_START,
    STATUS_GATEWAY_ERROR,
    STATUS_SUCCESS,
    generate_payment_records,
)


def test_generates_records_within_the_requested_window() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 2, tzinfo=timezone.utc)
    records = generate_payment_records(start, end, today_spike_start=end, today_spike_end=end)

    assert len(records) > 0
    for ts, service, status, amount_cents, failure_reason in records:
        assert start <= ts < end
        assert service == "payment-service"
        assert status in ALL_STATUSES
        assert amount_cents > 0


def test_success_records_have_no_failure_reason() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 1, 3, tzinfo=timezone.utc)
    records = generate_payment_records(start, end, today_spike_start=end, today_spike_end=end)

    for _, _, status, _, failure_reason in records:
        if status == STATUS_SUCCESS:
            assert failure_reason is None
        else:
            assert failure_reason is not None


def test_march_incident_window_has_elevated_gateway_error_rate() -> None:
    # Compare the incident window itself against an ordinary day.
    incident_records = generate_payment_records(
        MARCH_INCIDENT_START,
        MARCH_INCIDENT_END,
        today_spike_start=MARCH_INCIDENT_END,
        today_spike_end=MARCH_INCIDENT_END,
    )
    ordinary_start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ordinary_end = datetime(2026, 6, 1, 1, 30, tzinfo=timezone.utc)
    ordinary_records = generate_payment_records(
        ordinary_start, ordinary_end, today_spike_start=ordinary_end, today_spike_end=ordinary_end
    )

    def gateway_error_rate(records) -> float:
        if not records:
            return 0.0
        errors = sum(1 for r in records if r[2] == STATUS_GATEWAY_ERROR)
        return errors / len(records)

    assert gateway_error_rate(incident_records) > gateway_error_rate(ordinary_records) * 5


def test_today_spike_window_has_elevated_gateway_error_rate() -> None:
    now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=6)
    spike_start = now - timedelta(hours=2)

    records = generate_payment_records(start, now, today_spike_start=spike_start, today_spike_end=now)

    spike_records = [r for r in records if r[0] >= spike_start]
    baseline_records = [r for r in records if r[0] < spike_start]

    def gateway_error_rate(records) -> float:
        if not records:
            return 0.0
        errors = sum(1 for r in records if r[2] == STATUS_GATEWAY_ERROR)
        return errors / len(records)

    assert gateway_error_rate(spike_records) > gateway_error_rate(baseline_records) * 3


def test_generation_is_deterministic_given_same_seed() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 1, 5, tzinfo=timezone.utc)

    records_a = generate_payment_records(start, end, today_spike_start=end, today_spike_end=end, seed=7)
    records_b = generate_payment_records(start, end, today_spike_start=end, today_spike_end=end, seed=7)

    assert records_a == records_b


def test_different_seeds_produce_different_records() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 1, 5, tzinfo=timezone.utc)

    records_a = generate_payment_records(start, end, today_spike_start=end, today_spike_end=end, seed=1)
    records_b = generate_payment_records(start, end, today_spike_start=end, today_spike_end=end, seed=2)

    assert records_a != records_b


def test_end_before_start_raises_value_error() -> None:
    start = datetime(2026, 8, 2, tzinfo=timezone.utc)
    end = datetime(2026, 8, 1, tzinfo=timezone.utc)
    try:
        generate_payment_records(start, end, today_spike_start=end, today_spike_end=end)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
