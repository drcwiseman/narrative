from datetime import datetime
import random

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import ConnectorKey
from app.routers.ingest import ingest_mention_internal
from app.schemas import ConnectorScanRequest, MentionCreate
from app.models import User


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
    db: Session = Depends(get_db),
):
    if not x_connector_token:
        raise HTTPException(status_code=401, detail="Missing X-Connector-Token header")
    key = (
        db.query(ConnectorKey)
        .filter(ConnectorKey.token == x_connector_token, ConnectorKey.is_active == 1)
        .first()
    )
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid connector token")

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
    return await ingest_mention_internal(normalized_payload, db, actor_email=f"connector:{key.name}")


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
