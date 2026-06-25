from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import jwt

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import RevokedSubject, RevokedToken, User
from app.schemas import LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.services.audit import write_audit_log


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    first_user = db.query(User).count() == 0
    role = "platform_admin" if first_user else "org_admin"
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit_log(db, user, "auth.register", "user", str(user.id), {"role": role})
    return TokenResponse(
        access_token=create_access_token(user.email, user.role, user.full_name),
        refresh_token=create_refresh_token(user.email, user.role, user.full_name),
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.is_active != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")
    write_audit_log(db, user, "auth.login", "user", str(user.id))
    return TokenResponse(
        access_token=create_access_token(user.email, user.role, user.full_name),
        refresh_token=create_refresh_token(user.email, user.role, user.full_name),
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        decoded = jwt.decode(
            payload.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        if decoded.get("typ") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        email = decoded.get("sub")
        role = decoded.get("role", "analyst")
        full_name = decoded.get("full_name", "")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid refresh token subject")
        revoked_subject = db.query(RevokedSubject).filter(RevokedSubject.email == email).first()
        issued_at = int(decoded.get("iat", 0))
        if revoked_subject and issued_at <= revoked_subject.revoke_before_epoch:
            raise HTTPException(status_code=401, detail="Session revoked")
        return TokenResponse(
            access_token=create_access_token(email, role, full_name),
            refresh_token=create_refresh_token(email, role, full_name),
            role=role,
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Best effort token revocation for current issued token family.
    row = RevokedSubject(
        email=current_user.email,
        revoke_before_epoch=int(datetime.now(timezone.utc).timestamp()),
    )
    existing = db.query(RevokedSubject).filter(RevokedSubject.email == current_user.email).first()
    if existing:
        existing.revoke_before_epoch = row.revoke_before_epoch
        existing.updated_at = datetime.utcnow()
    else:
        db.add(row)
    db.commit()
    write_audit_log(db, current_user, "auth.logout", "user", str(current_user.id))
    return {"ok": True}


@router.post("/logout-all")
def logout_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(RevokedSubject).filter(RevokedSubject.email == current_user.email).first()
    cutoff = int(datetime.now(timezone.utc).timestamp())
    if existing:
        existing.revoke_before_epoch = cutoff
        existing.updated_at = datetime.utcnow()
    else:
        db.add(RevokedSubject(email=current_user.email, revoke_before_epoch=cutoff))
    db.commit()
    write_audit_log(db, current_user, "auth.logout_all", "user", str(current_user.id))
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=bool(current_user.is_active),
    )
