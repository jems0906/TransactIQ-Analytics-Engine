from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split


@dataclass
class ChurnModelArtifacts:
    model: RandomForestClassifier
    feature_columns: list[str]


class ChurnRiskModel:
    def __init__(self) -> None:
        self.artifacts: ChurnModelArtifacts | None = None

    def fit(self, merchant_df: pd.DataFrame) -> None:
        feature_cols = [
            "tx_count",
            "avg_amount",
            "max_amount",
            "decline_rate",
            "chargeback_rate",
            "active_days",
            "recency_days",
        ]
        train_df = merchant_df.copy()
        X = train_df[feature_cols]
        y = train_df["churn_label"]

        if y.nunique() < 2:
            y = (X["decline_rate"] > 0.2).astype(int)

        class_counts = y.value_counts()
        can_stratify = y.nunique() >= 2 and int(class_counts.min()) >= 2

        if can_stratify and len(X) >= 10:
            X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            model = RandomForestClassifier(n_estimators=250, random_state=42)
            model.fit(X_train, y_train)
        else:
            model = RandomForestClassifier(n_estimators=50, random_state=42)
            model.fit(X, y)

        self.artifacts = ChurnModelArtifacts(model=model, feature_columns=feature_cols)

    def save(self, model_path: str) -> None:
        if self.artifacts is None:
            raise RuntimeError("Churn model must be trained before saving.")

        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.artifacts, path)

    def load(self, model_path: str) -> bool:
        path = Path(model_path)
        if not path.exists():
            return False

        artifacts = joblib.load(path)
        if not isinstance(artifacts, ChurnModelArtifacts):
            return False
        self.artifacts = artifacts
        return True

    def predict_risk(self, merchant_df: pd.DataFrame) -> pd.DataFrame:
        if self.artifacts is None:
            raise RuntimeError("Churn model must be trained before prediction.")

        features = merchant_df[self.artifacts.feature_columns]
        probs = self.artifacts.model.predict_proba(features)[:, 1]

        result = merchant_df.copy()
        result["churn_risk_score"] = probs
        result["risk_bucket"] = pd.cut(
            result["churn_risk_score"],
            bins=[-0.01, 0.35, 0.7, 1.0],
            labels=["low", "medium", "high"],
        ).astype(str)
        return result


class AnomalyDetector:
    def __init__(self, contamination: float = 0.03) -> None:
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.feature_cols = ["amount", "amount_zscore", "hour", "is_declined"]
        self._is_trained = False

    def fit(self, tx_df: pd.DataFrame) -> None:
        features = tx_df[self.feature_cols]
        self.model.fit(features)
        self._is_trained = True

    def predict(self, tx_df: pd.DataFrame) -> pd.DataFrame:
        if not self._is_trained:
            raise RuntimeError("Anomaly model must be trained before prediction.")

        out = tx_df.copy()
        features = out[self.feature_cols]
        preds = self.model.predict(features)
        out["anomaly_flag"] = (preds == -1).astype(int)
        out["anomaly_reason"] = out.apply(_build_anomaly_reason, axis=1)
        return out

    def fit_predict(self, tx_df: pd.DataFrame) -> pd.DataFrame:
        self.fit(tx_df)
        return self.predict(tx_df)

    def save(self, model_path: str) -> None:
        if not self._is_trained:
            raise RuntimeError("Anomaly model must be trained before saving.")

        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"model": self.model, "feature_cols": self.feature_cols, "is_trained": self._is_trained}
        joblib.dump(payload, path)

    def load(self, model_path: str) -> bool:
        path = Path(model_path)
        if not path.exists():
            return False

        payload = joblib.load(path)
        if not isinstance(payload, dict) or "model" not in payload:
            return False

        self.model = payload["model"]
        self.feature_cols = payload.get("feature_cols", self.feature_cols)
        self._is_trained = bool(payload.get("is_trained", True))
        return True


def _build_anomaly_reason(row: pd.Series) -> str:
    reasons = []
    if row.get("amount_zscore", 0) > 2.5:
        reasons.append("transaction amount is unusually high for this merchant")
    if row.get("is_declined", 0) == 1:
        reasons.append("transaction was declined")
    if row.get("hour", 12) in {0, 1, 2, 3, 4, 5}:
        reasons.append("occurred in atypical off-hours")
    if not reasons:
        reasons.append("combined behavior deviates from historical baseline")
    return "; ".join(reasons)
