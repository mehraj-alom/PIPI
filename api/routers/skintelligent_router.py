"""
Handles image upload and runs the detection + classification pipeline +Explainability.
"""

import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from logger import SKIN_TELLIGENT_logger as logger

router = APIRouter(prefix="/Skin", tags=["SKIN_TELLIGENT"])


@router.post("/SKIN_TELLIGENT", summary="Upload an image and run detection + classification + explanation(what model focused on)", description="This endpoint accepts an image file, processes it through the SKIN_TELLIGENT pipeline to perform detection and classification, and returns the results along with an explanation of what the model focused on.")
async def detect_classify_and_explain(
    request: Request,
    file: UploadFile = File(...),
    patient_id: str | None = Form(default=None),
):
    """Upload an image and run detection + classification."""

    try:
        contents = await file.read()
        np_img = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if image is None:
            return JSONResponse(status_code=400, content={"error": "Invalid image file"})

        logger.info("Vision API received image")

        pipeline = request.app.state.vision_pipeline
        session_id = request.headers.get("x-session-id")
        case_context = request.app.state.case_output_manager.get_or_create(
            patient_id=patient_id,
            session_id=session_id,
        )

        visualized_img, crops, classification_results, output_info = pipeline.run_image(
            image,
            output_root=Path(case_context["skintelligent_dir"]),
        )

        return {
            "detections": len(crops),
            "classification_results": classification_results,
            "vision_summary": getattr(classification_results[0], "get", lambda *_: "")("vision_summary", "") if classification_results else "",
            "case": {
                "case_id": case_context.get("case_id"),
                "context_key": case_context.get("context_key"),
                "case_dir": str(case_context.get("case_dir")),
                "skintelligent_dir": str(case_context.get("skintelligent_dir")),
                "documents_dir": str(case_context.get("documents_dir")),
            },
            "output": output_info,
        }

    except Exception as e:
        logger.exception("Vision pipeline failed")
        return JSONResponse(status_code=500, content={"error": str(e)})

__all__ = ["router", "detect_classify_and_explain"]