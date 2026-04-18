import shutil
import uuid
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from logger import DocProcess_logger as logger
from backend.services.DOCPROCESS import get_docling_client,get_ade_client

document_router = APIRouter(prefix="/ade", tags=["ADE"])

UPLOAD_DIR = Path("uploads/ade")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DOCLING_UPLOAD_DIR = Path("uploads/docling")
DOCLING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _safe_write_json(path: Path, payload) -> None:
    """Write JSON artifacts safely even with non-serializable values."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)



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
    request: Request,
    file: UploadFile = File(...),
    report_type: Literal["prescription", "lab_report"] = Form("lab_report"),
    patient_id: str | None = Form(default=None),
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
    stored_original_path = ""
    stored_markdown_path = ""
    stored_fields_path = ""
    stored_chunks_path = ""
    stored_result_path = ""
    case_context = None

    try:
        with temp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info(f"[UPLOAD] Saved {file.filename} → {temp_path}")
        logger.info(f"[UPLOAD] Report type: {report_type}")

        session_id = request.headers.get("x-session-id")
        case_context = request.app.state.case_output_manager.get_or_create(
            patient_id=patient_id,
            session_id=session_id,
        )

        documents_dir = Path(case_context["documents_dir"])
        originals_dir = documents_dir / "originals"
        parsed_dir = documents_dir / "parsed"
        originals_dir.mkdir(parents=True, exist_ok=True)
        parsed_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(file.filename).name
        stem = Path(file.filename).stem
        artifact_id = uuid.uuid4().hex

        original_target = originals_dir / f"{artifact_id}_{original_name}"
        shutil.copy2(temp_path, original_target)
        stored_original_path = str(original_target)

        result = router(temp_path, report_type=report_type)

        stored_markdown = parsed_dir / f"{artifact_id}_{stem}.md"
        stored_markdown.write_text(result.get("markdown", ""), encoding="utf-8")
        stored_markdown_path = str(stored_markdown)

        stored_fields = parsed_dir / f"{artifact_id}_{stem}_medical_fields.json"
        _safe_write_json(stored_fields, result.get("medical_fields", {}))
        stored_fields_path = str(stored_fields)

        stored_chunks = parsed_dir / f"{artifact_id}_{stem}_chunks.json"
        _safe_write_json(stored_chunks, result.get("chunks", []))
        stored_chunks_path = str(stored_chunks)

        stored_result = parsed_dir / f"{artifact_id}_{stem}_result.json"
        _safe_write_json(stored_result, result)
        stored_result_path = str(stored_result)

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
        "case": {
            "case_id": case_context.get("case_id") if case_context else "",
            "context_key": case_context.get("context_key") if case_context else "",
            "case_dir": str(case_context.get("case_dir")) if case_context else "",
            "documents_dir": str(case_context.get("documents_dir")) if case_context else "",
            "skintelligent_dir": str(case_context.get("skintelligent_dir")) if case_context else "",
        },
        "stored_outputs": {
            "original_document": stored_original_path,
            "parsed_markdown": stored_markdown_path,
            "medical_fields_json": stored_fields_path,
            "chunks_json": stored_chunks_path,
            "result_json": stored_result_path,
        },
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