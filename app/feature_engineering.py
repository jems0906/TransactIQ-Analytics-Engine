from __future__ import annotations

import numpy as np
import pandas as pd


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["day_of_week"] = out["timestamp"].dt.dayofweek
    out["hour"] = out["timestamp"].dt.hour
    out["month"] = out["timestamp"].dt.month
    out["is_approved"] = (out["status"] == "approved").astype(int)
    return out


def merchant_features(df: pd.DataFrame) -> pd.DataFrame:
    latest_ts = df["timestamp"].max()
    grouped = df.groupby("merchant_id").agg(
        tx_count=("transaction_id", "count"),
        avg_amount=("amount", "mean"),
        max_amount=("amount", "max"),
        decline_rate=("is_approved", lambda s: 1.0 - s.mean()),
        chargeback_rate=("is_chargeback", "mean"),
        active_days=("timestamp", lambda s: s.dt.date.nunique()),
        last_seen=("timestamp", "max"),
    )
    grouped["recency_days"] = (latest_ts - grouped["last_seen"]).dt.days

    grouped["churn_label"] = (
        (grouped["recency_days"] > 20)
        | (grouped["decline_rate"] > 0.25)
        | (grouped["tx_count"] < 12)
    ).astype(int)
    return grouped.drop(columns=["last_seen"]).reset_index()


def cardholder_spending_profile(df: pd.DataFrame) -> pd.DataFrame:
    pivot = (
        df.pivot_table(
            index="cardholder_id",
            columns="merchant_category",
            values="amount",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .copy()
    )
    category_cols = [c for c in pivot.columns if c != "cardholder_id"]
    pivot["dominant_category"] = pivot[category_cols].idxmax(axis=1)
    pivot["total_spend"] = pivot[category_cols].sum(axis=1)

    q1 = pivot["total_spend"].quantile(0.33)
    q2 = pivot["total_spend"].quantile(0.66)

    def label_spend(v: float) -> str:
        if v <= q1:
            return "low_spend"
        if v <= q2:
            return "mid_spend"
        return "high_spend"

    pivot["spending_tier"] = pivot["total_spend"].apply(label_spend)
    return pivot[["cardholder_id", "dominant_category", "spending_tier", "total_spend"]]


def transaction_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    merchant_avg = out.groupby("merchant_id")["amount"].transform("mean")
    merchant_std = out.groupby("merchant_id")["amount"].transform("std").replace(0, np.nan)
    out["amount_zscore"] = ((out["amount"] - merchant_avg) / merchant_std).fillna(0)
    out["is_declined"] = (out["status"] != "approved").astype(int)
    return out
