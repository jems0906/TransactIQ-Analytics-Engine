from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import threading
from typing import Any

import pandas as pd

from app.config import settings
from app.data_loader import load_transactions_from_csv
from app.feature_engineering import (
    add_time_features,
    cardholder_spending_profile,
    merchant_features,
    transaction_anomaly_features,
)
from app.insights import compute_kpis, high_risk_merchants
from app.llm_assistant import LLMInsightAssistant
from app.ml_models import AnomalyDetector, ChurnRiskModel
from app.storage import StorageManager


@dataclass
class AnalysisResult:
    kpis: dict[str, Any]
    high_risk_merchants: pd.DataFrame
    anomalies: pd.DataFrame
    spending_profiles: pd.DataFrame


class TransactIQEngine:
    def __init__(self) -> None:
        self.storage = StorageManager()
        self.churn_model = ChurnRiskModel()
        self.anomaly_detector = AnomalyDetector()
        self.llm = LLMInsightAssistant()

        self.last_df: pd.DataFrame | None = None
        self.last_result: AnalysisResult | None = None

        model_dir = Path(settings.model_dir)
        self.churn_model_path = str(model_dir / "churn_model.joblib")
        self.anomaly_model_path = str(model_dir / "anomaly_model.joblib")

        self._retrain_thread: threading.Thread | None = None
        self._stop_retrain = threading.Event()
        self.model_version = "untrained"

        self._load_models()

        if settings.retrain_interval_minutes > 0:
            self.start_retraining_loop(settings.retrain_interval_minutes)

    def ingest_csv_bytes(self, payload: bytes, filename: str = "uploaded.csv") -> AnalysisResult:
        df = load_transactions_from_csv(BytesIO(payload))
        self.storage.save_transactions(df)
        self.storage.upload_to_s3(df, object_key=f"uploads/{filename}")

        result = self._analyze(df, retrain=True)
        self.last_df = df
        self.last_result = result
        return result

    def analyze_local_table(self) -> AnalysisResult:
        df = self.storage.load_transactions()
        result = self._analyze(df)
        self.last_df = df
        self.last_result = result
        return result

    def _analyze(self, df: pd.DataFrame, retrain: bool = False) -> AnalysisResult:
        tx = add_time_features(df)
        merchant_df = merchant_features(tx)
        if retrain or self.churn_model.artifacts is None:
            self.churn_model.fit(merchant_df)
            self.churn_model.save(self.churn_model_path)
        churn_scored = self.churn_model.predict_risk(merchant_df)

        anomaly_input = transaction_anomaly_features(tx)
        if retrain:
            anomalies = self.anomaly_detector.fit_predict(anomaly_input)
            self.anomaly_detector.save(self.anomaly_model_path)
        else:
            try:
                anomalies = self.anomaly_detector.predict(anomaly_input)
            except RuntimeError:
                anomalies = self.anomaly_detector.fit_predict(anomaly_input)
                self.anomaly_detector.save(self.anomaly_model_path)

        if retrain:
            self.model_version = self._new_model_version()
            self.storage.log_retraining_event(model_version=self.model_version, row_count=len(df))

        return AnalysisResult(
            kpis=compute_kpis(tx),
            high_risk_merchants=high_risk_merchants(churn_scored, top_n=3),
            anomalies=anomalies[anomalies["anomaly_flag"] == 1].copy(),
            spending_profiles=cardholder_spending_profile(tx),
        )

    def query(self, question: str) -> str:
        if self.last_result is None:
            return "No data loaded yet. Upload a CSV first."

        context = {
            "kpis": self.last_result.kpis,
            "high_risk_merchants": self.last_result.high_risk_merchants.to_dict(orient="records"),
            "anomaly_count": int(len(self.last_result.anomalies)),
            "sample_anomalies": self.last_result.anomalies.head(5).to_dict(orient="records"),
        }
        return self.llm.answer_query(question, context)

    def retrain_from_local_data(self) -> AnalysisResult:
        df = self.storage.load_transactions()
        result = self._analyze(df, retrain=True)
        self.last_df = df
        self.last_result = result
        return result

    def model_status(self) -> dict[str, Any]:
        churn_loaded = self.churn_model.artifacts is not None
        anomaly_loaded = getattr(self.anomaly_detector, "_is_trained", False)
        latest_event = self.storage.get_latest_retraining_event()
        return {
            "churn_model_loaded": bool(churn_loaded),
            "anomaly_model_loaded": bool(anomaly_loaded),
            "retraining_enabled": settings.retrain_interval_minutes > 0,
            "retrain_interval_minutes": settings.retrain_interval_minutes,
            "churn_model_path": self.churn_model_path,
            "anomaly_model_path": self.anomaly_model_path,
            "model_version": self.model_version,
            "latest_retraining_event": latest_event,
        }

    def start_retraining_loop(self, interval_minutes: int) -> None:
        if self._retrain_thread and self._retrain_thread.is_alive():
            return

        def _runner() -> None:
            while not self._stop_retrain.is_set():
                if self._stop_retrain.wait(timeout=interval_minutes * 60):
                    break
                try:
                    self.retrain_from_local_data()
                except Exception:
                    continue

        self._retrain_thread = threading.Thread(target=_runner, daemon=True)
        self._retrain_thread.start()

    def stop_retraining_loop(self) -> None:
        self._stop_retrain.set()

    def _load_models(self) -> None:
        churn_loaded = self.churn_model.load(self.churn_model_path)
        anomaly_loaded = self.anomaly_detector.load(self.anomaly_model_path)

        latest_event = self.storage.get_latest_retraining_event()
        if latest_event is not None:
            self.model_version = latest_event["model_version"]
        elif churn_loaded and anomaly_loaded:
            self.model_version = "loaded_legacy"

    def _new_model_version(self) -> str:
        return datetime.now(UTC).strftime("model_%Y%m%d%H%M%S")
