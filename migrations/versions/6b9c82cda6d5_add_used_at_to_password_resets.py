"""add used_at to password_resets

Revision ID: 6b9c82cda6d5
Revises: 3f82ed7c7636
Create Date: 2025-09-24 23:21:32.658981
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6b9c82cda6d5"
down_revision: Union[str, Sequence[str], None] = "3f82ed7c7636"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add nullable used_at timestamp (tz aware)."""
    op.add_column(
        "password_resets",
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema: remove used_at."""
    op.drop_column("password_resets", "used_at")