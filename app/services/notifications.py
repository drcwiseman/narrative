from sqlalchemy.orm import Session
import requests

from app.config import settings
from app.models import AlertEndpoint


def dispatch_harmful_alerts(db: Session, payload: dict) -> list[dict]:
    score = float(payload.get("harmful_claim_score") or 0.0)
    endpoints = db.query(AlertEndpoint).filter(AlertEndpoint.is_active == 1).all()
    results: list[dict] = []
    for endpoint in endpoints:
        if score < endpoint.min_harmful_score:
            continue
        try:
            response = requests.post(endpoint.url, json=payload, timeout=settings.webhook_timeout_seconds)
            results.append(
                {
                    "endpoint": endpoint.name,
                    "status_code": response.status_code,
                    "ok": response.ok,
                }
            )
        except requests.RequestException as exc:
            results.append({"endpoint": endpoint.name, "ok": False, "error": str(exc)})
    return results
