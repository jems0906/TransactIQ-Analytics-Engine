from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")

st.set_page_config(page_title="TransactIQ Analytics Engine", page_icon="TIQ", layout="wide")
st.title("TransactIQ Analytics Engine")
st.caption("Upload transactions, score churn risk, detect anomalies, and ask natural-language questions.")

uploaded_file = st.file_uploader("Upload transaction CSV", type=["csv"])

col_a, col_b = st.columns([2, 1])
with col_a:
    query = st.text_input("Ask a question", value="Show me high-risk merchants")
with col_b:
    ask_btn = st.button("Run Query", use_container_width=True)

if uploaded_file is not None:
    with st.spinner("Processing uploaded data..."):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
        upload_res = requests.post(f"{API_BASE_URL}/api/upload", files=files, timeout=90)

    if upload_res.ok:
        payload = upload_res.json()
        st.success(payload.get("message", "Processed"))

        kpi = payload["kpis"]
        kpi_cols = st.columns(5)
        kpi_cols[0].metric("Approval Rate", f"{kpi['approval_rate']:.1%}")
        kpi_cols[1].metric("Decline Rate", f"{kpi['decline_rate']:.1%}")
        kpi_cols[2].metric("Avg Ticket", f"${kpi['avg_ticket_size']:,.2f}")
        kpi_cols[3].metric("Total Volume", f"${kpi['total_volume']:,.0f}")
        kpi_cols[4].metric("Anomalies", f"{payload['anomaly_count']}")

        st.subheader("High-Risk Merchants")
        hr = pd.DataFrame(payload["high_risk_merchants"])
        st.dataframe(hr, use_container_width=True)

        if not hr.empty:
            fig = px.bar(
                hr,
                x="merchant_id",
                y="churn_risk_score",
                color="risk_bucket",
                title="Top High-Risk Merchants",
                text_auto=".2f",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top Anomalies")
        anomaly_res = requests.get(f"{API_BASE_URL}/api/anomalies", timeout=30)
        if anomaly_res.ok:
            anomalies = pd.DataFrame(anomaly_res.json())
            st.dataframe(anomalies.head(30), use_container_width=True)

        if ask_btn and query.strip():
            with st.spinner("Generating answer..."):
                q_res = requests.post(
                    f"{API_BASE_URL}/api/query",
                    json={"question": query},
                    timeout=60,
                )
            if q_res.ok:
                st.subheader("Insight")
                st.write(q_res.json().get("answer", "No answer available."))
            else:
                st.error(f"Query failed: {q_res.text}")

    else:
        st.error(f"Upload failed: {upload_res.text}")
else:
    sample_path = Path("data/sample_transactions.csv")
    if sample_path.exists():
        st.info("No file uploaded yet. You can use data/sample_transactions.csv for a quick demo.")
