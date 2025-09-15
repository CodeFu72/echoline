# app/routers/chapters.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chapter import Chapter

router = APIRouter()

def _templates(request: Request):
    # Use the shared Jinja instance + helpers registered in main.py
    return request.app.state.templates

@router.get("/", response_class=HTMLResponse)
def list_chapters(request: Request, db: Session = Depends(get_db)):
    chapters = db.query(Chapter).order_by(Chapter.created_at.desc()).all()
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

    # Prev/next by (created_at, id) for stability
    prev = (
        db.query(Chapter)
        .filter(
            (Chapter.created_at < chapter.created_at)
            | ((Chapter.created_at == chapter.created_at) & (Chapter.id < chapter.id))
        )
        .order_by(Chapter.created_at.desc(), Chapter.id.desc())
        .first()
    )

    next_ = (
        db.query(Chapter)
        .filter(
            (Chapter.created_at > chapter.created_at)
            | ((Chapter.created_at == chapter.created_at) & (Chapter.id > chapter.id))
        )
        .order_by(Chapter.created_at.asc(), Chapter.id.asc())
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