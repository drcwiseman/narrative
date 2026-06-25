from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import KOLScore
from app.models import User
from app.services.kol import purge_author_handle, rescore_constituency
from app.services.audit import write_audit_log


router = APIRouter(prefix="/api/kols", tags=["kols"])


@router.get("/leaderboard")
def get_kol_leaderboard(
    constituency: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    query = db.query(KOLScore)
    if constituency:
        query = query.filter(KOLScore.constituency == constituency)
    rows = query.order_by(desc(KOLScore.influence_score)).limit(min(limit, 250)).all()
    return [
        {
            "handle": row.handle,
            "name": row.name,
            "constituency": row.constituency,
            "followers": row.followers,
            "engagement_rate": row.engagement_rate,
            "mention_count": row.mention_count,
            "influence_score": row.influence_score,
            "tier": row.tier,
        }
        for row in rows
    ]


@router.delete("/{handle:path}")
def delete_kol(
    handle: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    result = purge_author_handle(db, handle)
    if not result["kol_deleted"] and not result["deleted_mentions"]:
        raise HTTPException(status_code=404, detail="KOL or mentions not found for handle")
    write_audit_log(
        db,
        current_user,
        "kol.delete",
        "kol",
        result["handle"],
        result,
    )
    return {"ok": True, **result}


@router.post("/rescore")
def bulk_rescore(
    constituency: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    count = rescore_constituency(db, constituency=constituency)
    return {"ok": True, "rescored": count, "constituency": constituency}
