# app/routers/auth.py
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.password_reset import PasswordReset
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


# ========= helpers =========
def _is_safe_next(next_url: str | None) -> bool:
    """
    Only allow local/relative redirects. Blocks absolute/externals.
    Accepts "" or None as safe (meaning: no redirect).
    """
    if not next_url:
        return True
    parts = urlparse(next_url)
    return (not parts.scheme and not parts.netloc and next_url.startswith("/"))


def _redirect_to_next(next_url: str | None, fallback: str = "/account") -> RedirectResponse:
    url = fallback
    if next_url and _is_safe_next(next_url):
        url = next_url
    return RedirectResponse(url=url, status_code=303)


def _now() -> datetime:
    # alembic/models use UTC, keep consistent
    return datetime.utcnow()


def _absolute_url(request: Request, path: str) -> str:
    """
    Build an absolute URL for email links.
    Respects X-Forwarded-Proto/Host when behind a proxy if your ASGI server forwards them.
    """
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.hostname))
    return f"{scheme}://{host}{path}"


def _send_password_reset_email_stub(to_email: str, link: str) -> None:
    """
    Temporary email sender: prints to server log.
    Replace with real mailer (e.g., FastMail, SES, SendGrid) later.
    """
    print(f"[Password Reset] To: {to_email}\n  Link: {link}\n")  # noqa: T201


# ========= login =========
@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    next: str | None = Query(default=None),
    reset: int | None = Query(default=None),
):
    """
    Render login form. If already logged in, send them where they intended (or /account).
    Shows a success banner when `?reset=1` is present (after password reset).
    """
    if request.session.get("user_id"):
        return _redirect_to_next(next, fallback="/account")

    success_msg = "Password updated. You can sign in now." if (reset and int(reset) == 1) else None
    ctx = {
        "request": request,
        "title": "Login",
        "next": next or "",
        "success": success_msg,   # Template can render a green banner if this exists
    }
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
    request.session["user"] = {"id": user.id, "email": user.email}

    return _redirect_to_next(next, fallback="/account")


# ========= register =========
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

    if len(password) < 8:
        ctx = {
            "request": request,
            "title": "Create Account",
            "error": "Password must be at least 8 characters.",
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


# ========= logout =========
@router.post("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user", None)
    return RedirectResponse(url="/", status_code=303)


# ========= forgot password =========
@router.get("/forgot", response_class=HTMLResponse)
def forgot_form(request: Request):
    """
    Show the 'send reset link' form.
    """
    ctx = {"request": request, "title": "Forgot Password"}
    return request.app.state.templates.TemplateResponse("auth/forgot.html", ctx)


@router.post("/forgot", response_class=HTMLResponse)
def forgot_submit(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Accepts an email, creates (or refreshes) a reset token, and 'sends' an email.
    Always returns the same success message to avoid user enumeration.
    """
    email_norm = (email or "").strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()

    if user:
        # Clear any previous tokens for this user (simple rate-limiting and avoids confusion)
        db.query(PasswordReset).filter(PasswordReset.user_id == user.id).delete()

        token = secrets.token_urlsafe(32)
        expires_at = _now() + timedelta(hours=2)

        pr = PasswordReset(user_id=user.id, token=token, expires_at=expires_at)
        db.add(pr)
        db.commit()

        # Build absolute reset link
        link = _absolute_url(request, f"/auth/reset?token={token}")
        # Send (stub logs to console)
        _send_password_reset_email_stub(user.email, link)

    # Respond the same either way
    ctx = {
        "request": request,
        "title": "Forgot Password",
        "message": "If that email exists, we’ve sent a reset link. Check your inbox.",
    }
    return request.app.state.templates.TemplateResponse("auth/forgot.html", ctx)


# ========= reset password =========
@router.get("/reset", response_class=HTMLResponse)
def reset_form(request: Request, token: str | None = Query(default=None), db: Session = Depends(get_db)):
    """
    Show the 'set new password' form if token is valid.
    """
    if not token:
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "Missing token.",
            "token": "",
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    pr = (
        db.query(PasswordReset)
        .filter(PasswordReset.token == token)
        .filter(PasswordReset.used_at.is_(None))
        .first()
    )

    if not pr or pr.expires_at < _now():
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "This reset link is invalid or has expired. Please request a new one.",
            "token": "",
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    ctx = {"request": request, "title": "Reset Password", "token": token}
    return request.app.state.templates.TemplateResponse("auth/reset.html", ctx)


@router.post("/reset", response_class=HTMLResponse)
def reset_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Validate token, set the new password, and mark the token as used.
    On success, redirect to login with ?reset=1 so the login page can show a green banner.
    """
    if not token:
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "Missing token.",
            "token": "",
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    pr = (
        db.query(PasswordReset)
        .filter(PasswordReset.token == token)
        .filter(PasswordReset.used_at.is_(None))
        .first()
    )

    if not pr or pr.expires_at < _now():
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "This reset link is invalid or has expired. Please request a new one.",
            "token": "",
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    if not password or len(password) < 8:
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "Password must be at least 8 characters.",
            "token": token,
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    if password != password_confirm:
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "Passwords do not match.",
            "token": token,
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    # Set new password
    user = db.query(User).filter(User.id == pr.user_id).first()
    if not user:
        ctx = {
            "request": request,
            "title": "Reset Password",
            "error": "Account not found.",
            "token": "",
        }
        return request.app.state.templates.TemplateResponse("auth/reset.html", ctx, status_code=400)

    user.password_hash = hash_password(password)
    pr.used_at = _now()
    db.add(user)
    db.add(pr)
    db.commit()

    # Optional: also invalidate any other outstanding tokens for this user
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id,
        PasswordReset.used_at.is_(None)
    ).delete()
    db.commit()

    # Success: send them to login with a banner
    return RedirectResponse(url="/auth/login?reset=1", status_code=303)