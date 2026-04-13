# TransactIQ Analytics Engine

TransactIQ is an AI-powered transaction analytics platform for payment intelligence use cases:

- Spending pattern categorization
- Churn risk prediction for merchants
- Anomaly detection for fraud and usage shifts
- KPI dashboards for approval rate and ticket size
- API integration endpoints for upstream systems
- Optional natural-language insights via OpenAI API
- Optional API-key authentication for endpoint security
- Persisted ML models and optional scheduled retraining

## Tech Stack

- Python: pandas, scikit-learn
- API: Flask
- Dashboard: Streamlit + Plotly
- Storage: SQLite (default), MySQL (optional), AWS S3 (optional)
- LLM: OpenAI API with local fallback answers

## Project Structure

- app/: analytics engine, models, API, storage
- dashboard/: Streamlit dashboard
- scripts/: mock data generator and container entrypoint
- data/: sample dataset (runtime DB/models are generated at run time)
- tests/: smoke tests

## Quick Start (Local)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set values in .env as needed for OpenAI, MySQL, and S3.

### Generate Demo Data

```bash
python scripts/generate_mock_data.py
```

This creates data/sample_transactions.csv and intentionally introduces three high-risk merchants.

### Run API

```bash
python run_api.py
```

The API runs at http://localhost:5000.
Set TRANSACTIQ_DEBUG=1 if you want Flask debug mode while using run_api.py.

### Run Dashboard

```bash
streamlit run dashboard/streamlit_app.py
```

Then open the dashboard URL from Streamlit output.

### Production API Command (No Flask Dev Server)

```bash
gunicorn --workers 2 --timeout 120 --bind 0.0.0.0:5000 app.api:app
```

## Quick Start (Docker)

```bash
docker compose up --build
```

- API: http://localhost:5000
- Dashboard: http://localhost:8501

### Deploying Docker Image To Render

- This project supports Render Docker deploys.
- The container now binds to `PORT` automatically (`${PORT:-5000}`).
- Use the repository root `Dockerfile` for the Web Service.
- Recommended environment variables on Render:
  - `LOCAL_DB_PATH=/var/data/transactiq.db`
  - `MODEL_DIR=/var/data/models`
  - `TRANSACTIQ_API_KEY` and `TRANSACTIQ_ADMIN_API_KEY`
  - `OPENAI_API_KEY` (optional)
- Attach a persistent disk at `/var/data` if you want DB/model persistence across deploys.

### Deploy To Render With Blueprint

1. Open this URL in your browser:
  - https://render.com/deploy?repo=https://github.com/jems0906/TransactIQ-Analytics-Engine
2. Render will detect `render.yaml` and preconfigure the `transactiq-api` Docker service.
3. Set secret environment variables in Render when prompted:
  - `TRANSACTIQ_API_KEY`
  - `TRANSACTIQ_ADMIN_API_KEY`
  - `OPENAI_API_KEY` (optional)
4. Click deploy.

## API Endpoints

- GET /health
- POST /api/upload
  - multipart form with file field named file
- GET /api/kpis
- GET /api/high-risk-merchants
- GET /api/anomalies
- POST /api/query
  - JSON body: {"question": "Show me high-risk merchants"}
- GET /api/admin/model-status
- POST /api/admin/retrain
- GET /api/admin/audit-log

If TRANSACTIQ_API_KEY is set, provide it as X-API-Key in every API request.
If TRANSACTIQ_ADMIN_API_KEY is set, only that key can call /api/admin/* endpoints.

## Model Persistence and Retraining

- Models are saved to MODEL_DIR (default: data/models).
- Uploading a dataset retrains and persists models.
- If RETRAIN_INTERVAL_MINUTES > 0, the engine runs background retraining from local stored data.
- You can trigger retraining manually via POST /api/admin/retrain.
- Each retrain writes a telemetry event (timestamp, model_version, row_count) to local metadata.

## Demo Flow

1. Generate mock data.
2. Start Flask API and Streamlit dashboard.
3. Upload data/sample_transactions.csv from the dashboard.
4. Ask: Show me high-risk merchants.
5. Expected: model flags 3 merchants and provides root-cause style explanations.

## Notes

- If OPENAI_API_KEY is not set, query answers fall back to deterministic local logic.
- SQLite is always enabled for local development.
- MySQL and S3 integrations are optional and non-blocking.
- Runtime artifacts such as data/*.db and *.joblib are generated locally and gitignored.

## Security Model

- TRANSACTIQ_API_KEY protects standard /api/* endpoints.
- TRANSACTIQ_ADMIN_API_KEY protects /api/admin/* endpoints.
- If admin key is not set, admin endpoints fall back to TRANSACTIQ_API_KEY.
