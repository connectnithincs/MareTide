"""
Image Preprocessing Pipeline for Container Slip Documents.
Includes contrast normalization, noise reduction, deskewing, adaptive binarization,
and automated document quality assessment (blur, contrast, resolution, rotation).
"""

import io
import cv2
import numpy as np
from PIL import Image
from typing import Union, Tuple, Optional, Dict, Any, List
from .config import MAX_IMAGE_DIMENSION, BILATERAL_D, BILATERAL_SIGMA_COLOR, BILATERAL_SIGMA_SPACE
from .models import DocumentQuality


class ImagePreprocessor:
    """
    Modular preprocessor for shipping documents, gate passes, and container slips.
    """

    @staticmethod
    def load_image(image_input: Union[bytes, str, Image.Image, np.ndarray]) -> np.ndarray:
        """
        Loads and standardizes input into a BGR numpy array (OpenCV format).
        """
        if isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 2:
                return cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
            return image_input
        elif isinstance(image_input, Image.Image):
            rgb = np.array(image_input.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode image bytes into valid image.")
            return img
        elif isinstance(image_input, str):
            img = cv2.imread(image_input, cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(f"Could not open or read image at path: {image_input}")
            return img
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    @classmethod
    def assess_document_quality(cls, image_input: Union[bytes, str, Image.Image, np.ndarray]) -> DocumentQuality:
        """
        Calculates image quality metrics: blur score (Laplacian variance), contrast (pixel std),
        resolution bounds, and rotation/skew issues.
        """
        img = cls.load_image(image_input)
        h, w = img.shape[:2]
        resolution_str = f"{w}x{h}"
        issues: List[str] = []

        # 1. Resolution Check
        if w < 400 or h < 300:
            issues.append("insufficient_resolution")

        # 2. Grayscale conversion for analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

        # 3. Blur Detection (Laplacian Variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = round(float(laplacian.var()), 2)
        if blur_score < 30.0:
            issues.append("blurred_image")

        # 4. Contrast Detection (Intensity standard deviation)
        contrast_score = round(float(gray.std()), 2)
        if contrast_score < 20.0:
            issues.append("low_contrast")

        # 5. Skew / Extreme Rotation Detection
        detected_angle = 0.0
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) >= 50:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            if angle < -45:
                detected_angle = -(90 + angle)
            else:
                detected_angle = -angle
            if abs(detected_angle) > 25.0:
                issues.append("extreme_rotation")

        # 6. Quality Classification
        if "insufficient_resolution" in issues and ("blurred_image" in issues or "low_contrast" in issues):
            quality = "unusable"
        elif blur_score < 10.0 or contrast_score < 10.0:
            quality = "unusable"
        elif len(issues) >= 2 or blur_score < 25.0:
            quality = "poor"
        elif len(issues) == 1:
            quality = "fair"
        else:
            quality = "good"

        return DocumentQuality(
            quality=quality,
            issues=issues,
            blur_score=blur_score,
            contrast_score=contrast_score,
            resolution=resolution_str,
            detected_angle=round(float(detected_angle), 2) if detected_angle != 0.0 else None
        )

    @classmethod
    def resize_to_standard(cls, img: np.ndarray, max_dim: int = MAX_IMAGE_DIMENSION) -> np.ndarray:
        """
        Resizes the image so its maximum dimension does not exceed max_dim, preserving aspect ratio.
        """
        h, w = img.shape[:2]
        if max(h, w) <= max_dim:
            return img

        scale = max_dim / float(max(h, w))
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    @classmethod
    def deskew(cls, img: np.ndarray, known_angle: Optional[float] = None) -> np.ndarray:
        """
        Detects document skew angle (or reuses pre-detected angle) and rotates the image back to horizontal.
        """
        if known_angle is not None:
            angle = known_angle
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 50:
                return img
            rect = cv2.minAreaRect(coords)
            raw_angle = rect[-1]
            if raw_angle < -45:
                angle = -(90 + raw_angle)
            else:
                angle = -raw_angle

        # If angle is minor, avoid rotating
        if abs(angle) < 0.5 or abs(angle) > 45.0:
            return img

        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        deskewed = cv2.warpAffine(
            img, rot_mat, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return deskewed

    @classmethod
    def enhance_contrast_and_denoise(cls, img: np.ndarray, force_enhance: bool = False) -> np.ndarray:
        """
        Applies bilateral filtering and CLAHE (Contrast Limited Adaptive Histogram Equalization).
        """
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)

        enhanced_lab = cv2.merge((l_clahe, a, b))
        enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        # Bilateral filter for noise reduction while keeping edges crisp
        denoised = cv2.bilateralFilter(
            enhanced_bgr,
            d=BILATERAL_D,
            sigmaColor=BILATERAL_SIGMA_COLOR,
            sigmaSpace=BILATERAL_SIGMA_SPACE
        )
        return denoised

    @classmethod
    def process_for_ocr(
        cls,
        image_input: Union[bytes, str, Image.Image, np.ndarray],
        quality_meta: Optional[DocumentQuality] = None
    ) -> np.ndarray:
        """
        Executes full preprocessing pipeline and returns the optimized BGR image for OCR.
        Reuses quality assessment metadata if provided to avoid duplicate decoding and calculations.
        """
        img = cls.load_image(image_input) if not isinstance(image_input, np.ndarray) else image_input
        img = cls.resize_to_standard(img)
        
        known_angle = quality_meta.detected_angle if quality_meta else None
        img = cls.deskew(img, known_angle=known_angle)
        img = cls.enhance_contrast_and_denoise(img)
        return img


