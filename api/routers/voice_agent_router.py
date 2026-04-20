import re
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.database.connections import SessionLocal
from backend.database.queries import (
    get_patient_by_phone,
    get_patient_by_name_exact,
    get_patient_name_suggestions,
    upsert_patient,
    get_available_doctors,
    get_available_slots_for_doctor_date,
    create_appointment,
    get_patient_appointment_for_slot,
    get_appointments_for_patient,
    cancel_appointment,
    reschedule_appointment,
    AppointmentConflictError,
)

from config.voice_agent_schemas import (
    GetPatientDetailsReq,
    RegisterNewPatientReq,
    SearchDoctorsReq,
    CheckDoctorAvailabilityReq,
    BookAppointmentReq,
    CancelAppointmentReq,   
    GetPatientAppointmentsReq,
    RescheduleAppointmentReq,
    SendUploadLinkReq
    )
from config.db_config import settings

router = APIRouter(prefix="/tools/VoiceAgent", tags=["Voice Agent Tools"])
ELEVENLABS_SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"


def _extract_agent_and_branch_ids(raw_agent_reference: str) -> tuple[str, str | None]:
    raw = str(raw_agent_reference or "").strip().strip('"').strip("'")
    if not raw:
        return "", None

    agent_match = re.search(r"agent_[a-z0-9]+", raw, re.IGNORECASE)
    branch_match = re.search(r"agtbrch_[a-z0-9]+", raw, re.IGNORECASE)

    if agent_match:
        return agent_match.group(0), branch_match.group(0) if branch_match else None

    agent_id = raw.split("?", 1)[0].strip()
    return agent_id, branch_match.group(0) if branch_match else None


def _build_signed_url_request_config() -> tuple[dict[str, str], dict[str, str]]:
    agent_id, branch_id = _extract_agent_and_branch_ids(settings.ELEVENLABS_AGENT_ID or "")
    api_key = (settings.ELEVENLABS_API_KEY or "").strip()

    if not agent_id:
        raise HTTPException(status_code=503, detail="ELEVENLABS_AGENT_ID is not configured on the backend.")

    if not api_key:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY is not configured on the backend.")

    params = {"agent_id": agent_id}
    if branch_id:
        params["branch_id"] = branch_id

    headers = {"xi-api-key": api_key}
    return headers, params


@router.get("/config", description="Expose non-sensitive voice agent runtime config for the web UI.")
def get_voice_agent_config():
    return {
        "agent_id": (settings.ELEVENLABS_AGENT_ID or "").strip()
    }


