# app/utils/authz.py
from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import HTTPException, Request

ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "grayfenrir@protonmail.com").strip().lower()

def require_admin(request: Request) -> None:
    """
    - If not logged in: redirect to /auth/login?next=<current-path>
    - If logged in but not the admin email: 403
    - If the admin: allow through (return None)
    """
    user = request.session.get("user")
    if not user:
        # redirect to login with a 'next' param back to where they wanted to go
        next_path = request.url.path or "/"
        raise HTTPException(
            status_code=307,
            headers={"Location": f"/auth/login?next={quote(next_path)}"}
        )

    email = (user.get("email") or "").strip().lower()
    if email != ADMIN_EMAIL:
        # logged in, but not the admin
        raise HTTPException(status_code=403, detail="Forbidden")