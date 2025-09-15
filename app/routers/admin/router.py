# app/routers/admin/router.py
import os
import json
import re
import unicodedata
from typing import Optional

import markdown2
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chapter import Chapter

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------- Templates + helpers (match main/chapters) ----------------
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
    return f"{base}/{k.lstrip('/')}" if base else f"/static/{k.lstrip('/')}"

templates.env.globals["asset"] = asset

def md_filter(text: str) -> str:
    if not text:
        return ""
    return markdown2.markdown(
        text,
        extras=["fenced-code-blocks", "tables", "strike", "smarty"]
    )

templates.env.filters["md"] = md_filter

def _tojson(value):
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return ""
templates.env.filters["tojson"] = _tojson
# ---------------------------------------------------------------------------


# --------- Helpers ---------
_slug_strip_re = re.compile(r"[^\w\s-]")
_slug_hyphenate_re = re.compile(r"[-\s]+")

def slugify(value: str) -> str:
    """
    Very small slugify: ASCII fold, strip punctuation, collapse spaces to hyphens, lowercase.
    """
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = _slug_strip_re.sub("", value).strip().lower()
    return _slug_hyphenate_re.sub("-", value)

def to_int_or_none(v: Optional[str]) -> Optional[int]:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None

def parse_json_or_none(v: Optional[str]):
    if v is None or str(v).strip() == "":
        return None
    try:
        return json.loads(v)
    except Exception:
        # Leave as raw string if not valid JSON
        return v

def _apply_optional_attrs(ch: Chapter, **kwargs):
    """
    Assign only attributes that exist on the current model to avoid blowing up
    if migrations are not fully applied yet.
    """
    for key, val in kwargs.items():
        if hasattr(ch, key):
            setattr(ch, key, val)
# ---------------------------


# --------- Routes ----------
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    latest = (
        db.query(Chapter)
        .order_by(Chapter.created_at.desc(), Chapter.id.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        "admin/dashboard.html", {"request": request, "latest": latest, "title": "Admin"}
    )

@router.get("/chapters/new", response_class=HTMLResponse)
def chapter_new(request: Request):
    return templates.TemplateResponse(
        "admin/chapter_new.html",
        {"request": request, "form": None, "error": None, "title": "New Chapter"},
    )

@router.post("/chapters/create")
async def chapter_create(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    slug: Optional[str] = Form(None),
    subtitle: Optional[str] = Form(None),
    display_order: Optional[str] = Form(None),
    hero_key: Optional[str] = Form(None),
    teaser: Optional[str] = Form(None),
    ambient_url: Optional[str] = Form(None),
    reel_url: Optional[str] = Form(None),
    meta: Optional[str] = Form(None),
):
    # Build slug
    final_slug = (slug or "").strip() or slugify(title)
    if not final_slug:
        return templates.TemplateResponse(
            "admin/chapter_new.html",
            {
                "request": request,
                "error": "Could not generate a slug from the title.",
                "form": {
                    "title": title,
                    "body": body,
                    "slug": slug,
                    "subtitle": subtitle,
                    "display_order": display_order,
                    "hero_key": hero_key,
                    "teaser": teaser,
                    "ambient_url": ambient_url,
                    "reel_url": reel_url,
                    "meta": meta,
                },
            },
            status_code=400,
        )

    # Enforce unique slug
    existing = db.query(Chapter).filter(Chapter.slug == final_slug).first()
    if existing:
        return templates.TemplateResponse(
            "admin/chapter_new.html",
            {
                "request": request,
                "error": f"Slug '{final_slug}' already exists. Choose a different slug.",
                "form": {
                    "title": title,
                    "body": body,
                    "slug": slug,
                    "subtitle": subtitle,
                    "display_order": display_order,
                    "hero_key": hero_key,
                    "teaser": teaser,
                    "ambient_url": ambient_url,
                    "reel_url": reel_url,
                    "meta": meta,
                },
            },
            status_code=400,
        )

    ch = Chapter(
        title=title.strip(),
        slug=final_slug,
        content=body,
    )

    # Optional fields (only set if present on model)
    _apply_optional_attrs(
        ch,
        subtitle=(subtitle or None),
        hero_key=(hero_key or None),
        reel_url=(reel_url or None),
        teaser=(teaser or None),
        ambient_url=(ambient_url or None),
        display_order=to_int_or_none(display_order),
        meta=parse_json_or_none(meta),
    )

    db.add(ch)
    db.commit()

    return RedirectResponse(url="/admin/dashboard", status_code=303)

@router.get("/chapters/{chapter_id}/edit", response_class=HTMLResponse)
def chapter_edit(chapter_id: int, request: Request, db: Session = Depends(get_db)):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        return templates.TemplateResponse(
            "pages/not_found.html",
            {"request": request, "title": "Not found"},
            status_code=404,
        )
    return templates.TemplateResponse(
        "admin/chapter_edit.html",
        {"request": request, "chapter": ch, "title": f"Edit · {ch.title}"},
    )

@router.post("/chapters/{chapter_id}/update")
async def chapter_update(
    chapter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    slug: Optional[str] = Form(None),
    subtitle: Optional[str] = Form(None),
    display_order: Optional[str] = Form(None),
    hero_key: Optional[str] = Form(None),
    teaser: Optional[str] = Form(None),
    ambient_url: Optional[str] = Form(None),
    reel_url: Optional[str] = Form(None),
    meta: Optional[str] = Form(None),
):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        return templates.TemplateResponse(
            "pages/not_found.html",
            {"request": request, "title": "Not found"},
            status_code=404,
        )

    # Handle slug (ensure unique if changed)
    new_slug = (slug or "").strip() or slugify(title)
    if not new_slug:
        new_slug = ch.slug

    if new_slug != ch.slug:
        exists = db.query(Chapter).filter(Chapter.slug == new_slug).first()
        if exists:
            return templates.TemplateResponse(
                "admin/chapter_edit.html",
                {
                    "request": request,
                    "chapter": ch,
                    "title": f"Edit · {ch.title}",
                    "error": f"Slug '{new_slug}' is already in use.",
                },
                status_code=400,
            )

    ch.title = title.strip()
    ch.slug = new_slug
    ch.content = body

    _apply_optional_attrs(
        ch,
        subtitle=(subtitle or None),
        hero_key=(hero_key or None),
        reel_url=(reel_url or None),
        teaser=(teaser or None),
        ambient_url=(ambient_url or None),
        display_order=to_int_or_none(display_order),
        meta=parse_json_or_none(meta),
    )

    db.add(ch)
    db.commit()

    return RedirectResponse(url="/admin/dashboard", status_code=303)
# ---------------------------