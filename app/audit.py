from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Callable

from flask import Flask, g, request


def _classify_key(provided_key: str, api_key: str, admin_api_key: str) -> str:
    if admin_api_key and provided_key == admin_api_key:
        return "admin"
    if api_key and provided_key == api_key:
        return "client"
    if not api_key and not admin_api_key:
        return "none"
    return "unauthenticated"


def register_audit_hooks(flask_app: Flask, get_storage: Callable) -> None:
    """Attach before/after request hooks that record one audit row per request."""

    @flask_app.before_request
    def _start_request():
        g.request_id = str(uuid.uuid4())
        g.request_start = time.monotonic()
        g.request_timestamp_utc = datetime.now(UTC).isoformat(timespec="seconds")

    @flask_app.after_request
    def _log_request(response):
        from app.config import settings

        latency_ms = int((time.monotonic() - g.request_start) * 1000)
        provided_key = request.headers.get("X-API-Key", "")
        key_type = _classify_key(provided_key, settings.api_key, settings.admin_api_key)

        try:
            storage = get_storage()
            storage.log_audit_event(
                request_id=g.request_id,
                timestamp_utc=g.request_timestamp_utc,
                method=request.method,
                endpoint=request.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
                key_type=key_type,
            )
        except Exception:
            pass

        response.headers["X-Request-Id"] = g.request_id
        return response