@router.get("/signed-url", description="Create a signed ElevenLabs conversation URL for browser WebSocket fallback.")
def get_voice_agent_signed_url():
    headers, params = _build_signed_url_request_config()

    try:
        response = httpx.get(
            ELEVENLABS_SIGNED_URL_ENDPOINT,
            params=params,
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(
            status_code=502,
            detail=f"ElevenLabs signed URL request failed ({status_code}).",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not reach ElevenLabs to create a signed URL.",
        ) from exc

    payload = response.json()
    signed_url = str(payload.get("signed_url") or "").strip()
    if not signed_url:
        raise HTTPException(status_code=502, detail="ElevenLabs response did not include a signed URL.")

    return {"signed_url": signed_url}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/getPatientDetails",description="Fetch patient details using phone number or exact name match.")
def get_patient_details(req: GetPatientDetailsReq, db = Depends(get_db)):
    patient = get_patient_by_phone(db, req.patient_phone)
    if not patient:
        patient = get_patient_by_name_exact(db, req.Patient_Name)
    if not patient:
        suggestions = get_patient_name_suggestions(db, req.Patient_Name)
        if suggestions:
            suggested_matches = [
                {
                    "name": match.name,
                    "phone_last4": match.phone[-4:] if match.phone else None,
                }
                for match in suggestions
            ]
            suggestion_text = ", ".join(
                f"{match['name']} (phone ending {match['phone_last4']})"
                if match["phone_last4"]
                else match["name"]
                for match in suggested_matches
            )
            return {
                "error": (
                    "Patient not found. Similar records found: "
                    f"{suggestion_text}. Please confirm the exact name or phone number."
                ),
                "suggested_matches": suggested_matches,
            }
        return {"error": "Patient not found."}
    return {
        "patient_id": patient.id,
        "name": patient.name,
        "phone": patient.phone,
        "age": patient.age,
        "conditions": patient.conditions,
        "assigned_doctor_id": patient.assigned_doctor_id
    }


@router.post("/registerNewPatient",description="Register a new patient or update existing patient details based on phone number.")
def register_new_patient(req: RegisterNewPatientReq, db = Depends(get_db)):
    conditions_list = [c.strip() for c in req.Patient_conditions.split(",")] if req.Patient_conditions else []
    try:
        patient = upsert_patient(
            db,
            phone=req.patient_phone,
            name=req.patient_name,
            age=req.age,
            conditions=conditions_list
        )
        return {"success": True, "patient_id": patient.id, "message": "Patient registered successfully."}
    except Exception as e:
        return {"error": str(e)}



@router.post("/searchDoctors", description="Search for available doctors based on specialization.")
def search_doctors(req: SearchDoctorsReq, db = Depends(get_db)):
    doctors = get_available_doctors(db, req.specialization)
    return {
        "doctors": [
            {"doctor_id": d.id, "name": d.name, "specialization": d.specialization}
            for d in doctors
        ]
    }


@router.post("/checkDoctorAvailability", description="Check the availability of a doctor for a specific date and time.")
def check_doctor_availability(req: CheckDoctorAvailabilityReq, db = Depends(get_db)):
    try:
        dt = datetime.strptime(req.appointment_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}
    slots = get_available_slots_for_doctor_date(
        db,
        doctor_id=req.doctor_id,
        appointment_date=dt,
        time_preference=req.time_preference
    )
    return {"available_slots": slots, "date": req.appointment_date}



@router.post("/bookAppointment", description="Book a new appointment with a doctor.")
def book_appointment(req: BookAppointmentReq, db = Depends(get_db)):
    try:
        pid = int(req.patient_id)
        dt = datetime.strptime(req.appointment_date, "%Y-%m-%d").date()
        existing = get_patient_appointment_for_slot(
            db,
            patient_id=pid,
            doctor_id=req.doctor_id,
            appointment_date=dt,
            time_slot=req.time_slot,
        )
        if existing is not None:
            return {
                "success": True,
                "appointment_id": existing.id,
                "status": getattr(existing.status, "value", existing.status),
                "already_booked": True,
            }

        appointment = create_appointment(
            db,
            patient_id=pid,
            doctor_id=req.doctor_id,
            appointment_date=dt,
            time_slot=req.time_slot
        )
        return {
            "success": True,
            "appointment_id": appointment.id,
            "status": getattr(appointment.status, "value", appointment.status),
            "already_booked": False,
        }
    except AppointmentConflictError:
        return {"error": "The selected time slot is no longer available."}
    except Exception as e:
        return {"error": str(e)}



@router.post("/cancelAppointment", description="Cancel an existing appointment.")
def cancel_appointment_endpoint(req: CancelAppointmentReq, db = Depends(get_db)):
    try:
        app = cancel_appointment(db, req.appointment_id, reason=req.reason)
        return {"success": True, "appointment_id": app.id, "status": app.status}
    except Exception as e:
        return {"error": str(e)}


@router.post("/getPatientAppointments", description="Retrieve all appointments for a specific patient.")
def get_patient_appointments(req: GetPatientAppointmentsReq, db = Depends(get_db)):
    apps = get_appointments_for_patient(db, req.patient_id)
    return {
        "appointments": [
            {
                "appointment_id": app.id,
                "doctor_id": app.doctor_id,
                "date": str(app.date),
                "time_slot": app.time_slot,
                "status": app.status
            } for app in apps
        ]
    }


@router.post("/rescheduleAppointment", description="Reschedule an existing appointment.")
def reschedule_appointment_endpoint(req: RescheduleAppointmentReq, db = Depends(get_db)):
    try:
        dt = datetime.strptime(req.appointment_date, "%Y-%m-%d").date()
        app = reschedule_appointment(
            db,
            appointment_id=req.appointment_id,
            appointment_date=dt,
            time_slot=req.time_slot
        )
        return {"success": True, "appointment_id": app.id, "new_date": str(app.date), "new_time": app.time_slot}
    except Exception as e:
        return {"error": str(e)}



# NOTE: Upload is now handled as a client-side tool (requestUpload)
# in the webui. The upload modal opens directly in the phone widget and
# calls /Skin/SKIN_TELLIGENT or /ade/upload. This endpoint is kept as
# a fallback for non-UI integrations.
@router.post("/sendUploadLink", description="[Legacy] Upload is now handled in-UI via requestUpload client tool.")
def send_upload_link(req: SendUploadLinkReq):
    return {"success": True, "message": "Upload handled via client UI.", "upload_type": req.upload_type}
