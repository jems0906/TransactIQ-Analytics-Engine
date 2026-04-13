from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import settings


class LLMInsightAssistant:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def answer_query(self, question: str, context: dict[str, Any]) -> str:
        if self.client is None:
            return self._fallback_answer(question, context)

        prompt = (
            "You are a payments analytics assistant. "
            "Use the given JSON context to answer user questions with concise business insights."
        )
        user_content = (
            f"Question: {question}\n"
            f"Context JSON: {json.dumps(context, default=str)[:6000]}\n"
            "Answer with plain language and include likely root causes."
        )

        response = self.client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
        )
        return response.output_text.strip()

    def _fallback_answer(self, question: str, context: dict[str, Any]) -> str:
        q = question.lower()
        if "high-risk" in q or "high risk" in q or "merchant" in q:
            merchants = context.get("high_risk_merchants", [])
            if not merchants:
                return "No high-risk merchants found in current dataset."
            summary = [
                f"{m['merchant_id']} (risk={m['churn_risk_score']:.2f}) because {m['risk_explanation']}"
                for m in merchants[:3]
            ]
            return "Top high-risk merchants: " + "; ".join(summary)

        if "anomal" in q or "fraud" in q:
            count = context.get("anomaly_count", 0)
            return f"Detected {count} anomalous transactions. Review off-hour high-value declines first."

        if "kpi" in q or "approval" in q:
            kpis = context.get("kpis", {})
            return (
                f"Approval rate is {kpis.get('approval_rate', 0):.1%}, "
                f"average ticket size is ${kpis.get('avg_ticket_size', 0):,.2f}."
            )

        return "I can answer questions about KPIs, anomalies, and high-risk merchants once data is loaded."
