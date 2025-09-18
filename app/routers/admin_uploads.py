# app/routers/admin_uploads.py
import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException

router = APIRouter()

@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    key: str | None = Form(None),
):
    """
    Same-origin upload (multipart/form-data). Bypasses browser CORS.
    Optional 'key' form field lets you choose the destination path.
    """
    s3 = getattr(request.app.state, "s3", None) or None
    bucket = os.getenv("S3_BUCKET", "")
    endpoint = os.getenv("S3_ENDPOINT", "")
    assets_base = (os.getenv("ASSETS_BASE_URL") or "").rstrip("/")

    if not bucket or not endpoint:
        raise HTTPException(status_code=500, detail="S3 not configured")

    # Lazy client (so this router works even if main didn't bind one)
    if s3 is None:
        import boto3
        from botocore.client import Config as BotoConfig
        s3 = boto3.client(
            "s3",
            region_name=os.getenv("S3_REGION", ""),
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY", ""),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY", ""),
            config=BotoConfig(s3={"addressing_style": "virtual"}),
        )

    content_type = file.content_type or "application/octet-stream"

    if key:
        key = key.lstrip("/")
    else:
        # choose a folder by content type, default to 'misc'
        if content_type.startswith("image/"):
            folder = "uploads/images"
        elif content_type in ("text/html", "application/xhtml+xml"):
            folder = "uploads/pages"
        else:
            folder = "uploads/misc"
        original = (file.filename or "file")
        ext = "." + original.rsplit(".", 1)[1].lower() if "." in original else ""
        key = f"{folder}/{uuid.uuid4().hex}{ext}"

    body = await file.read()
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            ACL="public-read",  # server can safely set ACL
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    public_url = f"{assets_base}/{key}" if assets_base else f"{endpoint.rstrip('/')}/{bucket}/{key}"
    return {"key": key, "public_url": public_url}