from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Analysis, Claim, EmotionSignal, KOLScore, Mention


def normalize_handle(handle: str) -> str:
    value = handle.strip()
    if not value:
        return value
    return value if value.startswith("@") else f"@{value}"


def handle_variants(handle: str) -> set[str]:
    normalized = normalize_handle(handle)
    bare = normalized.lstrip("@")
    return {normalized, bare, f"@{bare}"}


def delete_mention_record(db: Session, mention: Mention) -> None:
    mention_id = mention.id
    db.query(Claim).filter(Claim.mention_id == mention_id).delete()
    db.query(EmotionSignal).filter(EmotionSignal.mention_id == mention_id).delete()
    db.query(Analysis).filter(Analysis.mention_id == mention_id).delete()
    db.delete(mention)


def purge_author_handle(db: Session, handle: str) -> dict:
    variants = handle_variants(handle)
    mentions = db.query(Mention).filter(Mention.author_handle.in_(variants)).all()
    deleted_mention_ids = []
    for mention in mentions:
        deleted_mention_ids.append(mention.id)
        delete_mention_record(db, mention)

    kol = db.query(KOLScore).filter(KOLScore.handle.in_(variants)).first()
    kol_deleted = False
    if kol is not None:
        db.delete(kol)
        kol_deleted = True

    db.commit()
    return {
        "handle": normalize_handle(handle),
        "deleted_mentions": len(deleted_mention_ids),
        "mention_ids": deleted_mention_ids,
        "kol_deleted": kol_deleted,
    }


def get_tier(score: float) -> str:
    if score >= 80:
        return "mega"
    if score >= 45:
        return "macro"
    return "micro"


def compute_influence_score(followers: int, engagement_rate: float, mention_count: int) -> float:
    follower_band = min(70.0, followers / 2000.0)
    engagement_band = min(20.0, max(0.0, engagement_rate) * 100)
    activity_band = min(10.0, mention_count * 0.8)
    return round(follower_band + engagement_band + activity_band, 2)


def upsert_kol_from_mention(db: Session, mention: Mention, *, increment_count: bool = True) -> KOLScore:
    kol = db.query(KOLScore).filter(KOLScore.handle == mention.author_handle).first()
    if kol is None:
        kol = KOLScore(
            handle=mention.author_handle,
            name=mention.author_name,
            constituency=mention.constituency,
            followers=mention.followers,
            engagement_rate=mention.engagement_rate,
            mention_count=1 if increment_count else 0,
        )
        db.add(kol)
    else:
        kol.name = mention.author_name or kol.name
        kol.constituency = mention.constituency or kol.constituency
        kol.followers = max(kol.followers, mention.followers)
        kol.engagement_rate = max(kol.engagement_rate, mention.engagement_rate)
        if increment_count:
            kol.mention_count += 1

    kol.influence_score = compute_influence_score(kol.followers, kol.engagement_rate, kol.mention_count)
    kol.tier = get_tier(kol.influence_score)
    kol.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(kol)
    return kol


def decrement_kol_from_mention(db: Session, handle: str) -> None:
    kol = db.query(KOLScore).filter(KOLScore.handle == handle).first()
    if kol is None:
        return
    kol.mention_count = max(0, kol.mention_count - 1)
    kol.influence_score = compute_influence_score(kol.followers, kol.engagement_rate, kol.mention_count)
    kol.tier = get_tier(kol.influence_score)
    kol.updated_at = datetime.utcnow()
    db.commit()


def rescore_constituency(db: Session, constituency: str) -> int:
    kols = db.query(KOLScore).filter(KOLScore.constituency == constituency).all()
    for kol in kols:
        kol.influence_score = compute_influence_score(kol.followers, kol.engagement_rate, kol.mention_count)
        kol.tier = get_tier(kol.influence_score)
        kol.updated_at = datetime.utcnow()
    db.commit()
    return len(kols)
