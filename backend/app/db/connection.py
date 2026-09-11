"""
connection.py
-------------
Opens connections to MySQL and runs the (already validated) read-only queries.

Uses a connection pool. Opening a fresh connection for every question would
add a noticeable delay each time, so instead we keep a handful open and hand
one out per request.
"""

import logging
import time
from typing import Any

import mysql.connector
from mysql.connector import pooling

from app.config import get_settings

logger = logging.getLogger(__name__)

_pool: pooling.MySQLConnectionPool | None = None


def get_pool() -> pooling.MySQLConnectionPool:
    """Creates the pool the first time it is needed, then reuses it."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = pooling.MySQLConnectionPool(
            pool_name="foodiequery_pool",
            pool_size=5,
            host=settings.db_host,
            port=settings.db_port,
            # Deliberately the restricted account, not root.
            user=settings.read_user,
            password=settings.read_password,
            database=settings.db_name,
            charset="utf8mb4",
            connection_timeout=10,
        )
        logger.info("MySQL pool created for user %s", settings.read_user)
    return _pool


def run_select(sql: str, max_rows: int) -> dict[str, Any]:
    """
    Runs one read-only query and returns the rows, the column names, and how
    long it took.

    Assumes the query has already been through validate_sql(). This function
    does not judge the SQL, it only runs it and stops reading at max_rows.
    """
    settings = get_settings()
    started = time.perf_counter()

    connection = get_pool().get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        # Ask MySQL itself to abort anything that runs too long, so one
        # accidental heavy join cannot tie up the server.
        cursor.execute(
            f"SET SESSION MAX_EXECUTION_TIME = {settings.query_timeout_seconds * 1000}"
        )
        cursor.execute(sql)

        rows = cursor.fetchmany(max_rows) if cursor.with_rows else []
        truncated = len(rows) == max_rows and bool(cursor.fetchone())

        # Any unread rows must be drained before the connection goes back to
        # the pool, otherwise the next request inherits a confused cursor.
        if cursor.with_rows:
            cursor.fetchall()

        columns = list(rows[0].keys()) if rows else [
            desc[0] for desc in (cursor.description or [])
        ]
        cursor.close()
    finally:
        connection.close()      # returns it to the pool, does not really close

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    logger.info("query ok: %s rows in %s ms", len(rows), elapsed_ms)

    return {
        "columns": columns,
        "rows": _make_json_safe(rows),
        "row_count": len(rows),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }


def _make_json_safe(rows: list[dict]) -> list[dict]:
    """
    Converts MySQL types that JSON cannot represent.

    DECIMAL comes back as Python's Decimal and dates as datetime objects.
    Neither survives being turned into JSON, so they become float and text.
    """
    from datetime import date, datetime
    from decimal import Decimal

    safe = []
    for row in rows:
        clean = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                clean[key] = float(value)
            elif isinstance(value, (datetime, date)):
                clean[key] = value.isoformat()
            elif isinstance(value, (bytes, bytearray)):
                clean[key] = value.decode("utf-8", errors="replace")
            else:
                clean[key] = value
        safe.append(clean)
    return safe


def check_database() -> dict[str, Any]:
    """A quick liveness probe used by the /health endpoint."""
    try:
        connection = get_pool().get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM restaurants")
        count = cursor.fetchone()[0]
        cursor.close()
        connection.close()
        return {"connected": True, "restaurants": count}
    except mysql.connector.Error as exc:
        logger.error("database health check failed: %s", exc)
        return {"connected": False, "error": str(exc)}
