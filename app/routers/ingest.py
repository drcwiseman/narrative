from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis, Mention
from app.schemas import MentionCreate
from app.services.analyzer import extract_topic, harmful_claim_score, score_sentiment
from app.services.kol import upsert_kol_from_mention
from app.services.stream import event_stream


router = APIRouter(prefix="/api/mentions", tags=["mentions"])


@router.post("")
async def ingest_mention(payload: MentionCreate, db: Session = Depends(get_db)):
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

    sentiment = score_sentiment(payload.content)
    topic = extract_topic(payload.content)
    harmful_score = harmful_claim_score(payload.content)
    analysis = Analysis(
        mention_id=mention.id,
        sentiment_score=sentiment,
        topic=topic,
        harmful_claim_score=harmful_score,
        is_harmful=1 if harmful_score >= 0.5 else 0,
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
        "kol_tier": kol.tier,
    }
    await event_stream.publish(event)
    return {"ok": True, "mention_id": mention.id, "analysis_id": analysis.id}
