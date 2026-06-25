from pathlib import Path
import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, SessionLocal, engine
from app.middleware import basic_rate_limit_middleware, request_context_middleware
from app.observability import metrics_snapshot
from app.routers import admin, auth, campaigns, connectors, ingest, kol, monitoring, queue
from app.services.queue import process_pending_jobs


Base.metadata.create_all(bind=engine)
logger = logging.getLogger(__name__)

app = FastAPI(title="Narrative Monitoring System", version="0.1.0")
app.middleware("http")(request_context_middleware)
app.middleware("http")(basic_rate_limit_middleware)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ingest.router)
app.include_router(connectors.router)
app.include_router(monitoring.router)
app.include_router(kol.router)
app.include_router(campaigns.router)
app.include_router(queue.router)


STATIC_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/web", StaticFiles(directory=STATIC_DIR), name="web")


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/signup")
def signup_page():
    return FileResponse(STATIC_DIR / "signup.html")


@app.get("/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_ok = False
    return {"ok": db_ok, "database": "ok" if db_ok else "error"}


@app.get("/metrics")
def metrics():
    return metrics_snapshot()


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


async def queue_worker_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            await process_pending_jobs(db, max_jobs=10)
        finally:
            db.close()
        await asyncio.sleep(2)


@app.on_event("startup")
async def startup_worker() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database connectivity check failed on startup")
        raise RuntimeError("Database connectivity check failed") from exc
    asyncio.create_task(queue_worker_loop())
