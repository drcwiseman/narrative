import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import AlertEndpoint, AuditLog, ConnectorKey, User
from app.schemas import AlertEndpointCreate, ConnectorKeyCreate
from app.services.audit import write_audit_log


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/connector-keys")
def create_connector_key(
    payload: ConnectorKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing = db.query(ConnectorKey).filter(ConnectorKey.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Connector key name already exists")
    token = secrets.token_urlsafe(32)
    key = ConnectorKey(name=payload.name, platform=payload.platform, token=token, is_active=1)
    db.add(key)
    db.commit()
    db.refresh(key)
    write_audit_log(db, current_user, "connector_key.create", "connector_key", str(key.id), {"name": key.name})
    return {"id": key.id, "name": key.name, "platform": key.platform, "token": token}


@router.get("/connector-keys")
def list_connector_keys(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "coordinator"))
):
    rows = db.query(ConnectorKey).order_by(ConnectorKey.created_at.desc()).all()
    write_audit_log(db, current_user, "connector_key.list", "connector_key")
    return [
        {
            "id": row.id,
            "name": row.name,
            "platform": row.platform,
            "is_active": bool(row.is_active),
            "token_preview": f"{row.token[:6]}...{row.token[-4:]}",
        }
        for row in rows
    ]


@router.post("/alert-endpoints")
def create_alert_endpoint(
    payload: AlertEndpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing = db.query(AlertEndpoint).filter(AlertEndpoint.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Alert endpoint name already exists")
    endpoint = AlertEndpoint(
        name=payload.name,
        url=payload.url,
        min_harmful_score=payload.min_harmful_score,
        is_active=1,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    write_audit_log(
        db, current_user, "alert_endpoint.create", "alert_endpoint", str(endpoint.id), {"name": endpoint.name}
    )
    return endpoint


@router.get("/alert-endpoints")
def list_alert_endpoints(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "coordinator"))
):
    rows = db.query(AlertEndpoint).order_by(AlertEndpoint.created_at.desc()).all()
    write_audit_log(db, current_user, "alert_endpoint.list", "alert_endpoint")
    return rows


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()
    write_audit_log(db, current_user, "audit_log.list", "audit_log")
    return [
        {
            "id": row.id,
            "actor_email": row.actor_email,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "metadata_json": row.metadata_json,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/users")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": row.id,
            "email": row.email,
            "full_name": row.full_name,
            "role": row.role,
            "is_active": bool(row.is_active),
        }
        for row in rows
    ]


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    if role not in {"admin", "coordinator", "analyst", "outreach"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    db.refresh(user)
    write_audit_log(db, current_user, "user.role_update", "user", str(user.id), {"role": role})
    return {"id": user.id, "email": user.email, "role": user.role}
