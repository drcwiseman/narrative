import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import authenticate_token, require_roles
from app.models import Analysis, Campaign, EmotionSignal, KOLScore, Mention, Narrative, SavedView
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


@router.get("/counter-attack-plan")
def counter_attack_plan(
    keyword: str,
    topic: str | None = None,
    constituency: str | None = None,
    hours: int = 72,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    window_hours = min(max(hours, 1), 24 * 14)
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
            "keyword": keyword,
            "window_hours": window_hours,
            "status": "no_signal",
            "plan": {
                "urgency": "low",
                "response_objective": "Monitor and prepare rapid response assets.",
                "message_pillars": [
                    "Publish a factual baseline statement.",
                    "Prepare spokesperson talking points.",
                    "Set keyword watch for early detection.",
                ],
                "sample_counter_messages": [
                    f"We are monitoring claims related to '{keyword}' and will publish verified updates.",
                    f"Unverified information about '{keyword}' can mislead communities; rely on official channels.",
                ],
                "channels_priority": ["dashboard", "slack"],
                "kol_targets": [],
                "execution_checklist": [
                    "Activate watchlist and alerts.",
                    "Assign analyst to monitor spread every hour.",
                    "Prepare coordinator-approved response pack.",
                ],
            },
        }

    platform_counts: dict[str, int] = {}
    harmful_count = 0
    for mention, analysis in rows:
        platform = (mention.platform or "unknown").lower()
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        if analysis.is_harmful:
            harmful_count += 1

    harmful_ratio = harmful_count / max(len(rows), 1)
    dominant_platforms = [p for p, _ in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)]
    dominant_topic = topic or rows[-1][1].topic or "general"
    inferred_constituency = constituency or rows[-1][0].constituency

    urgency = "high" if harmful_ratio >= 0.55 else "medium" if harmful_ratio >= 0.3 else "low"
    objective_by_topic = {
        "elections": "Protect voter confidence with verifiable election-process facts.",
        "security": "Reduce panic by clarifying official safety guidance quickly.",
        "health": "Counter misinformation with clinical facts and trusted medical sources.",
        "economy": "Stabilize perception with data-backed economic context and practical steps.",
    }
    response_objective = objective_by_topic.get(dominant_topic, "Replace rumor velocity with trusted factual narrative.")

    pillar_by_topic = {
        "elections": [
            "Use election authority data and transparent process timelines.",
            "Explain verification steps clearly in simple language.",
            "Address top rumor claim directly with evidence links.",
        ],
        "security": [
            "Lead with verified safety status and official contacts.",
            "Clarify what is confirmed vs unverified.",
            "Discourage resharing of unverified threats.",
        ],
        "health": [
            "Use clinical sources and ministry guidance.",
            "Debunk harmful health myths with plain-language facts.",
            "Provide clear do/do-not actions for the public.",
        ],
        "economy": [
            "Publish source-backed figures and context.",
            "Correct exaggerated claims with comparative data.",
            "Give practical citizen-facing guidance and resources.",
        ],
    }
    message_pillars = pillar_by_topic.get(
        dominant_topic,
        [
            "Acknowledge concern and provide verified facts.",
            "Correct false claim with clear evidence.",
            "Provide action steps and where to verify updates.",
        ],
    )

    sample_counter_messages = [
        f"Fact-check update: claims about '{keyword}' are being reviewed against verified sources. Please avoid forwarding unverified posts.",
        f"We have confirmed official information on '{keyword}'. See verified details and share only trusted updates.",
        f"If you see misleading content about '{keyword}', report it and refer to the official response channel.",
    ]

    kols_query = db.query(KOLScore).order_by(KOLScore.influence_score.desc())
    if inferred_constituency:
        kols_query = kols_query.filter(KOLScore.constituency == inferred_constituency)
    kol_targets = [
        {"handle": row.handle, "tier": row.tier, "influence_score": row.influence_score}
        for row in kols_query.limit(5).all()
    ]

    channels_priority = dominant_platforms[:3] if dominant_platforms else ["x", "facebook", "whatsapp"]
    if "slack" not in channels_priority:
        channels_priority.append("slack")

    execution_checklist = [
        "Publish initial correction message within 15 minutes.",
        "Launch constituency-specific campaign copy in dashboard.",
        "Assign top KOL outreach tasks with approved talking points.",
        "Track spread-analysis trend every 30 minutes and adjust messaging.",
    ]

    return {
        "ok": True,
        "keyword": keyword,
        "window_hours": window_hours,
        "status": "active_signal",
        "plan": {
            "urgency": urgency,
            "response_objective": response_objective,
            "message_pillars": message_pillars,
            "sample_counter_messages": sample_counter_messages,
            "channels_priority": channels_priority,
            "kol_targets": kol_targets,
            "execution_checklist": execution_checklist,
            "stats": {
                "mentions": len(rows),
                "harmful_ratio": round(harmful_ratio, 3),
                "dominant_topic": dominant_topic,
                "dominant_platform": dominant_platforms[0] if dominant_platforms else "unknown",
            },
        },
    }


