from app.engine import TransactIQEngine
from scripts.generate_mock_data import generate_transactions


def test_analysis_pipeline_smoke():
    engine = TransactIQEngine()
    df = generate_transactions(n=500)
    payload = df.to_csv(index=False).encode("utf-8")

    result = engine.ingest_csv_bytes(payload, filename="test.csv")

    assert result.kpis["total_transactions"] == 500
    assert len(result.high_risk_merchants) == 3
    assert "risk_explanation" in result.high_risk_merchants.columns
    status = engine.model_status()
    assert status["churn_model_loaded"] is True
    assert status["model_version"].startswith("model_")
    assert status["latest_retraining_event"]["row_count"] == 500
