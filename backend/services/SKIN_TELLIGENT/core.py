"""

"""
import cv2
import numpy as np
import yaml
from yaml.loader import SafeLoader
from pathlib import Path
import os
from typing import Union, IO
import torch
import torch.nn as nn
from torch import load as torch_load
import torch.nn.functional as F
from PIL import Image
from config.vision_config import DetectorConfig, PredictionConfig
from backend.services.SKIN_TELLIGENT.preprocess import Transform
from logger import SKIN_TELLIGENT_logger as logger 
from config.vision_config import Paths


# =========================================================
#                       DETECTOR
# =========================================================

class Detector:

    def __init__(self, model_path: Path | str, yaml_path: Path | str, config: DetectorConfig ):
        """
        Initialize detector

        Args:
            model_path (Path): path to ONNX detection model
            yaml_path (str): path to YAML file containing labels
            config (DetectorConfig): detector configuration
        """

        self.config = config if config else DetectorConfig()
        self.labels = self.load_labels(yaml_path)
        self.model = self.load_model(model_path)


    def load_labels(self, labels_file_path: Path | str):
        """
        Load class labels from YAML file

        args:
            labels_file_path (str): path to labels yaml file

        returns:
            list : list of class names
        """

        try:
            labels_file_path = str(labels_file_path)

            with open(labels_file_path, "r") as f:
                data_yaml = yaml.load(f, Loader=SafeLoader)

            logger.info(f"YAML file {labels_file_path} loaded successfully.")

            return data_yaml["names"]

        except Exception as e:

            logger.error(f"Error loading YAML file from {labels_file_path}: {e}")

            raise e
    

    def load_model(self, file_path: Path | str):
        """
        Load detector model from ONNX file

        args:
            file_path (str): path to onnx model file

        returns:
            cv2.dnn_Net : loaded detection model
        """

        try:

            file_path = str(file_path)

            if not os.path.exists(file_path):
                logger.warning(f"Detector model not found at {file_path}; detector will be disabled.")
                return None

            detector_model = cv2.dnn.readNetFromONNX(file_path)

            detector_model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)

            detector_model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

            return detector_model

        except Exception as e:

            logger.warning(
                f"Detector model at {file_path} could not be loaded as ONNX; "
                "falling back to classification-only inference."
            )
            logger.debug(f"Detector load failure details: {e}")
            return None


    def prepare_image(self, image: np.ndarray):
        """
        Prepare image for detector input

        args:
            image (np.ndarray): input image

        returns:
            blob, input_img, x_factor, y_factor
        """
        if isinstance(image,np.ndarray):
            try:
                img = image.copy()
            except Exception as e:
                logger.error("error in copying image during preprocessing .. error :{e}")
     
            height, width , c = img.shape

            max_wh = max(width, height)

            input_img = np.zeros((max_wh, max_wh, c), dtype=np.uint8)

            input_img[0:height, 0:width] = img

            blob = cv2.dnn.blobFromImage(
                image=input_img,
                scalefactor = 1/255.0,
                size = (self.config.input_width, self.config.input_height),
                swapRB = True,
                crop = False
            )

            x_factor = max_wh / self.config.input_width
            y_factor = max_wh / self.config.input_height

            return blob, input_img, x_factor, y_factor
        else:
            logger.error("The Image file found corrupted during preprocessing in Prepare image...")


    def apply_nms(self, detections: np.ndarray):
        """
        Filter detections using thresholds

        args:
            detections (np.ndarray): raw model detections

        returns:
            boxes, confidences, classes
        """

        boxes = []
        confidences = []
        classes = []

        for i in range(len(detections)):

            row = detections[i]

            confidence = row[4]

            if confidence > max(self.config.confidence_threshold, 0.50):

                class_score = row[5:].max()

                class_id = row[5:].argmax()

                if class_score > self.config.prob_threshold:

                    cx, cy, w, h = row[0:4]

                    left = int(cx - 0.5*w)
                    top = int(cy - 0.5*h)
                    width = int(w)
                    height = int(h)

                    box = np.array([left, top, width, height])

                    boxes.append(box)
                    confidences.append(confidence)
                    classes.append(class_id)

        return boxes, confidences, classes


    def detect(self, image: np.ndarray):
        """
        Perform lesion detection 

        args:
            image (np.ndarray): input image

        returns:
            filtered_boxes, filtered_confidences,
            filtered_classes, x_factor, y_factor
        """

        if self.model is None:
            logger.warning("Detector is unavailable; skipping detection and using full-image classification fallback.")
            return [], [], [], 1.0, 1.0

        logger.info("Starting detection process..")

        blob, input_img, x_factor, y_factor = self.prepare_image(image)

        self.model.setInput(blob)

        preds = self.model.forward()

        if preds.ndim == 2:
            preds = np.expand_dims(preds, axis=0)

        detections = preds[0]

        boxes, confidences, classes = self.apply_nms(detections)

        indices = cv2.dnn.NMSBoxes(
            boxes,
            confidences,
            self.config.prob_threshold,
            self.config.nms_threshold
        )

        if len(indices) > 0:

            indices = indices.flatten()

            filtered_boxes = [boxes[i] for i in indices]
            filtered_confidences = [confidences[i] for i in indices]
            filtered_classes = [classes[i] for i in indices]

            return filtered_boxes, filtered_confidences, filtered_classes, x_factor, y_factor

        else:
            return [], [], [], x_factor, y_factor


