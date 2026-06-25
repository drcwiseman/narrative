import json
import hashlib

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def write_audit_log(
    db: Session,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str = "",
    metadata: dict | None = None,
) -> None:
    previous = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = previous.event_hash if previous else ""
    base = json.dumps(
        {
            "actor_email": actor.email if actor else "system",
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "prev_hash": prev_hash,
        },
        sort_keys=True,
    )
    event_hash = hashlib.sha256(base.encode("utf-8")).hexdigest()
    row = AuditLog(
        actor_email=actor.email if actor else "system",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata or {}),
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    db.add(row)
    db.commit()
