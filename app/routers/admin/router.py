# app/routers/admin/router.py
import os
import re
from dotenv import load_dotenv

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chapter import Chapter

# Load environment before reading variables
load_dotenv()

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/admin", tags=["admin"])

# Credentials from .env
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "password123")


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\- ]+", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


@router.get("/", response_class=HTMLResponse)
def admin_root(request: Request):
    """If logged in, go to dashboard; otherwise to login."""
    if request.session.get("admin"):
        return RedirectResponse(url="/admin/dashboard", status_code=HTTP_302_FOUND)
    return RedirectResponse(url="/admin/login", status_code=HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Render the login form."""
    return templates.TemplateResponse("admin/login.html", {"request": request})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Validate credentials and create a session."""
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["admin"] = True
        return RedirectResponse(url="/admin/dashboard", status_code=HTTP_302_FOUND)

    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "error": "Invalid credentials"},
        status_code=401,
    )


@router.get("/chapters/new", response_class=HTMLResponse)
def chapter_new(request: Request):
    """New chapter form."""
    if not request.session.get("admin"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("admin/chapter_new.html", {"request": request})


@router.post("/chapters/create")
def chapter_create(
    request: Request,
    title: str = Form(...),
    slug: str = Form(""),
    body: str = Form(""),
    hero_key: str = Form(""),
    db: Session = Depends(get_db),
):
    """Create a new chapter record."""
    if not request.session.get("admin"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_302_FOUND)

    # Basic validation
    title = title.strip()
    if not title:
        return templates.TemplateResponse(
            "admin/chapter_new.html",
            {
                "request": request,
                "error": "Title is required.",
                "form": {"title": title, "slug": slug, "body": body, "hero_key": hero_key},
            },
            status_code=400,
        )

    # Derive/normalize slug
    _slug = slugify(slug or title)

    # Uniqueness check
    if db.query(Chapter).filter(Chapter.slug == _slug).first():
        return templates.TemplateResponse(
            "admin/chapter_new.html",
            {
                "request": request,
                "error": f"Slug '{_slug}' already exists.",
                "form": {"title": title, "slug": slug, "body": body, "hero_key": hero_key},
            },
            status_code=400,
        )

    # Model uses `content` as the text field
    ch = Chapter(
        title=title,
        slug=_slug,
        content=body,
        hero_key=hero_key or None,
    )
    db.add(ch)
    db.commit()

    return RedirectResponse(url="/admin/dashboard", status_code=HTTP_302_FOUND)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Protected dashboard showing recent chapters."""
    if not request.session.get("admin"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_302_FOUND)

    latest = (
        db.query(Chapter)
        .order_by(Chapter.created_at.desc())
        .limit(5)
        .all()
    )
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "latest": latest},
    )


@router.get("/logout")
def logout(request: Request):
    """Clear the session and return to home."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)