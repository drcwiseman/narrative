import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import DeadLetterJob, QueueJob
from app.routers.ingest import ingest_mention_internal
from app.schemas import MentionCreate
from app.services.request_trace import IngestTraceContext


def enqueue_job(db: Session, job_type: str, payload: dict) -> QueueJob:
    row = QueueJob(job_type=job_type, payload_json=json.dumps(payload), status="pending")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _split_queue_payload(payload: dict) -> tuple[dict, IngestTraceContext | None]:
    trace_raw = payload.pop("_ingest_trace", None)
    trace = IngestTraceContext.from_dict(trace_raw)
    return payload, trace


async def process_pending_jobs(db: Session, max_jobs: int = 20) -> dict:
    jobs = (
        db.query(QueueJob)
        .filter(QueueJob.status.in_(["pending", "retry"]))
        .order_by(QueueJob.created_at.asc())
        .limit(max_jobs)
        .all()
    )
    processed = 0
    failed = 0
    for job in jobs:
        processed += 1
        try:
            payload = json.loads(job.payload_json)
            job.status = "processing"
            job.attempts += 1
            job.updated_at = datetime.utcnow()
            db.commit()

            if job.job_type == "mention_ingest":
                mention_data, trace = _split_queue_payload(payload)
                mention_payload = MentionCreate(**mention_data)
                await ingest_mention_internal(
                    mention_payload,
                    db,
                    actor_email="queue-worker",
                    trace=trace,
                )
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")

            job.status = "completed"
            job.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            job.last_error = str(exc)
            job.updated_at = datetime.utcnow()
            if job.attempts >= 3:
                job.status = "dead_lettered"
                db.add(
                    DeadLetterJob(
                        queue_job_id=job.id,
                        job_type=job.job_type,
                        payload_json=job.payload_json,
                        reason=job.last_error,
                    )
                )
            else:
                job.status = "retry"
            db.commit()
    return {"processed": processed, "failed": failed}
