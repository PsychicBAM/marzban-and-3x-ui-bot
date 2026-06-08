"""Add provisioning status fields to payment_requests.

Revision ID: 0003_payment_request_provisioning_status
Revises: 0002_payment_request_receipt_fields
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_payment_request_provisioning_status"
down_revision: Union[str, None] = "0002_payment_request_receipt_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_requests",
        sa.Column("provisioning_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payment_requests", "provisioning_error")
