# app/models/password_reset.py
from __future__ import annotations

import datetime as dt
import secrets
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import INET  # safe to import; we guard its usage below

from app.db.base import Base  # your Declarative Base
from app.models.user import User


def _now_utc() -> dt.datetime:
    """Return a timezone-aware UTC timestamp."""
    return dt.datetime.now(dt.timezone.utc)


class PasswordReset(Base):
    """
    A single-use password reset token for a user.

    Typical lifecycle:
      1) Create with `PasswordReset.issue(user_id, ttl_minutes=60)`
      2) Email `token` to the user as a link
      3) When redeemed, call `mark_used()` and commit
    """

    __tablename__ = "password_resets"

    # --- Columns ---
    id: orm.Mapped[int] = orm.mapped_column(
        sa.Integer, primary_key=True, autoincrement=True
    )

    user_id: orm.Mapped[int] = orm.mapped_column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # URL-safe token; keep length generous for different token generators
    token: orm.Mapped[str] = orm.mapped_column(
        sa.String(128), nullable=False, unique=True, index=True
    )

    # Timestamps
    created_at: orm.Mapped[dt.datetime] = orm.mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now_utc, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    expires_at: orm.Mapped[Optional[dt.datetime]] = orm.mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    used_at: orm.Mapped[Optional[dt.datetime]] = orm.mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Metadata about the request (optional)
    # Use INET on Postgres for nicer type; fall back to String elsewhere.
    try:
        ip_address: orm.Mapped[Optional[str]] = orm.mapped_column(INET, nullable=True)
    except Exception:
        ip_address = orm.mapped_column(sa.String(45), nullable=True)  # IPv6 max text length

    user_agent: orm.Mapped[Optional[str]] = orm.mapped_column(sa.String(256), nullable=True)

    # --- Relationships ---
    user: orm.Mapped[User] = orm.relationship(
        "User",
        backref=orm.backref("password_resets", lazy="selectin", cascade="all, delete-orphan"),
    )

    # --- Table args / indexes ---
    __table_args__ = (
        sa.Index("ix_password_resets_user_created_at", "user_id", "created_at"),
    )

    # --- Helpers / Constructors ---

    @staticmethod
    def _generate_token(nbytes: int = 32) -> str:
        """
        Generate a cryptographically strong, URL-safe token.
        nbytes=32 -> ~43-char string.
        """
        return secrets.token_urlsafe(nbytes)

    @classmethod
    def issue(
        cls,
        user_id: int,
        *,
        ttl_minutes: int = 60,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        token_bytes: int = 32,
    ) -> "PasswordReset":
        """
        Create a new reset token object (not added/committed).
        Call session.add() + commit() yourself.
        """
        now = _now_utc()
        expires = now + dt.timedelta(minutes=ttl_minutes) if ttl_minutes > 0 else None
        return cls(
            user_id=user_id,
            token=cls._generate_token(token_bytes),
            created_at=now,
            expires_at=expires,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # --- Instance methods ---

    def is_used(self) -> bool:
        return self.used_at is not None

    def is_expired(self, *, at: Optional[dt.datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        current = at or _now_utc()
        # Normalize naive -> aware (UTC) if needed
        if current.tzinfo is None:
            current = current.replace(tzinfo=dt.timezone.utc)
        return current >= self.expires_at

    def can_redeem(self) -> bool:
        """True if not used and not expired."""
        return (not self.is_used()) and (not self.is_expired())

    def mark_used(self, *, when: Optional[dt.datetime] = None) -> None:
        when = when or _now_utc()
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        self.used_at = when

    # --- Dunder ---

    def __repr__(self) -> str:
        status = "used" if self.is_used() else ("expired" if self.is_expired() else "active")
        return f"<PasswordReset id={self.id} user_id={self.user_id} status={status}>"