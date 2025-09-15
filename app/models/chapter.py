# app/models/chapter.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, func
from app.db.base import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(120), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(240), nullable=True)

    # NEW canonical text field
    content = Column(Text, nullable=False)

    hero_key = Column(String(240), nullable=True)
    reel_url = Column(String(400), nullable=True)

    # Metadata fields (from migration)
    display_order = Column(Integer, nullable=True, index=True)
    teaser = Column(Text, nullable=True)
    ambient_url = Column(String(1024), nullable=True)
    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())