@router.get("/executive-overview")
def executive_overview(
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    window_hours = min(max(hours, 1), 24 * 30)
    start_ts = datetime.utcnow() - timedelta(hours=window_hours)
    total_mentions = db.query(Mention).filter(Mention.posted_at >= start_ts).count()
    active_narratives = db.query(Narrative).filter(Narrative.last_seen >= start_ts).count()
    misinformation_alerts = (
        db.query(Analysis)
        .join(Mention, Mention.id == Analysis.mention_id)
        .filter(Analysis.is_harmful == 1, Mention.posted_at >= start_ts)
        .count()
    )
    influential_voices = db.query(KOLScore).filter(KOLScore.influence_score >= 50).count()
    avg_sentiment = (
        db.query(func.avg(Analysis.sentiment_score))
        .join(Mention, Mention.id == Analysis.mention_id)
        .filter(Mention.posted_at >= start_ts)
        .scalar()
    )
    emotion_rows = (
        db.query(
            func.avg(EmotionSignal.anger),
            func.avg(EmotionSignal.fear),
            func.avg(EmotionSignal.hope),
            func.avg(EmotionSignal.confusion),
            func.avg(EmotionSignal.trust),
        )
        .join(Mention, Mention.id == EmotionSignal.mention_id)
        .filter(Mention.posted_at >= start_ts)
        .first()
    )
    return {
        "window_hours": window_hours,
        "active_narratives": active_narratives,
        "mentions": total_mentions,
        "misinformation_alerts": misinformation_alerts,
        "influential_voices": influential_voices,
        "average_sentiment": round(float(avg_sentiment or 0.0), 3),
        "emotion_mix": {
            "anger": round(float((emotion_rows[0] if emotion_rows else 0) or 0), 3),
            "fear": round(float((emotion_rows[1] if emotion_rows else 0) or 0), 3),
            "hope": round(float((emotion_rows[2] if emotion_rows else 0) or 0), 3),
            "confusion": round(float((emotion_rows[3] if emotion_rows else 0) or 0), 3),
            "trust": round(float((emotion_rows[4] if emotion_rows else 0) or 0), 3),
        },
    }


@router.get("/narrative-map")
def narrative_map(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    rows = db.query(Narrative).order_by(desc(Narrative.last_seen)).limit(50).all()
    return [
        {
            "id": row.id,
            "label": row.name,
            "topic": row.topic,
            "constituency": row.constituency,
            "volume": row.mention_count,
            "risk_score": row.risk_score,
            "status": row.status,
            "last_seen": row.last_seen.isoformat(),
        }
        for row in rows
    ]


@router.get("/coordinated-campaigns")
def coordinated_campaigns(
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    window_hours = min(max(hours, 1), 24 * 7)
    start_ts = datetime.utcnow() - timedelta(hours=window_hours)
    rows = (
        db.query(Mention.content, Mention.platform, func.count(Mention.id).label("count"))
        .filter(Mention.posted_at >= start_ts)
        .group_by(Mention.content, Mention.platform)
        .having(func.count(Mention.id) >= 3)
        .order_by(desc("count"))
        .limit(25)
        .all()
    )
    return [
        {
            "platform": platform,
            "repeat_count": count,
            "signature": content[:220],
            "risk": "high" if count >= 8 else "medium",
        }
        for content, platform, count in rows
    ]


@router.get("/influence-network")
def influence_network(
    topic: str | None = None,
    constituency: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    query = db.query(Mention, Analysis).join(Analysis, Analysis.mention_id == Mention.id)
    if topic:
        query = query.filter(Analysis.topic == topic)
    if constituency:
        query = query.filter(Mention.constituency == constituency)
    rows = query.order_by(desc(Mention.posted_at)).limit(300).all()
    node_weights: dict[str, float] = {}
    for mention, analysis in rows:
        node_weights[mention.author_handle] = node_weights.get(mention.author_handle, 0.0) + (
            1.0 + float(analysis.harmful_claim_score)
        )
    top_nodes = sorted(node_weights.items(), key=lambda x: x[1], reverse=True)[:20]
    handles = [h for h, _ in top_nodes]
    edges = []
    for i in range(len(handles) - 1):
        edges.append({"source": handles[i], "target": handles[i + 1], "weight": round(top_nodes[i][1], 3)})
    return {
        "nodes": [{"id": handle, "weight": round(weight, 3)} for handle, weight in top_nodes],
        "edges": edges,
    }


@router.get("/counter-messaging-performance")
def counter_messaging_performance(
    campaign_id: int,
    hours_before: int = 48,
    hours_after: int = 48,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    before_start = campaign.created_at - timedelta(hours=min(max(hours_before, 1), 24 * 14))
    after_end = campaign.created_at + timedelta(hours=min(max(hours_after, 1), 24 * 14))

    before_rows = (
        db.query(func.avg(Analysis.sentiment_score), func.avg(Analysis.harmful_claim_score))
        .join(Mention, Mention.id == Analysis.mention_id)
        .filter(
            Mention.constituency == campaign.constituency,
            Mention.posted_at >= before_start,
            Mention.posted_at < campaign.created_at,
        )
        .first()
    )
    after_rows = (
        db.query(func.avg(Analysis.sentiment_score), func.avg(Analysis.harmful_claim_score))
        .join(Mention, Mention.id == Analysis.mention_id)
        .filter(
            Mention.constituency == campaign.constituency,
            Mention.posted_at >= campaign.created_at,
            Mention.posted_at <= after_end,
        )
        .first()
    )
    before_sentiment = float((before_rows[0] if before_rows else 0) or 0)
    after_sentiment = float((after_rows[0] if after_rows else 0) or 0)
    before_harmful = float((before_rows[1] if before_rows else 0) or 0)
    after_harmful = float((after_rows[1] if after_rows else 0) or 0)

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "constituency": campaign.constituency,
        "before": {"avg_sentiment": round(before_sentiment, 3), "avg_harmful_score": round(before_harmful, 3)},
        "after": {"avg_sentiment": round(after_sentiment, 3), "avg_harmful_score": round(after_harmful, 3)},
        "delta": {
            "sentiment_change": round(after_sentiment - before_sentiment, 3),
            "harmful_change": round(after_harmful - before_harmful, 3),
        },
    }


@router.get("/assistant/query")
def assistant_query(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    rows = (
        db.query(Mention, Analysis)
        .join(Analysis, Analysis.mention_id == Mention.id)
        .filter(Mention.content.ilike(f"%{query}%"))
        .order_by(desc(Mention.posted_at))
        .limit(120)
        .all()
    )
    if not rows:
        return {
            "answer": f"No active signal found for '{query}'. Run Google Source Scan and widen the time window.",
            "insights": [],
        }

    platform_counts: dict[str, int] = {}
    harmful_count = 0
    for mention, analysis in rows:
        platform_counts[mention.platform] = platform_counts.get(mention.platform, 0) + 1
        if analysis.is_harmful:
            harmful_count += 1
    top_platform = max(platform_counts.items(), key=lambda x: x[1])[0]
    harmful_ratio = harmful_count / max(len(rows), 1)
    first = rows[-1][0]
    answer = (
        f"The '{query}' narrative started from {first.author_handle} on {first.platform} at {first.posted_at.isoformat()}. "
        f"Primary spread channel is {top_platform}. Harmful ratio is {round(harmful_ratio, 3)}. "
        "Recommended: publish clarification, activate KOL outreach, and monitor spread-analysis every 30 minutes."
    )
    return {
        "answer": answer,
        "insights": [
            {"metric": "mentions", "value": len(rows)},
            {"metric": "harmful_ratio", "value": round(harmful_ratio, 3)},
            {"metric": "top_platform", "value": top_platform},
        ],
    }
