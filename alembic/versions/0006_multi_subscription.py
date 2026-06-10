"""Multi-subscription: display names and purchase targets.

Revision ID: 0006_multi_subscription
Revises: 0005_widen_pr_status
Create Date: 2026-06-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_multi_subscription"
down_revision: Union[str, None] = "0005_widen_pr_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Renames pre-migration / old test-data duplicates so a global unique index can be applied.
_DEDUPE_VPN_ACCOUNT_NAMES_SQL = """
WITH ranked AS (
    SELECT
        id,
        vpn_account_name,
        ROW_NUMBER() OVER (
            PARTITION BY vpn_account_name
            ORDER BY
                CASE
                    WHEN deleted_at IS NULL AND status <> 'deleted' THEN 0
                    ELSE 1
                END,
                CASE status
                    WHEN 'active' THEN 0
                    WHEN 'disabled' THEN 1
                    WHEN 'expired' THEN 2
                    ELSE 3
                END,
                created_at DESC NULLS LAST,
                id DESC
        ) AS rn
    FROM vpn_accounts
),
to_rename AS (
    SELECT
        id,
        CASE
            WHEN char_length(vpn_account_name) + char_length('_old_' || id::text) <= 64
            THEN vpn_account_name || '_old_' || id::text
            ELSE left(vpn_account_name, 64 - char_length('_old_' || id::text))
                || '_old_' || id::text
        END AS new_name
    FROM ranked
    WHERE rn > 1
)
UPDATE vpn_accounts AS va
SET vpn_account_name = tr.new_name
FROM to_rename AS tr
WHERE va.id = tr.id;
"""

# Safety pass if a renamed value collides with an unrelated existing row name.
_FORCE_UNIQUE_VPN_ACCOUNT_NAMES_SQL = """
UPDATE vpn_accounts AS va
SET vpn_account_name = 'acct_' || va.id::text
WHERE va.id IN (
    SELECT dup.id
    FROM vpn_accounts AS dup
    INNER JOIN (
        SELECT vpn_account_name
        FROM vpn_accounts
        GROUP BY vpn_account_name
        HAVING COUNT(*) > 1
    ) AS names ON names.vpn_account_name = dup.vpn_account_name
);
"""


def upgrade() -> None:
    op.add_column(
        "vpn_accounts",
        sa.Column("display_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "vpn_accounts",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "payment_requests",
        sa.Column("target_vpn_account_name", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payment_requests",
        sa.Column("target_display_name", sa.String(length=128), nullable=True),
    )

    # Old test data / pre-migration rows may share vpn_account_name; keep the best row
    # per name and rename other duplicates to {name}_old_{id} before the unique index.
    op.execute(sa.text(_DEDUPE_VPN_ACCOUNT_NAMES_SQL))
    op.execute(sa.text(_FORCE_UNIQUE_VPN_ACCOUNT_NAMES_SQL))

    op.create_index(
        "uq_vpn_accounts_vpn_account_name",
        "vpn_accounts",
        ["vpn_account_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_vpn_accounts_vpn_account_name", table_name="vpn_accounts")
    op.drop_column("payment_requests", "target_display_name")
    op.drop_column("payment_requests", "target_vpn_account_name")
    op.drop_column("vpn_accounts", "is_primary")
    op.drop_column("vpn_accounts", "display_name")
