"""create chapters table

Revision ID: 18cbf1d02a76
Revises:
Create Date: 2025-09-12 19:30:16.461175
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "18cbf1d02a76"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create table if it doesn't exist (idempotent-ish for our reset)
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=240), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hero_key", sa.String(length=240), nullable=True),
        sa.Column("reel_url", sa.String(length=400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_chapters_slug", "chapters", ["slug"], unique=True)


def downgrade() -> None:
    # Use IF EXISTS so downgrade doesn't fail when objects are missing
    op.execute("DROP INDEX IF EXISTS ix_chapters_slug;")
    op.execute("DROP TABLE IF EXISTS chapters;")