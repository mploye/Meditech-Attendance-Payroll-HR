"""device_commands queue for persistent ADMS server->device commands

Revision ID: b7c1e9d4f2a3
Revises: a2f9c7e4b1d0
Create Date: 2026-10-22 04:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from models.base import GUID


# revision identifiers, used by Alembic.
revision: str = "b7c1e9d4f2a3"
down_revision: Union[str, None] = "a2f9c7e4b1d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_commands",
        sa.Column("company_id", GUID(), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_commands")),
    )
    op.create_index(op.f("ix_device_commands_company_id"), "device_commands", ["company_id"], unique=False)
    op.create_index(op.f("ix_device_commands_serial_number"), "device_commands", ["serial_number"], unique=False)
    op.create_index(op.f("ix_device_commands_delivered"), "device_commands", ["delivered"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_device_commands_delivered"), table_name="device_commands")
    op.drop_index(op.f("ix_device_commands_serial_number"), table_name="device_commands")
    op.drop_index(op.f("ix_device_commands_company_id"), table_name="device_commands")
    op.drop_table("device_commands")
