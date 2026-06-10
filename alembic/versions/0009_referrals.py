"""Referral program tables and user referral fields.

Revision ID: 0009_referrals
Revises: 0008_promo_codes
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_referrals"
down_revision: Union[str, None] = "0008_promo_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("referred_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_referred_by_user_id",
        "users",
        "users",
        ["referred_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    op.create_table(
        "referral_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reward_days_per_paid_referral", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("milestone_paid_referrals", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("milestone_reward_days", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("min_purchase_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("count_only_first_paid_purchase", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_zero_amount_rewards", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("apply_reward_automatically", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO referral_settings (
            is_enabled,
            reward_days_per_paid_referral,
            milestone_paid_referrals,
            milestone_reward_days,
            min_purchase_amount,
            count_only_first_paid_purchase,
            allow_zero_amount_rewards,
            apply_reward_automatically
        ) VALUES (true, 10, 12, 180, 0, true, false, true)
        """
    )

    op.create_table(
        "referral_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_user_id", sa.Integer(), nullable=False),
        sa.Column("referred_user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="link"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="registered"),
        sa.Column("payment_request_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_user_id", name="uq_referral_events_referred_user"),
    )

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_user_id", sa.Integer(), nullable=False),
        sa.Column("referred_user_id", sa.Integer(), nullable=True),
        sa.Column("payment_request_id", sa.Integer(), nullable=True),
        sa.Column("reward_type", sa.String(length=16), nullable=False),
        sa.Column("reward_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("applied_vpn_account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_vpn_account_id"], ["vpn_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_referral_rewards_per_referral",
        "referral_rewards",
        ["referred_user_id"],
        unique=True,
        postgresql_where=sa.text("reward_type = 'per_referral'"),
    )
    op.create_index(
        "uq_referral_rewards_milestone",
        "referral_rewards",
        ["referrer_user_id"],
        unique=True,
        postgresql_where=sa.text("reward_type = 'milestone'"),
    )


def downgrade() -> None:
    op.drop_index("uq_referral_rewards_milestone", table_name="referral_rewards")
    op.drop_index("uq_referral_rewards_per_referral", table_name="referral_rewards")
    op.drop_table("referral_rewards")
    op.drop_table("referral_events")
    op.drop_table("referral_settings")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_constraint("fk_users_referred_by_user_id", "users", type_="foreignkey")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
