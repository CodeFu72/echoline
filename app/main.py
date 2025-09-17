# app/main.py
import os
import hashlib
import markdown2
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

# Load env vars (.env)
load_dotenv()

# DB + routers
from app.db.session import get_db
from app.models.chapter import Chapter
from app.routers.chapters import router as chapters_router
from app.routers.admin import router as admin_router

app = FastAPI(title="Echo Line")

# ---- Middleware ----
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"))

# ---- Static & Templates ----
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Make the templates object available to routers
app.state.templates = templates

# ---- Jinja helpers (single source of truth) ----
ASSETS_BASE = os.getenv("ASSETS_BASE_URL", "").rstrip("/")
templates.env.globals["ASSETS_BASE"] = ASSETS_BASE

def asset(key: str) -> str:
    """
    Build a full asset URL.
    - Absolute URLs (http/https) are returned unchanged.
    - Otherwise, prefix with ASSETS_BASE if set, else /static/.
    """
    if not key:
        return ""
    k = key.strip()
    if k.startswith("http://") or k.startswith("https://"):
        return k
    base = ASSETS_BASE.rstrip("/")
    return f"{base}/{k.lstrip('/')}" if base else f"/static/{k.lstrip('/')}"

templates.env.globals["asset"] = asset

def md_filter(text: str) -> str:
    """Markdown → safe HTML (basic extras)."""
    if not text:
        return ""
    return markdown2.markdown(text, extras=["fenced-code-blocks", "tables", "strike", "smarty"])

templates.env.filters["md"] = md_filter

# Optional ambient: YouTube embed URL
templates.env.globals["YT_AMBIENT_URL"] = os.getenv("YT_AMBIENT_URL", "")

# ---- CSS cache-busting without client JS (prevents flash) ----
def _static_file_version(path: str) -> str:
    """
    Return a short hash (or mtime fallback) for cache-busting.
    We compute it once per process start; no per-request JS rewriting.
    """
    try:
        with open(path, "rb") as f:
            h = hashlib.sha1(f.read()).hexdigest()[:10]
            return h
    except Exception:
        try:
            mtime = os.path.getmtime(path)
            return str(int(mtime))
        except Exception:
            return "dev"

SITE_CSS_PATH = os.path.join("static", "css", "site.css")
STATIC_VERSION = _static_file_version(SITE_CSS_PATH)
templates.env.globals["STATIC_VERSION"] = STATIC_VERSION

# -----------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    latest = db.query(Chapter).order_by(Chapter.created_at.desc()).first()
    latest_list = db.query(Chapter).order_by(Chapter.created_at.desc()).limit(9).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Echo Line", "latest": latest, "latest_list": latest_list},
    )

# Routers
app.include_router(chapters_router, prefix="/chapters", tags=["chapters"])
app.include_router(admin_router)