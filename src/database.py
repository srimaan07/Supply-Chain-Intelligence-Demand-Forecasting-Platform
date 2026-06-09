"""Database connection and utility helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Iterable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import get_settings

logger = logging.getLogger(__name__)


def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


@contextmanager
def get_connection() -> Generator:
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_sql(sql: str, params: dict[str, Any] | None = None) -> None:
    with get_connection() as conn:
        conn.execute(text(sql), params or {})


def read_sql(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


def bulk_insert_dataframe(
    df: pd.DataFrame,
    table_name: str,
    if_exists: str = "append",
    chunksize: int = 5000,
) -> int:
    engine = get_engine()
    rows = len(df)
    df.to_sql(table_name, engine, if_exists=if_exists, index=False, chunksize=chunksize)
    logger.info("Inserted %d rows into %s", rows, table_name)
    return rows


def truncate_tables(tables: Iterable[str]) -> None:
    with get_connection() as conn:
        for table in tables:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    logger.info("Truncated tables: %s", list(tables))


def log_etl_audit(
    pipeline_name: str,
    stage: str,
    records_processed: int,
    records_failed: int,
    status: str,
    started_at,
    completed_at,
    error_message: str | None = None,
) -> None:
    duration = (completed_at - started_at).total_seconds()
    sql = """
        INSERT INTO etl_audit_log
        (pipeline_name, stage, records_processed, records_failed, status,
         error_message, started_at, completed_at, duration_seconds)
        VALUES
        (:pipeline_name, :stage, :records_processed, :records_failed, :status,
         :error_message, :started_at, :completed_at, :duration_seconds)
    """
    try:
        execute_sql(
            sql,
            {
                "pipeline_name": pipeline_name,
                "stage": stage,
                "records_processed": records_processed,
                "records_failed": records_failed,
                "status": status,
                "error_message": error_message,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_seconds": duration,
            },
        )
    except Exception as exc:
        logger.debug("ETL audit log skipped (database unavailable): %s", exc)
