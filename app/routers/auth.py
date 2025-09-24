# app/routers/auth.py
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


# --------- helpers ---------
def _is_safe_next(next_url: str | None) -> bool:
    """
    Only allow local/relative redirects. Blocks absolute/externals.
    Accepts "" or None as safe (meaning: no redirect).
    """
    if not next_url:
        return True
    # Must be relative (no scheme/host) and start with '/'
    parts = urlparse(next_url)
    return (not parts.scheme and not parts.netloc and next_url.startswith("/"))


def _redirect_to_next(next_url: str | None, fallback: str = "/account") -> RedirectResponse:
    url = fallback
    if next_url and _is_safe_next(next_url):
        url = next_url
    return RedirectResponse(url=url, status_code=303)


# --------- login ---------
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str | None = Query(default=None)):
    """
    Render login form. If already logged in, send them where they intended (or /account).
    """
    if request.session.get("user_id"):
        return _redirect_to_next(next, fallback="/account")

    ctx = {"request": request, "title": "Login", "next": next or ""}
    return request.app.state.templates.TemplateResponse("auth/login.html", ctx)


@router.post("/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    email_norm = (email or "").strip().lower()
    if not email_norm or not password:
        ctx = {
            "request": request,
            "title": "Login",
            "error": "Email and password are required.",
            "next": next or "",
            "email": email_norm,
        }
        return request.app.state.templates.TemplateResponse("auth/login.html", ctx, status_code=400)

    user = db.query(User).filter(User.email == email_norm).first()
    if not user or not verify_password(password, user.password_hash):
        ctx = {
            "request": request,
            "title": "Login",
            "error": "Invalid credentials.",
            "next": next or "",
            "email": email_norm,
        }
        return request.app.state.templates.TemplateResponse("auth/login.html", ctx, status_code=400)

    request.session["user_id"] = user.id
    # Keep a tiny, non-sensitive user object available (your main.py also hydrates state.user fully for templates)
    request.session["user"] = {"id": user.id, "email": user.email}

    return _redirect_to_next(next, fallback="/account")


# --------- register ---------
@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request, next: str | None = Query(default=None)):
    if request.session.get("user_id"):
        return _redirect_to_next(next, fallback="/account")

    ctx = {"request": request, "title": "Create Account", "next": next or ""}
    return request.app.state.templates.TemplateResponse("auth/register.html", ctx)


@router.post("/register")
def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    email_norm = (email or "").strip().lower()

    if not email_norm or not password:
        ctx = {
            "request": request,
            "title": "Create Account",
            "error": "Email and password are required.",
            "next": next or "",
            "email": email_norm,
        }
        return request.app.state.templates.TemplateResponse("auth/register.html", ctx, status_code=400)

    if db.query(User).filter(User.email == email_norm).first():
        ctx = {
            "request": request,
            "title": "Create Account",
            "error": "Email already in use.",
            "next": next or "",
            "email": email_norm,
        }
        return request.app.state.templates.TemplateResponse("auth/register.html", ctx, status_code=400)

    user = User(email=email_norm, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    request.session["user"] = {"id": user.id, "email": user.email}

    return _redirect_to_next(next, fallback="/account")


# --------- logout ---------
@router.post("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user", None)
    return RedirectResponse(url="/", status_code=303)