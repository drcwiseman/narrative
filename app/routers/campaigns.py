from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Campaign, OutreachTask
from app.models import User
from app.schemas import CampaignCreate, OutreachCreate, OutreachStatusUpdate
from app.services.audit import write_audit_log


router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("")
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator")),
):
    campaign = Campaign(name=payload.name, message=payload.message, constituency=payload.constituency)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    write_audit_log(db, current_user, "campaign.create", "campaign", str(campaign.id), {"name": campaign.name})
    return {
        "id": campaign.id,
        "name": campaign.name,
        "message": campaign.message,
        "constituency": campaign.constituency,
    }


@router.get("")
def list_campaigns(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst", "outreach")),
):
    rows = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [
        {"id": row.id, "name": row.name, "message": row.message, "constituency": row.constituency}
        for row in rows
    ]


@router.post("/{campaign_id}/outreach")
def create_outreach_tasks(
    campaign_id: int,
    payload: OutreachCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "outreach")),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    tasks = []
    for handle in payload.kol_handles:
        task = OutreachTask(campaign_id=campaign.id, kol_handle=handle, notes=payload.notes)
        db.add(task)
        tasks.append(task)
    db.commit()
    write_audit_log(
        db,
        current_user,
        "outreach.create_batch",
        "campaign",
        str(campaign.id),
        {"task_count": len(tasks)},
    )
    return {"ok": True, "campaign_id": campaign.id, "created": len(tasks)}


@router.get("/{campaign_id}/outreach")
def list_outreach_tasks(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "outreach", "analyst")),
):
    rows = db.query(OutreachTask).filter(OutreachTask.campaign_id == campaign_id).all()
    return [
        {
            "id": row.id,
            "campaign_id": row.campaign_id,
            "kol_handle": row.kol_handle,
            "status": row.status,
            "notes": row.notes,
        }
        for row in rows
    ]


@router.patch("/outreach/{task_id}")
def update_outreach_task(
    task_id: int,
    payload: OutreachStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "outreach")),
):
    row = db.query(OutreachTask).filter(OutreachTask.id == task_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Outreach task not found")
    row.status = payload.status
    row.notes = payload.notes
    db.commit()
    db.refresh(row)
    write_audit_log(db, current_user, "outreach.update", "outreach_task", str(row.id), {"status": row.status})
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "kol_handle": row.kol_handle,
        "status": row.status,
        "notes": row.notes,
    }
