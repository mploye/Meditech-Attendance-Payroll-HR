"""add device clock offset calibration fields

Revision ID: e3b1c7a94d20
Revises: c9a4e71f2b83
Create Date: 2026-10-23 10:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e3b1c7a94d20"
down_revision: Union[str, None] = "c9a4e71f2b83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("clock_offset_minutes", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("calibration_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "calibration_requested_at")
    op.drop_column("devices", "clock_offset_minutes")
