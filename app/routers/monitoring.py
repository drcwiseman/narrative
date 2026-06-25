import csv
import io
from datetime import datetime, timedelta

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


@router.get("/spread-analysis")
def spread_analysis(
    keyword: str,
    topic: str | None = None,
    constituency: str | None = None,
    hours: int = 168,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    window_hours = min(max(hours, 1), 24 * 30)
    start_ts = datetime.utcnow() - timedelta(hours=window_hours)
    query = (
        db.query(Mention, Analysis)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .filter(Mention.posted_at >= start_ts)
        .filter(Mention.content.ilike(f"%{keyword}%"))
    )
    if topic:
        query = query.filter(Analysis.topic == topic)
    if constituency:
        query = query.filter(Mention.constituency == constituency)

    rows = query.order_by(Mention.posted_at.asc()).all()
    if not rows:
        return {
            "ok": True,
            "total_mentions": 0,
            "keyword": keyword,
            "window_hours": window_hours,
            "suggestions": [
                "No spread detected in selected window; keep monitoring with lower threshold.",
                "Run Google Source Scan for external web context and compare with social mentions.",
            ],
        }

    first_mention, first_analysis = rows[0]
    platform_counts: dict[str, int] = {}
    harmful_count = 0
    timeline_counts: dict[str, int] = {}
    for mention, analysis in rows:
        platform = (mention.platform or "unknown").lower()
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        if analysis.is_harmful:
            harmful_count += 1
        hour_bucket = mention.posted_at.replace(minute=0, second=0, microsecond=0).isoformat()
        timeline_counts[hour_bucket] = timeline_counts.get(hour_bucket, 0) + 1

    harmful_ratio = harmful_count / max(len(rows), 1)
    top_platform = max(platform_counts.items(), key=lambda x: x[1])[0]

    suggestions = [
        f"Prioritize rapid response messaging on {top_platform} where spread is currently highest.",
        "Assign outreach tasks to trusted KOLs in affected constituencies within first 60 minutes.",
    ]
    if harmful_ratio >= 0.5:
        suggestions.append("Escalate to critical workflow: activate high-severity Slack channel and legal/comms review.")
    else:
        suggestions.append("Maintain watch mode with hourly trend checks and targeted counter-message campaigns.")

    return {
        "ok": True,
        "keyword": keyword,
        "window_hours": window_hours,
        "total_mentions": len(rows),
        "harmful_ratio": round(harmful_ratio, 3),
        "first_seen": {
            "posted_at": first_mention.posted_at.isoformat(),
            "platform": first_mention.platform,
            "author_handle": first_mention.author_handle,
            "topic": first_analysis.topic,
            "harmful_claim_score": first_analysis.harmful_claim_score,
            "content_preview": first_mention.content[:280],
        },
        "platform_breakdown": [{"platform": k, "count": v} for k, v in sorted(platform_counts.items())],
        "timeline_hourly": [{"hour": k, "count": v} for k, v in sorted(timeline_counts.items())],
        "suggestions": suggestions,
    }
