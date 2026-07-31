"""Database connections.

A pooled implementation behind the original context-manager interface, so the
115 call sites did not have to change.

Why an overflow path exists
---------------------------
A single review turn nests connections: the orchestrator holds one open across
the LLM call while material loading, memory lookups, grounding and six
thinking-step writes each take their own. That is 12-15 at once. With a fixed
pool that blocks when exhausted, two concurrent turns would wait on each other
while holding connections — a deadlock. So exhaustion falls back to a direct
connection instead of blocking: the pool caps steady-state usage without ever
becoming a bottleneck the app can deadlock against.
"""
import threading
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
from psycopg2.extras import RealDictCursor

from .config import settings

_pool = None
_pool_lock = threading.Lock()

# Counters for the readiness endpoint; overflow use is the signal that the
# pool is undersized for the workload.
_stats = {"pooled": 0, "overflow": 0}


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pg_pool.ThreadedConnectionPool(
                    minconn=settings.db_pool_min,
                    maxconn=settings.db_pool_max,
                    dsn=settings.database_url,
                )
    return _pool


def _return(conn, from_pool: bool) -> None:
    """Return a connection, never leaving an open transaction behind."""
    broken = conn.closed != 0
    if not broken:
        try:
            if conn.get_transaction_status() != TRANSACTION_STATUS_IDLE:
                # A connection handed back mid-transaction would poison
                # whoever borrows it next.
                conn.rollback()
        except Exception:
            broken = True

    if from_pool:
        try:
            _get_pool().putconn(conn, close=broken)
            return
        except Exception:
            pass
    try:
        conn.close()
    except Exception:
        pass


@contextmanager
def get_db_connection() -> Generator:
    """Borrow a connection; commits on clean exit, rolls back on error."""
    conn = None
    from_pool = False

    try:
        conn = _get_pool().getconn()
        from_pool = True
        _stats["pooled"] += 1
    except Exception:
        # Pool exhausted or unavailable — see the module docstring.
        conn = psycopg2.connect(settings.database_url)
        _stats["overflow"] += 1

    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        _return(conn, from_pool)


def get_cursor(conn):
    """Get cursor from connection"""
    return conn.cursor(cursor_factory=RealDictCursor)


def pool_stats() -> dict:
    """Borrow counts since start, for the readiness endpoint."""
    return {
        **_stats,
        "min": settings.db_pool_min,
        "max": settings.db_pool_max,
        "initialised": _pool is not None,
    }


def close_pool() -> None:
    """Release every pooled connection (shutdown, or between test runs)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            finally:
                _pool = None
