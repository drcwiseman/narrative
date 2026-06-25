from datetime import datetime

import json

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Analysis, IdempotencyRecord, Mention, User
from app.observability import METRICS
from app.schemas import MentionCreate
from app.services.analyzer import extract_topic, harmful_claim_score, score_sentiment
from app.services.audit import write_audit_log
from app.services.detection_rules import get_detection_rules
from app.services.kol import upsert_kol_from_mention
from app.services.notifications import dispatch_harmful_alerts
from app.services.stream import event_stream


router = APIRouter(prefix="/api/mentions", tags=["mentions"])


async def ingest_mention_internal(payload: MentionCreate, db: Session, actor_email: str = "system"):
    rules = get_detection_rules(db)
    mention = Mention(
        platform=payload.platform,
        author_handle=payload.author_handle,
        author_name=payload.author_name,
        followers=payload.followers,
        engagement_rate=payload.engagement_rate,
        constituency=payload.constituency,
        content=payload.content,
        posted_at=payload.posted_at or datetime.utcnow(),
    )
    db.add(mention)
    db.commit()
    db.refresh(mention)

    sentiment = score_sentiment(payload.content, negative_words=rules["negative_words"])
    topic = extract_topic(
        payload.content,
        topic_keywords={k: set(v) for k, v in rules["topic_keywords"].items()},
    )
    harmful_score = harmful_claim_score(payload.content, harmful_patterns=rules["harmful_patterns"])
    platform_thresholds = rules.get("platform_harmful_thresholds", {})
    harmful_threshold = float(platform_thresholds.get(payload.platform.lower(), rules["default_harmful_threshold"]))
    analysis = Analysis(
        mention_id=mention.id,
        sentiment_score=sentiment,
        topic=topic,
        harmful_claim_score=harmful_score,
        is_harmful=1 if harmful_score >= harmful_threshold else 0,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    kol = upsert_kol_from_mention(db, mention)

    event = {
        "type": "mention_ingested",
        "mention_id": mention.id,
        "platform": mention.platform,
        "author_handle": mention.author_handle,
        "content": mention.content,
        "sentiment_score": sentiment,
        "topic": topic,
        "harmful_claim_score": harmful_score,
        "is_harmful": analysis.is_harmful == 1,
        "harmful_threshold": harmful_threshold,
        "kol_tier": kol.tier,
    }
    notification_results = dispatch_harmful_alerts(db, event)
    if notification_results:
        event["notification_results"] = notification_results
    await event_stream.publish(event)
    METRICS["mentions_ingested"] += 1
    write_audit_log(
        db,
        actor=None,
        action="mention.ingest",
        resource_type="mention",
        resource_id=str(mention.id),
        metadata={"actor_email": actor_email, "platform": mention.platform, "is_harmful": bool(analysis.is_harmful)},
    )
    return {"ok": True, "mention_id": mention.id, "analysis_id": analysis.id}


@router.post("")
async def ingest_mention(
    payload: MentionCreate,
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    if idempotency_key:
        existing = db.query(IdempotencyRecord).filter(IdempotencyRecord.idempotency_key == idempotency_key).first()
        if existing:
            try:
                return json.loads(existing.response_json)
            except json.JSONDecodeError:
                return {"ok": True, "deduped": True}
    result = await ingest_mention_internal(payload, db, actor_email=current_user.email)
    if idempotency_key:
        db.add(
            IdempotencyRecord(
                idempotency_key=idempotency_key,
                endpoint="/api/mentions",
                response_json=json.dumps(result),
                status_code=200,
            )
        )
        db.commit()
    return result
