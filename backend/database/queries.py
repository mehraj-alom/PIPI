from __future__ import annotations

from difflib import SequenceMatcher
from datetime import date, datetime, time, timedelta
from typing import Iterable

from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from logger import Database_logger as logger

from .models import Appointment, AppointmentStatus, CallSession, Doctor, Patient

DEFAULT_SLOT_DURATION_MINUTES = 30
EVENING_START_HOUR = 16
DEFAULT_PATIENT_NAME_SUGGESTION_LIMIT = 3
PATIENT_NAME_SUGGESTION_MIN_SCORE = 0.82


class DatabaseOperationError(RuntimeError):
    """Raised when a database operation fails unexpectedly."""


class PatientNotFoundError(DatabaseOperationError):
    """Raised when a patient lookup does not find a record."""


class AppointmentConflictError(DatabaseOperationError):
    """Raised when a slot is already booked."""


def commit(session: Session) -> None:
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")


def normalize_name(name: str | None) -> str:
    return " ".join((name or "").strip().split())


def patient_name_similarity(left: str | None, right: str | None) -> float:
    left_normalized = normalize_name(left).casefold()
    right_normalized = normalize_name(right).casefold()
    if not left_normalized or not right_normalized:
        return 0.0

    collapsed_left = left_normalized.replace(" ", "")
    collapsed_right = right_normalized.replace(" ", "")
    return max(
        SequenceMatcher(None, left_normalized, right_normalized).ratio(),
        SequenceMatcher(None, collapsed_left, collapsed_right).ratio(),
    )


def parse_time_slot(value: str) -> time:
    for pattern in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(value.strip(), pattern).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported time slot format: {value!r}")


def format_time_slot(value: time) -> str:
    return value.strftime("%H:%M")


def doctor_is_available_on_date(doctor: Doctor, appointment_date: date) -> bool:
    available_days = doctor.available_days or []
    if not available_days:
        return True

    weekday = appointment_date.weekday()
    weekday_name = appointment_date.strftime("%A").lower()
    weekday_short = appointment_date.strftime("%a").lower()

    for raw_value in available_days:
        if isinstance(raw_value, int) and raw_value == weekday:
            return True
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in {weekday_name, weekday_short}:
                return True
            if normalized.isdigit() and int(normalized) == weekday:
                return True
    return False


def slot_matches_preference(slot_value: time, time_preference: str | None) -> bool:
    if not time_preference:
        return True

    preference = time_preference.strip().lower()
    if preference in {"evening", "night"}:
        return slot_value.hour >= EVENING_START_HOUR
    if preference in {"morning"}:
        return slot_value.hour < 12
    if preference in {"afternoon"}:
        return 12 <= slot_value.hour < EVENING_START_HOUR
    return True


def appointment_exists(session: Session, doctor_id: int, appointment_date: date, time_slot: str) -> bool:
    return (
        session.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date == appointment_date,
            Appointment.time_slot == time_slot,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
        .first()
        is not None
    )


def get_patient_appointment_for_slot(
    session: Session,
    *,
    patient_id: int,
    doctor_id: int,
    appointment_date: date,
    time_slot: str,
) -> Appointment | None:
    slot_label = format_time_slot(parse_time_slot(time_slot))
    return (
        session.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.date == appointment_date,
            Appointment.time_slot == slot_label,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
        .order_by(desc(Appointment.id))
        .first()
    )


def get_patient_by_phone(session: Session, phone: str) -> Patient | None:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    return session.query(Patient).filter(Patient.phone == normalized_phone).first()


def get_patient_by_id(session: Session, patient_id: int) -> Patient | None:
    return session.query(Patient).filter(Patient.id == patient_id).first()


def get_patient_by_name_exact(session: Session, name: str) -> Patient | None:
    normalized_name = normalize_name(name)
    if not normalized_name:
        return None
    return session.query(Patient).filter(Patient.name.ilike(normalized_name)).first()


