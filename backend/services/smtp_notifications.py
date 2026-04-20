from __future__ import annotations

import mimetypes
import smtplib
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from backend.database.models import Doctor, Patient
from config.db_config import settings
from logger import Database_logger as logger


@dataclass(slots=True)
class NotificationResult:
    sent: bool
    recipient: str | None = None
    error: str | None = None
    attachment_count: int = 0


def smtp_is_configured() -> bool:
    return bool((settings.SMTP_HOST or "").strip() and (settings.SMTP_FROM_EMAIL or "").strip())


def _build_sender_header() -> str:
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    from_name = (settings.SMTP_FROM_NAME or "").strip()
    if from_name:
        return f"{from_name} <{from_email}>"
    return from_email


def _build_appointment_email(
    *,
    doctor: Doctor,
    patient: Patient,
    appointment_date: date,
    time_slot: str,
    appointment_id: int,
    case_id: str | None = None,
    report_pdf_path: str | Path | None = None,
    attachment_paths: list[str | Path] | None = None,
) -> EmailMessage:
    doctor_email = (doctor.email or "").strip()
    message = EmailMessage()
    message["Subject"] = (
        f"New appointment assigned: {patient.name} on {appointment_date.isoformat()} at {time_slot}"
    )
    message["From"] = _build_sender_header()
    message["To"] = doctor_email

    patient_conditions = ", ".join(
        str(value) for value in (patient.conditions or []) if str(value).strip()
    ) or "None provided"
    patient_age = patient.age if patient.age is not None else "Not provided"
    doctor_specialization = (doctor.specialization or "").strip() or "General"
    original_attachment_count = len(list(attachment_paths or []))
    has_pdf_report = report_pdf_path is not None

    message.set_content(
        "\n".join(
            [
                f"Hello {doctor.name},",
                "",
                "A new appointment has been booked in PIPI.",
                "",
                f"Appointment ID: {appointment_id}",
                f"Date: {appointment_date.isoformat()}",
                f"Time: {time_slot}",
                f"Specialization: {doctor_specialization}",
                f"Case ID: {case_id or 'Not available'}",
                "",
                "Patient details:",
                f"- Name: {patient.name}",
                f"- Phone: {patient.phone}",
                f"- Age: {patient_age}",
                f"- Conditions: {patient_conditions}",
                "",
                "Attachments included:",
                f"- Combined doctor packet PDF: {'yes' if has_pdf_report else 'no'}",
                f"- Original uploaded files: {original_attachment_count}",
                "",
                "Please review the case packet and clinical workflow before the consultation.",
            ]
        )
    )
    return message


def _attach_file(message: EmailMessage, path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    with path.open("rb") as f:
        message.add_attachment(
            f.read(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )
    return True


def send_doctor_appointment_email(
    *,
    doctor: Doctor,
    patient: Patient,
    appointment_date: date,
    time_slot: str,
    appointment_id: int,
    case_id: str | None = None,
    report_pdf_path: str | Path | None = None,
    attachment_paths: list[str | Path] | None = None,
) -> NotificationResult:
    doctor_email = (doctor.email or "").strip()
    if not doctor_email:
        return NotificationResult(sent=False, error="Doctor does not have an email address configured.")

    if not smtp_is_configured():
        return NotificationResult(
            sent=False,
            recipient=doctor_email,
            error="SMTP is not configured on the backend.",
        )

    message = _build_appointment_email(
        doctor=doctor,
        patient=patient,
        appointment_date=appointment_date,
        time_slot=time_slot,
        appointment_id=appointment_id,
        case_id=case_id,
        report_pdf_path=report_pdf_path,
        attachment_paths=attachment_paths,
    )

    files_to_attach: list[Path] = []
    if report_pdf_path:
        files_to_attach.append(Path(report_pdf_path))
    files_to_attach.extend(Path(path) for path in (attachment_paths or []))

    attached_count = 0
    for path in files_to_attach:
        try:
            if _attach_file(message, path):
                attached_count += 1
        except Exception:
            logger.exception("Failed to attach %s to appointment email", path)

    smtp_host = (settings.SMTP_HOST or "").strip()
    smtp_username = (settings.SMTP_USERNAME or "").strip()
    smtp_password = settings.SMTP_PASSWORD or ""
    timeout = max(float(settings.SMTP_TIMEOUT_SECONDS or 10.0), 1.0)

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(smtp_host, settings.SMTP_PORT, timeout=timeout) as server:
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, settings.SMTP_PORT, timeout=timeout) as server:
                server.ehlo()
                if settings.SMTP_USE_TLS:
                    server.starttls()
                    server.ehlo()
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.send_message(message)
    except Exception as exc:
        logger.exception(
            "Failed to send appointment notification email for appointment_id=%s to doctor_id=%s",
            appointment_id,
            doctor.id,
        )
        return NotificationResult(
            sent=False,
            recipient=doctor_email,
            error=str(exc),
            attachment_count=attached_count,
        )

    return NotificationResult(sent=True, recipient=doctor_email, attachment_count=attached_count)
