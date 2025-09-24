# app/main.py
import os
import hashlib
from datetime import datetime

import markdown2
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

# S3 presign
import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

# ---- Load env (.env) ----
load_dotenv()

# ---- DB + models ----
from app.db.session import get_db
from app.models.chapter import Chapter
from app.models.user import User

# ---- Routers ----
from app.routers.chapters import router as chapters_router
from app.routers.admin import router as admin_router
from app.routers import about
from app.routers import auth as auth_router
from app.routers import account as account_router
from app.routers import telemetry
from app.routers import extras as extras_router

app = FastAPI(title="Echo Line")

# =============================================================================
# Middleware
# =============================================================================

class UserAttachMiddleware(BaseHTTPMiddleware):
    """
    Attaches request.state.user = {'id', 'email'} if session has 'user_id'.
    MUST run *after* SessionMiddleware, so we add it to the stack *before*
    SessionMiddleware (making it the inner middleware).
    """
    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        uid = None
        try:
            # Will raise AssertionError if SessionMiddleware hasn't run.
            uid = request.session.get("user_id")
        except AssertionError:
            uid = None

        if uid:
            db = None
            try:
                db = next(get_db())
                row = db.query(User.id, User.email).filter(User.id == uid).first()
                if row:
                    request.state.user = {"id": row.id, "email": row.email}
            except Exception:
                request.state.user = None
            finally:
                if db:
                    try:
                        db.close()
                    except Exception:
                        pass

        return await call_next(request)

# Order matters:
# 1) Add UserAttach first (inner)
app.add_middleware(UserAttachMiddleware)
# 2) Then sessions (outer of user attach)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"))
# 3) Then gzip etc.
app.add_middleware(GZipMiddleware, minimum_size=500)

# Optional: redirect HTML GET 401s to /auth/login?next=...
@app.exception_handler(401)
async def handle_unauthorized(request: Request, exc: HTTPException):
    accepts_html = "text/html" in (request.headers.get("accept") or "")
    if request.method == "GET" and accepts_html:
        next_path = str(request.url.path)
        if request.url.query:
            next_path += f"?{request.url.query}"
        return RedirectResponse(url=f"/auth/login?next={next_path}", status_code=303)
    return JSONResponse({"detail": "Unauthorized"}, status_code=401)

# =============================================================================
# Static & Templates
# =============================================================================
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.state.templates = templates

# ---- Jinja helpers ----
ASSETS_BASE = os.getenv("ASSETS_BASE_URL", "").rstrip("/")
templates.env.globals["ASSETS_BASE"] = ASSETS_BASE

def asset(key: str) -> str:
    """Build a full asset URL (absolute kept; otherwise ASSETS_BASE or /static)."""
    if not key:
        return ""
    k = key.strip()
    if k.startswith("http://") or k.startswith("https://"):
        return k
    base = ASSETS_BASE.rstrip("/")
    return f"{base}/{k.lstrip('/')}" if base else f"/static/{k.lstrip('/')}"

templates.env.globals["asset"] = asset

def md_filter(text: str) -> str:
    """Markdown → safe HTML (basic extras)."""
    if not text:
        return ""
    return markdown2.markdown(text, extras=["fenced-code-blocks", "tables", "strike", "smarty"])

templates.env.filters["md"] = md_filter

# Footer/helper: use as {{ (now().year if now else '') }}
templates.env.globals["now"] = lambda: datetime.now()

# ---- CSS cache-busting (no client JS) ----
def _static_file_version(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except Exception:
        try:
            return str(int(os.path.getmtime(path)))
        except Exception:
            return "dev"

SITE_CSS_PATH = os.path.join("static", "css", "site.css")
STATIC_VERSION = _static_file_version(SITE_CSS_PATH)
templates.env.globals["STATIC_VERSION"] = STATIC_VERSION

# =============================================================================
# S3 / Linode Object Storage presign
# =============================================================================
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")  # e.g. https://us-southeast-1.linodeobjects.com
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")

def _s3_client():
    if not (S3_REGION and S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY and S3_BUCKET):
        raise RuntimeError("S3 env is missing. Check S3_REGION, S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET.")
    return boto3.client(
        "s3",
        region_name=S3_REGION,
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=BotoConfig(s3={"addressing_style": "virtual"}),
    )

def _public_url_for(key: str) -> str:
    key = key.lstrip("/")
    return f"{ASSETS_BASE.rstrip('/')}/{key}" if ASSETS_BASE else f"{S3_ENDPOINT.rstrip('/')}/{S3_BUCKET}/{key}"

def _presign_put(key: str, content_type: str, expires: int = 300) -> dict:
    """
    Return {'upload_url', 'public_url'} for a direct PUT upload.
    NOTE: No ACL in signature (avoids needing extra headers on the PUT).
    Make sure your bucket policy permits public read, or serve via ASSETS_BASE.
    """
    s3 = _s3_client()
    key = key.lstrip("/")
    try:
        upload_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": key,
                "ContentType": content_type or "application/octet-stream",
            },
            ExpiresIn=expires,
        )
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Presign failed: {e}") from e
    return {"upload_url": upload_url, "public_url": _public_url_for(key)}

@app.post("/admin/uploads/presign")
def presign_upload(payload: dict = Body(...)):
    """
    Body: {"key":"path/in/bucket/file.ext","content_type":"type"}
    Returns: {"upload_url":"...","public_url":"..."}
    """
    key = (payload or {}).get("key", "").strip()
    ctype = (payload or {}).get("content_type", "application/octet-stream")
    if not key:
        return JSONResponse({"error": "Missing key"}, status_code=400)
    try:
        out = _presign_put(key, ctype)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# =============================================================================
# Routes
# =============================================================================
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    latest = db.query(Chapter).order_by(Chapter.created_at.desc()).first()
    latest_list = db.query(Chapter).order_by(Chapter.created_at.desc()).limit(9).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Echo Line", "latest": latest, "latest_list": latest_list},
    )

# Routers
app.include_router(chapters_router, prefix="/chapters", tags=["chapters"])
app.include_router(admin_router)
app.include_router(about.router, prefix="/about")
app.include_router(auth_router.router)      # /auth/...
app.include_router(account_router.router)   # /account
app.include_router(telemetry.router)
app.include_router(extras_router.router)