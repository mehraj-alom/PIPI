from __future__ import annotations

import sys
from datetime import date, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.connections import Base
from backend.database.models import Doctor, Patient


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_doctor(db_session):
    doctor = Doctor(
        name="Dr. Maya Reed",
        specialization="Dermatology",
        available_days=["monday", "tuesday", "2"],
        slot_start=time(9, 0),
        slot_end=time(12, 0),
        slot_duration=30,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture()
def seeded_patient(db_session):
    patient = Patient(name="John Smith", phone="+1234567890", age=28, conditions=["eczema"])
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture()
def monday_date():
    return date(2026, 4, 20)
