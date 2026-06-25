import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import authenticate_token, require_roles
from app.models import Analysis, Mention, SavedView
from app.models import User
from app.services.stream import event_stream


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/mentions")
def get_recent_mentions(
    limit: int = 50,
    start_time: str | None = None,
    end_time: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    query = db.query(Mention, Analysis).join(Analysis, Analysis.mention_id == Mention.id)
    if start_time:
        query = query.filter(Mention.posted_at >= datetime.fromisoformat(start_time))
    if end_time:
        query = query.filter(Mention.posted_at <= datetime.fromisoformat(end_time))
    rows = query.order_by(desc(Mention.posted_at)).limit(min(limit, 250)).all()
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
def get_alerts(
    limit: int = 25,
    start_time: str | None = None,
    end_time: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    query = (
        db.query(Mention, Analysis)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .filter(Analysis.is_harmful == 1)
    )
    if start_time:
        query = query.filter(Mention.posted_at >= datetime.fromisoformat(start_time))
    if end_time:
        query = query.filter(Mention.posted_at <= datetime.fromisoformat(end_time))
    rows = query.order_by(desc(Mention.posted_at)).limit(min(limit, 250)).all()
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
async def stream_events(token: str, db: Session = Depends(get_db)):
    user = authenticate_token(token, db)
    if user.role not in {"admin", "coordinator", "analyst", "outreach"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return StreamingResponse(event_stream.subscribe(), media_type="text/event-stream")


@router.get("/alerts/export.csv")
def export_alerts_csv(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    rows = (
        db.query(Mention, Analysis)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .filter(Analysis.is_harmful == 1)
        .order_by(desc(Mention.posted_at))
        .limit(min(limit, 5000))
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "mention_id",
            "platform",
            "author_handle",
            "constituency",
            "topic",
            "harmful_claim_score",
            "posted_at",
            "content",
        ]
    )
    for mention, analysis in rows:
        writer.writerow(
            [
                mention.id,
                mention.platform,
                mention.author_handle,
                mention.constituency,
                analysis.topic,
                analysis.harmful_claim_score,
                mention.posted_at.isoformat(),
                mention.content,
            ]
        )
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv")


@router.get("/trends")
def trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    topic_rows = (
        db.query(Analysis.topic, func.count(Analysis.id).label("count"))
        .group_by(Analysis.topic)
        .order_by(desc("count"))
        .limit(10)
        .all()
    )
    platform_rows = (
        db.query(Mention.platform, func.count(Mention.id).label("count"))
        .group_by(Mention.platform)
        .order_by(desc("count"))
        .limit(10)
        .all()
    )
    return {
        "top_topics": [{"topic": topic, "count": count} for topic, count in topic_rows],
        "top_platforms": [{"platform": platform, "count": count} for platform, count in platform_rows],
    }


@router.post("/saved-views")
def create_saved_view(
    name: str,
    view_type: str,
    query_json: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    row = SavedView(owner_email=current_user.email, name=name, view_type=view_type, query_json=query_json)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "view_type": row.view_type}


@router.get("/saved-views")
def list_saved_views(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    rows = db.query(SavedView).filter(SavedView.owner_email == current_user.email).order_by(desc(SavedView.created_at)).all()
    return [{"id": row.id, "name": row.name, "view_type": row.view_type, "query_json": row.query_json} for row in rows]
