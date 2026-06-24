from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Campaign, OutreachTask
from app.schemas import CampaignCreate, OutreachCreate, OutreachStatusUpdate


router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(name=payload.name, message=payload.message, constituency=payload.constituency)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return {
        "id": campaign.id,
        "name": campaign.name,
        "message": campaign.message,
        "constituency": campaign.constituency,
    }


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    rows = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [
        {"id": row.id, "name": row.name, "message": row.message, "constituency": row.constituency}
        for row in rows
    ]


@router.post("/{campaign_id}/outreach")
def create_outreach_tasks(campaign_id: int, payload: OutreachCreate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    tasks = []
    for handle in payload.kol_handles:
        task = OutreachTask(campaign_id=campaign.id, kol_handle=handle, notes=payload.notes)
        db.add(task)
        tasks.append(task)
    db.commit()
    return {"ok": True, "campaign_id": campaign.id, "created": len(tasks)}


@router.get("/{campaign_id}/outreach")
def list_outreach_tasks(campaign_id: int, db: Session = Depends(get_db)):
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
def update_outreach_task(task_id: int, payload: OutreachStatusUpdate, db: Session = Depends(get_db)):
    row = db.query(OutreachTask).filter(OutreachTask.id == task_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Outreach task not found")
    row.status = payload.status
    row.notes = payload.notes
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "kol_handle": row.kol_handle,
        "status": row.status,
        "notes": row.notes,
    }
