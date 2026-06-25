from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Claim, EmotionSignal, Narrative, NarrativeEvent


def _narrative_name(topic: str, constituency: str) -> str:
    return f"{topic.title()} Narrative - {constituency.title()}"


def upsert_narrative(
    db: Session,
    *,
    topic: str,
    constituency: str,
    posted_at: datetime,
    harmful_score: float,
) -> Narrative:
    row = (
        db.query(Narrative)
        .filter(Narrative.topic == topic, Narrative.constituency == constituency)
        .order_by(Narrative.last_seen.desc())
        .first()
    )
    if row is None:
        row = Narrative(
            name=_narrative_name(topic, constituency),
            topic=topic,
            constituency=constituency,
            status="origin",
            first_seen=posted_at,
            last_seen=posted_at,
            mention_count=1,
            risk_score=harmful_score,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        db.add(
            NarrativeEvent(
                narrative_id=row.id,
                stage="origin",
                label="First mention detected",
                metadata_json=json.dumps({"risk_score": harmful_score}),
                occurred_at=posted_at,
            )
        )
        db.commit()
        return row

    row.last_seen = posted_at
    row.mention_count += 1
    row.risk_score = round((row.risk_score + harmful_score) / 2, 3)
    if row.mention_count >= 50:
        row.status = "mass_adoption"
    elif row.mention_count >= 10:
        row.status = "early_influencers"
    else:
        row.status = "emerging"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)

    if row.mention_count in {10, 50}:
        stage = "early_influencers" if row.mention_count == 10 else "mass_adoption"
        label = "Influencer amplification detected" if stage == "early_influencers" else "Mass adoption threshold reached"
        db.add(
            NarrativeEvent(
                narrative_id=row.id,
                stage=stage,
                label=label,
                metadata_json=json.dumps({"mention_count": row.mention_count, "risk_score": row.risk_score}),
                occurred_at=posted_at,
            )
        )
        db.commit()
    return row


def add_claims(db: Session, *, narrative_id: int, mention_id: int, claims: list[str], harmful_score: float) -> None:
    for claim in claims:
        db.add(
            Claim(
                narrative_id=narrative_id,
                mention_id=mention_id,
                text=claim,
                risk_score=harmful_score,
                status="under_review" if harmful_score >= 0.5 else "observed",
                reason="linguistic-claim-pattern",
            )
        )
    db.commit()


def add_emotion_signal(db: Session, *, mention_id: int, emotions: dict[str, float]) -> None:
    db.add(
        EmotionSignal(
            mention_id=mention_id,
            anger=float(emotions.get("anger", 0.0)),
            fear=float(emotions.get("fear", 0.0)),
            hope=float(emotions.get("hope", 0.0)),
            confusion=float(emotions.get("confusion", 0.0)),
            trust=float(emotions.get("trust", 0.0)),
        )
    )
    db.commit()
