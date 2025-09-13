from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(
        "pages/about.html",
        {"request": request, "title": "About • Echo Line"}
    )