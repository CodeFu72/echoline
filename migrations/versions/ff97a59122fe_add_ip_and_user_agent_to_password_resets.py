"""add ip and user_agent to password_resets

Revision ID: ff97a59122fe
Revises: 6b9c82cda6d5
Create Date: 2025-09-24 23:24:58.218882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff97a59122fe'
down_revision: Union[str, Sequence[str], None] = '6b9c82cda6d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ip_address and user_agent to password_resets."""
    op.add_column("password_resets", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("password_resets", sa.Column("user_agent", sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Remove ip_address and user_agent from password_resets."""
    op.drop_column("password_resets", "user_agent")
    op.drop_column("password_resets", "ip_address")