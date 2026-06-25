import requests

from app.config import settings


def send_slack_notification(payload: dict) -> dict:
    if not settings.slack_webhook_url:
        return {"ok": False, "skipped": True, "reason": "SLACK_WEBHOOK_URL not configured"}
    try:
        response = requests.post(settings.slack_webhook_url, json={"text": str(payload)}, timeout=5)
        return {"ok": response.ok, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def send_crm_update(payload: dict) -> dict:
    if not settings.crm_webhook_url:
        return {"ok": False, "skipped": True, "reason": "CRM_WEBHOOK_URL not configured"}
    try:
        response = requests.post(settings.crm_webhook_url, json=payload, timeout=5)
        return {"ok": response.ok, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}
