"""Database access for db-mcp.

Owns the connection pool and the one query this server currently runs.
Kept separate from `server.py` so the query/pool logic can be reasoned
about (and eventually tested with a real test database) independently
of the MCP tool wiring.

SAFETY: the query below is parameterized (asyncpg's $1/$2/$3
placeholders — never raw string interpolation of caller input) and
bounded by `query_timeout_seconds`. The date range itself is already
validated (max `max_date_range_days`) before this is ever called, in
`app/schemas.py`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import asyncpg

from app.span_helper import start_span

logger = logging.getLogger(__name__)


class Database:
    """Wraps an asyncpg connection pool for db-mcp's read-only queries."""

    def __init__(self, dsn: str, min_size: int, max_size: int, query_timeout_seconds: float) -> None:
        if not dsn:
            raise RuntimeError(
                "DATABASE_URL is not configured. db-mcp cannot serve real queries without it."
            )
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._query_timeout_seconds = query_timeout_seconds
        self._pool: Optional[asyncpg.pool.Pool] = None

    async def connect(self) -> None:
        logger.info("db_pool_connecting", extra={"event": "db_pool_connecting"})
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=self._query_timeout_seconds,
        )
        logger.info("db_pool_connected", extra={"event": "db_pool_connected"})

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            logger.info("db_pool_closed", extra={"event": "db_pool_closed"})

    async def ping(self) -> bool:
        """Cheap connectivity check for the readiness endpoint."""
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1", timeout=self._query_timeout_seconds)
            return True
        except Exception:  # noqa: BLE001 - readiness must report, not raise
            logger.warning("db_ping_failed", extra={"event": "db_ping_failed"})
            return False

    async def get_payment_failure_stats(
        self, start_date: str, end_date: str, service: Optional[str]
    ) -> dict:
        with start_span("db.query.get_payment_failure_stats", {"service": service or "all"}):
            if self._pool is None:
                raise RuntimeError("Database pool is not connected yet.")

            # Inclusive end_date -> exclusive upper bound at the next day's
            # midnight UTC, so "2026-08-14" includes the entirety of Aug 14.
            start_ts = datetime.combine(date.fromisoformat(start_date), time.min, tzinfo=timezone.utc)
            end_ts = datetime.combine(
                date.fromisoformat(end_date) + timedelta(days=1), time.min, tzinfo=timezone.utc
            )

            query = """
                SELECT
                    COUNT(*) AS total_attempts,
                    COUNT(*) FILTER (WHERE status != 'success') AS failed_attempts
                FROM payments
                WHERE created_at >= $1
                  AND created_at < $2
                  AND ($3::text IS NULL OR service = $3)
            """

            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, start_ts, end_ts, service, timeout=self._query_timeout_seconds
                )

        total_attempts = row["total_attempts"] if row else 0
        failed_attempts = row["failed_attempts"] if row else 0
        failure_rate_pct = round((failed_attempts / total_attempts) * 100, 2) if total_attempts else 0.0

        return {
            "start_date": start_date,
            "end_date": end_date,
            "service": service,
            "total_attempts": total_attempts,
            "failed_attempts": failed_attempts,
            "failure_rate_pct": failure_rate_pct,
        }
