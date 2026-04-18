"""
Handles image upload and runs the detection + classification pipeline +Explainability.
"""

import cv2
import numpy as np
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from logger import SKIN_TELLIGENT_logger as logger

router = APIRouter(prefix="/Skin", tags=["SKIN_TELLIGENT"])


@router.post("/SKIN_TELLIGENT", summary="Upload an image and run detection + classification + explanation(what model focused on)", description="This endpoint accepts an image file, processes it through the SKIN_TELLIGENT pipeline to perform detection and classification, and returns the results along with an explanation of what the model focused on.")
async def detect_classify_and_explain(request: Request, file: UploadFile = File(...)):
    """Upload an image and run detection + classification."""

    try:
        contents = await file.read()
        np_img = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if image is None:
            return JSONResponse(status_code=400, content={"error": "Invalid image file"})

        logger.info("Vision API received image")

        pipeline = request.app.state.vision_pipeline
        visualized_img, crops, classification_results, output_info = pipeline.run_image(image)

        return {
            "detections": len(crops),
            "classification_results": classification_results,
            "vision_summary": getattr(classification_results[0], "get", lambda *_: "")("vision_summary", "") if classification_results else "",
            "output": output_info,
        }

    except Exception as e:
        logger.exception("Vision pipeline failed")
        return JSONResponse(status_code=500, content={"error": str(e)})

__all__ = ["router", "detect_classify_and_explain"]