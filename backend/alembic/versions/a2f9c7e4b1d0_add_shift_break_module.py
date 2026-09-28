"""shift break config, shift_breaks and break_logs tables

Revision ID: a2f9c7e4b1d0
Revises: 87472dfe8b52
Create Date: 2026-09-28 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from models.base import GUID


# revision identifiers, used by Alembic.
revision: str = "a2f9c7e4b1d0"
down_revision: Union[str, None] = "87472dfe8b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BREAK_TYPE = sa.Enum("SCHEDULED", "RESTROOM", name="break_type")
_BREAK_STATUS = sa.Enum("ACTIVE", "COMPLETED", "MISSING_OUT", "CANCELLED", name="break_status")


def _drop_enum(name: str, values: list[str]) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"DROP TYPE IF EXISTS {name}")
        return
    sa.Enum(*values, name=name).drop(bind, checkfirst=True)


def upgrade() -> None:
    # Shift break-policy configuration (no hardcoded 8/9 hours or break counts).
    op.add_column("shifts", sa.Column("minimum_shift_hours", sa.Float(), server_default="8.0", nullable=False))
    op.add_column("shifts", sa.Column("maximum_shift_hours", sa.Float(), server_default="9.0", nullable=False))
    op.add_column("shifts", sa.Column("scheduled_break_count", sa.Integer(), server_default="3", nullable=False))
    op.add_column("shifts", sa.Column("scheduled_break_duration", sa.Integer(), server_default="15", nullable=False))

    op.create_table(
        "shift_breaks",
        sa.Column("company_id", GUID(), nullable=False),
        sa.Column("shift_id", GUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("break_type", _BREAK_TYPE, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("max_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_breaks")),
        sa.UniqueConstraint("company_id", "shift_id", "name", name="uq_shift_breaks_company_id_shift_id_name"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_shift_breaks_company_id_companies")),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], name=op.f("fk_shift_breaks_shift_id_shifts")),
    )
    op.create_index(op.f("ix_shift_breaks_company_id"), "shift_breaks", ["company_id"], unique=False)
    op.create_index(op.f("ix_shift_breaks_shift_id"), "shift_breaks", ["shift_id"], unique=False)

    op.create_table(
        "break_logs",
        sa.Column("company_id", GUID(), nullable=False),
        sa.Column("employee_id", GUID(), nullable=False),
        sa.Column("shift_id", GUID(), nullable=True),
        sa.Column("scheduled_break_id", GUID(), nullable=True),
        sa.Column("break_date", sa.Date(), nullable=False),
        sa.Column("break_type", sa.Enum("SCHEDULED", "RESTROOM", name="break_type", create_type=False), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("status", _BREAK_STATUS, nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_break_logs")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_break_logs_company_id_companies")),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_break_logs_employee_id_employees")),
        sa.ForeignKeyConstraint(
            ["scheduled_break_id"], ["shift_breaks.id"], name=op.f("fk_break_logs_scheduled_break_id_shift_breaks")
        ),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], name=op.f("fk_break_logs_shift_id_shifts")),
    )
    op.create_index(
        op.f("ix_break_logs_company_employee_date"), "break_logs", ["company_id", "employee_id", "break_date"], unique=False
    )
    op.create_index(op.f("ix_break_logs_company_id"), "break_logs", ["company_id"], unique=False)
    op.create_index(op.f("ix_break_logs_employee_id"), "break_logs", ["employee_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_break_logs_employee_id"), table_name="break_logs")
    op.drop_index(op.f("ix_break_logs_company_id"), table_name="break_logs")
    op.drop_index(op.f("ix_break_logs_company_employee_date"), table_name="break_logs")
    op.drop_table("break_logs")
    op.drop_index(op.f("ix_shift_breaks_shift_id"), table_name="shift_breaks")
    op.drop_index(op.f("ix_shift_breaks_company_id"), table_name="shift_breaks")
    op.drop_table("shift_breaks")
    _drop_enum("break_status", ["ACTIVE", "COMPLETED", "MISSING_OUT", "CANCELLED"])
    _drop_enum("break_type", ["SCHEDULED", "RESTROOM"])
    op.drop_column("shifts", "scheduled_break_duration")
    op.drop_column("shifts", "scheduled_break_count")
    op.drop_column("shifts", "maximum_shift_hours")
    op.drop_column("shifts", "minimum_shift_hours")