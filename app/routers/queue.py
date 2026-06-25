from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import DeadLetterJob, QueueJob, User
from app.services.queue import enqueue_job, process_pending_jobs


router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/jobs")
def create_job(
    payload: dict,
    job_type: str = "mention_ingest",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator", "analyst")),
):
    job = enqueue_job(db, job_type=job_type, payload=payload)
    return {"id": job.id, "status": job.status, "job_type": job.job_type}


@router.post("/process")
async def process_jobs(
    max_jobs: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await process_pending_jobs(db, max_jobs=max_jobs)


@router.get("/jobs")
def list_jobs(
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "coordinator")),
):
    query = db.query(QueueJob)
    if status:
        query = query.filter(QueueJob.status == status)
    rows = query.order_by(QueueJob.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": row.id,
            "job_type": row.job_type,
            "status": row.status,
            "attempts": row.attempts,
            "last_error": row.last_error,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/dlq")
def list_dlq(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rows = db.query(DeadLetterJob).order_by(DeadLetterJob.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": row.id,
            "queue_job_id": row.queue_job_id,
            "job_type": row.job_type,
            "reason": row.reason,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
