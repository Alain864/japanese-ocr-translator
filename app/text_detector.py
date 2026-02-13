"""
text_detector.py
─────────────────────────────────────────────
Uses Google Cloud Vision API for accurate Japanese text detection.
Provides pixel-perfect coordinate detection for manga text.
"""

from typing import List, Dict
from PIL import Image
import io

from google.cloud import vision

from app.logger import get_logger
from config.settings import GOOGLE_CLOUD_API_KEY

log = get_logger("text_detector")


class TextDetector:
    """Accurate text detection using Google Cloud Vision API."""

    def __init__(self):
        """
        Initialize Google Cloud Vision client for Japanese text detection.
        
        Uses API key authentication for simplicity.
        """
        log.info("Initializing Google Cloud Vision for Japanese text detection...")

        if not GOOGLE_CLOUD_API_KEY:
            raise ValueError(
                "GOOGLE_CLOUD_API_KEY is not set. "
                "Please add it to your .env file."
            )

        try:
            # Initialize Vision API client
            self.client = vision.ImageAnnotatorClient(
                client_options={"api_key": GOOGLE_CLOUD_API_KEY}
            )
            log.info("Google Cloud Vision initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize Google Cloud Vision: {e}")
            raise

    def detect_text(self, image: Image.Image, label: str = "") -> List[Dict]:
        """
        Detect Japanese text in an image with accurate bounding boxes.
        
        Uses document text detection to get structured blocks (paragraphs)
        instead of individual characters, providing better translations
        and more accurate bounding boxes.

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
        log.info(f"  [{label}] Detecting Japanese text with Google Cloud Vision...")

        # Convert PIL Image to bytes for Google Cloud Vision
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        img_width, img_height = image.size

        try:
            # Create Vision API image object
            vision_image = vision.Image(content=img_byte_arr.read())

            # Run DOCUMENT_TEXT_DETECTION for structured output
            # This gives us paragraphs/blocks instead of individual characters
            response = self.client.document_text_detection(image=vision_image)

            if response.error.message:
                log.error(f"  [{label}] Vision API error: {response.error.message}")
                return []

            # Use the full document structure for better text grouping
            detections = self._extract_text_blocks(response, img_width, img_height, label)
            
            log.info(f"  [{label}] Detected {len(detections)} text block(s)")
            return detections

        except Exception as exc:
            log.error(f"  [{label}] Google Cloud Vision detection failed: {exc}")
            return []

    def _extract_text_blocks(
        self, 
        response, 
        img_width: int, 
        img_height: int,
        label: str
    ) -> List[Dict]:
        """
        Extract text blocks from the document structure.
        
        Uses paragraphs as the unit of text detection - this gives us
        complete phrases/sentences instead of individual characters,
        leading to better translations and more useful bounding boxes.
        """
        detections = []
        
        # The full text annotation contains the document structure
        document = response.full_text_annotation
        
        if not document or not document.pages:
            return detections

        for page in document.pages:
            for block in page.blocks:
                # Skip non-text blocks
                if block.block_type != vision.Block.BlockType.TEXT:
                    continue
                    
                for paragraph in block.paragraphs:
                    # Extract the text from the paragraph
                    text = self._get_paragraph_text(paragraph)
                    
                    if not text or len(text.strip()) < 2:
                        continue
                    
                    # Check if this contains Japanese characters
                    if not self._contains_japanese(text):
                        continue
                    
                    # Get bounding box from paragraph
                    bbox_norm = self._vertices_to_normalized_bbox(
                        paragraph.bounding_box.vertices,
                        img_width,
                        img_height
                    )
                    
                    if bbox_norm["width"] <= 0 or bbox_norm["height"] <= 0:
                        continue
                    
                    # Get confidence from paragraph
                    confidence = paragraph.confidence if paragraph.confidence else 0.9
                    
                    detections.append({
                        "japanese_text": text.strip(),
                        "bounding_box": bbox_norm,
                        "confidence": float(confidence)
                    })

        return detections

    def _get_paragraph_text(self, paragraph) -> str:
        """
        Extract the full text from a paragraph structure.
        """
        text_parts = []
        for word in paragraph.words:
            word_text = "".join(symbol.text for symbol in word.symbols)
            text_parts.append(word_text)
        return " ".join(text_parts)

    def _contains_japanese(self, text: str) -> bool:
        """
        Check if text contains Japanese characters (Hiragana, Katakana, Kanji).
        """
        for char in text:
            # Hiragana: 3040-309F
            # Katakana: 30A0-30FF
            # Kanji (CJK Unified Ideographs): 4E00-9FFF
            code = ord(char)
            if (0x3040 <= code <= 0x309F or
                0x30A0 <= code <= 0x30FF or
                0x4E00 <= code <= 0x9FFF):
                return True
        return False

    def _vertices_to_normalized_bbox(
        self,
        vertices,
        img_width: int,
        img_height: int
    ) -> Dict[str, float]:
        """
        Convert Google Cloud Vision vertices to normalized bounding box.

        Parameters
        ----------
        vertices : list
            List of Vertex objects from Google Cloud Vision.
            Each vertex has x, y coordinates.
        img_width : int
            Image width in pixels.
        img_height : int
            Image height in pixels.

        Returns
        -------
        dict
            Normalized bounding box {x, y, width, height} in 0-1 range.
        """
        # Extract x and y coordinates from vertices
        x_coords = [v.x for v in vertices if hasattr(v, 'x') and v.x is not None]
        y_coords = [v.y for v in vertices if hasattr(v, 'y') and v.y is not None]

        if not x_coords or not y_coords:
            return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}

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