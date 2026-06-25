from datetime import datetime

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Analysis, Claim, EmotionSignal, IdempotencyRecord, Mention, MentionIngestTrace, Narrative, User
from app.observability import METRICS
from app.schemas import MentionCreate, MentionUpdate
from app.services.analyzer import emotion_scores, extract_claim_candidates, extract_topic, harmful_claim_score, score_sentiment
from app.services.audit import write_audit_log
from app.services.detection_rules import get_detection_rules
from app.services.kol import decrement_kol_from_mention, delete_mention_record, purge_author_handle, upsert_kol_from_mention
from app.services.mention_trace import save_mention_trace
from app.services.narratives import add_claims, add_emotion_signal, upsert_emotion_signal, upsert_narrative
from app.services.notifications import dispatch_harmful_alerts
from app.services.request_trace import IngestTraceContext, extract_client_ip
from app.services.stream import event_stream


router = APIRouter(prefix="/api/mentions", tags=["mentions"])


def _mention_out(mention: Mention, analysis: Analysis, trace: MentionIngestTrace | None = None) -> dict:
    trace_ip = trace.source_ip if trace else ""
    return {
        "id": mention.id,
        "platform": mention.platform,
        "author_handle": mention.author_handle,
        "author_name": mention.author_name,
        "followers": mention.followers,
        "engagement_rate": mention.engagement_rate,
        "constituency": mention.constituency,
        "content": mention.content,
        "origin_ip": mention.origin_ip or "",
        "source_ip": trace_ip,
        "trace_ip": mention.origin_ip or trace_ip,
        "ingest_channel": trace.ingest_channel if trace else "",
        "forwarded_for": trace.forwarded_for if trace else "",
        "posted_at": mention.posted_at.isoformat(),
        "sentiment_score": analysis.sentiment_score,
        "topic": analysis.topic,
        "harmful_claim_score": analysis.harmful_claim_score,
        "is_harmful": bool(analysis.is_harmful),
    }