def get_patient_name_suggestions(
    session: Session,
    name: str,
    *,
    limit: int = DEFAULT_PATIENT_NAME_SUGGESTION_LIMIT,
    min_score: float = PATIENT_NAME_SUGGESTION_MIN_SCORE,
) -> list[Patient]:
    normalized_name = normalize_name(name)
    if not normalized_name:
        return []

    scored_matches: list[tuple[float, Patient]] = []
    patients = session.query(Patient).order_by(asc(Patient.name), asc(Patient.id)).all()
    for patient in patients:
        score = patient_name_similarity(normalized_name, patient.name)
        if score >= min_score:
            scored_matches.append((score, patient))

    scored_matches.sort(key=lambda item: (-item[0], item[1].name.casefold(), item[1].id))
    return [patient for _, patient in scored_matches[: max(limit, 1)]]


def get_call_session_by_session_id(session: Session, session_id: str) -> CallSession | None:
    normalized = (session_id or "").strip()
    if not normalized:
        return None
    return session.query(CallSession).filter(CallSession.session_id == normalized).first()


def upsert_call_session(
    session: Session,
    *,
    session_id: str,
    patient_id: int | None = None,
    triage_intent: str = "",
    clinical_summary: str = "",
    image_paths: list[str] | None = None,
    document_paths: list[str] | None = None,
    vision_results: list[dict] | dict | None = None,
    status: str = "active",
) -> CallSession:
    normalized_session_id = (session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    call_session = get_call_session_by_session_id(session, normalized_session_id)
    payload_images = list(image_paths or [])
    payload_docs = list(document_paths or [])
    if isinstance(vision_results, list):
        payload_vision_results = vision_results
    elif isinstance(vision_results, dict):
        payload_vision_results = [vision_results]
    else:
        payload_vision_results = []

    try:
        if call_session is None:
            call_session = CallSession(
                session_id=normalized_session_id,
                patient_id=patient_id,
                triage_intent=triage_intent or "",
                clinical_summary=clinical_summary or "",
                image_paths=payload_images,
                document_paths=payload_docs,
                vision_results=payload_vision_results,
                status=status or "active",
            )
            session.add(call_session)
        else:
            if patient_id is not None:
                call_session.patient_id = patient_id
            if triage_intent:
                call_session.triage_intent = triage_intent
            if clinical_summary:
                call_session.clinical_summary = clinical_summary
            if image_paths is not None:
                call_session.image_paths = payload_images
            if document_paths is not None:
                call_session.document_paths = payload_docs
            if vision_results is not None:
                call_session.vision_results = payload_vision_results
            if status:
                call_session.status = status

        call_session.updated_at = datetime.utcnow()
        commit(session)
        session.refresh(call_session)
        return call_session
    except IntegrityError as exc:
        # Concurrent request race: another worker may have inserted the same session_id
        # between our read and write. Retry as an update before failing.
        session.rollback()
        existing = get_call_session_by_session_id(session, normalized_session_id)
        if existing is not None:
            try:
                if patient_id is not None:
                    existing.patient_id = patient_id
                if triage_intent:
                    existing.triage_intent = triage_intent
                if clinical_summary:
                    existing.clinical_summary = clinical_summary
                if image_paths is not None:
                    existing.image_paths = payload_images
                if document_paths is not None:
                    existing.document_paths = payload_docs
                if vision_results is not None:
                    existing.vision_results = payload_vision_results
                if status:
                    existing.status = status
                existing.updated_at = datetime.utcnow()
                commit(session)
                session.refresh(existing)
                return existing
            except Exception:
                session.rollback()

        logger.exception("Failed to upsert call_session for session_id=%s", normalized_session_id)
        raise DatabaseOperationError("Could not save call session") from exc


def upsert_patient(
    session: Session,
    *,
    phone: str,
    name: str,
    age: int | None = None,
    conditions: Iterable[str] | None = None,
    assigned_doctor_id: int | None = None,
) -> Patient:
    normalized_phone = normalize_phone(phone)
    normalized_name = normalize_name(name)
    if not normalized_phone:
        raise ValueError("Patient phone is required for upsert")
    if not normalized_name:
        raise ValueError("Patient name is required for upsert")

    patient = get_patient_by_phone(session, normalized_phone)
    payload_conditions = list(conditions or [])

    try:
        if patient is None:
            patient = Patient(
                phone=normalized_phone,
                name=normalized_name,
                age=age,
                conditions=payload_conditions,
                assigned_doctor_id=assigned_doctor_id,
            )
            session.add(patient)
        else:
            patient.name = normalized_name or patient.name
            if age is not None:
                patient.age = age
            if conditions is not None:
                patient.conditions = payload_conditions
            if assigned_doctor_id is not None:
                patient.assigned_doctor_id = assigned_doctor_id

        commit(session)
        session.refresh(patient)
        return patient
    except IntegrityError as exc:
        session.rollback()
        logger.exception("Failed to upsert patient with phone=%s", normalized_phone)
        raise DatabaseOperationError("Could not save patient record") from exc


def list_patients(session: Session, *, skip: int = 0, limit: int = 50) -> list[Patient]:
    return (
        session.query(Patient)
        .order_by(asc(Patient.name), asc(Patient.id))
        .offset(max(skip, 0))
        .limit(max(limit, 1))
        .all()
    )


def get_doctor_by_id(session: Session, doctor_id: int) -> Doctor | None:
    return session.query(Doctor).filter(Doctor.id == doctor_id).first()


def get_available_doctors(session: Session, specialization: str | None = None) -> list[Doctor]:
    query = session.query(Doctor)
    if specialization:
        normalized = specialization.strip()
        query = query.filter(Doctor.specialization.ilike(f"%{normalized}%"))
    return query.order_by(asc(Doctor.specialization), asc(Doctor.name), asc(Doctor.id)).all()


def get_available_slots_for_doctor_date(
    session: Session,
    doctor_id: int,
    appointment_date: date,
    *,
    time_preference: str | None = None,
    limit: int = 5,
) -> list[str]:
    doctor = get_doctor_by_id(session, doctor_id)
    if doctor is None or not doctor_is_available_on_date(doctor, appointment_date):
        return []

    slot_duration_minutes = doctor.slot_duration or DEFAULT_SLOT_DURATION_MINUTES
    slot_duration_minutes = max(slot_duration_minutes, 5)
    slot_start = doctor.slot_start or time(9, 0)
    slot_end = doctor.slot_end or time(17, 0)

    current = datetime.combine(appointment_date, slot_start)
    end_dt = datetime.combine(appointment_date, slot_end)
    slots: list[str] = []

    while current + timedelta(minutes=slot_duration_minutes) <= end_dt:
        slot_value = current.time()
        slot_label = format_time_slot(slot_value)
        if slot_matches_preference(slot_value, time_preference) and not appointment_exists(session, doctor_id, appointment_date, slot_label):
            slots.append(slot_label)
        current += timedelta(minutes=slot_duration_minutes)

    return slots[: max(limit, 1)]


def validate_slot_for_doctor(session: Session, doctor_id: int, appointment_date: date, time_slot: str) -> bool:
    doctor = get_doctor_by_id(session, doctor_id)
    if doctor is None or not doctor_is_available_on_date(doctor, appointment_date):
        return False

    try:
        parsed_slot = parse_time_slot(time_slot)
    except ValueError:
        return False

    if doctor.slot_start and parsed_slot < doctor.slot_start:
        return False
    if doctor.slot_end and parsed_slot >= doctor.slot_end:
        return False

    slot_label = format_time_slot(parsed_slot)
    return not appointment_exists(session, doctor_id, appointment_date, slot_label)


def get_appointments_for_patient(session: Session, patient_id: int) -> list[Appointment]:
    return (
        session.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(desc(Appointment.date), desc(Appointment.time_slot), desc(Appointment.id))
        .all()
    )


def get_latest_appointment_for_patient(session: Session, patient_id: int) -> Appointment | None:
    return (
        session.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(desc(Appointment.date), desc(Appointment.time_slot), desc(Appointment.id))
        .first()
    )


def create_appointment(
    session: Session,
    *,
    patient_id: int,
    doctor_id: int,
    appointment_date: date,
    time_slot: str,
    notes: str = "",
    status: AppointmentStatus = AppointmentStatus.CONFIRMED,
) -> Appointment:
    doctor = get_doctor_by_id(session, doctor_id)
    patient = get_patient_by_id(session, patient_id)
    if doctor is None:
        raise ValueError(f"Doctor {doctor_id} was not found")
    if patient is None:
        raise ValueError(f"Patient {patient_id} was not found")

    slot_label = format_time_slot(parse_time_slot(time_slot))
    existing = get_patient_appointment_for_slot(
        session,
        patient_id=patient_id,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        time_slot=slot_label,
    )
    if existing is not None:
        return existing

    if not validate_slot_for_doctor(session, doctor_id, appointment_date, slot_label):
        raise AppointmentConflictError("The selected slot is no longer available")

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        date=appointment_date,
        time_slot=slot_label,
        status=status,
        notes=notes,
    )

    try:
        session.add(appointment)
        commit(session)
        session.refresh(appointment)
        return appointment
    except IntegrityError as exc:
        session.rollback()
        existing = get_patient_appointment_for_slot(
            session,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            time_slot=slot_label,
        )
        if existing is not None:
            return existing
        logger.exception(
            "Appointment conflict for patient_id=%s doctor_id=%s date=%s time_slot=%s",
            patient_id,
            doctor_id,
            appointment_date,
            slot_label,
        )
        raise AppointmentConflictError("The selected slot is already booked") from exc
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("Failed to create appointment")
        raise DatabaseOperationError("Could not create appointment") from exc


