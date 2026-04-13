from __future__ import annotations

import pandas as pd


def compute_kpis(df: pd.DataFrame) -> dict:
    approved = (df["status"] == "approved").sum()
    total = len(df)
    declined = total - approved
    return {
        "total_transactions": int(total),
        "total_volume": float(df["amount"].sum()),
        "approval_rate": float(approved / total) if total else 0.0,
        "decline_rate": float(declined / total) if total else 0.0,
        "avg_ticket_size": float(df["amount"].mean()) if total else 0.0,
        "chargeback_rate": float(df["is_chargeback"].mean()) if total else 0.0,
    }


def high_risk_merchants(churn_df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    ranked = churn_df.sort_values("churn_risk_score", ascending=False).head(top_n).copy()
    ranked["risk_explanation"] = ranked.apply(_explain_risk, axis=1)
    return ranked[
        [
            "merchant_id",
            "churn_risk_score",
            "risk_bucket",
            "decline_rate",
            "chargeback_rate",
            "recency_days",
            "risk_explanation",
        ]
    ]


def _explain_risk(row: pd.Series) -> str:
    signals = []
    if row["decline_rate"] > 0.2:
        signals.append("high decline ratio")
    if row["chargeback_rate"] > 0.08:
        signals.append("elevated chargeback frequency")
    if row["recency_days"] > 20:
        signals.append("inactive for long period")
    if not signals:
        signals.append("risk model confidence from aggregate behavior")
    return " | ".join(signals)
