# app/routers/chapters.py
import os
from typing import Optional

import markdown2
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chapter import Chapter

router = APIRouter()

# --- Templates & Globals ---
templates = Jinja2Templates(directory="templates")

ASSETS_BASE = os.getenv("ASSETS_BASE_URL", "").rstrip("/")
templates.env.globals["ASSETS_BASE"] = ASSETS_BASE


def md_filter(text: str | None) -> str:
    if not text:
        return ""
    return markdown2.markdown(
        text,
        extras=[
            "fenced-code-blocks",
            "tables",
            "strike",
            "smarty",
            "break-on-newline",   # 👈 add this
        ],
    )


templates.env.filters["md"] = md_filter


# -----------------
# Routes
# -----------------
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

    # Prev/Next by created_at
    prev_chapter = (
        db.query(Chapter)
        .filter(Chapter.created_at < chapter.created_at)
        .order_by(Chapter.created_at.desc())
        .first()
    )
    next_chapter = (
        db.query(Chapter)
        .filter(Chapter.created_at > chapter.created_at)
        .order_by(Chapter.created_at.asc())
        .first()
    )

    return templates.TemplateResponse(
        "pages/chapter_detail.html",
        {
            "request": request,
            "chapter": chapter,
            "prev": prev_chapter,
            "next": next_chapter,
            "title": chapter.title,
        },
    )