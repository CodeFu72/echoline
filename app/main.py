# app/main.py
import os
import markdown2
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

load_dotenv()

from app.db.session import get_db
from app.models.chapter import Chapter
from app.routers.chapters import router as chapters_router
from app.routers.admin import router as admin_router

app = FastAPI(title="Echo Line")

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"))

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---- Jinja helpers ----
ASSETS_BASE = os.getenv("ASSETS_BASE_URL", "").rstrip("/")
templates.env.globals["ASSETS_BASE"] = ASSETS_BASE

def asset(key: str) -> str:
    if not key:
        return ""
    if key.startswith("http://") or key.startswith("https://"):
        return key
    base = ASSETS_BASE.rstrip("/")
    return f"{base}/{key.lstrip('/')}" if base else f"/static/{key.lstrip('/')}"

templates.env.globals["asset"] = asset

def md_filter(text: str) -> str:
    if not text:
        return ""
    return markdown2.markdown(text, extras=["fenced-code-blocks", "tables", "strike", "smarty"])
templates.env.filters["md"] = md_filter

# Ambient (YouTube embed url, e.g. https://www.youtube-nocookie.com/embed/VIDEO_ID?autoplay=1&loop=1&playlist=VIDEO_ID)
templates.env.globals["YT_AMBIENT_URL"] = os.getenv("YT_AMBIENT_URL", "")

# -----------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    latest = db.query(Chapter).order_by(Chapter.created_at.desc()).first()
    latest_list = db.query(Chapter).order_by(Chapter.created_at.desc()).limit(9).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Echo Line", "latest": latest, "latest_list": latest_list},
    )

app.include_router(chapters_router, prefix="/chapters", tags=["chapters"])
app.include_router(admin_router)