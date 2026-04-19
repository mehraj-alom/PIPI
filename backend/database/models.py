"""
SQLAlchemy ORM models for the PIPI system.
Tables: doctors, patients, appointments, call_sessions.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time as SATime,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connections import Base


#    Enums

class AppointmentStatus(str, enum.Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


#                  Doctor

class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = (Index("ix_doctors_specialization_name", "specialization", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialization: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    available_days: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    slot_start: Mapped[time] = mapped_column(SATime, default=time(9, 0))
    slot_end: Mapped[time] = mapped_column(SATime, default=time(17, 0))
    slot_duration: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    appointments: Mapped[list[Appointment]] = relationship(back_populates="doctor")

    def __repr__(self):  # for debugging and logging it provides a readable string representation
        return f"<Doctor {self.name} ({self.specialization})>"


# Patient 

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conditions: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    assigned_doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("doctors.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    assigned_doctor: Mapped[Doctor | None] = relationship(foreign_keys=[assigned_doctor_id])
    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")

    def __repr__(self):
        return f"<Patient {self.name} ({self.phone})>"


#     Appointment 

class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("doctor_id", "date", "time_slot", name="uq_appointments_doctor_date_slot"),
        Index("ix_appointments_patient_date", "patient_id", "date"),
        Index("ix_appointments_doctor_date_status", "doctor_id", "date", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("doctors.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_slot: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "10:00 AM"
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus),
        default=AppointmentStatus.PENDING,
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    doctor: Mapped[Doctor] = relationship(back_populates="appointments")

    def __repr__(self):
        return f"<Appointment {self.patient_id} {self.doctor_id} on {self.date} {self.time_slot}>"


#Call Session

class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    patient_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("patients.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    triage_intent: Mapped[str] = mapped_column(String(50), default="")
    clinical_summary: Mapped[str] = mapped_column(Text, default="")
    image_paths: Mapped[list[Any] | None] = mapped_column(JSON, default=list)  # list of strings
    document_paths: Mapped[list[Any] | None] = mapped_column(JSON, default=list)  # list of strings
    vision_results: Mapped[list[Any] | None] = mapped_column(JSON, default=list)  # list of dicts
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / completed
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    patient: Mapped[Patient | None] = relationship()

    def __repr__(self):
        return f"<CallSession {self.session_id}>"