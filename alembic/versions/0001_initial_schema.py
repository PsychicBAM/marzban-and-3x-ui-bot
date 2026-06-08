"""Initial database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("vpn_account_name", sa.String(length=64), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)
    op.create_index("ix_users_vpn_account_name", "users", ["vpn_account_name"], unique=False)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("traffic_limit_gb", sa.Integer(), nullable=False),
        sa.Column("ip_limit", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("issuing_mode", sa.String(length=16), nullable=False, server_default="both"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vpn_panels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("panel_type", sa.String(length=16), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("inbound_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vpn_panels_panel_type", "vpn_panels", ["panel_type"], unique=False)

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_logs_admin_telegram_id", "admin_logs", ["admin_telegram_id"], unique=False)
    op.create_index("ix_admin_logs_action_type", "admin_logs", ["action_type"], unique=False)

    op.create_table(
        "vpn_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("vpn_account_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("traffic_used_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("traffic_limit_gb", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ip_limit", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("marzban_username", sa.String(length=64), nullable=True),
        sa.Column("marzban_subscription_url", sa.String(length=1024), nullable=True),
        sa.Column("marzban_status", sa.String(length=32), nullable=True),
        sa.Column("xui_client_uuid", sa.String(length=64), nullable=True),
        sa.Column("xui_email", sa.String(length=128), nullable=True),
        sa.Column("xui_subscription_url", sa.String(length=1024), nullable=True),
        sa.Column("xui_status", sa.String(length=32), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vpn_accounts_user_id", "vpn_accounts", ["user_id"], unique=False)
    op.create_index("ix_vpn_accounts_vpn_account_name", "vpn_accounts", ["vpn_account_name"], unique=False)
    op.create_index("ix_vpn_accounts_status", "vpn_accounts", ["status"], unique=False)

    op.create_table(
        "payment_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("vpn_account_id", sa.Integer(), nullable=True),
        sa.Column("request_type", sa.String(length=16), nullable=False, server_default="purchase"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("receipt_file_id", sa.String(length=255), nullable=True),
        sa.Column("receipt_message_id", sa.Integer(), nullable=True),
        sa.Column("processed_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vpn_account_id"], ["vpn_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_requests_user_id", "payment_requests", ["user_id"], unique=False)
    op.create_index("ix_payment_requests_vpn_account_id", "payment_requests", ["vpn_account_id"], unique=False)
    op.create_index("ix_payment_requests_status", "payment_requests", ["status"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vpn_account_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vpn_account_id"], ["vpn_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vpn_account_id", "notification_type", name="uq_notifications_account_type"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_vpn_account_id", "notifications", ["vpn_account_id"], unique=False)


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("payment_requests")
    op.drop_table("vpn_accounts")
    op.drop_table("admin_logs")
    op.drop_table("settings")
    op.drop_table("vpn_panels")
    op.drop_table("plans")
    op.drop_table("users")
