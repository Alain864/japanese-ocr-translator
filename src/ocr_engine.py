"""OCR engine module using Tesseract for Japanese text extraction with manga support."""

import logging
from typing import Dict, List
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import cv2
import numpy as np

from src.config import Config

logger = logging.getLogger(__name__)


class OCREngine:
    """Tesseract OCR wrapper for Japanese text extraction with manga support."""
    
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
    
    def _preprocess_for_manga(self, image: Image.Image) -> Image.Image:
        """
        Advanced preprocessing for manga/comic images.
        
        Handles:
        - Binarization for black/white manga
        - Noise removal (screentones)
        - Contrast enhancement
        """
        # Convert PIL to OpenCV format
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Adaptive thresholding for better text extraction
        # This handles varying brightness across the image
        binary = cv2.adaptiveThreshold(
            denoised, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Convert back to PIL
        result = Image.fromarray(cleaned)
        
        return result
    
    def extract_text(self, image: Image.Image) -> Dict[str, any]:
        """Extract text from an image using OCR with multiple strategies."""
        
        best_result = {'text': '', 'confidence': 0.0, 'has_text': False}
        
        # Strategy 1: Try with manga preprocessing and vertical text
        try:
            processed = self._preprocess_for_manga(image)
            
            # PSM 5: Single vertical block (for manga)
            config_vertical = r'--psm 5 --oem 3'
            
            text_vertical = pytesseract.image_to_string(
                processed,
                lang=self.lang,
                config=config_vertical
            ).strip()
            
            if text_vertical:
                # Get confidence
                data = pytesseract.image_to_data(
                    processed,
                    lang=self.lang,
                    config=config_vertical,
                    output_type=pytesseract.Output.DICT
                )
                
                confidences = [float(c) for c in data['conf'] if c != -1]
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                
                logger.info(f"Strategy 1 (vertical): {len(text_vertical)} chars, {avg_conf:.1f}% confidence")
                
                if avg_conf > best_result['confidence'] * 100:
                    best_result = {
                        'text': text_vertical,
                        'confidence': avg_conf / 100.0,
                        'has_text': True
                    }
        except Exception as e:
            logger.warning(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Try with sparse text detection
        try:
            processed = self._preprocess_for_manga(image)
            
            # PSM 11: Sparse text
            config_sparse = r'--psm 11 --oem 3'
            
            text_sparse = pytesseract.image_to_string(
                processed,
                lang=self.lang,
                config=config_sparse
            ).strip()
            
            if text_sparse:
                data = pytesseract.image_to_data(
                    processed,
                    lang=self.lang,
                    config=config_sparse,
                    output_type=pytesseract.Output.DICT
                )
                
                confidences = [float(c) for c in data['conf'] if c != -1]
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                
                logger.info(f"Strategy 2 (sparse): {len(text_sparse)} chars, {avg_conf:.1f}% confidence")
                
                if avg_conf > best_result['confidence'] * 100:
                    best_result = {
                        'text': text_sparse,
                        'confidence': avg_conf / 100.0,
                        'has_text': True
                    }
        except Exception as e:
            logger.warning(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Standard horizontal text
        try:
            processed = self._preprocess_for_manga(image)
            
            # PSM 6: Uniform block of text
            config_standard = r'--psm 6 --oem 3'
            
            text_standard = pytesseract.image_to_string(
                processed,
                lang=self.lang,
                config=config_standard
            ).strip()
            
            if text_standard:
                data = pytesseract.image_to_data(
                    processed,
                    lang=self.lang,
                    config=config_standard,
                    output_type=pytesseract.Output.DICT
                )
                
                confidences = [float(c) for c in data['conf'] if c != -1]
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                
                logger.info(f"Strategy 3 (standard): {len(text_standard)} chars, {avg_conf:.1f}% confidence")
                
                if avg_conf > best_result['confidence'] * 100:
                    best_result = {
                        'text': text_standard,
                        'confidence': avg_conf / 100.0,
                        'has_text': True
                    }
        except Exception as e:
            logger.warning(f"Strategy 3 failed: {e}")
        
        # Check if we got meaningful results
        if best_result['confidence'] < Config.OCR_CONFIDENCE_THRESHOLD:
            best_result['has_text'] = False
            logger.info(f"Best result below threshold: {best_result['confidence']:.2%}")
        elif best_result['text']:
            logger.info(f"✓ Extracted {len(best_result['text'])} characters with {best_result['confidence']:.2%} confidence")
        else:
            best_result['has_text'] = False
            logger.info("No text detected")
        
        return best_result