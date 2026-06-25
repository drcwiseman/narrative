import base64
import hashlib
import hmac
import random
import time
from datetime import datetime
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_roles
from app.models import ConnectorKey, IdempotencyRecord
from app.routers.ingest import ingest_mention_internal
from app.services.queue import enqueue_job
from app.schemas import ConnectorScanRequest, MentionCreate
from app.models import User
from app.security import verify_connector_token


router = APIRouter(prefix="/api/connectors", tags=["connectors"])

SUPPORTED_PLATFORMS = ["x", "facebook", "whatsapp", "slack", "instagram", "telegram", "tiktok"]
SCAN_TEMPLATES = [
    "Election update says results are fake news across districts.",
    "Community jobs program is improving local businesses and trust.",
    "Threat rumors are spreading in groups tonight, verify before sharing.",
    "Public health response is effective and hospitals report progress.",
    "Unverified claim says ballots were switched in central constituency.",
]


def _hmac_sha256_base64(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _hmac_sha256_hex(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _resolve_header(headers: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = headers.get(name)
        if value:
            return value
    return None


def _verify_x_request_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not settings.x_webhook_secret or not signature_header:
        return False
    expected = "sha256=" + _hmac_sha256_base64(settings.x_webhook_secret, raw_body)
    return hmac.compare_digest(signature_header, expected)


def _verify_meta_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret or not signature_header:
        return False
    expected = "sha256=" + _hmac_sha256_hex(secret, raw_body)
    return hmac.compare_digest(signature_header, expected)


def _verify_slack_signature(
    raw_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
) -> bool:
    if not settings.slack_signing_secret or not signature_header or not timestamp_header:
        return False
    try:
        timestamp = int(timestamp_header)
    except ValueError:
        return False
    # Slack recommends rejecting requests older than 5 minutes.
    if abs(int(time.time()) - timestamp) > 300:
        return False
    signature_base = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
    expected = "v0=" + _hmac_sha256_hex(settings.slack_signing_secret, signature_base.encode("utf-8"))
    return hmac.compare_digest(signature_header, expected)


def _parse_x_mentions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    tweet_events = payload.get("tweet_create_events")
    if isinstance(tweet_events, list):
        for event in tweet_events:
            user = event.get("user") if isinstance(event, dict) else {}
            parsed.append(
                {
                    "platform": "x",
                    "author_handle": f"@{(user or {}).get('screen_name', 'unknown')}",
                    "author_name": (user or {}).get("name", ""),
                    "followers": int((user or {}).get("followers_count", 0) or 0),
                    "engagement_rate": 0.0,
                    "constituency": "default",
                    "content": event.get("text", "") if isinstance(event, dict) else "",
                    "posted_at": datetime.utcnow().isoformat(),
                }
            )
    elif isinstance(payload, dict):
        parsed.append(
            {
                "platform": "x",
                "author_handle": payload.get("author_handle", "@unknown"),
                "author_name": payload.get("author_name", ""),
                "followers": int(payload.get("followers", 0) or 0),
                "engagement_rate": float(payload.get("engagement_rate", 0) or 0),
                "constituency": payload.get("constituency", "default"),
                "content": payload.get("content", ""),
                "posted_at": datetime.utcnow().isoformat(),
            }
        )
    return [row for row in parsed if row.get("content")]


def _parse_facebook_mentions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return parsed
    for entry in entries:
        for change in (entry.get("changes", []) if isinstance(entry, dict) else []):
            value = change.get("value", {}) if isinstance(change, dict) else {}
            message = value.get("message") or value.get("text") or ""
            actor = value.get("from", {}) if isinstance(value.get("from"), dict) else {}
            if message:
                parsed.append(
                    {
                        "platform": "facebook",
                        "author_handle": f"@{actor.get('id', 'unknown')}",
                        "author_name": actor.get("name", ""),
                        "followers": 0,
                        "engagement_rate": 0.0,
                        "constituency": "default",
                        "content": message,
                        "posted_at": datetime.utcnow().isoformat(),
                    }
                )
    return parsed


def _parse_whatsapp_mentions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return parsed
    for entry in entries:
        for change in (entry.get("changes", []) if isinstance(entry, dict) else []):
            value = change.get("value", {}) if isinstance(change, dict) else {}
            for message in (value.get("messages", []) if isinstance(value, dict) else []):
                text = message.get("text", {}) if isinstance(message, dict) else {}
                content = text.get("body", "") if isinstance(text, dict) else ""
                if content:
                    parsed.append(
                        {
                            "platform": "whatsapp",
                            "author_handle": f"@{message.get('from', 'unknown')}",
                            "author_name": message.get("profile", {}).get("name", ""),
                            "followers": 0,
                            "engagement_rate": 0.0,
                            "constituency": "default",
                            "content": content,
                            "posted_at": datetime.utcnow().isoformat(),
                        }
                    )
    return parsed


def _parse_slack_mentions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    event = payload.get("event")
    if not isinstance(event, dict):
        return []
    if event.get("type") != "message":
        return []
    if event.get("subtype") == "bot_message":
        return []
    content = event.get("text", "")
    if not content:
        return []
    user_id = event.get("user", "unknown")
    return [
        {
            "platform": "slack",
            "author_handle": f"@{user_id}",
            "author_name": user_id,
            "followers": 0,
            "engagement_rate": 0.0,
            "constituency": "default",
            "content": content,
            "posted_at": datetime.utcnow().isoformat(),
        }
    ]


@router.post("/mentions")
async def ingest_from_connector(
    payload: MentionCreate,
    x_connector_token: str | None = Header(default=None),
    x_source_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_connector_token:
        raise HTTPException(status_code=401, detail={"code": "missing_connector_token", "retryable": False})
    keys = db.query(ConnectorKey).filter(ConnectorKey.is_active == 1).all()
    key = next((row for row in keys if verify_connector_token(x_connector_token, row.token)), None)
    if key is None:
        raise HTTPException(status_code=401, detail={"code": "invalid_connector_token", "retryable": False})

    if x_source_id:
        dedupe_key = f"connector:{key.name}:{x_source_id}"
        existing = db.query(IdempotencyRecord).filter(IdempotencyRecord.idempotency_key == dedupe_key).first()
        if existing:
            return {"ok": True, "deduped": True, "source_id": x_source_id}

    normalized_payload = MentionCreate(
        platform=payload.platform or key.platform,
        author_handle=payload.author_handle,
        author_name=payload.author_name,
        followers=payload.followers,
        engagement_rate=payload.engagement_rate,
        constituency=payload.constituency,
        content=payload.content,
        posted_at=payload.posted_at or datetime.utcnow(),
    )
    result = await ingest_mention_internal(normalized_payload, db, actor_email=f"connector:{key.name}")
    if x_source_id:
        dedupe_key = f"connector:{key.name}:{x_source_id}"
        db.add(
            IdempotencyRecord(
                idempotency_key=dedupe_key,
                endpoint="/api/connectors/mentions",
                response_json=str(result),
                status_code=200,
            )
        )
        db.commit()
    return result


@router.get("/platforms")
def list_supported_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


@router.get("/accounts")
def list_connected_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    keys = db.query(ConnectorKey).filter(ConnectorKey.is_active == 1).all()
    platform_key_counts: dict[str, int] = {}
    for row in keys:
        platform = (row.platform or "").lower()
        platform_key_counts[platform] = platform_key_counts.get(platform, 0) + 1

    accounts = [
        {
            "platform": "x",
            "connected": bool(settings.x_webhook_secret) and platform_key_counts.get("x", 0) > 0,
            "mode": "webhook+connector-key",
            "active_connector_keys": platform_key_counts.get("x", 0),
            "webhook_configured": bool(settings.x_webhook_secret),
        },
        {
            "platform": "facebook",
            "connected": bool(settings.facebook_webhook_secret) and bool(settings.facebook_webhook_verify_token),
            "mode": "webhook",
            "active_connector_keys": platform_key_counts.get("facebook", 0),
            "webhook_configured": bool(settings.facebook_webhook_secret),
        },
        {
            "platform": "whatsapp",
            "connected": bool(settings.whatsapp_webhook_secret) and bool(settings.whatsapp_webhook_verify_token),
            "mode": "webhook",
            "active_connector_keys": platform_key_counts.get("whatsapp", 0),
            "webhook_configured": bool(settings.whatsapp_webhook_secret),
        },
        {
            "platform": "slack",
            "connected": bool(settings.slack_signing_secret) and bool(settings.slack_webhook_url),
            "mode": "events+alerts",
            "active_connector_keys": platform_key_counts.get("slack", 0),
            "events_configured": bool(settings.slack_signing_secret),
            "alerts_configured": bool(settings.slack_webhook_url),
        },
        {
            "platform": "instagram",
            "connected": platform_key_counts.get("instagram", 0) > 0,
            "mode": "simulated/connector-key",
            "active_connector_keys": platform_key_counts.get("instagram", 0),
        },
        {
            "platform": "telegram",
            "connected": platform_key_counts.get("telegram", 0) > 0,
            "mode": "simulated/connector-key",
            "active_connector_keys": platform_key_counts.get("telegram", 0),
        },
        {
            "platform": "tiktok",
            "connected": platform_key_counts.get("tiktok", 0) > 0,
            "mode": "simulated/connector-key",
            "active_connector_keys": platform_key_counts.get("tiktok", 0),
        },
    ]
    return {"accounts": accounts}


@router.post("/scan-all")
async def scan_all_social_platforms(
    payload: ConnectorScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    target_platforms = [p.lower() for p in payload.platforms if p.lower() in SUPPORTED_PLATFORMS]
    if not target_platforms:
        raise HTTPException(status_code=400, detail="No supported platforms provided")

    created = []
    for platform in target_platforms:
        for i in range(payload.batch_size_per_platform):
            mention_payload = MentionCreate(
                platform=platform,
                author_handle=f"@{platform}_source_{random.randint(1000, 9999)}",
                author_name=f"{platform.title()} Source",
                followers=random.randint(200, 120000),
                engagement_rate=round(random.uniform(0.01, 0.2), 3),
                constituency=payload.constituency,
                content=random.choice(SCAN_TEMPLATES),
                posted_at=datetime.utcnow(),
            )
            result = await ingest_mention_internal(mention_payload, db, actor_email=current_user.email)
            created.append(result["mention_id"])

    return {
        "ok": True,
        "scanned_platforms": target_platforms,
        "mentions_created": len(created),
        "mention_ids": created,
    }


def _verify_platform_secret(secret: str | None, expected: str, platform: str) -> None:
    if not expected:
        raise HTTPException(status_code=503, detail=f"{platform} webhook secret not configured")
    if not secret or secret != expected:
        raise HTTPException(status_code=401, detail=f"Invalid {platform} webhook secret")


@router.post("/x/webhook")
async def ingest_x_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    signature_header = _resolve_header(headers, "x-twitter-webhooks-signature")
    fallback_secret = _resolve_header(headers, "x-webhook-secret")

    signature_ok = _verify_x_request_signature(raw_body, signature_header)
    if not signature_ok:
        _verify_platform_secret(fallback_secret, settings.x_webhook_secret, "x")

    payload = await request.json()
    mentions = _parse_x_mentions(payload)
    if not mentions:
        raise HTTPException(status_code=400, detail="No mention content found in X webhook payload")
    job_ids = [enqueue_job(db, "mention_ingest", mention).id for mention in mentions]
    return {"ok": True, "queued_jobs": len(job_ids), "queued_job_ids": job_ids}


@router.get("/x/webhook")
def verify_x_webhook_crc(crc_token: str = Query(...)):
    """
    X webhook CRC check endpoint.
    X sends a GET with ?crc_token=... and expects:
    {"response_token":"sha256=<base64_hmac_sha256>"}
    """
    if not settings.x_webhook_secret:
        raise HTTPException(status_code=503, detail="X_WEBHOOK_SECRET not configured")
    response_token = "sha256=" + _hmac_sha256_base64(settings.x_webhook_secret, crc_token.encode("utf-8"))
    return {"response_token": response_token}


@router.get("/facebook/webhook")
def verify_facebook_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    expected_token = settings.facebook_webhook_verify_token or settings.facebook_webhook_secret
    if not expected_token:
        raise HTTPException(status_code=503, detail="FACEBOOK_WEBHOOK_VERIFY_TOKEN not configured")
    if hub_mode != "subscribe" or hub_verify_token != expected_token:
        raise HTTPException(status_code=403, detail="Facebook webhook verification failed")
    return Response(content=unquote(hub_challenge), media_type="text/plain")


@router.post("/facebook/webhook")
async def ingest_facebook_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    signature_header = _resolve_header(headers, "x-hub-signature-256")
    fallback_secret = _resolve_header(headers, "x-webhook-secret", "x-facebook-webhook-secret")

    signature_ok = _verify_meta_signature(raw_body, signature_header, settings.facebook_webhook_secret)
    if not signature_ok:
        _verify_platform_secret(fallback_secret, settings.facebook_webhook_secret, "facebook")

    payload = await request.json()
    mentions = _parse_facebook_mentions(payload)
    if not mentions:
        mentions = _parse_x_mentions(payload)  # fallback for manual test payloads
    if not mentions:
        raise HTTPException(status_code=400, detail="No mention content found in Facebook webhook payload")
    job_ids = [enqueue_job(db, "mention_ingest", mention).id for mention in mentions]
    return {"ok": True, "queued_jobs": len(job_ids), "queued_job_ids": job_ids}


@router.get("/whatsapp/webhook")
def verify_whatsapp_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    expected_token = settings.whatsapp_webhook_verify_token or settings.whatsapp_webhook_secret
    if not expected_token:
        raise HTTPException(status_code=503, detail="WHATSAPP_WEBHOOK_VERIFY_TOKEN not configured")
    if hub_mode != "subscribe" or hub_verify_token != expected_token:
        raise HTTPException(status_code=403, detail="WhatsApp webhook verification failed")
    return Response(content=unquote(hub_challenge), media_type="text/plain")


@router.post("/whatsapp/webhook")
async def ingest_whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    signature_header = _resolve_header(headers, "x-hub-signature-256")
    fallback_secret = _resolve_header(headers, "x-webhook-secret", "x-whatsapp-webhook-secret")

    signature_ok = _verify_meta_signature(raw_body, signature_header, settings.whatsapp_webhook_secret)
    if not signature_ok:
        _verify_platform_secret(fallback_secret, settings.whatsapp_webhook_secret, "whatsapp")

    payload = await request.json()
    mentions = _parse_whatsapp_mentions(payload)
    if not mentions:
        mentions = _parse_x_mentions(payload)  # fallback for manual test payloads
    if not mentions:
        raise HTTPException(status_code=400, detail="No mention content found in WhatsApp webhook payload")
    job_ids = [enqueue_job(db, "mention_ingest", mention).id for mention in mentions]
    return {"ok": True, "queued_jobs": len(job_ids), "queued_job_ids": job_ids}


@router.post("/slack/events")
async def ingest_slack_events(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    slack_signature = _resolve_header(headers, "x-slack-signature")
    slack_timestamp = _resolve_header(headers, "x-slack-request-timestamp")
    fallback_secret = _resolve_header(headers, "x-webhook-secret", "x-slack-webhook-secret")

    signature_ok = _verify_slack_signature(raw_body, slack_signature, slack_timestamp)
    if not signature_ok:
        _verify_platform_secret(fallback_secret, settings.slack_signing_secret, "slack")

    payload = await request.json()
    if payload.get("type") == "url_verification":
        token = payload.get("token", "")
        if settings.slack_verification_token and token != settings.slack_verification_token:
            raise HTTPException(status_code=403, detail="Slack verification token mismatch")
        return {"challenge": payload.get("challenge", "")}

    mentions = _parse_slack_mentions(payload)
    if not mentions:
        return {"ok": True, "queued_jobs": 0, "reason": "No ingestible Slack message event"}
    job_ids = [enqueue_job(db, "mention_ingest", mention).id for mention in mentions]
    return {"ok": True, "queued_jobs": len(job_ids), "queued_job_ids": job_ids}
