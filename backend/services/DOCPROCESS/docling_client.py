from pathlib import Path
from functools import lru_cache
import os
import json

from langchain_openai import ChatOpenAI
from docling.document_converter import DocumentConverter

from backend.services.DOCPROCESS.doc_utils.docling_scanner import scan_document
from logger import DocProcess_logger as logger
from pydantic import SecretStr


def build_docling_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")

    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        model="nvidia/nemotron-3-super-120b-a12b:free",
        api_key=SecretStr(api_key),
    )


#DOCLING CLIiENT(LAB REPORT ONLY)
# ============================

class DoclingClient:
    def __init__(self):
        self.converter = DocumentConverter()
        self.llm = build_docling_llm()


    def process_document(self, doc_path: str | Path, report_type: str = "lab_report") -> dict:
        """
        Only handles lab reports (router ensures this)
        """
        doc_path = str(doc_path)
        if doc_path.lower().endswith((".jpg", ".jpeg", ".png")):
            doc_path = scan_document(doc_path)

    
        result = self.converter.convert(doc_path)
        markdown = result.document.export_to_markdown()


        medical_fields = self.extract_medical_fields(markdown)

        return {
            "markdown": markdown,
            "chunks": [],
            "medical_fields": medical_fields
        }


    def extract_medical_fields(self, markdown: str) -> dict:
        logger.info("[Docling] Extracting LAB REPORT fields")
        prompt = f"""
                You are a medical data extraction engine. Your sole task is to parse the lab report below and return a single, valid JSON object.

                HARD RULES:
                - Output ONLY raw JSON. No markdown, no code fences, no explanation, no preamble.
                - Never invent or infer values not explicitly stated in the document. Missing → null or [].
                - Preserve exact units as written (mg/dL, bpm, °C, mmHg, etc.).
                - Names must be properly cased (e.g., "John Smith", not "john smith" or "JOHN SMITH").
                - confidence reflects how completely the document was parsed (0.0 = unreadable, 1.0 = fully extracted).
                - If the document is not a lab report, still return the schema with nulls and confidence: 0.0.

                FIELD RULES:
                - "report_type"       : always "lab_report"
                - "age"               : integer only (extract from DOB if not stated directly)
                - "gender"            : "Male" | "Female" | "Other" | null
                - "visit_date"        : ISO 8601 format → "YYYY-MM-DD" | null
                - "date_of_birth"     : ISO 8601 format → "YYYY-MM-DD" | null
                - "diagnosis"         : list of condition name strings
                - "symptoms"          : list of symptom strings as reported
                - "medical_history"   : list of past condition/event strings
                - "allergies"         : list of allergen strings (include reaction if stated)
                - "medications"       : list of objects → {{"name": "", "dose": "", "frequency": "", "route": ""}}
                - "lab_tests"         : list of objects → {{"test_name": "", "value": "", "unit": "", "reference_range": "", "status": "Normal|Abnormal|Critical|null"}}
                - "procedures"        : list of procedure name strings
                - "summary"           : one concise paragraph of clinical findings; empty string if nothing useful found
                - "vital_signs"       : extract only what is present; null for anything absent

                OUTPUT SCHEMA:
                {{
                "patient_name": null,
                "age": null,
                "gender": null,
                "date_of_birth": null,
                "visit_date": null,
                "report_type": "lab_report",
                "hospital_or_clinic": null,
                "doctor_name": null,

                "diagnosis": [],
                "symptoms": [],
                "medical_history": [],
                "allergies": [],

                "medications": [],
                "lab_tests": [],

                "vital_signs": {{
                    "blood_pressure": null,
                    "heart_rate": null,
                    "temperature": null,
                    "respiratory_rate": null,
                    "oxygen_saturation": null
                }},

                "procedures": [],
                "summary": "",
                "confidence": 0.0
                }}

                DOCUMENT:
                {markdown}
                
                """

        response = self.llm.invoke([
            {"role": "user", "content": prompt}
        ])


        try:
            content = response.content
            if isinstance(content, list):
                text = "".join(part if isinstance(part, str) else str(part) for part in content)
            else:
                text = content

            text = text.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)

        except Exception as e:
            logger.error(f"[Docling] JSON parse failed: {e}")

            return {
                "error": "invalid_llm_output",
                "raw_output": response.content
            }

@lru_cache(maxsize=2)
def get_docling_client():
    return DoclingClient()