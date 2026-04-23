from __future__ import annotations

import cv2
import numpy as np

from backend.services.SKIN_TELLIGENT.core import Detector
from config.vision_config import DetectorConfig


def test_detector_load_failure_falls_back_to_full_image_classification(monkeypatch, tmp_path):
    labels_path = tmp_path / "labels.yaml"
    labels_path.write_text("names:\n  - lesion\n", encoding="utf-8")

    model_path = tmp_path / "detector_model.onnx"
    model_path.write_bytes(b"not-a-real-onnx")

    def _raise_load_failure(*args, **kwargs):
        raise cv2.error("mock onnx load failure")

    monkeypatch.setattr(cv2.dnn, "readNetFromONNX", _raise_load_failure)

    detector = Detector(model_path=model_path, yaml_path=labels_path, config=DetectorConfig())

    assert detector.model is None
    assert detector.labels == ["lesion"]

    boxes, confidences, classes, x_factor, y_factor = detector.detect(
        np.zeros((12, 12, 3), dtype=np.uint8)
    )

    assert boxes == []
    assert confidences == []
    assert classes == []
    assert x_factor == 1.0
    assert y_factor == 1.0