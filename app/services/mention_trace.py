from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Mention, MentionIngestTrace
from app.services.request_trace import IngestTraceContext


def save_mention_trace(db: Session, mention_id: int, trace: IngestTraceContext | None) -> None:
    if trace is None:
        return
    row = MentionIngestTrace(
        mention_id=mention_id,
        source_ip=trace.source_ip,
        forwarded_for=trace.forwarded_for,
        user_agent=trace.user_agent,
        ingest_channel=trace.ingest_channel,
    )
    db.add(row)
    db.commit()


def delete_mention_trace(db: Session, mention_id: int) -> None:
    db.query(MentionIngestTrace).filter(MentionIngestTrace.mention_id == mention_id).delete()


def effective_ip(mention: Mention, trace: MentionIngestTrace | None) -> str:
    if mention.origin_ip:
        return mention.origin_ip
    if trace is not None and trace.source_ip:
        return trace.source_ip
    return ""
