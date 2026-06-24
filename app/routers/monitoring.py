from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis, Mention
from app.services.stream import event_stream


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/mentions")
def get_recent_mentions(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(Mention, Analysis)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .order_by(desc(Mention.posted_at))
        .limit(min(limit, 250))
        .all()
    )
    return [
        {
            "id": mention.id,
            "platform": mention.platform,
            "author_handle": mention.author_handle,
            "author_name": mention.author_name,
            "constituency": mention.constituency,
            "content": mention.content,
            "posted_at": mention.posted_at.isoformat(),
            "sentiment_score": analysis.sentiment_score,
            "topic": analysis.topic,
            "harmful_claim_score": analysis.harmful_claim_score,
            "is_harmful": bool(analysis.is_harmful),
        }
        for mention, analysis in rows
    ]


@router.get("/alerts")
def get_alerts(limit: int = 25, db: Session = Depends(get_db)):
    rows = (
        db.query(Mention, Analysis)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .filter(Analysis.is_harmful == 1)
        .order_by(desc(Mention.posted_at))
        .limit(min(limit, 250))
        .all()
    )
    return [
        {
            "mention_id": mention.id,
            "platform": mention.platform,
            "author_handle": mention.author_handle,
            "content": mention.content,
            "topic": analysis.topic,
            "harmful_claim_score": analysis.harmful_claim_score,
            "posted_at": mention.posted_at.isoformat(),
        }
        for mention, analysis in rows
    ]


@router.get("/stream")
async def stream_events():
    return StreamingResponse(event_stream.subscribe(), media_type="text/event-stream")
