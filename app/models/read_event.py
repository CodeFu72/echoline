from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base

class ReadEvent(Base):
    __tablename__ = "read_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    chapter = relationship("Chapter")

    __table_args__ = (UniqueConstraint("user_id", "chapter_id", name="uq_user_chapter"),)