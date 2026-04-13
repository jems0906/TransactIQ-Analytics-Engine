from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application configuration loaded from environment variables."""

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    local_db_path: str = os.getenv("LOCAL_DB_PATH", "data/transactiq.db")
    mysql_uri: str = os.getenv("MYSQL_URI", "")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_s3_bucket: str = os.getenv("AWS_S3_BUCKET", "")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    api_key: str = os.getenv("TRANSACTIQ_API_KEY", "")
    admin_api_key: str = os.getenv("TRANSACTIQ_ADMIN_API_KEY", "")
    model_dir: str = os.getenv("MODEL_DIR", "data/models")
    retrain_interval_minutes: int = int(os.getenv("RETRAIN_INTERVAL_MINUTES", "0"))


settings = Settings()
