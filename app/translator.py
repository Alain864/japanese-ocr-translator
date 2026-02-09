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

Format: Return ONLY the translations, one per line, maintaining the same numbering as the input.
Example:
Input:
1. こんにちは
2. ありがとう

Output:
1. Hello
2. Thank you"""

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
                translations = self._parse_translations(content, len(japanese_texts))

                if len(translations) == len(japanese_texts):
                    log.info(f"  [{label}] Translation successful")
                    return translations
                else:
                    log.warning(
                        f"  [{label}] Translation count mismatch "
                        f"(expected {len(japanese_texts)}, got {len(translations)})"
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
                    # Return what we have, pad with empty strings
                    while len(translations) < len(japanese_texts):
                        translations.append("")
                    return translations

            except Exception as exc:
                log.error(f"  [{label}] Translation error (attempt {attempt}): {exc}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    # Return empty translations on final failure
                    return [""] * len(japanese_texts)

        return [""] * len(japanese_texts)

    def _parse_translations(self, content: str, expected_count: int) -> List[str]:
        """
        Parse numbered translations from GPT response.

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
        translations = []
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove numbering (e.g., "1. " or "1) ")
            if '. ' in line:
                _, text = line.split('. ', 1)
                translations.append(text.strip())
            elif ') ' in line:
                _, text = line.split(') ', 1)
                translations.append(text.strip())
            else:
                # No numbering found, use as-is
                translations.append(line)

        return translations[:expected_count]  # Return only expected count
