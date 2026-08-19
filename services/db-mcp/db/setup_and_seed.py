"""Apply schema.sql, provision a least-privilege read-only role, and seed
synthetic payment data — including a failure spike matching the March
2026 incident doc (services/rag-mcp/data/sample_docs/) and a second
spike ending "now" (simulating an ongoing issue, for the project's
canonical demo query: "why did payment failures increase today, and is
this related to the March incident?").

This is an ADMIN/bootstrap script — it connects with a superuser/owner
connection string (`DATABASE_ADMIN_URL`), which db-mcp's *running server*
never holds. The server only ever gets the read-only `db_mcp_reader`
connection string (`DATABASE_URL` in db-mcp's own `.env`), consistent
with the project's least-privilege requirement.

NOT intended for production credential provisioning as-is — the reader
password is passed as a plain argument/env var and embedded into a DDL
statement here for local-development simplicity. In a real deployment,
provision the role via your infrastructure/secrets tooling instead and
skip `ensure_reader_role()`.

Usage:
    python -m db.setup_and_seed \\
        --admin-database-url postgresql://postgres:postgres@localhost:5432/adaptive_mcp \\
        --reader-password some-local-dev-password
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import asyncpg

from db.data_generation import STATUS_GATEWAY_ERROR, generate_payment_records

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("db_mcp.setup_and_seed")

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def apply_schema(admin_conn: asyncpg.Connection) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    await admin_conn.execute(schema_sql)
    logger.info("schema applied")


async def ensure_reader_role(admin_conn: asyncpg.Connection, database_name: str, password: str) -> None:
    """Create (or update the password of) the least-privilege read-only
    role db-mcp's running server connects as, and grant it SELECT on
    `payments` (including future tables via default privileges)."""
    escaped_password = password.replace("'", "''")

    role_exists = await admin_conn.fetchval(
        "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'db_mcp_reader'"
    )
    if role_exists:
        await admin_conn.execute(f"ALTER ROLE db_mcp_reader WITH LOGIN PASSWORD '{escaped_password}'")
        logger.info("reader role password updated")
    else:
        await admin_conn.execute(f"CREATE ROLE db_mcp_reader WITH LOGIN PASSWORD '{escaped_password}'")
        logger.info("reader role created")

    await admin_conn.execute(f'GRANT CONNECT ON DATABASE "{database_name}" TO db_mcp_reader')
    await admin_conn.execute("GRANT USAGE ON SCHEMA public TO db_mcp_reader")
    await admin_conn.execute("GRANT SELECT ON payments TO db_mcp_reader")
    await admin_conn.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO db_mcp_reader"
    )
    logger.info("reader role privileges granted (SELECT only)")


async def seed_data(admin_conn: asyncpg.Connection, records: List[tuple]) -> None:
    await admin_conn.execute("TRUNCATE TABLE payments RESTART IDENTITY")
    await admin_conn.copy_records_to_table(
        "payments",
        records=records,
        columns=["created_at", "service", "status", "amount_cents", "failure_reason"],
    )
    logger.info(f"seeded {len(records)} payment records")


async def main_async(args: argparse.Namespace) -> None:
    admin_url = args.admin_database_url or os.environ.get("DATABASE_ADMIN_URL")
    reader_password = args.reader_password or os.environ.get("DB_MCP_READER_PASSWORD")

    if not admin_url:
        raise SystemExit(
            "Provide --admin-database-url or set DATABASE_ADMIN_URL "
            "(a superuser/owner connection string, used only by this script)."
        )
    if not reader_password:
        raise SystemExit(
            "Provide --reader-password or set DB_MCP_READER_PASSWORD "
            "(never hard-code this)."
        )

    database_name = urlparse(admin_url).path.lstrip("/")
    if not database_name:
        raise SystemExit("Could not determine database name from --admin-database-url.")

    admin_conn = await asyncpg.connect(dsn=admin_url)
    try:
        await apply_schema(admin_conn)
        await ensure_reader_role(admin_conn, database_name, reader_password)

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=args.days)
        today_spike_start = now - timedelta(hours=args.today_spike_hours)
        today_spike_end = now

        records = generate_payment_records(
            start=start, end=now, today_spike_start=today_spike_start, today_spike_end=today_spike_end
        )
        await seed_data(admin_conn, records)

        today_gateway_errors = sum(
            1 for r in records if r[0] >= today_spike_start and r[2] == STATUS_GATEWAY_ERROR
        )
        logger.info(
            f"seed complete: {len(records)} total records, "
            f"{today_gateway_errors} gateway_error records in the simulated "
            f"'today' spike window ({today_spike_start.isoformat()} to {today_spike_end.isoformat()})"
        )
    finally:
        await admin_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply schema, create the read-only reader role, and seed synthetic payment data."
    )
    parser.add_argument(
        "--admin-database-url",
        default=None,
        help="Superuser/owner connection string. Falls back to DATABASE_ADMIN_URL env var.",
    )
    parser.add_argument(
        "--reader-password",
        default=None,
        help="Password to set for the db_mcp_reader role. Falls back to DB_MCP_READER_PASSWORD env var.",
    )
    parser.add_argument(
        "--days", type=int, default=75, help="Days of baseline history to generate, ending now."
    )
    parser.add_argument(
        "--today-spike-hours",
        type=int,
        default=2,
        help="Length, in hours, of the simulated ongoing failure spike ending now.",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
