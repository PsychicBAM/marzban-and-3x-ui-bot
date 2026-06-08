"""Add payment request receipt and amount fields.

Revision ID: 0002_payment_request_receipt_fields
Revises: 0001_initial_schema
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_payment_request_receipt_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_requests",
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "payment_requests",
        sa.Column("receipt_file_type", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "payment_requests",
        sa.Column("user_comment", sa.Text(), nullable=True),
    )
    op.add_column(
        "payment_requests",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payment_requests",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("payment_requests", "amount", server_default=None)


def downgrade() -> None:
    op.drop_column("payment_requests", "rejected_at")
    op.drop_column("payment_requests", "approved_at")
    op.drop_column("payment_requests", "user_comment")
    op.drop_column("payment_requests", "receipt_file_type")
    op.drop_column("payment_requests", "amount")
