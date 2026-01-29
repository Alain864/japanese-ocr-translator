"""Translation module using OpenAI API for Japanese to English translation."""

import logging
from typing import Optional
from openai import OpenAI

from .config import Config

logger = logging.getLogger(__name__)


class Translator:
    """OpenAI-based translator for Japanese to English."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize translator."""
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.model = model or Config.OPENAI_MODEL
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"Translator initialized with model: {self.model}")
    
    def translate(self, japanese_text: str) -> dict:
        """Translate Japanese text to English."""
        if not japanese_text or not japanese_text.strip():
            return {
                'translation': '',
                'success': False,
                'error': 'Empty text provided'
            }
        
        try:
            logger.info(f"Translating text ({len(japanese_text)} characters)")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional translator specializing in Japanese to English translation. "
                            "Translate the provided Japanese text to natural, fluent English. "
                            "Only provide the translation without any explanations or additional text."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Translate this Japanese text to English:\n\n{japanese_text}"
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            translation = response.choices[0].message.content.strip()
            
            logger.info(f"Translation successful ({len(translation)} characters)")
            
            return {
                'translation': translation,
                'success': True,
                'error': None,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
            
        except Exception as e:
            error_msg = f"Translation failed: {str(e)}"
            logger.error(error_msg)
            return {
                'translation': '',
                'success': False,
                'error': error_msg
            }
