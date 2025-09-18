# app/routers/admin/router.py
import os
import json
import re
import unicodedata
from typing import Optional

import markdown2
from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    HTTPException,
    UploadFile,
    File,
    Body,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chapter import Chapter

# S3 presign
import boto3
from botocore.config import Config as BotoConfig

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------- Helpers ----------------
_slug_strip_re = re.compile(r"[^\w\s-]")
_slug_hyphenate_re = re.compile(r"[-\s]+")


def slugify(value: str) -> str:
    if not value:
        return ""
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
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
        # Keep raw if not valid JSON
        return v


def _apply_optional_attrs(ch: Chapter, **kwargs):
    for key, val in kwargs.items():
        if hasattr(ch, key):
            setattr(ch, key, val)


def _tpl(request: Request):
    # Use the shared Jinja2Templates configured in main.py
    return request.app.state.templates


def _s3_client_from_env():
    bucket = os.getenv("S3_BUCKET")
    region = os.getenv("S3_REGION")
    endpoint = os.getenv("S3_ENDPOINT")
    access_key = os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("S3_SECRET_KEY")
    if not all([bucket, region, endpoint, access_key, secret_key]):
        raise HTTPException(status_code=500, detail="S3 env not fully configured")
    s3 = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(s3={"addressing_style": "virtual"}),
    )
    return s3, bucket, endpoint
# -----------------------------------------


# --------------- Dashboard ----------------
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    latest = (
        db.query(Chapter)
        .order_by(Chapter.created_at.desc(), Chapter.id.desc())
        .limit(20)
        .all()
    )
    return _tpl(request).TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "latest": latest, "title": "Admin"},
    )
# -----------------------------------------


# --------------- Create -------------------
@router.get("/chapters/new", response_class=HTMLResponse)
def chapter_new(request: Request):
    # Single form template (with uploader helpers)
    return _tpl(request).TemplateResponse(
        "admin/chapter_form.html",
        {
            "request": request,
            "mode": "new",
            "form": {},
            "error": None,
            "title": "New Chapter",
        },
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
    meta_text: Optional[str] = Form(None),  # legacy field name
):
    # prefer "meta" but accept "meta_text"
    meta_value = meta if (meta is not None and meta.strip() != "") else meta_text

    final_slug = (slug or "").strip() or slugify(title)
    if not final_slug:
        return _tpl(request).TemplateResponse(
            "admin/chapter_form.html",
            {
                "request": request,
                "mode": "new",
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
                    "meta": meta_value,
                },
            },
            status_code=400,
        )

    # Unique slug
    if db.query(Chapter).filter(Chapter.slug == final_slug).first():
        return _tpl(request).TemplateResponse(
            "admin/chapter_form.html",
            {
                "request": request,
                "mode": "new",
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
                    "meta": meta_value,
                },
            },
            status_code=400,
        )

    ch = Chapter(title=title.strip(), slug=final_slug, content=body)

    _apply_optional_attrs(
        ch,
        subtitle=(subtitle or None),
        hero_key=(hero_key or None),
        reel_url=(reel_url or None),
        teaser=(teaser or None),
        ambient_url=(ambient_url or None),
        display_order=to_int_or_none(display_order),
        meta=parse_json_or_none(meta_value),
    )

    db.add(ch)
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)
# -----------------------------------------


# --------------- Edit / Update ------------
@router.get("/chapters/{chapter_id}/edit", response_class=HTMLResponse)
def chapter_edit(chapter_id: int, request: Request, db: Session = Depends(get_db)):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        return _tpl(request).TemplateResponse(
            "pages/not_found.html",
            {"request": request, "title": "Not found"},
            status_code=404,
        )

    form = {
        "title": ch.title,
        "slug": ch.slug,
        "subtitle": getattr(ch, "subtitle", None),
        "display_order": getattr(ch, "display_order", None),
        "hero_key": getattr(ch, "hero_key", None),
        "teaser": getattr(ch, "teaser", None),
        "body": ch.content,
        "ambient_url": getattr(ch, "ambient_url", None),
        "reel_url": getattr(ch, "reel_url", None),
        # always provide a string for the textarea called "meta"
        "meta": (
            ch.meta
            if isinstance(ch.meta, str)
            else json.dumps(ch.meta or {}, ensure_ascii=False)
        ),
    }

    return _tpl(request).TemplateResponse(
        "admin/chapter_form.html",
        {
            "request": request,
            "mode": "edit",
            "chapter": ch,
            "form": form,
            "error": None,
            "title": f"Edit · {ch.title}",
        },
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
    meta_text: Optional[str] = Form(None),  # legacy
):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        return _tpl(request).TemplateResponse(
            "pages/not_found.html",
            {"request": request, "title": "Not found"},
            status_code=404,
        )

    meta_value = meta if (meta is not None and meta.strip() != "") else meta_text

    new_slug = (slug or "").strip() or slugify(title) or ch.slug
    if new_slug != ch.slug:
        exists = db.query(Chapter).filter(Chapter.slug == new_slug).first()
        if exists:
            return _tpl(request).TemplateResponse(
                "admin/chapter_form.html",
                {
                    "request": request,
                    "mode": "edit",
                    "chapter": ch,
                    "form": {
                        "title": title,
                        "slug": slug,
                        "subtitle": subtitle,
                        "display_order": display_order,
                        "hero_key": hero_key,
                        "teaser": teaser,
                        "body": body,
                        "ambient_url": ambient_url,
                        "reel_url": reel_url,
                        "meta": meta_value,
                    },
                    "error": f"Slug '{new_slug}' is already in use.",
                    "title": f"Edit · {ch.title}",
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
        meta=parse_json_or_none(meta_value),
    )

    db.add(ch)
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)
# -----------------------------------------


# --------------- Upload Presign -----------
@router.post("/uploads/presign")
def presign_upload(payload: dict = Body(...)):
    """
    Returns:
    {
      "upload_url": "<pre-signed PUT>",
      "public_url": "<https://.../bucket/key>"
    }
    """
    key = (payload or {}).get("key", "").lstrip("/")
    content_type = (payload or {}).get("content_type") or "application/octet-stream"
    if not key:
        raise HTTPException(status_code=400, detail="Missing 'key'")

    s3, bucket, endpoint = _s3_client_from_env()

    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
            "ACL": "public-read",
        },
        ExpiresIn=300,
    )

    assets_base = (os.getenv("ASSETS_BASE_URL") or "").rstrip("/")
    public_url = (
        f"{assets_base}/{key}"
        if assets_base
        else f"{endpoint.rstrip('/')}/{bucket}/{key}"
    )

    return JSONResponse({"upload_url": upload_url, "public_url": public_url})


# --------------- Upload Fallback (POST) ---
@router.post("/uploads/upload")
async def upload_via_server(
    file: UploadFile = File(...),
    key: Optional[str] = Form(None),
):
    key = (key or (file.filename or "upload")).lstrip("/")
    s3, bucket, endpoint = _s3_client_from_env()
    body = await file.read()
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=file.content_type or "application/octet-stream",
            ACL="public-read",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    assets_base = (os.getenv("ASSETS_BASE_URL") or "").rstrip("/")
    public_url = (
        f"{assets_base}/{key}"
        if assets_base
        else f"{endpoint.rstrip('/')}/{bucket}/{key}"
    )
    return JSONResponse({"key": key, "public_url": public_url})
# -----------------------------------------