def _get_mention_with_analysis(db: Session, mention_id: int) -> tuple[Mention, Analysis, MentionIngestTrace | None]:
    row = (
        db.query(Mention, Analysis, MentionIngestTrace)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .outerjoin(MentionIngestTrace, MentionIngestTrace.mention_id == Mention.id)
        .filter(Mention.id == mention_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Mention not found")
    return row


def _analyze_mention(db: Session, mention: Mention, analysis: Analysis | None = None) -> Analysis:
    rules = get_detection_rules(db)
    sentiment = score_sentiment(mention.content, negative_words=rules["negative_words"])
    topic = extract_topic(
        mention.content,
        topic_keywords={k: set(v) for k, v in rules["topic_keywords"].items()},
    )
    harmful_score = harmful_claim_score(mention.content, harmful_patterns=rules["harmful_patterns"])
    platform_thresholds = rules.get("platform_harmful_thresholds", {})
    harmful_threshold = float(platform_thresholds.get(mention.platform.lower(), rules["default_harmful_threshold"]))
    if analysis is None:
        analysis = Analysis(
            mention_id=mention.id,
            sentiment_score=sentiment,
            topic=topic,
            harmful_claim_score=harmful_score,
            is_harmful=1 if harmful_score >= harmful_threshold else 0,
        )
        db.add(analysis)
    else:
        analysis.sentiment_score = sentiment
        analysis.topic = topic
        analysis.harmful_claim_score = harmful_score
        analysis.is_harmful = 1 if harmful_score >= harmful_threshold else 0
    db.commit()
    db.refresh(analysis)
    return analysis


def _sync_mention_derivatives(
    db: Session,
    mention: Mention,
    analysis: Analysis,
    *,
    is_new: bool,
    previous_handle: str | None = None,
) -> dict:
    rules = get_detection_rules(db)
    emotions = emotion_scores(mention.content)
    claim_candidates = extract_claim_candidates(mention.content)
    harmful_score = analysis.harmful_claim_score

    if is_new:
        add_emotion_signal(db, mention_id=mention.id, emotions=emotions)
    else:
        upsert_emotion_signal(db, mention_id=mention.id, emotions=emotions)
        db.query(Claim).filter(Claim.mention_id == mention.id).delete()
        db.commit()

    if is_new:
        narrative = upsert_narrative(
            db,
            topic=analysis.topic,
            constituency=mention.constituency,
            posted_at=mention.posted_at,
            harmful_score=harmful_score,
        )
    else:
        narrative = (
            db.query(Narrative)
            .filter(Narrative.topic == analysis.topic, Narrative.constituency == mention.constituency)
            .order_by(Narrative.last_seen.desc())
            .first()
        )
        if narrative is None:
            narrative = upsert_narrative(
                db,
                topic=analysis.topic,
                constituency=mention.constituency,
                posted_at=mention.posted_at,
                harmful_score=harmful_score,
            )
        else:
            narrative.risk_score = round((narrative.risk_score + harmful_score) / 2, 3)
            narrative.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(narrative)
    if claim_candidates:
        add_claims(
            db,
            narrative_id=narrative.id,
            mention_id=mention.id,
            claims=claim_candidates,
            harmful_score=harmful_score,
        )

    if is_new:
        kol = upsert_kol_from_mention(db, mention)
    else:
        if previous_handle and previous_handle != mention.author_handle:
            decrement_kol_from_mention(db, previous_handle)
            kol = upsert_kol_from_mention(db, mention, increment_count=True)
        else:
            kol = upsert_kol_from_mention(db, mention, increment_count=False)
    platform_thresholds = rules.get("platform_harmful_thresholds", {})
    harmful_threshold = float(platform_thresholds.get(mention.platform.lower(), rules["default_harmful_threshold"]))
    return {
        "sentiment_score": analysis.sentiment_score,
        "topic": analysis.topic,
        "harmful_claim_score": harmful_score,
        "is_harmful": analysis.is_harmful == 1,
        "harmful_threshold": harmful_threshold,
        "narrative_id": narrative.id,
        "emotions": emotions,
        "kol_tier": kol.tier,
    }


async def ingest_mention_internal(
    payload: MentionCreate,
    db: Session,
    actor_email: str = "system",
    trace: IngestTraceContext | None = None,
):
    mention = Mention(
        platform=payload.platform,
        author_handle=payload.author_handle,
        author_name=payload.author_name,
        followers=payload.followers,
        engagement_rate=payload.engagement_rate,
        constituency=payload.constituency,
        content=payload.content,
        origin_ip=(payload.origin_ip or "").strip()[:64],
        posted_at=payload.posted_at or datetime.utcnow(),
    )
    db.add(mention)
    db.commit()
    db.refresh(mention)
    save_mention_trace(db, mention.id, trace)

    analysis = _analyze_mention(db, mention)
    derived = _sync_mention_derivatives(db, mention, analysis, is_new=True)

    event = {
        "type": "mention_ingested",
        "mention_id": mention.id,
        "platform": mention.platform,
        "author_handle": mention.author_handle,
        "content": mention.content,
        **derived,
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
        metadata={"actor_email": actor_email, "platform": mention.platform, "is_harmful": derived["is_harmful"]},
    )
    return {"ok": True, "mention_id": mention.id, "analysis_id": analysis.id}


@router.get("/{mention_id}")
def get_mention(
    mention_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    mention, analysis, trace_row = _get_mention_with_analysis(db, mention_id)
    return _mention_out(mention, analysis, trace_row)


@router.patch("/{mention_id}")
async def update_mention(
    mention_id: int,
    payload: MentionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    mention, analysis, _trace_row = _get_mention_with_analysis(db, mention_id)
    previous_handle = mention.author_handle
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "platform" in updates:
        platform = updates["platform"].strip()
        if not platform:
            raise HTTPException(status_code=400, detail="Platform cannot be empty")
        mention.platform = platform
    if "author_handle" in updates:
        handle = updates["author_handle"].strip()
        if not handle:
            raise HTTPException(status_code=400, detail="Author handle cannot be empty")
        mention.author_handle = handle
    if "author_name" in updates:
        mention.author_name = updates["author_name"].strip()
    if "followers" in updates:
        mention.followers = int(updates["followers"])
    if "engagement_rate" in updates:
        mention.engagement_rate = float(updates["engagement_rate"])
    if "constituency" in updates:
        constituency = updates["constituency"].strip()
        if not constituency:
            raise HTTPException(status_code=400, detail="Constituency cannot be empty")
        mention.constituency = constituency
    if "content" in updates:
        content = updates["content"].strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content cannot be empty")
        mention.content = content
    if "origin_ip" in updates:
        mention.origin_ip = (updates["origin_ip"] or "").strip()[:64]
    if "posted_at" in updates and updates["posted_at"] is not None:
        mention.posted_at = updates["posted_at"]

    db.commit()
    db.refresh(mention)

    analysis = _analyze_mention(db, mention, analysis)
    derived = _sync_mention_derivatives(
        db,
        mention,
        analysis,
        is_new=False,
        previous_handle=previous_handle,
    )

    event = {
        "type": "mention_updated",
        "mention_id": mention.id,
        "platform": mention.platform,
        "author_handle": mention.author_handle,
        "content": mention.content,
        **derived,
    }
    await event_stream.publish(event)
    write_audit_log(
        db,
        current_user,
        "mention.update",
        "mention",
        str(mention.id),
        {"fields": sorted(updates.keys())},
    )
    mention, analysis, trace_row = _get_mention_with_analysis(db, mention_id)
    return {"ok": True, "mention": _mention_out(mention, analysis, trace_row)}


@router.delete("/{mention_id}")
def delete_mention(
    mention_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    mention = db.query(Mention).filter(Mention.id == mention_id).first()
    if mention is None:
        raise HTTPException(status_code=404, detail="Mention not found")

    handle = mention.author_handle
    delete_mention_record(db, mention)
    db.commit()
    decrement_kol_from_mention(db, handle)

    write_audit_log(
        db,
        current_user,
        "mention.delete",
        "mention",
        str(mention_id),
        {"author_handle": handle},
    )
    return {"ok": True, "deleted_id": mention_id}


@router.post("")
async def ingest_mention(
    payload: MentionCreate,
    request: Request,
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
    trace = extract_client_ip(request, ingest_channel="manual_api")
    result = await ingest_mention_internal(payload, db, actor_email=current_user.email, trace=trace)
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
