"""Customer events, support tickets, admin daily report settings.

Revision ID: 0011_production_features
Revises: 0010_user_language
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_production_features"
down_revision: Union[str, None] = "0010_user_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vpn_account_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vpn_account_id"], ["vpn_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_events_user_id", "customer_events", ["user_id"])
    op.create_index("ix_customer_events_created_at", "customer_events", ["created_at"])

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("topic", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_index("ix_support_tickets_updated_at", "support_tickets", ["updated_at"])

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("sender_type", sa.String(length=16), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=True),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("photo_file_id", sa.String(length=255), nullable=True),
        sa.Column("document_file_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])

    op.create_table(
        "admin_report_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("report_hour", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("report_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO admin_report_settings (is_enabled, report_hour, report_minute) "
            "VALUES (true, 9, 0)"
        )
    )


def downgrade() -> None:
    op.drop_table("support_messages")
    op.drop_table("support_tickets")
    op.drop_table("customer_events")
    op.drop_table("admin_report_settings")
