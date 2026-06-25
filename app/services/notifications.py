from sqlalchemy.orm import Session
import requests
import time

from app.config import settings
from app.models import AlertEndpoint
from app.observability import METRICS
from app.security import sign_webhook_payload
from app.services.integrations import send_slack_notification


def dispatch_harmful_alerts(db: Session, payload: dict) -> list[dict]:
    score = float(payload.get("harmful_claim_score") or 0.0)
    endpoints = db.query(AlertEndpoint).filter(AlertEndpoint.is_active == 1).all()
    results: list[dict] = []
    if score >= settings.slack_alert_threshold:
        slack_result = send_slack_notification(payload)
        results.append({"endpoint": "slack", **slack_result})
    for endpoint in endpoints:
        if score < endpoint.min_harmful_score:
            continue
        signature = sign_webhook_payload(payload)
        attempts = 0
        last_error = ""
        status_code = 0
        ok = False
        while attempts < 3 and not ok:
            attempts += 1
            try:
                response = requests.post(
                    endpoint.url,
                    json=payload,
                    timeout=settings.webhook_timeout_seconds,
                    headers={"X-Signature": signature, "X-Attempt": str(attempts)},
                )
                status_code = response.status_code
                ok = response.ok
                if not ok:
                    last_error = response.text[:200]
            except requests.RequestException as exc:
                last_error = str(exc)
            if not ok and attempts < 3:
                time.sleep(0.2 * attempts)
        results.append(
            {
                "endpoint": endpoint.name,
                "status_code": status_code,
                "ok": ok,
                "attempts": attempts,
                "error": last_error if not ok else "",
            }
        )
        if ok:
            METRICS["alerts_dispatched"] += 1
    return results
