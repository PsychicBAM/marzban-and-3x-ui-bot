"""Add reminder metadata fields to notifications.

Revision ID: 0004_notification_fields
Revises: 0003_provisioning_status
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_notification_fields"
down_revision: Union[str, None] = "0003_provisioning_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("reminder_days_before", sa.Integer(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="telegram"),
    )
    op.add_column(
        "notifications",
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.drop_constraint("uq_notifications_account_type", "notifications", type_="unique")
    op.create_unique_constraint(
        "uq_notifications_account_type_days",
        "notifications",
        ["vpn_account_id", "notification_type", "reminder_days_before"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_notifications_account_type_days", "notifications", type_="unique")
    op.create_unique_constraint(
        "uq_notifications_account_type",
        "notifications",
        ["vpn_account_id", "notification_type"],
    )
    op.drop_column("notifications", "details")
    op.drop_column("notifications", "channel")
    op.drop_column("notifications", "reminder_days_before")
