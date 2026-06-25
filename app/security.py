from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
import jwt

from app.config import settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str, full_name: str = "") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.token_exp_minutes)
    payload = {"sub": subject, "role": role, "full_name": full_name, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
