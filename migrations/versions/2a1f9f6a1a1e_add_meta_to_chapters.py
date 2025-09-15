"""add meta to chapters

Revision ID: 2a1f9f6a1a1e
Revises: 18cbf1d02a76
Create Date: 2025-09-15 01:44:39.038544

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a1f9f6a1a1e"
down_revision: Union[str, Sequence[str], None] = "18cbf1d02a76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.add_column(sa.Column("display_order", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("teaser", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ambient_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("meta", sa.JSON(), nullable=True))

        batch_op.create_index("ix_chapters_display_order", ["display_order"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.drop_index("ix_chapters_display_order")
        batch_op.drop_column("meta")
        batch_op.drop_column("ambient_url")
        batch_op.drop_column("teaser")
        batch_op.drop_column("display_order")