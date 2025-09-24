"""shrink chapters.slug to 120 + unique

Revision ID: 1016a829879f
Revises: f137569255bd
Create Date: 2025-09-22 12:57:16.280519
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1016a829879f"
down_revision: Union[str, Sequence[str], None] = "f137569255bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Shrink slug to 120 (safe—you already verified no rows > 120)
    op.alter_column(
        "chapters",
        "slug",
        existing_type=sa.String(length=255),  # prior DB type
        type_=sa.String(length=120),
        existing_nullable=False,
    )

    # 2) Ensure unique constraint exists on slug (name matches older schema)
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'chapters_slug_key'
            """
        )
    ).scalar()
    if not exists:
        op.create_unique_constraint("chapters_slug_key", "chapters", ["slug"])

    # NOTE: no separate non-unique index is created here; the unique
    # constraint already creates a unique index. If your SQLAlchemy model
    # still has index=True on slug, consider removing it to avoid redundancy.


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the unique constraint if present
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'chapters_slug_key'
            """
        )
    ).scalar()
    if exists:
        op.drop_constraint("chapters_slug_key", "chapters", type_="unique")

    # Grow slug back to 255
    op.alter_column(
        "chapters",
        "slug",
        existing_type=sa.String(length=120),
        type_=sa.String(length=255),
        existing_nullable=False,
    )