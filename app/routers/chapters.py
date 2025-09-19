# app/routers/chapters.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, asc, desc, and_, or_

from app.db.session import get_db
from app.models.chapter import Chapter

router = APIRouter()

def _templates(request: Request):
    # Use the shared Jinja instance + helpers registered in main.py
    return request.app.state.templates

# Single source of truth for ordering:
#   1) display_order ASC (NULLs last via COALESCE to a big number)
#   2) id ASC (stable tie-breaker)
def _ord_key():
    # 1e9 is an arbitrarily large sentinel to push NULLs last
    return func.coalesce(Chapter.display_order, 1_000_000_000)

@router.get("/", response_class=HTMLResponse)
def list_chapters(request: Request, db: Session = Depends(get_db)):
    chapters = (
        db.query(Chapter)
        .order_by(asc(_ord_key()), asc(Chapter.id))
        .all()
    )
    return _templates(request).TemplateResponse(
        "pages/chapters.html",
        {"request": request, "chapters": chapters, "title": "Chapters"},
    )

@router.get("/{slug}", response_class=HTMLResponse)
def show_chapter(slug: str, request: Request, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.slug == slug).first()
    if not chapter:
        return _templates(request).TemplateResponse(
            "pages/not_found.html",
            {"request": request, "title": "Not found"},
            status_code=404,
        )

    # Normalize the current chapter's ordering key for comparisons
    cur_key = db.query(func.coalesce(Chapter.display_order, 1_000_000_000)).filter(Chapter.id == chapter.id).scalar()

    # Prev = the immediately smaller (key, id) by our global ordering
    prev = (
        db.query(Chapter)
        .filter(
            or_(
                _ord_key() < cur_key,
                and_(_ord_key() == cur_key, Chapter.id < chapter.id),
            )
        )
        .order_by(desc(_ord_key()), desc(Chapter.id))
        .first()
    )

    # Next = the immediately larger (key, id)
    next_ = (
        db.query(Chapter)
        .filter(
            or_(
                _ord_key() > cur_key,
                and_(_ord_key() == cur_key, Chapter.id > chapter.id),
            )
        )
        .order_by(asc(_ord_key()), asc(Chapter.id))
        .first()
    )

    return _templates(request).TemplateResponse(
        "pages/chapter_detail.html",
        {
            "request": request,
            "chapter": chapter,
            "prev": prev,
            "next": next_,
            "title": chapter.title,
        },
    )