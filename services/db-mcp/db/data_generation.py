"""Synthetic payment-record generation — pure logic, no database dependency.

Split out from `setup_and_seed.py` specifically so this can be unit
tested without `asyncpg` installed (that script's I/O — connecting,
applying schema, seeding — genuinely needs it; the data-shaping logic
here doesn't).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

STATUS_SUCCESS = "success"
STATUS_DECLINED = "declined"
STATUS_VALIDATION_ERROR = "validation_error"
STATUS_GATEWAY_ERROR = "gateway_error"

ALL_STATUSES = (STATUS_SUCCESS, STATUS_DECLINED, STATUS_VALIDATION_ERROR, STATUS_GATEWAY_ERROR)

# Baseline: ~2.2% overall failure rate, matching the range stated in
# services/rag-mcp/data/sample_docs/payment-retry-policy.md ("typically
# between 1.5% and 2.5%").
BASELINE_WEIGHTS: Dict[str, float] = {
    STATUS_SUCCESS: 0.978,
    STATUS_DECLINED: 0.015,
    STATUS_VALIDATION_ERROR: 0.004,
    STATUS_GATEWAY_ERROR: 0.003,
}

# Matches "~6% of checkout attempts... failed with a gateway timeout"
# from the March incident doc.
MARCH_INCIDENT_WEIGHTS: Dict[str, float] = {
    STATUS_SUCCESS: 0.920,
    STATUS_DECLINED: 0.014,
    STATUS_VALIDATION_ERROR: 0.004,
    STATUS_GATEWAY_ERROR: 0.062,
}

# A second, smaller ongoing spike ending "now" — above the 3% alerting
# threshold from the retry-policy doc, but distinct in magnitude from
# the March incident.
TODAY_SPIKE_WEIGHTS: Dict[str, float] = {
    STATUS_SUCCESS: 0.940,
    STATUS_DECLINED: 0.014,
    STATUS_VALIDATION_ERROR: 0.004,
    STATUS_GATEWAY_ERROR: 0.042,
}

MARCH_INCIDENT_START = datetime(2026, 3, 14, 14, 10, tzinfo=timezone.utc)
MARCH_INCIDENT_END = datetime(2026, 3, 14, 15, 40, tzinfo=timezone.utc)

FAILURE_REASONS: Dict[str, List[str]] = {
    STATUS_DECLINED: ["insufficient_funds", "card_declined_by_issuer", "expired_card"],
    STATUS_VALIDATION_ERROR: ["invalid_card_number", "invalid_expiry_date", "invalid_cvv"],
    STATUS_GATEWAY_ERROR: ["gateway_timeout", "gateway_connection_error"],
}


def weights_for(ts: datetime, today_spike_start: datetime, today_spike_end: datetime) -> Dict[str, float]:
    if MARCH_INCIDENT_START <= ts <= MARCH_INCIDENT_END:
        return MARCH_INCIDENT_WEIGHTS
    if today_spike_start <= ts <= today_spike_end:
        return TODAY_SPIKE_WEIGHTS
    return BASELINE_WEIGHTS


def _pick_status(weights: Dict[str, float], rng: random.Random) -> str:
    statuses = list(weights.keys())
    probs = list(weights.values())
    return rng.choices(statuses, weights=probs, k=1)[0]


def generate_payment_records(
    start: datetime,
    end: datetime,
    today_spike_start: datetime,
    today_spike_end: datetime,
    attempts_per_hour_range: Tuple[int, int] = (150, 250),
    service: str = "payment-service",
    seed: int = 42,
) -> List[tuple]:
    """Generate (created_at, service, status, amount_cents, failure_reason)
    tuples for every hour in `[start, end)`, deterministic given `seed`."""
    if end <= start:
        raise ValueError("end must be after start")

    rng = random.Random(seed)
    records: List[tuple] = []

    current_hour = start.replace(minute=0, second=0, microsecond=0)
    while current_hour < end:
        n_attempts = rng.randint(*attempts_per_hour_range)
        for _ in range(n_attempts):
            ts = current_hour + timedelta(seconds=rng.randint(0, 3599))
            if ts < start or ts >= end:
                continue

            weights = weights_for(ts, today_spike_start, today_spike_end)
            status = _pick_status(weights, rng)
            amount_cents = rng.randint(500, 50000)
            failure_reason = rng.choice(FAILURE_REASONS[status]) if status != STATUS_SUCCESS else None

            records.append((ts, service, status, amount_cents, failure_reason))

        current_hour += timedelta(hours=1)

    return records
