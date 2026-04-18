import os
import cv2
from pathlib import Path
from datetime import datetime
import uuid
import yaml
from yaml import SafeLoader
from backend.services.SKIN_TELLIGENT.core import Detector, ROIExtractor , Classifier , GradCAMPlusPlus , apply_heatmap_on_image
from config.vision_config import DetectorConfig , PredictionConfig,Paths,Config
from logger import SKIN_TELLIGENT_logger as logger
from PIL import Image




class InferencePipeline:
    """
    InferencePipeline

    Purpose:
        runs detection -> ROI extraction -> classification -> Explainabilty 
    """

    def __init__(self):
        """
        Initialize pipeline using YAML config

        args:
            config_path (str): path to configuration file
        """

        logger.info(f"Initializing InferencePipeline")

        self.config =  DetectorConfig()

        detector_config = DetectorConfig(
            confidence_threshold=self.config.confidence_threshold,
            prob_threshold=self.config.prob_threshold,
            nms_threshold=self.config.nms_threshold,
            input_width=self.config.input_width,
            input_height=self.config.input_height,
        )

        self.Paths = Paths()
        self.detector = Detector(
            model_path= self.Paths.detector_model,
            yaml_path=str(self.Paths.data_yaml),
            config=detector_config
        )

        classifier_config = PredictionConfig(
            model_path=Path(self.Paths.classifier_model),
            device="cpu"
        )
        #clf
        self.classifier = Classifier(config=classifier_config)

        # Gradcam 
        self.gradcam = GradCAMPlusPlus(self.classifier.model)

        #ROI extractor
        self.roi_extractor = ROIExtractor()

        # Load disease labels
        self.class_labels = self.load_class_labels(str(Paths.classifier_labels))

        logger.info("Inference Pipeline initialized successfully.")


    def load_class_labels(self, labels_path: str):
        """
        Load disease class labels

        args:
            labels_path (str): path to classifier labels yaml

        returns:
            list : disease class names
        """

        if not os.path.exists(labels_path):
            logger.warning(f"Labels YAML not found at {labels_path}")
            return []

        with open(labels_path, "r") as f:
            data = yaml.load(f, Loader=SafeLoader)

        return [data["names"][i] for i in sorted(data["names"].keys())]

    def create_run_output_dirs(self):
        """Create a unique output folder for each SKIN_TELLIGENT request."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{timestamp}_{uuid.uuid4().hex}"

        run_dir = Path("output") / "SKIN_TELLIGENT" / run_id
        gradcam_dir = run_dir / "gradcam"
        detections_dir = run_dir / "detections"

        run_dir.mkdir(parents=True, exist_ok=True)
        gradcam_dir.mkdir(parents=True, exist_ok=True)
        detections_dir.mkdir(parents=True, exist_ok=True)

        return {
            "run_id": run_id,
            "run_dir": run_dir,
            "gradcam_dir": gradcam_dir,
            "detections_dir": detections_dir,
        }

    def save_image(self, path: Path, image, description: str):
        """Save image and log if write fails."""
        ok = cv2.imwrite(str(path), image)
        if not ok:
            logger.warning(f"Failed to save {description} at {path}")
        return str(path)

    def draw_detection_boxes(self, image, boxes, confidences, x_factor, y_factor):
        """Render detected boxes on a copy of the original image."""
        boxed_image = image.copy()

        for i, box in enumerate(boxes):
            left = int(box[0] * x_factor)
            top = int(box[1] * y_factor)
            width = int(box[2] * x_factor)
            height = int(box[3] * y_factor)

            right = max(left + width, left + 1)
            bottom = max(top + height, top + 1)

            cv2.rectangle(boxed_image, (left, top), (right, bottom), (0, 255, 0), 2)

            confidence = float(confidences[i]) if i < len(confidences) else 0.0
            label = f"det_{i}: {confidence:.2f}"
            cv2.putText(
                boxed_image,
                label,
                (left, max(top - 8, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        return boxed_image

    # ==========================
    # FASTAPI IMAGE PIPELINE ===
    # ==========================

    def run_image(self, image):
        output_paths = self.create_run_output_dirs()
        run_dir = output_paths["run_dir"]
        gradcam_dir = output_paths["gradcam_dir"]
        detections_dir = output_paths["detections_dir"]

        original_image_path = self.save_image(
            run_dir / "original_image.jpg", image, "original image"
        )

        boxes, confidences, classes, x_factor, y_factor = self.detector.detect(image)

        boxed_image = self.draw_detection_boxes(image, boxes, confidences, x_factor, y_factor)
        boxed_image_path = self.save_image(
            run_dir / "original_with_detection_boxes.jpg",
            boxed_image,
            "original image with detection boxes",
        )

        output_info = {
            "run_id": output_paths["run_id"],
            "run_dir": str(run_dir),
            "original_image": original_image_path,
            "detection_boxes_image": boxed_image_path,
            "gradcam_dir": str(gradcam_dir),
            "detections_dir": str(detections_dir),
        }

        if not boxes:

            high_conf_indices = [
                i for i, conf in enumerate(confidences) if conf >= 0.50
            ]

            if len(high_conf_indices) == 0:

                logger.warning("No high-confidence detections (>=50%). Falling back to full image classification.")

                classification_results = []

                try:
                    preds = self.classifier.predict(image)

                    if preds and isinstance(preds, dict):

                        try:
                            pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                            input_tensor = self.classifier.transform.preprocess_image(
                                pil_img
                            ).unsqueeze(0)

                            top_predictions = preds.get("top_3_predictions") or [
                                {
                                    "class_name": preds.get("class_name", "unknown"),
                                    "confidence": float(preds.get("confidence", 0.0)),
                                    "class_idx": int(preds.get("class_idx", 0)),
                                }
                            ]

                            top_3_gradcams = []
                            for rank, top_pred in enumerate(top_predictions[:3], start=1):
                                class_idx = int(top_pred.get("class_idx", 0))

                                heatmap = self.gradcam.generate_cam(
                                    input_tensor,
                                    target_class=class_idx,
                                    upsample_size=image.shape[:2]
                                )

                                overlay = apply_heatmap_on_image(image, heatmap)
                                gradcam_path = os.path.join(
                                    str(gradcam_dir),
                                    f"gradcam_full_image_top{rank}_class{class_idx}.jpg"
                                )
                                cv2.imwrite(gradcam_path, overlay)

                                top_3_gradcams.append(
                                    {
                                        "rank": rank,
                                        "class_name": top_pred.get("class_name", f"class_{class_idx}"),
                                        "confidence": float(top_pred.get("confidence", 0.0)),
                                        "class_idx": class_idx,
                                        "gradcam": gradcam_path,
                                    }
                                )

                            preds["top_3_gradcams"] = top_3_gradcams
                            if top_3_gradcams:
                                preds["gradcam"] = top_3_gradcams[0]["gradcam"]
                        except Exception:
                            logger.exception("Failed to generate full-image Grad-CAM")

                        if preds["confidence"] < 0.60:
                            logger.warning(f"Low classification confidence: {preds['confidence']:.2f}")

                        classification_results.append(preds)

                except Exception:
                    logger.exception("Full-image classification failed.")

                return boxed_image, [], classification_results, output_info

        # -----------------------------
        # Extract ROIs
        # -----------------------------
        cropped_regions = self.roi_extractor.crop_rois(image, boxes, x_factor, y_factor)
        classification_results = []


        # -----------------------------
        # Classify each ROI
        # -----------------------------
        for i, crop in enumerate(cropped_regions):

            preds = self.classifier.predict(crop)

            logger.info(f"Classifier output for ROI {i}: {preds}")

            roi_path = str(detections_dir / f"detection_{i}.jpg")
            cv2.imwrite(roi_path, crop)

            preds["roi_image"] = roi_path
            preds["detection_image"] = roi_path
            preds["roi_index"] = i

            if preds["confidence"] < 0.60:
                logger.warning(f"ROI {i}: Low classification confidence: {preds['confidence']:.2f}")
                preds["warning"] = "Low confidence prediction"

            if i < len(confidences):
                preds["det_confidence"] = float(confidences[i])

            # ==========================
            # GradCAM EXPLAINABILITY
            # ==========================
            try:
                pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

                input_tensor = self.classifier.transform.preprocess_image(
                    pil_img
                ).unsqueeze(0)

                top_predictions = preds.get("top_3_predictions") or [
                    {
                        "class_name": preds.get("class_name", "unknown"),
                        "confidence": float(preds.get("confidence", 0.0)),
                        "class_idx": int(preds.get("class_idx", 0)),
                    }
                ]

                top_3_gradcams = []
                for rank, top_pred in enumerate(top_predictions[:3], start=1):
                    class_idx = int(top_pred.get("class_idx", 0))

                    heatmap = self.gradcam.generate_cam(
                        input_tensor,
                        target_class=class_idx,
                        upsample_size=crop.shape[:2]
                    )

                    overlay = apply_heatmap_on_image(crop, heatmap)
                    gradcam_path = os.path.join(
                        str(gradcam_dir),
                        f"gradcam_roi_{i}_top{rank}_class{class_idx}.jpg"
                    )
                    cv2.imwrite(gradcam_path, overlay)

                    top_3_gradcams.append(
                        {
                            "rank": rank,
                            "class_name": top_pred.get("class_name", f"class_{class_idx}"),
                            "confidence": float(top_pred.get("confidence", 0.0)),
                            "class_idx": class_idx,
                            "gradcam": gradcam_path,
                        }
                    )

                preds["top_3_gradcams"] = top_3_gradcams
                if top_3_gradcams:
                    preds["gradcam"] = top_3_gradcams[0]["gradcam"]

            except Exception:
                logger.exception("Failed to generate Grad-CAM")

            classification_results.append(preds)

        return boxed_image, cropped_regions, classification_results, output_info