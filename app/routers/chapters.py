# app/routers/chapters.py
import os
import markdown2
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chapter import Chapter

router = APIRouter()

# Templates (this instance needs the same helpers as main.py)
templates = Jinja2Templates(directory="templates")

ASSETS_BASE = os.getenv("ASSETS_BASE_URL", "").rstrip("/")
templates.env.globals["ASSETS_BASE"] = ASSETS_BASE

def asset(key: str) -> str:
    if not key:
        return ""
    k = key.strip()
    if k.startswith("http://") or k.startswith("https://"):
        return k
    base = ASSETS_BASE.rstrip("/")
    return f"{base}/{k.lstrip('/')}" if base else f"/{k.lstrip('/')}"

templates.env.globals["asset"] = asset

def md_filter(text: str) -> str:
    if not text:
        return ""
    return markdown2.markdown(
        text,
        extras=["fenced-code-blocks", "tables", "strike", "smarty"]
    )

templates.env.filters["md"] = md_filter


@router.get("/", response_class=HTMLResponse)
def list_chapters(request: Request, db: Session = Depends(get_db)):
    chapters = db.query(Chapter).order_by(Chapter.created_at.desc()).all()
    return templates.TemplateResponse(
        "pages/chapters.html",
        {"request": request, "chapters": chapters, "title": "Chapters"},
    )


@router.get("/{slug}", response_class=HTMLResponse)
def show_chapter(slug: str, request: Request, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.slug == slug).first()
    if not chapter:
        return templates.TemplateResponse(
            "pages/not_found.html",
            {"request": request, "title": "Not found"},
            status_code=404,
        )

    # Simple prev/next (by created_at, then id fallback)
    prev = (
        db.query(Chapter)
        .filter(Chapter.created_at <= chapter.created_at, Chapter.id < chapter.id)
        .order_by(Chapter.created_at.desc(), Chapter.id.desc())
        .first()
    )
    next_ = (
        db.query(Chapter)
        .filter(Chapter.created_at >= chapter.created_at, Chapter.id > chapter.id)
        .order_by(Chapter.created_at.asc(), Chapter.id.asc())
        .first()
    )

    return templates.TemplateResponse(
        "pages/chapter_detail.html",
        {
            "request": request,
            "chapter": chapter,
            "prev": prev,
            "next": next_,
            "title": chapter.title,
        },
    )