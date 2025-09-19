# app/routers/about.py
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

def _templates(request: Request):
    return request.app.state.templates

@router.get("/", response_class=HTMLResponse)
def about(request: Request):
    year = datetime.now().year
    return _templates(request).TemplateResponse(
        "pages/about.html",
        {"request": request, "title": "About", "year": year},
    )