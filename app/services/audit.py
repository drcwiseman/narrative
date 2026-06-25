import json

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
    row = AuditLog(
        actor_email=actor.email if actor else "system",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(row)
    db.commit()
