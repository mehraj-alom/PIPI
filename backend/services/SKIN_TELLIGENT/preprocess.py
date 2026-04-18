from torchvision.transforms import v2 as transform
from config.vision_config import ClassifierConstants
import torch
from PIL import Image


class Transform:

    def __init__(self):
        self.transform_pipeline = transform.Compose([
            transform.Resize((380, 380)),
            transform.ToImage(),
            transform.ToDtype(torch.float32, scale=True),
            transform.Normalize(mean=ClassifierConstants.imagenet_mean, std=ClassifierConstants.imagenet_std),
        ])

    def preprocess_image(self, image):
        """
        Loads and preprocesses an image for model prediction.

        Handles:
        - File path (str)
        - PIL Image
        - Converts grayscale → RGB
        - Normalizes to ImageNet mean/std

        Returns:
            torch.Tensor : Preprocessed image tensor.
        """
        if not isinstance(image, Image.Image):
            try:
                image = Image.open(image)
            except Exception as e:
                raise ValueError(f"Cannot open image: {e}")

        if image.mode != "RGB":
            image = image.convert("RGB")

        try:
            return self.transform_pipeline(image)
        except Exception as e:
            raise ValueError(f"error during preprocessing: {e}")