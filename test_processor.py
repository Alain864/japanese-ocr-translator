"""Tests for the OCR translator components."""

import pytest
from PIL import Image

from src.ocr_engine import OCREngine
from src.translator import Translator
from src.config import Config


class TestOCREngine:
    """Tests for OCR engine."""
    
    def test_ocr_initialization(self):
        """Test OCR engine initializes correctly."""
        ocr = OCREngine()
        assert ocr.lang == Config.TESSERACT_LANG
    
    def test_extract_text_from_empty_image(self):
        """Test OCR on empty image."""
        ocr = OCREngine()
        img = Image.new('RGB', (100, 100), color='white')
        result = ocr.extract_text(img)
        
        assert 'text' in result
        assert 'confidence' in result
        assert 'has_text' in result


class TestTranslator:
    """Tests for translator."""
    
    @pytest.fixture
    def translator(self):
        """Create translator instance."""
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == 'your_openai_api_key_here':
            pytest.skip("OpenAI API key not configured")
        return Translator()
    
    def test_translator_initialization(self, translator):
        """Test translator initializes correctly."""
        assert translator.model == Config.OPENAI_MODEL
        assert translator.client is not None
    
    def test_translate_empty_text(self, translator):
        """Test translation of empty text."""
        result = translator.translate("")
        assert result['success'] is False


class TestConfig:
    """Tests for configuration."""
    
    def test_config_has_required_fields(self):
        """Test config has all required fields."""
        assert hasattr(Config, 'OPENAI_API_KEY')
        assert hasattr(Config, 'OPENAI_MODEL')
        assert hasattr(Config, 'OUTPUT_DIR')
