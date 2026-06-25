import requests

from app.config import settings


def _resolve_dashboard_url(payload: dict) -> str:
    base = (settings.app_base_url or "").rstrip("/")
    if not base:
        return ""
    mention_id = payload.get("mention_id")
    if mention_id:
        return f"{base}/?mention_id={mention_id}"
    campaign_id = payload.get("campaign_id")
    if campaign_id:
        return f"{base}/?campaign_id={campaign_id}"
    return f"{base}/"


def _alert_severity(payload: dict) -> str:
    harmful_score = float(payload.get("harmful_claim_score") or 0.0)
    if harmful_score >= settings.slack_critical_threshold:
        return "critical"
    if harmful_score >= settings.slack_alert_threshold:
        return "warning"
    return "info"


def _webhook_for_payload(payload: dict) -> str:
    severity = _alert_severity(payload)
    if severity == "critical" and settings.slack_critical_webhook_url:
        return settings.slack_critical_webhook_url
    return settings.slack_webhook_url


def _format_slack_message(payload: dict) -> dict:
    event = payload.get("event") or payload.get("type") or "system.event"
    severity = _alert_severity(payload)
    harmful_score = float(payload.get("harmful_claim_score") or 0.0)
    sentiment = payload.get("sentiment_score")
    topic = payload.get("topic") or "unknown"
    platform = payload.get("platform") or "unknown"
    constituency = payload.get("constituency") or "default"
    actor = payload.get("actor") or payload.get("actor_email") or "system"
    content = str(payload.get("content") or payload.get("message") or "").strip()
    mention_id = payload.get("mention_id")
    campaign_id = payload.get("campaign_id")
    dashboard_url = _resolve_dashboard_url(payload)

    icon = {"critical": ":rotating_light:", "warning": ":warning:", "info": ":information_source:"}.get(severity, ":information_source:")
    title = f"{icon} Narrative {severity.upper()} - {event}"
    lines = [
        f"*Platform:* `{platform}`",
        f"*Topic:* `{topic}`",
        f"*Constituency:* `{constituency}`",
        f"*Harmful Score:* `{harmful_score:.2f}`",
    ]
    if sentiment is not None:
        try:
            lines.append(f"*Sentiment:* `{float(sentiment):.2f}`")
        except (TypeError, ValueError):
            lines.append(f"*Sentiment:* `{sentiment}`")
    if mention_id:
        lines.append(f"*Mention ID:* `{mention_id}`")
    if campaign_id:
        lines.append(f"*Campaign ID:* `{campaign_id}`")
    lines.append(f"*Actor:* `{actor}`")

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
    ]
    if content:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Content preview:*\n>{content[:2800]}"},
            }
        )
    if dashboard_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open Narrative Dashboard"},
                        "url": dashboard_url,
                    }
                ],
            }
        )
    return {"text": title, "blocks": blocks}


def send_slack_notification(payload: dict) -> dict:
    webhook_url = _webhook_for_payload(payload)
    if not webhook_url:
        return {"ok": False, "skipped": True, "reason": "SLACK_WEBHOOK_URL not configured"}
    message = _format_slack_message(payload)
    try:
        response = requests.post(webhook_url, json=message, timeout=5)
        return {"ok": response.ok, "status_code": response.status_code, "severity": _alert_severity(payload)}
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