# =====================================================
#                     ROI EXTRACTOR
# ==================================================
class ROIExtractor:

    def __init__(self):
        """
        Extracts the region of interest (ROI) from the original image based on the detected bounding boxes.

        Purpose:
            crops regions of interest from detection boxes
        """
        pass


    def crop_rois(self, image: np.ndarray, boxes, x_factor, y_factor):
        """
        Crop ROIs from detected bounding boxes

        args:
            image (np.ndarray): original image
            boxes (list): detection boxes
            x_factor (float): width scale factor
            y_factor (float): height scale factor

        returns:
            list : ROI images
        """

        rois = []

        for box in boxes:

            left = int(box[0] * x_factor)
            top = int(box[1] * y_factor)
            width = int(box[2] * x_factor)
            height = int(box[3] * y_factor)

            roi = image[top:top + height, left:left + width]

            rois.append(roi)

        return rois


# =========================================================
#                      CLASSIFIER
# =========================================================

class Classifier:

    def __init__(self, config: PredictionConfig):
        """
        Initialize classifier

        args:
            config (PredictionConfig): classifier configuration
        """

        self.config = config
        self.device = config.device
        self.model_path = config.model_path
        self.labels_path = Paths.classifier_labels

        self.class_labels = self.load_labels(self.labels_path)
        self.model = self.load_model()

        self.transform = Transform()


    def load_labels(self, labels_path):

        if labels_path is None:
            return []

        if not os.path.exists(labels_path):
            logger.warning(f"Labels file not found: {labels_path}")
            return []

        with open(labels_path, "r") as f:

            data = yaml.load(f, Loader=SafeLoader)

        labels = [data["names"][i] for i in sorted(data["names"].keys())]

        return labels


    # def load_model(self):

    #     if not os.path.exists(self.model_path):

    #         logger.error(f"Model file not found: {self.model_path}")

    #         return None

    #     model = torch_load(self.model_path, map_location=self.device, weights_only=False)

    #     if hasattr(model, "to"):
    #         model = model.to(self.device)

    #     logger.info("Classifier model loaded successfully")

    #     return model
    #  ======================================
    #   [Above] If Fallback to previous model 
    #  ======================================

    def _build_model(self):

        from torchvision import models
        import torch.nn as nn

        num_classes = len(self.class_labels)

        model = models.efficientnet_b4(weights=None)

        in_features = model.classifier[1].in_features

        model.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(in_features, num_classes)
        )

        return model

    def load_model(self):

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            return None

        checkpoint = torch_load(self.model_path, map_location=self.device)

        if isinstance(checkpoint, dict):

            if "model_state" in checkpoint:
                state_dict = checkpoint["model_state"]

            elif "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]

            else:
                state_dict = checkpoint  

        else:
            model = checkpoint.to(self.device)
            model.eval()
            return model

        model = self._build_model()

        model.load_state_dict(state_dict)

        model = model.to(self.device)
        model.eval()

        logger.info("Classifier model loaded successfully")

        return model


    def predict(self, image_input: Union[str, Path, IO, Image.Image, np.ndarray]):
        """
        Predict disease class

        args:
            image_input : ROI image

        returns:
            dict : prediction result
        """

        if isinstance(image_input, np.ndarray):

            image = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))

        elif isinstance(image_input, Image.Image):

            image = image_input

        else:

            image = Image.open(image_input).convert("RGB")

        image_tensor = self.transform.preprocess_image(image).unsqueeze(0).to(self.device)

        self.model.eval()

        with torch.no_grad():

            output = self.model(image_tensor)

            probabilities = nn.Softmax(dim=1)(output)

            probs = probabilities.cpu().numpy().squeeze()

            top_idx = int(np.argmax(probs))

            confidence = float(probs[top_idx])

            top_k = min(3, int(probs.shape[0]))
            top_indices = np.argsort(probs)[::-1][:top_k]
            top_3_predictions = []
            for idx in top_indices:
                class_idx = int(idx)
                class_label = self.class_labels[class_idx] if self.class_labels else f"class_{class_idx}"
                top_3_predictions.append(
                    {
                        "class_name": class_label,
                        "confidence": float(probs[class_idx]),
                        "class_idx": class_idx,
                    }
                )

            class_name = self.class_labels[top_idx] if self.class_labels else f"class_{top_idx}"

            logger.info(f"Predicted {class_name} ({confidence:.4f})")

            return {
                "class_name": class_name,
                "confidence": confidence,
                "class_idx": top_idx,
                "top_3_predictions": top_3_predictions,
            }



