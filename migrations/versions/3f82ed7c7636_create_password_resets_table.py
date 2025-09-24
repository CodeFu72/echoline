"""create password_resets table

Revision ID: 3f82ed7c7636
Revises: 1016a829879f
Create Date: 2025-09-24 21:16:37.617755
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f82ed7c7636"
down_revision: Union[str, Sequence[str], None] = "1016a829879f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # helpful indexes
    op.create_index(
        "ix_password_resets_token", "password_resets", ["token"], unique=True
    )
    op.create_index(
        "ix_password_resets_user_created",
        "password_resets",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_password_resets_user_created", table_name="password_resets")
    op.drop_index("ix_password_resets_token", table_name="password_resets")
    op.drop_table("password_resets")