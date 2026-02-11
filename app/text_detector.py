"""
text_detector.py
─────────────────────────────────────────────
Uses EasyOCR for accurate Japanese text detection and bounding boxes.
Provides pixel-perfect coordinate detection for manga text.
EasyOCR uses HuggingFace models and avoids PaddleOCR framework issues.
"""

from typing import List, Dict, Tuple
from PIL import Image
import numpy as np

import easyocr
from app.logger import get_logger

log = get_logger("text_detector")


class TextDetector:
    """Accurate text detection using EasyOCR."""

    def __init__(self):
        """Initialize EasyOCR with Japanese language support."""
        log.info("Initializing EasyOCR for Japanese text detection...")

        # Initialize EasyOCR reader for Japanese
        # Downloads HuggingFace models automatically on first use
        self.reader = easyocr.Reader(['ja'], gpu=False)

        log.info("EasyOCR initialized successfully")

    def detect_text(self, image: Image.Image, label: str = "") -> List[Dict]:
        """
        Detect Japanese text in an image with accurate bounding boxes.

        Parameters
        ----------
        image : PIL.Image.Image
            The page image to analyze.
        label : str, optional
            Human-readable label for logging.

        Returns
        -------
        list[dict]
            List of detected text regions, each containing:
            - japanese_text: The detected Japanese text
            - bounding_box: Normalized coordinates (0-1)
            - confidence: Detection confidence score
        """
        log.info(f"  [{label}] Detecting Japanese text with EasyOCR...")

        # Convert PIL Image to numpy array for EasyOCR
        img_array = np.array(image)
        img_height, img_width = img_array.shape[:2]

        try:
            # Run EasyOCR detection + recognition
            # Returns: [[([x1,y1], [x2,y2], [x3,y3], [x4,y4]), text, confidence], ...]
            result = self.reader.readtext(img_array, detail=1)

            if not result:
                log.info(f"  [{label}] No Japanese text detected")
                return []

            detections = []

            # Process each detected text region
            for detection in result:
                # detection format: ([bounding_box_points], text, confidence)
                bbox_points = detection[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                japanese_text = detection[1]
                confidence = float(detection[2])

                # Convert polygon points to normalized bounding box
                bbox_norm = self._points_to_normalized_bbox(
                    bbox_points, img_width, img_height
                )

                detections.append({
                    "japanese_text": japanese_text,
                    "bounding_box": bbox_norm,
                    "confidence": confidence
                })

            log.info(f"  [{label}] Detected {len(detections)} text region(s)")
            return detections

        except Exception as exc:
            log.error(f"  [{label}] EasyOCR detection failed: {exc}")
            return []

    def _points_to_normalized_bbox(
        self,
        points: List[List[float]],
        img_width: int,
        img_height: int
    ) -> Dict[str, float]:
        """
        Convert 4-point polygon to normalized bounding box.

        Parameters
        ----------
        points : list[list[float]]
            Four corner points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]].
        img_width : int
            Image width in pixels.
        img_height : int
            Image height in pixels.

        Returns
        -------
        dict
            Normalized bounding box {x, y, width, height} in 0-1 range.
        """
        # Extract x and y coordinates
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

        # Get min/max to form bounding box
        x_min = min(x_coords)
        x_max = max(x_coords)
        y_min = min(y_coords)
        y_max = max(y_coords)

        # Normalize to 0-1 range
        x_norm = x_min / img_width
        y_norm = y_min / img_height
        width_norm = (x_max - x_min) / img_width
        height_norm = (y_max - y_min) / img_height

        return {
            "x": float(x_norm),
            "y": float(y_norm),
            "width": float(width_norm),
            "height": float(height_norm)
        }
