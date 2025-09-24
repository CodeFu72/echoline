# app/routers/telemetry.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import get_db
from app.models.read_event import ReadEvent

router = APIRouter(prefix="/t", tags=["telemetry"])


def _user_id(request: Request) -> int | None:
    # SessionMiddleware attaches request.session; main.py already installs it
    return request.session.get("user_id")


@router.post("/read")
def mark_read(request: Request, chapter_id: int, db: Session = Depends(get_db)):
    """
    Records that a user opened/read a chapter. Designed to be idempotent.

    Querystring: ?chapter_id=123
    - Anonymous users: we simply return ok (no DB write).
    - Logged-in users: Insert (user_id, chapter_id) with ON CONFLICT DO NOTHING.
    """
    uid = _user_id(request)
    if not uid:
        # Keep the client happy; nothing to store.
        return JSONResponse({"ok": True, "skip": "anon"}, status_code=200)

    # Prefer native Postgres upsert when available
    try:
        stmt = pg_insert(ReadEvent).values(user_id=uid, chapter_id=chapter_id)
        # Match your unique constraint on (user_id, chapter_id)
        stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "chapter_id"])
        db.execute(stmt)
        db.commit()
        return JSONResponse({"ok": True}, status_code=200)
    except Exception:
        # If something about the dialect/import fails, fall back to plain ORM with
        # a guarded insert so we still return 200s (client polling shouldn't 500).
        db.rollback()
        try:
            ev = ReadEvent(user_id=uid, chapter_id=chapter_id)
            db.add(ev)
            db.commit()
        except IntegrityError:
            db.rollback()
        return JSONResponse({"ok": True}, status_code=200)