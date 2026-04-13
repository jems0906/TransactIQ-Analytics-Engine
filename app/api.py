from __future__ import annotations

from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

from app.audit import register_audit_hooks
from app.config import settings
from app.engine import TransactIQEngine


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB upload limit
engine = TransactIQEngine()
register_audit_hooks(app, lambda: engine.storage)


def require_api_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not settings.api_key:
            return func(*args, **kwargs)

        header_key = request.headers.get("X-API-Key", "")
        if header_key != settings.api_key:
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)

    return wrapper


def require_admin_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        expected_admin_key = settings.admin_api_key or settings.api_key
        if not expected_admin_key:
            return func(*args, **kwargs)

        header_key = request.headers.get("X-API-Key", "")
        if header_key != expected_admin_key:
            return jsonify({"error": "Admin authorization required"}), 401
        return func(*args, **kwargs)

    return wrapper


@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "service": "TransactIQ Analytics Engine"})


@app.post("/api/upload")
@require_api_key
def upload_transactions():
    if "file" not in request.files:
        return jsonify({"error": "Missing file in request."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename."}), 400

    filename = secure_filename(file.filename)
    result = engine.ingest_csv_bytes(file.read(), filename=filename)

    return jsonify(
        {
            "message": "File processed successfully.",
            "kpis": result.kpis,
            "high_risk_merchants": result.high_risk_merchants.to_dict(orient="records"),
            "anomaly_count": int(len(result.anomalies)),
        }
    )


@app.get("/api/kpis")
@require_api_key
def get_kpis():
    if engine.last_result is None:
        return jsonify({"error": "No analysis available. Upload data first."}), 400
    return jsonify(engine.last_result.kpis)


@app.get("/api/high-risk-merchants")
@require_api_key
def get_high_risk_merchants():
    if engine.last_result is None:
        return jsonify({"error": "No analysis available. Upload data first."}), 400
    return jsonify(engine.last_result.high_risk_merchants.to_dict(orient="records"))


@app.get("/api/anomalies")
@require_api_key
def get_anomalies():
    if engine.last_result is None:
        return jsonify({"error": "No analysis available. Upload data first."}), 400
    subset = engine.last_result.anomalies[
        ["transaction_id", "merchant_id", "cardholder_id", "amount", "anomaly_reason"]
    ]
    return jsonify(subset.head(200).to_dict(orient="records"))


@app.post("/api/query")
@require_api_key
def query_insights():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    answer = engine.query(question)
    return jsonify({"question": question, "answer": answer})


@app.get("/api/admin/model-status")
@require_admin_key
def model_status():
    return jsonify(engine.model_status())


@app.post("/api/admin/retrain")
@require_admin_key
def retrain_models():
    try:
        result = engine.retrain_from_local_data()
    except Exception as exc:
        return jsonify({"error": f"Retraining failed: {exc}"}), 500

    return jsonify(
        {
            "message": "Retraining complete.",
            "kpis": result.kpis,
            "high_risk_merchants": result.high_risk_merchants.to_dict(orient="records"),
            "anomaly_count": int(len(result.anomalies)),
        }
    )


@app.get("/api/admin/audit-log")
@require_admin_key
def audit_log():
    try:
        limit = int(request.args.get("limit", 100))
        limit = max(1, min(limit, 1000))
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer."}), 400

    events = engine.storage.get_audit_log(limit=limit)
    return jsonify({"count": len(events), "events": events})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