# ======================================================
#                GRADCAM++ EXPLAINABILITY
# =========================================================

class GradCAMPlusPlus:

    def __init__(self, model, target_layer=None):
        """
        Initialize GradCAM++

        args:
            model : pytorch model
            target_layer : convolution layer for cam
        """

        self.model = model
        self.model.eval()

        self.activations = None
        self.gradients = None

        if target_layer is None:
            target_layer = self._find_target_layer()

        self.target_layer = target_layer

        self._register_hooks()


    def _find_target_layer(self):
        """
        Find last convolution layer

        returns:
            nn.Module : conv layer used for gradcam
        """

        target = None

        for name, module in self.model.named_modules():

            if isinstance(module, nn.Conv2d):
                target = module

        if target is None:
            raise RuntimeError("No Conv2d layer found in model for Grad-CAM")

        return target


    def _register_hooks(self):
        """
        Register forward and backward hooks

        Purpose:
            capture activations and gradients
        """

        def forward_hook(module, input, output):

            self.activations = output.detach()


        def backward_hook(module, grad_in, grad_out):

            self.gradients = grad_out[0].detach()


        self.target_layer.register_forward_hook(forward_hook)

        self.target_layer.register_backward_hook(backward_hook)


    def generate_cam(self, input_tensor, target_class=None, upsample_size=None):
        """
        Generate GradCAM heatmap

        args:
            input_tensor (torch.Tensor): model input
            target_class (int): class index
            upsample_size (tuple): resize heatmap

        returns:
            np.ndarray : heatmap
        """

        device = next(self.model.parameters()).device

        input_tensor = input_tensor.to(device)

        output = self.model(input_tensor)

        if isinstance(output, tuple) or isinstance(output, list):
            logits = output[0]
        else:
            logits = output

        if target_class is None:

            target_class = int(torch.argmax(logits, dim=1).item())


        self.model.zero_grad()

        one_hot = torch.zeros_like(logits, device=device)

        one_hot[0, target_class] = 1.0

        logits.backward(gradient=one_hot, retain_graph=True)


        activations = self.activations[0]

        grads = self.gradients[0]


        grads_power_2 = grads.pow(2)

        grads_power_3 = grads.pow(3)


        eps = 1e-8


        alpha_num = grads_power_2

        alpha_denom = 2 * grads_power_2 + activations * grads_power_3.sum(dim=(1,2), keepdim=True)

        alpha = alpha_num / (alpha_denom + eps)


        score = logits[0, target_class].detach()


        positive_grads = F.relu(torch.exp(score) * grads)


        weights = (alpha * positive_grads).sum(dim=(1,2))


        cam = torch.zeros(activations.shape[1:], dtype=torch.float32, device=device)


        for i, w in enumerate(weights):

            cam += w * activations[i]


        cam = F.relu(cam)


        cam_np = cam.detach().cpu().numpy()


        cam_np -= cam_np.min()


        if cam_np.max() != 0:

            cam_np = cam_np / (cam_np.max() + eps)


        if upsample_size is not None:

            cam_np = cv2.resize(cam_np, (upsample_size[1], upsample_size[0]))


        return cam_np



def apply_heatmap_on_image(image_np, heatmap, colormap=None, alpha=0.5):
    """
    Overlay heatmap on image

    args:
        image_np (np.ndarray): original image
        heatmap (np.ndarray): gradcam heatmap
        colormap : opencv colormap
        alpha (float): blending factor

    returns:
        np.ndarray : heatmap overlay image
    """

    if colormap is None:

        colormap = cv2.COLORMAP_TURBO

    heatmap = cv2.GaussianBlur(heatmap, (11,11), 0)
    heatmap_uint8 = (heatmap * 255).astype('uint8')


    heatmap_color = cv2.applyColorMap(heatmap_uint8, colormap)




    if image_np.dtype != 'uint8':

        image_uint8 = (image_np * 255).astype('uint8')

    else:

        image_uint8 = image_np

    
    overlay = cv2.addWeighted(image_uint8, 1 - alpha, heatmap_color, alpha, 0)


    return overlay