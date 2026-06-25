from datetime import datetime
import base64
import hashlib
import hmac
import random

from fastapi import APIRouter, Depends, Header, HTTPException, Query
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

SUPPORTED_PLATFORMS = ["x", "facebook", "whatsapp", "instagram", "telegram", "tiktok"]
SCAN_TEMPLATES = [
    "Election update says results are fake news across districts.",
    "Community jobs program is improving local businesses and trust.",
    "Threat rumors are spreading in groups tonight, verify before sharing.",
    "Public health response is effective and hospitals report progress.",
    "Unverified claim says ballots were switched in central constituency.",
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
def ingest_x_webhook(
    payload: dict,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_platform_secret(x_webhook_secret, settings.x_webhook_secret, "x")
    mention = {
        "platform": "x",
        "author_handle": payload.get("author_handle", "@unknown"),
        "author_name": payload.get("author_name", ""),
        "followers": int(payload.get("followers", 0)),
        "engagement_rate": float(payload.get("engagement_rate", 0)),
        "constituency": payload.get("constituency", "default"),
        "content": payload.get("content", ""),
        "posted_at": datetime.utcnow().isoformat(),
    }
    job = enqueue_job(db, "mention_ingest", mention)
    return {"ok": True, "queued_job_id": job.id}


@router.get("/x/webhook")
def verify_x_webhook_crc(crc_token: str = Query(...)):
    """
    X webhook CRC check endpoint.
    X sends a GET with ?crc_token=... and expects:
    {"response_token":"sha256=<base64_hmac_sha256>"}
    """
    if not settings.x_webhook_secret:
        raise HTTPException(status_code=503, detail="X_WEBHOOK_SECRET not configured")
    digest = hmac.new(
        settings.x_webhook_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    response_token = "sha256=" + base64.b64encode(digest).decode("utf-8")
    return {"response_token": response_token}


@router.post("/facebook/webhook")
def ingest_facebook_webhook(
    payload: dict,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_platform_secret(x_webhook_secret, settings.facebook_webhook_secret, "facebook")
    mention = {
        "platform": "facebook",
        "author_handle": payload.get("author_handle", "@unknown"),
        "author_name": payload.get("author_name", ""),
        "followers": int(payload.get("followers", 0)),
        "engagement_rate": float(payload.get("engagement_rate", 0)),
        "constituency": payload.get("constituency", "default"),
        "content": payload.get("content", ""),
        "posted_at": datetime.utcnow().isoformat(),
    }
    job = enqueue_job(db, "mention_ingest", mention)
    return {"ok": True, "queued_job_id": job.id}


@router.post("/whatsapp/webhook")
def ingest_whatsapp_webhook(
    payload: dict,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_platform_secret(x_webhook_secret, settings.whatsapp_webhook_secret, "whatsapp")
    mention = {
        "platform": "whatsapp",
        "author_handle": payload.get("author_handle", "@unknown"),
        "author_name": payload.get("author_name", ""),
        "followers": int(payload.get("followers", 0)),
        "engagement_rate": float(payload.get("engagement_rate", 0)),
        "constituency": payload.get("constituency", "default"),
        "content": payload.get("content", ""),
        "posted_at": datetime.utcnow().isoformat(),
    }
    job = enqueue_job(db, "mention_ingest", mention)
    return {"ok": True, "queued_job_id": job.id}
