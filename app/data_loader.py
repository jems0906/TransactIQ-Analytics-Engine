from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = [
    "transaction_id",
    "timestamp",
    "merchant_id",
    "cardholder_id",
    "amount",
    "currency",
    "status",
    "merchant_category",
    "country",
    "channel",
    "is_chargeback",
]


def validate_schema(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def load_transactions_from_csv(file_path_or_buffer) -> pd.DataFrame:
    df = pd.read_csv(file_path_or_buffer)
    validate_schema(df)

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["is_chargeback"] = df["is_chargeback"].astype(int)

    clean_df = df.dropna(subset=["timestamp", "amount"]).copy()
    clean_df["status"] = clean_df["status"].str.lower()
    clean_df["merchant_category"] = clean_df["merchant_category"].str.lower()
    clean_df["channel"] = clean_df["channel"].str.lower()
    return clean_df
