# app/routers/account.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.user import User
from app.models.read_event import ReadEvent
from app.models.chapter import Chapter

router = APIRouter(prefix="/account", tags=["account"])


def _templates(request: Request):
    return request.app.state.templates


def _me(request: Request, db: Session) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    # SQLAlchemy 2.x: Session.get(Model, pk)
    return db.get(User, uid)


@router.get("", response_class=HTMLResponse)
def account_home(request: Request, db: Session = Depends(get_db)):
    me = _me(request, db)
    if not me:
        # Let our app-level 401 handler bounce users to /auth/login, but do it explicitly here for clarity.
        return RedirectResponse(url="/auth/login?next=/account", status_code=303)

    # Recent reading activity (order by the timestamp column that actually exists)
    events = (
        db.query(ReadEvent)
        .filter(ReadEvent.user_id == me.id)
        .order_by(desc(ReadEvent.created_at))
        .limit(15)
        .all()
    )

    # Join in chapter titles (guard against empty list to avoid IN () query)
    chapter_ids = [e.chapter_id for e in events]
    chapters = {}
    if chapter_ids:
        chapters = {
            c.id: c
            for c in db.query(Chapter).filter(Chapter.id.in_(chapter_ids)).all()
        }

    return _templates(request).TemplateResponse(
        "account/index.html",
        {
            "request": request,
            "title": "Your Reading",
            "me": me,
            "events": events,
            "chapters": chapters,
        },
    )