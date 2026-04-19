"""Initial schema for OptimaCare scheduling and triage tables."""

from __future__ import annotations

from datetime import datetime, time

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


appointment_status = sa.Enum("pending", "confirmed", "cancelled", "completed", name="appointmentstatus")


def upgrade() -> None:
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("specialization", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("available_days", sa.JSON(), nullable=True),
        sa.Column("slot_start", sa.Time(), nullable=True, server_default=sa.text("'09:00:00'")),
        sa.Column("slot_end", sa.Time(), nullable=True, server_default=sa.text("'17:00:00'")),
        sa.Column("slot_duration", sa.Integer(), nullable=True, server_default=sa.text("30")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_doctors_specialization", "doctors", ["specialization"])
    op.create_index("ix_doctors_specialization_name", "doctors", ["specialization", "name"])

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False, unique=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=True),
        sa.Column("assigned_doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_patients_phone", "patients", ["phone"], unique=True)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time_slot", sa.String(length=20), nullable=False),
        sa.Column("status", appointment_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("notes", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("doctor_id", "date", "time_slot", name="uq_appointments_doctor_date_slot"),
    )
    op.create_index("ix_appointments_patient_date", "appointments", ["patient_id", "date"])
    op.create_index("ix_appointments_doctor_date_status", "appointments", ["doctor_id", "date", "status"])

    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("triage_intent", sa.String(length=50), nullable=False, server_default=sa.text("''")),
        sa.Column("clinical_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("image_paths", sa.JSON(), nullable=True),
        sa.Column("document_paths", sa.JSON(), nullable=True),
        sa.Column("vision_results", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_call_sessions_session_id", "call_sessions", ["session_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_call_sessions_session_id", table_name="call_sessions")
    op.drop_table("call_sessions")
    op.drop_index("ix_appointments_doctor_date_status", table_name="appointments")
    op.drop_index("ix_appointments_patient_date", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_table("patients")
    op.drop_index("ix_doctors_specialization_name", table_name="doctors")
    op.drop_index("ix_doctors_specialization", table_name="doctors")
    op.drop_table("doctors")
