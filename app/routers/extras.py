# app/routers/extras.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Create a local templates instance so we don't import from non-existent modules
templates = Jinja2Templates(directory="templates")

router = APIRouter(tags=["extras"])

@router.get("/extras/missing", response_class=HTMLResponse)
def extras_missing(
    request: Request,
    chapter_slug: str | None = None,
    chapter_title: str | None = None,
    kind: str = "extra",
):
    title = f"{(kind or 'extra').title()} — {chapter_title or 'Echo Line'}"
    ctx = {
        "request": request,
        "chapter_slug": chapter_slug or "",
        "chapter_title": chapter_title or "",
        "kind": kind or "extra",
        "title": title,
    }
    return templates.TemplateResponse("extras_missing.html", ctx)