"""Japanese OCR Translator package."""

__version__ = '1.0.0'

from .config import Config
from .pdf_processor import PDFProcessor
from .ocr_engine import OCREngine
from .translator import Translator

__all__ = [
    'Config',
    'PDFProcessor',
    'OCREngine',
    'Translator',
]
