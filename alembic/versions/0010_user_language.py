"""User language preference for customer UI.

Revision ID: 0010_user_language
Revises: 0009_referrals
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_user_language"
down_revision: Union[str, None] = "0009_referrals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language_code", sa.String(length=8), nullable=False, server_default="ru"),
    )


def downgrade() -> None:
    op.drop_column("users", "language_code")
