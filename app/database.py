import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _resolve_database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured

    # Vercel serverless filesystem is read-only except for /tmp.
    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return "sqlite:////tmp/narrative.db"

    return "sqlite:///./narrative.db"


DATABASE_URL = _resolve_database_url()

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite:///"):
    sqlite_path = DATABASE_URL.replace("sqlite:///", "", 1)
    if sqlite_path and sqlite_path != ":memory:":
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
