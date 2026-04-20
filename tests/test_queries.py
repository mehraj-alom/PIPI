from __future__ import annotations

from datetime import date

import pytest

from backend.database.models import AppointmentStatus, Patient
from backend.database.queries import (
    AppointmentConflictError,
    cancel_appointment,
    create_appointment,
    format_time_slot,
    get_available_slots_for_doctor_date,
    get_patient_name_suggestions,
    normalize_name,
    normalize_phone,
    parse_time_slot,
    upsert_call_session,
    upsert_patient,
)


def test_normalizers_and_time_parser():
    assert normalize_phone(" +1 (234) 567-8900 ") == "+12345678900"
    assert normalize_name("  Jane    Doe ") == "Jane Doe"
    assert format_time_slot(parse_time_slot("10:30 AM")) == "10:30"


def test_upsert_patient_create_and_update(db_session):
    created = upsert_patient(
        db_session,
        phone="(111) 222-3333",
        name="Alice  Green",
        age=31,
        conditions=["asthma"],
    )
    assert created.id is not None
    assert created.phone == "1112223333"
    assert created.name == "Alice Green"

    updated = upsert_patient(
        db_session,
        phone="1112223333",
        name="Alice Green",
        age=32,
        conditions=["asthma", "allergy"],
    )
    assert updated.id == created.id
    assert updated.age == 32
    assert updated.conditions == ["asthma", "allergy"]


def test_get_patient_name_suggestions_returns_close_matches_in_order(db_session):
    db_session.add_all(
        [
            Patient(name="Mehraj Alom", phone="3647849434", age=13, conditions=[]),
            Patient(name="Meraj Alam Tabader", phone="6001549292", age=21, conditions=[]),
        ]
    )
    db_session.commit()

    suggestions = get_patient_name_suggestions(db_session, "Mehraj Alam")

    assert [patient.name for patient in suggestions] == ["Mehraj Alom"]


def test_upsert_call_session_create_then_update(db_session, seeded_patient):
    created = upsert_call_session(
        db_session,
        session_id="session-1",
        patient_id=seeded_patient.id,
        triage_intent="skin_rash",
        vision_results={"score": 0.88},
    )
    assert created.session_id == "session-1"
    assert created.vision_results == [{"score": 0.88}]

    updated = upsert_call_session(
        db_session,
        session_id="session-1",
        clinical_summary="Patient has mild irritation",
        status="completed",
    )
    assert updated.id == created.id
    assert updated.clinical_summary == "Patient has mild irritation"
    assert updated.status == "completed"


def test_get_available_slots_filters_booked_and_preference(
    db_session,
    seeded_doctor,
    seeded_patient,
    monday_date,
):
    _ = create_appointment(
        db_session,
        patient_id=seeded_patient.id,
        doctor_id=seeded_doctor.id,
        appointment_date=monday_date,
        time_slot="09:30",
    )

    slots = get_available_slots_for_doctor_date(
        db_session,
        doctor_id=seeded_doctor.id,
        appointment_date=monday_date,
        time_preference="morning",
        limit=10,
    )

    assert "09:30" not in slots
    assert "09:00" in slots
    assert all(int(slot.split(":")[0]) < 12 for slot in slots)


def test_create_appointment_conflict_raises(db_session, seeded_doctor, seeded_patient, monday_date):
    _ = create_appointment(
        db_session,
        patient_id=seeded_patient.id,
        doctor_id=seeded_doctor.id,
        appointment_date=monday_date,
        time_slot="10:00",
    )

    other_patient = Patient(name="Jane Doe", phone="+1987654321", age=34, conditions=["psoriasis"])
    db_session.add(other_patient)
    db_session.commit()
    db_session.refresh(other_patient)

    with pytest.raises(AppointmentConflictError):
        create_appointment(
            db_session,
            patient_id=other_patient.id,
            doctor_id=seeded_doctor.id,
            appointment_date=monday_date,
            time_slot="10:00",
        )


def test_create_appointment_is_idempotent_for_same_patient_slot(db_session, seeded_doctor, seeded_patient, monday_date):
    first = create_appointment(
        db_session,
        patient_id=seeded_patient.id,
        doctor_id=seeded_doctor.id,
        appointment_date=monday_date,
        time_slot="10:30",
    )

    second = create_appointment(
        db_session,
        patient_id=seeded_patient.id,
        doctor_id=seeded_doctor.id,
        appointment_date=monday_date,
        time_slot="10:30",
    )

    assert second.id == first.id


def test_cancel_appointment_marks_status_and_reason(db_session, seeded_doctor, seeded_patient, monday_date):
    appointment = create_appointment(
        db_session,
        patient_id=seeded_patient.id,
        doctor_id=seeded_doctor.id,
        appointment_date=monday_date,
        time_slot="11:00",
    )

    cancelled = cancel_appointment(db_session, appointment.id, reason="Patient unavailable")
    assert cancelled.status == AppointmentStatus.CANCELLED
    assert "Patient unavailable" in cancelled.notes
