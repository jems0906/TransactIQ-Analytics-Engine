from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
import sqlite3

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings


class StorageManager:
    """Handles local, MySQL, and optional S3 persistence for uploaded data."""

    def __init__(self) -> None:
        self.local_db_path = settings.local_db_path
        self.mysql_engine = create_engine(settings.mysql_uri) if settings.mysql_uri else None
        self._ensure_metadata_tables()

    def _ensure_metadata_tables(self) -> None:
        Path(self.local_db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.local_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_retraining_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trained_at_utc TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    row_count INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    method TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    key_type TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_transactions(self, transactions: pd.DataFrame, table_name: str = "transactions") -> dict:
        result = {"local": False, "mysql": False}

        Path(self.local_db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.local_db_path) as conn:
            transactions.to_sql(table_name, conn, if_exists="replace", index=False)
        result["local"] = True

        if self.mysql_engine is not None:
            try:
                transactions.to_sql(table_name, self.mysql_engine, if_exists="replace", index=False)
                result["mysql"] = True
            except SQLAlchemyError:
                result["mysql"] = False

        return result

    def load_transactions(self, table_name: str = "transactions") -> pd.DataFrame:
        query = f"SELECT * FROM {table_name}"
        with sqlite3.connect(self.local_db_path) as conn:
            return pd.read_sql(query, conn)

    def log_retraining_event(self, model_version: str, row_count: int) -> None:
        trained_at_utc = datetime.now(UTC).isoformat(timespec="seconds")
        with sqlite3.connect(self.local_db_path) as conn:
            conn.execute(
                """
                INSERT INTO model_retraining_events (trained_at_utc, model_version, row_count)
                VALUES (?, ?, ?)
                """,
                (trained_at_utc, model_version, int(row_count)),
            )
            conn.commit()

    def log_audit_event(
        self,
        request_id: str,
        timestamp_utc: str,
        method: str,
        endpoint: str,
        status_code: int,
        latency_ms: int,
        key_type: str,
    ) -> None:
        with sqlite3.connect(self.local_db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (request_id, timestamp_utc, method, endpoint, status_code, latency_ms, key_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, timestamp_utc, method, endpoint, int(status_code), int(latency_ms), key_type),
            )
            conn.commit()

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.local_db_path) as conn:
            rows = conn.execute(
                """
                SELECT request_id, timestamp_utc, method, endpoint, status_code, latency_ms, key_type
                FROM audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        return [
            {
                "request_id": r[0],
                "timestamp_utc": r[1],
                "method": r[2],
                "endpoint": r[3],
                "status_code": r[4],
                "latency_ms": r[5],
                "key_type": r[6],
            }
            for r in rows
        ]

    def get_latest_retraining_event(self) -> dict | None:
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.execute(
                """
                SELECT trained_at_utc, model_version, row_count
                FROM model_retraining_events
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return {"trained_at_utc": row[0], "model_version": row[1], "row_count": int(row[2])}

    def upload_to_s3(self, transactions: pd.DataFrame, object_key: str) -> bool:
        if not settings.aws_s3_bucket:
            return False

        import boto3  # lazy import — only needed when S3 is configured

        csv_buffer = StringIO()
        transactions.to_csv(csv_buffer, index=False)
        try:
            client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id or None,
                aws_secret_access_key=settings.aws_secret_access_key or None,
            )
            client.put_object(Bucket=settings.aws_s3_bucket, Key=object_key, Body=csv_buffer.getvalue())
            return True
        except Exception:
            return False
