"""Promo codes and payment request discounts.

Revision ID: 0008_promo_codes
Revises: 0007_broadcasts
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_promo_codes"
down_revision: Union[str, None] = "0007_broadcasts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("discount_type", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("max_uses_per_user", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("applies_to_plan_id", sa.Integer(), nullable=True),
        sa.Column("applies_to_request_type", sa.String(length=16), nullable=True),
        sa.Column("new_users_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["applies_to_plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_promo_codes_code", "promo_codes", ["code"])
    op.create_index("ix_promo_codes_is_active", "promo_codes", ["is_active"])

    op.create_table(
        "promo_code_redemptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promo_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payment_request_id", sa.Integer(), nullable=True),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("extra_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"]),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_codes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promo_code_redemptions_promo_code_id", "promo_code_redemptions", ["promo_code_id"])
    op.create_index("ix_promo_code_redemptions_user_id", "promo_code_redemptions", ["user_id"])

    op.add_column("payment_requests", sa.Column("promo_code_id", sa.Integer(), nullable=True))
    op.add_column("payment_requests", sa.Column("original_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("payment_requests", sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("payment_requests", sa.Column("final_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "payment_requests",
        sa.Column("extra_days_from_promo", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_payment_requests_promo_code_id",
        "payment_requests",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_payment_requests_promo_code_id", "payment_requests", type_="foreignkey")
    op.drop_column("payment_requests", "extra_days_from_promo")
    op.drop_column("payment_requests", "final_amount")
    op.drop_column("payment_requests", "discount_amount")
    op.drop_column("payment_requests", "original_amount")
    op.drop_column("payment_requests", "promo_code_id")
    op.drop_index("ix_promo_code_redemptions_user_id", table_name="promo_code_redemptions")
    op.drop_index("ix_promo_code_redemptions_promo_code_id", table_name="promo_code_redemptions")
    op.drop_table("promo_code_redemptions")
    op.drop_index("ix_promo_codes_is_active", table_name="promo_codes")
    op.drop_index("ix_promo_codes_code", table_name="promo_codes")
    op.drop_table("promo_codes")
