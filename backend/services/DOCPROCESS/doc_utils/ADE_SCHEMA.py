# ##########################################
# EXTRACTION SCHEMA
# Define exactly what fields you want pulled from medical documents.
# ADE uses this schema to locate and return specific values.
###########################
from typing import Optional
from pydantic import BaseModel, Field

class LabValue(BaseModel):
    test:  str = Field(..., description="Lab test name e.g. HbA1c, Hemoglobin, Blood Pressure")
    value: str = Field(..., description="Result value with unit e.g. 7.2%, 13.5 g/dL")


class MedicalRecordSchema(BaseModel):
    patient_name:        Optional[str]            = Field(None, description="Full name of the patient")
    date_of_birth:       Optional[str]            = Field(None, description="Patient date of birth")
    visit_date:          Optional[str]            = Field(None, description="Date of the clinic visit or report")
    diagnosis:           Optional[list[str]]      = Field(..., description="List of diagnoses or conditions")
    medications:         Optional[list[str]]      = Field(None, description="List of prescribed medications with dosage")
    lab_values:          Optional[list[LabValue]] = Field(..., description="List of lab test results each with test name and value")
    doctor_name:         Optional[str]            = Field(None, description="Name of the treating physician")
    referred_specialist: Optional[str]            = Field(None, description="Specialist the patient is referred to, if any")
    follow_up_date:      Optional[str]            = Field(None, description="Next appointment or follow-up date")
    summary:             Optional[str]            = Field(..., description="A brief summary of the medical record, key findings, or important notes for quick reference")