def update_appointment_status(session: Session, appointment_id: int, status: AppointmentStatus) -> Appointment:
    appointment = session.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment is None:
        raise ValueError(f"Appointment {appointment_id} was not found")

    appointment.status = status
    commit(session)
    session.refresh(appointment)
    return appointment


def cancel_appointment(session: Session, appointment_id: int, *, reason: str = "") -> Appointment:
    appointment = update_appointment_status(session, appointment_id, AppointmentStatus.CANCELLED)
    if reason:
        appointment.notes = (appointment.notes or "").strip()
        appointment.notes = f"{appointment.notes}\nCancellation reason: {reason}".strip()
        commit(session)
        session.refresh(appointment)
    return appointment


def reschedule_appointment(
    session: Session,
    *,
    appointment_id: int,
    appointment_date: date,
    time_slot: str,
) -> Appointment:
    appointment = session.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment is None:
        raise ValueError(f"Appointment {appointment_id} was not found")

    if not validate_slot_for_doctor(session, appointment.doctor_id, appointment_date, time_slot):
        raise AppointmentConflictError("The selected slot is not available")

    appointment.date = appointment_date
    appointment.time_slot = format_time_slot(parse_time_slot(time_slot))
    commit(session)
    session.refresh(appointment)
    return appointment


__all__ = [
    "AppointmentConflictError",
    "AppointmentStatus",
    "DatabaseOperationError",
    "PatientNotFoundError",
    "cancel_appointment",
    "create_appointment",
    "get_appointments_for_patient",
    "get_call_session_by_session_id",
    "get_available_doctors",
    "get_available_slots_for_doctor_date",
    "get_doctor_by_id",
    "get_latest_appointment_for_patient",
    "get_patient_appointment_for_slot",
    "get_patient_by_id",
    "get_patient_by_name_exact",
    "get_patient_name_suggestions",
    "get_patient_by_phone",
    "list_patients",
    "patient_name_similarity",
    "reschedule_appointment",
    "upsert_call_session",
    "upsert_patient",
    "update_appointment_status",
    "validate_slot_for_doctor",
]
