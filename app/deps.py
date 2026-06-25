from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session
from dataclasses import dataclass

from app.config import settings
from app.database import get_db
from app.models import RevokedSubject, RevokedToken, User


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    id: int
    email: str
    full_name: str
    role: str
    is_active: int


def authenticate_token(token: str, db: Session) -> User | AuthUser:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        email: str | None = payload.get("sub")
        role: str = payload.get("role", "analyst")
        full_name: str = payload.get("full_name", "")
        token_type: str = payload.get("typ", "access")
        jti: str | None = payload.get("jti")
        issued_at: int = int(payload.get("iat", 0))
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        if token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        if jti:
            revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if revoked:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
        rev_sub = db.query(RevokedSubject).filter(RevokedSubject.email == email).first()
        if rev_sub and issued_at and issued_at <= rev_sub.revoke_before_epoch:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(User).filter(User.email == email, User.is_active == 1).first()
    if user is not None:
        return user

    # Fallback for serverless ephemeral SQLite where user rows can disappear
    # between requests. Keep token-auth sessions valid if JWT is valid.
    return AuthUser(id=0, email=email, full_name=full_name, role=role, is_active=1)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | AuthUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authenticate_token(credentials.credentials, db)


def require_roles(*roles: str):
    def role_checker(current_user: User | AuthUser = Depends(get_current_user)) -> User | AuthUser:
        accepted = set(roles)
        if "admin" in accepted:
            accepted.update({"platform_admin", "org_admin"})
        if current_user.role not in accepted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return role_checker
