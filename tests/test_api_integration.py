from __future__ import annotations

from io import BytesIO

from app import api as api_module
from app.engine import TransactIQEngine
from scripts.generate_mock_data import generate_transactions


def _csv_payload(n: int = 250) -> bytes:
    df = generate_transactions(n=n, seed=123)
    return df.to_csv(index=False).encode("utf-8")


def _reset_engine_for_tests(tmp_path, api_key: str = "", admin_key: str = ""):
    api_module.settings.local_db_path = str(tmp_path / "transactiq_test.db")
    api_module.settings.model_dir = str(tmp_path / "models")
    api_module.settings.retrain_interval_minutes = 0
    api_module.settings.api_key = api_key
    api_module.settings.admin_api_key = admin_key
    api_module.engine = TransactIQEngine()


def test_upload_and_query_flow(tmp_path):
    _reset_engine_for_tests(tmp_path)
    client = api_module.app.test_client()

    payload = _csv_payload()
    data = {"file": (BytesIO(payload), "sample.csv")}
    upload = client.post("/api/upload", data=data, content_type="multipart/form-data")

    assert upload.status_code == 200
    body = upload.get_json()
    assert body["kpis"]["total_transactions"] == 250
    assert len(body["high_risk_merchants"]) == 3

    query = client.post("/api/query", json={"question": "Show me high-risk merchants"})
    assert query.status_code == 200
    assert "answer" in query.get_json()


def test_api_key_required_when_configured(tmp_path):
    _reset_engine_for_tests(tmp_path, api_key="client-key")
    client = api_module.app.test_client()

    no_key = client.get("/api/kpis")
    assert no_key.status_code == 401

    with_key = client.get("/api/kpis", headers={"X-API-Key": "client-key"})
    assert with_key.status_code == 400


def test_admin_key_separate_from_client_key(tmp_path):
    _reset_engine_for_tests(tmp_path, api_key="client-key", admin_key="admin-key")
    client = api_module.app.test_client()

    payload = _csv_payload()
    upload = client.post(
        "/api/upload",
        data={"file": (BytesIO(payload), "sample.csv")},
        content_type="multipart/form-data",
        headers={"X-API-Key": "client-key"},
    )
    assert upload.status_code == 200

    blocked_admin = client.get("/api/admin/model-status", headers={"X-API-Key": "client-key"})
    assert blocked_admin.status_code == 401

    allowed_admin = client.get("/api/admin/model-status", headers={"X-API-Key": "admin-key"})
    assert allowed_admin.status_code == 200
    status_body = allowed_admin.get_json()
    assert status_body["latest_retraining_event"]["row_count"] == 250


def test_audit_log_records_requests(tmp_path):
    _reset_engine_for_tests(tmp_path, api_key="client-key", admin_key="admin-key")
    client = api_module.app.test_client()

    payload = _csv_payload()
    upload = client.post(
        "/api/upload",
        data={"file": (BytesIO(payload), "sample.csv")},
        content_type="multipart/form-data",
        headers={"X-API-Key": "client-key"},
    )
    assert upload.status_code == 200
    assert "X-Request-Id" in upload.headers

    audit = client.get("/api/admin/audit-log", headers={"X-API-Key": "admin-key"})
    assert audit.status_code == 200
    body = audit.get_json()
    assert body["count"] >= 1

    upload_event = next(
        (e for e in body["events"] if e["endpoint"] == "/api/upload"),
        None,
    )
    assert upload_event is not None
    assert upload_event["method"] == "POST"
    assert upload_event["status_code"] == 200
    assert upload_event["key_type"] == "client"
    assert upload_event["latency_ms"] >= 0
    assert len(upload_event["request_id"]) == 36
