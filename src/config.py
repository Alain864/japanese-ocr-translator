"""Configuration management for the OCR translator application."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    ROOT_DIR = Path(__file__).parent.parent
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    
    # Paths
    OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', 'data/output'))
    INPUT_DIR = Path('data/input')
    
    # OCR Configuration
    TESSERACT_LANG = os.getenv('TESSERACT_LANG', 'jpn')
    OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '0.5'))
    
    # Processing Configuration
    MAX_IMAGE_SIZE = int(os.getenv('MAX_IMAGE_SIZE', '4096'))
    DPI = int(os.getenv('DPI', '300'))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is required. Please set it in your .env file."
            )
        
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return True


Config.validate()
