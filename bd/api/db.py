"""Підключення до PostgreSQL і перетворення помилок СУБД на HTTP-відповіді."""
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent.parent
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# API працює від імені ролі edu_api (CRUD без права змінювати структуру)
DSN = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
    dbname=os.environ.get("API_DB_NAME", "elearn_db"),
    user=os.environ.get("API_DB_USER", "edu_api"),
    password=os.environ.get("API_DB_PASSWORD", ""),
    options="-c search_path=edu,public -c timezone=Europe/Kyiv",
)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, **DSN)
    return _pool


# SQLSTATE -> (HTTP-статус, короткий опис)
PG_ERRORS = {
    "23505": (409, "unique_violation"),
    "23503": (409, "foreign_key_violation"),
    "23001": (409, "restrict_violation"),
    "23514": (422, "check_violation"),
    "23502": (422, "not_null_violation"),
    "22P02": (422, "invalid_text_representation"),
    "22007": (422, "invalid_datetime_format"),
    "22003": (422, "numeric_value_out_of_range"),
    "42501": (403, "insufficient_privilege"),
    "P0002": (404, "no_data_found"),
    "55P03": (423, "lock_not_available"),
    "40001": (409, "serialization_failure"),
}


@contextmanager
def transaction():
    """Одна HTTP-операція = одна транзакція: COMMIT при успіху, ROLLBACK при помилці."""
    conn = pool().getconn()
    try:  # pre-ping: з'єднання могло бути розірване (перезапуск сервера, DROP DATABASE)
        with conn.cursor() as c:
            c.execute("SELECT 1")
        conn.rollback()
    except psycopg2.Error:
        pool().putconn(conn, close=True)
        conn = pool().getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        status, kind = PG_ERRORS.get(e.pgcode, (400, "database_error"))
        message = (e.diag.message_primary or str(e)).strip()
        raise HTTPException(status_code=status, detail={
            "error": kind, "sqlstate": e.pgcode, "message": message,
            "detail": e.diag.message_detail, "constraint": e.diag.constraint_name,
        }) from None
    except Exception:
        conn.rollback()
        raise
    finally:
        pool().putconn(conn)
