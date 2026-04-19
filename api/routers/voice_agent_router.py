from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.database.connections import SessionLocal
from backend.database.queries import (
    get_patient_by_phone,
    get_patient_by_name_exact,
    upsert_patient,
    get_available_doctors,
    get_available_slots_for_doctor_date,
    create_appointment,
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


@router.get("/config", description="Expose non-sensitive voice agent runtime config for the web UI.")
def get_voice_agent_config():
    return {
        "agent_id": settings.ELEVENLABS_AGENT_ID or ""
    }

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
        appointment = create_appointment(
            db,
            patient_id=pid,
            doctor_id=req.doctor_id,
            appointment_date=dt,
            time_slot=req.time_slot
        )
        return {"success": True, "appointment_id": appointment.id, "status": "CONFIRMED"}
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
