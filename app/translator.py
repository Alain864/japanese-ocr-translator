"""
translator.py
─────────────────────────────────────────────
Uses GPT-4o Text API (not Vision) for Japanese to English translation.
Much faster and cheaper than vision API, with better translation quality.
"""

import time
from typing import Dict, List
from openai import OpenAI

from config.settings import (
    OPENAI_API_KEY,
    MODEL,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)
from app.logger import get_logger

log = get_logger("translator")


class Translator:
    """Japanese to English translation using GPT-4o text API."""

    def __init__(self):
        """Initialize OpenAI client."""
        if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
            raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

        self._client = OpenAI(api_key=OPENAI_API_KEY)

    def translate_batch(
        self,
        japanese_texts: List[str],
        label: str = ""
    ) -> List[str]:
        """
        Translate multiple Japanese texts to English in a single API call.

        Parameters
        ----------
        japanese_texts : list[str]
            List of Japanese text strings to translate.
        label : str, optional
            Human-readable label for logging.

        Returns
        -------
        list[str]
            List of English translations in the same order.
        """
        if not japanese_texts:
            return []

        log.info(f"  [{label}] Translating {len(japanese_texts)} text(s)...")

        # Format texts with numbering for batch translation
        numbered_texts = "\n".join(
            f"{i+1}. {text}" for i, text in enumerate(japanese_texts)
        )

        system_prompt = """You are an expert Japanese to English translator specializing in manga and comic translation.

Your task:
- Translate each Japanese text to natural, fluent English
- Maintain the original tone and style  
- Keep translations concise for speech bubbles
- Preserve any emphasis or emotion in the text

CRITICAL OUTPUT FORMAT:
Return ONLY a numbered list of translations, one per line.
EACH LINE MUST BE: {number}. {translation}
DO NOT include any other text, explanations, or formatting.
DO NOT use markdown code blocks.

Example if 3 texts:
1. Hello
2. Thank you
3. How are you?"""

        user_prompt = f"""Translate these Japanese texts to English:

{numbered_texts}"""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,  # Slight creativity for natural translation
                    max_tokens=2000
                )

                # Parse response
                content = response.choices[0].message.content.strip()
                log.debug(f"  [{label}] Raw response preview: {content[:200]}...")
                translations = self._parse_translations(content, len(japanese_texts))

                if len(translations) == len(japanese_texts):
                    log.info(f"  [{label}] Translation successful ({len(translations)} texts)")
                    return translations
                else:
                    log.warning(
                        f"  [{label}] Translation count mismatch "
                        f"(expected {len(japanese_texts)}, got {len(translations)}) on attempt {attempt}/{MAX_RETRIES}"
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
                    # On final attempt, return what we have (padded with empty strings)
                    log.warning(f"  [{label}] Returning {len(translations)} translations (padded with empty strings)")
                    while len(translations) < len(japanese_texts):
                        translations.append("")
                    return translations

            except Exception as exc:
                log.error(f"  [{label}] Translation error (attempt {attempt}): {exc}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    # Return empty translations on final failure
                    log.error(f"  [{label}] All retries exhausted, returning empty translations")
                    return [""] * len(japanese_texts)

        return [""] * len(japanese_texts)

    def _parse_translations(self, content: str, expected_count: int) -> List[str]:
        """
        Parse numbered translations from GPT response.
        Handles multiple formats: numbered, bullet points, markdown code blocks, JSON.

        Parameters
        ----------
        content : str
            GPT response content.
        expected_count : int
            Expected number of translations.

        Returns
        -------
        list[str]
            Parsed translations.
        """
        import json
        
        # Remove markdown code blocks if present
        content = content.strip()
        original_content = content
        
        if content.startswith('```'):
            lines = content.split('\n')
            start_idx = 0
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if i == 0 or (i > 0 and line.strip().startswith('```')):
                    if i > 0:
                        end_idx = i
                        break
                    start_idx = i + 1
            if start_idx < end_idx:
                content = '\n'.join(lines[start_idx:end_idx])
        
        # Try parsing as JSON array first
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, list):
                translations = [str(item).strip() for item in parsed]
                return translations[:expected_count]
            elif isinstance(parsed, dict) and 'translations' in parsed:
                items = parsed['translations']
                if isinstance(items, list):
                    return [str(item).strip() for item in items[:expected_count]]
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        
        # Parse numbered/bulleted format
        translations = []
        lines = content.strip().split('\n')

        for line in lines:
            original_line = line
            line = line.strip()
            
            if not line or len(line) == 0:
                continue

            # Skip instruction lines
            if any(line.lower().startswith(x) for x in ['input:', 'output:', 'translations:', 'notes:', 'example:']):
                continue

            # Try to extract translation text
            translation_text = None
            
            # Format: "1. Translation"
            if '. ' in line:
                parts = line.split('. ', 1)
                if parts[0].strip().replace('-', '').isdigit():
                    translation_text = parts[1].strip()
            
            # Format: "1) Translation"
            if translation_text is None and ') ' in line:
                parts = line.split(') ', 1)
                if parts[0].strip().replace('-', '').isdigit():
                    translation_text = parts[1].strip()
            
            # Format: "- Translation" or "* Translation"
            if translation_text is None and (line.startswith('- ') or line.startswith('* ')):
                translation_text = line[2:].strip()
            
            # Format: Plain translation (no numbering)
            if translation_text is None and line and not line.endswith(':'):
                translation_text = line
            
            # Add if we found translation text
            if translation_text and len(translation_text) > 0:
                translations.append(translation_text)

        # Debug logging
        if len(translations) == 0 and expected_count > 0:
            log.debug(f"Parser got 0 translations from {expected_count} expected. Raw (300 chars): {original_content[:300]}...")
        elif len(translations) != expected_count:
            log.debug(f"Parser got {len(translations)} translations vs {expected_count} expected")

        return translations[:expected_count]  # Return only expected count
