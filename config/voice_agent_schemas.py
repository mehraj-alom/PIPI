from pydantic import BaseModel
from typing import Optional

class GetPatientDetailsReq(BaseModel):
    Patient_Name: str
    patient_phone: str



class RegisterNewPatientReq(BaseModel):
    patient_phone: str
    patient_name: str
    age: Optional[int] = None
    Patient_conditions: Optional[str] = None
    
    
class SearchDoctorsReq(BaseModel):
    specialization: Optional[str] = None
    

class CheckDoctorAvailabilityReq(BaseModel):
    doctor_id: int
    appointment_date: str
    time_preference: Optional[str] = None
    
class BookAppointmentReq(BaseModel):
    doctor_id: int
    patient_id: str
    appointment_date: str
    time_slot: str
    
class CancelAppointmentReq(BaseModel):
    appointment_id: int
    reason: str
    
class GetPatientAppointmentsReq(BaseModel):
    patient_id: int


class RescheduleAppointmentReq(BaseModel):
    appointment_id: int
    appointment_date: str
    time_slot: str
    
class SendUploadLinkReq(BaseModel):
    patient_phone: str
    upload_type: str

