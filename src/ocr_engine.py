"""OCR engine module using Tesseract for Japanese text extraction."""

import logging
from typing import Dict
import pytesseract
from PIL import Image

from .config import Config

logger = logging.getLogger(__name__)


class OCREngine:
    """Tesseract OCR wrapper for Japanese text extraction."""
    
    def __init__(self, lang: str = None):
        """Initialize OCR engine."""
        self.lang = lang or Config.TESSERACT_LANG
        self._verify_tesseract()
    
    def _verify_tesseract(self):
        """Verify Tesseract installation and language support."""
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
        except Exception as e:
            raise RuntimeError(
                f"Tesseract not found or not properly installed: {e}"
            )
        
        try:
            langs = pytesseract.get_languages()
            if self.lang not in langs:
                raise RuntimeError(
                    f"Language '{self.lang}' not available. "
                    f"Available languages: {', '.join(langs)}"
                )
            logger.info(f"Tesseract language '{self.lang}' is available")
        except Exception as e:
            logger.warning(f"Could not verify language support: {e}")
    
    def extract_text(self, image: Image.Image) -> Dict[str, any]:
        """Extract text from an image using OCR."""
        try:
            # Get detailed OCR data
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and calculate average confidence
            texts = []
            confidences = []
            
            for i, conf in enumerate(data['conf']):
                if conf != -1:
                    text = data['text'][i].strip()
                    if text:
                        texts.append(text)
                        confidences.append(float(conf))
            
            full_text = ' '.join(texts)
            avg_confidence = (
                sum(confidences) / len(confidences) 
                if confidences else 0.0
            )
            
            normalized_confidence = avg_confidence / 100.0
            
            result = {
                'text': full_text,
                'confidence': normalized_confidence,
                'has_text': bool(full_text and 
                               normalized_confidence >= Config.OCR_CONFIDENCE_THRESHOLD)
            }
            
            if result['has_text']:
                logger.info(
                    f"Extracted {len(full_text)} characters "
                    f"with {normalized_confidence:.2%} confidence"
                )
            else:
                logger.info("No text detected or confidence too low")
            
            return result
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                'text': '',
                'confidence': 0.0,
                'has_text': False,
                'error': str(e)
            }
