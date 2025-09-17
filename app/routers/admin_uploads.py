# app/routers/admin_uploads.py
import os
import uuid
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

router = APIRouter()

@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    s3 = request.app.state.s3
    bucket = request.app.state.s3_bucket
    if not s3 or not bucket:
        raise HTTPException(status_code=500, detail="S3 not configured")

    # choose a folder by content type, default to 'misc'
    content_type = file.content_type or ""
    if content_type.startswith("image/"):
        folder = "uploads/images"
    elif content_type in ("text/html", "application/xhtml+xml"):
        folder = "uploads/pages"
    else:
        folder = "uploads/misc"

    # sanitize filename (very light)
    original = file.filename or "file"
    ext = ""
    if "." in original:
        ext = "." + original.rsplit(".", 1)[1].lower()
    key = f"{folder}/{uuid.uuid4().hex}{ext}"

    body = await file.read()
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type or "application/octet-stream",
            ACL="public-read",  # ensure the object is public
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    # Build a public URL using your ASSETS_BASE_URL
    assets_base = (os.getenv("ASSETS_BASE_URL") or "").rstrip("/")
    url = f"{assets_base}/{key}" if assets_base else key
    return {"key": key, "url": url}