import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from logger import DocProcess_logger as logger
from backend.services.DOCPROCESS import get_docling_client,get_ade_client

document_router = APIRouter(prefix="/ade", tags=["ADE"])

UPLOAD_DIR = Path("uploads/ade")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DOCLING_UPLOAD_DIR = Path("uploads/docling")
DOCLING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)



def router(file_path: Path, report_type: str):
    """
    Routing logic:
    - lab_report → Docling
    - prescription → ADE
    """
    if report_type == "lab_report":
        logger.info("[Router] Using DOCLING (lab_report)")
        return get_docling_client().process_document(file_path, report_type=report_type)

    elif report_type == "prescription":
        logger.info("[Router] Using ADE (prescription)")
        return get_ade_client().process_document(file_path)

    else:
        raise ValueError("Invalid report_type")


@document_router.post("/upload", description="Upload and process a medical document (ADE for prescriptions, Docling for lab reports)")
async def upload_and_process(
    file: UploadFile = File(...),
    report_type: Literal["prescription", "lab_report"] = Form("lab_report"),
):
    """
    Accepts: PDF, PNG, JPG
    Routing:
      - lab_report → Docling
      - prescription → ADE
    """

    allowed = {".pdf", ".png", ".jpg", ".jpeg"}
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()

    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {allowed}"
        )

    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"

    try:
        with temp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info(f"[UPLOAD] Saved {file.filename} → {temp_path}")
        logger.info(f"[UPLOAD] Report type: {report_type}")

        result = router(temp_path, report_type=report_type)

        engine = "docling" if report_type == "lab_report" else "ade"

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"[UPLOAD] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return JSONResponse(content={
        "status": "ok",
        "engine": engine,
        "report_type": report_type,
        "filename": file.filename,
        "chunk_count": len(result.get("chunks", [])),
        "medical_fields": result.get("medical_fields", {}),
        "chunks": result.get("chunks", []),
        "markdown": result.get("markdown", ""),
    })



class ExtractRequest(BaseModel):
    markdown: str


@document_router.post("/extract", description="Endpoint to extract medical fields from markdown using ADE")
async def extract_fields(body: ExtractRequest):
    """Endpoint to extract medical fields from markdown using ADE."""
    if not body.markdown.strip():
        raise HTTPException(status_code=400, detail="markdown field is empty")

    try:
        fields = get_ade_client().extract_medical_fields(body.markdown)
    except Exception as e:
        logger.error(f"[ADE /extract] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={
        "status": "ok",
        "medical_fields": fields,
    })


@document_router.post("/docling/ext_markdown" ,description="Docling-specific endpoint to extract medical fields from markdown")
async def docling_extract(body: ExtractRequest):
    """Docling-specific endpoint to extract medical fields from markdown."""
    if not body.markdown.strip():
        raise HTTPException(status_code=400, detail="markdown field is empty")

    try:
        fields = get_docling_client().extract_medical_fields(body.markdown)
    except Exception as e:
        logger.error(f"[Docling /extract] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={
        "status": "ok",
        "medical_fields": fields,
    })