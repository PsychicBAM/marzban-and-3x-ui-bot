"""Partial unique index on vpn_account_name for non-deleted accounts.

Revision ID: 0012_vpn_account_name_partial_unique
Revises: 0011_production_features
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_vpn_account_name_partial_unique"
down_revision: Union[str, None] = "0011_production_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE_NAME_INDEX = "uq_vpn_accounts_vpn_account_name_active"
_LEGACY_NAME_INDEX = "uq_vpn_accounts_vpn_account_name"


def upgrade() -> None:
    op.drop_index(_LEGACY_NAME_INDEX, table_name="vpn_accounts")
    op.create_index(
        _ACTIVE_NAME_INDEX,
        "vpn_accounts",
        ["vpn_account_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status != 'deleted'"),
    )


def downgrade() -> None:
    op.drop_index(_ACTIVE_NAME_INDEX, table_name="vpn_accounts")
    op.create_index(
        _LEGACY_NAME_INDEX,
        "vpn_accounts",
        ["vpn_account_name"],
        unique=True,
    )
