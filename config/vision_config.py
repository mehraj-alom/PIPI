"""
Central configuration file for Inference pipeline
"""

from dataclasses import dataclass
from pathlib import Path


# ==============================
# MODEL PATHS
# ==============================

@dataclass(frozen=True)
class Paths:
    detector_model: Path | str = Path("artifacts/detector_model.onnx")
    data_yaml: Path | str = Path("backend/services/SKIN_TELLIGENT/data.yaml") 
    classifier_model: Path = Path("artifacts/best_skin_model.pth")
    classifier_labels: Path = Path("backend/services/SKIN_TELLIGENT/classifier_labels.yaml")


# ==============================
#     YOLO DETECTOR CONFIG
# ==============================

@dataclass
class DetectorConfig:
    """
    Configuration for YOLO detection model

    Args:
        confidence_threshold: Detection confidence threshold
        prob_threshold: Class probability threshold
        nms_threshold: Non-Maximum Suppression threshold
        input_width: Model input width
        input_height: Model input height
    """

    confidence_threshold: float = 0.269
    prob_threshold: float = 0.20
    nms_threshold: float = 0.70
    input_width: int = 640
    input_height: int = 640


# ==============================
# CLASSIFIER CONSTANTS
# ==============================

@dataclass(frozen=True)
class ClassifierConstants:
    imagenet_mean: tuple = (0.485, 0.456, 0.406)
    imagenet_std: tuple = (0.229, 0.224, 0.225)


# ==============================
# INFERENCE CONFIG
# ==============================

@dataclass(frozen=True)
class InferenceConfig:
    input_image: Path = Path("ade_visualization.png")
    output_dir: Path = Path("output")


# ==============================
# PREDICTION DEVICE CONFIG
# ==============================

@dataclass(frozen=True)
class PredictionConfig:
    model_path: Path
    device: str = "cpu"


# ==============================
# GLOBAL CONFIG OBJECT
# ==============================

class Config:
    paths = Paths()
    detector = DetectorConfig()
    classifier = ClassifierConstants()
    inference = InferenceConfig()