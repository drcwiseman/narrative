from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets

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
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "full_name": full_name,
        "typ": "access",
        "jti": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, role: str, full_name: str = "") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_token_exp_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "full_name": full_name,
        "typ": "refresh",
        "jti": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def hash_connector_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def verify_connector_token(raw_token: str, stored_hash: str) -> bool:
    if not stored_hash.startswith("sha256$"):
        return hmac.compare_digest(raw_token, stored_hash)
    digest = stored_hash.split("$", 1)[1]
    expected = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, expected)


def sign_webhook_payload(payload: dict) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(
        settings.webhook_signing_secret.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    return signature
