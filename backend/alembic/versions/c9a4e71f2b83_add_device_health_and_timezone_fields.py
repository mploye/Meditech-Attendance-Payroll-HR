"""add device health and timezone fields

Revision ID: c9a4e71f2b83
Revises: b7c1e9d4f2a3
Create Date: 2026-10-22 08:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9a4e71f2b83"
down_revision: Union[str, None] = "b7c1e9d4f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("last_punch_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("timezone", sa.String(length=64), nullable=True, server_default="Asia/Kolkata"))
    op.add_column("devices", sa.Column("clock_drift_minutes", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_devices_last_punch_at"), "devices", ["last_punch_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_devices_last_punch_at"), table_name="devices")
    op.drop_column("devices", "clock_drift_minutes")
    op.drop_column("devices", "timezone")
    op.drop_column("devices", "last_punch_at")
