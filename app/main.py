from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import admin, auth, campaigns, connectors, ingest, kol, monitoring


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Narrative Monitoring System", version="0.1.0")
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ingest.router)
app.include_router(connectors.router)
app.include_router(monitoring.router)
app.include_router(kol.router)
app.include_router(campaigns.router)


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
    return {"ok": True}


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)
