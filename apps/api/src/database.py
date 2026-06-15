"""Database connection and utilities"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Generator
from .config import settings


@contextmanager
def get_db_connection() -> Generator:
    """Get database connection with context manager"""
    conn = None
    try:
        conn = psycopg2.connect(settings.database_url)
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_cursor(conn):
    """Get cursor from connection"""
    return conn.cursor(cursor_factory=RealDictCursor)
