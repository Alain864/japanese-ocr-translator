"""
ocr_client.py
─────────────────────────────────────────────
All OpenAI Vision API interactions.
Sends images to GPT-4o and returns:
  - Japanese text
  - English translation
  - Bounding box (normalized coordinates)
  - Font styling (bold, italic)
"""

import base64
import json
import time
from io import BytesIO
from typing import Dict

from openai import OpenAI
from PIL import Image

from config.settings import (
    OPENAI_API_KEY,
    MODEL,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)
from app.logger import get_logger

log = get_logger("ocr_client")

# ── System prompt for unified extraction ────
_SYSTEM_PROMPT = """You are a specialist OCR and translation assistant focused on Japanese text.

Your task for each image:
1. Carefully scan the ENTIRE image for any Japanese text (kanji, hiragana, katakana, or mixed).
2. For each piece of Japanese text found, extract:
   - The exact Japanese text as it appears
   - English translation
   - Bounding box location (normalized coordinates)
   - Font styling (bold, italic)

IMPORTANT RULES:
- If there is NO Japanese text in the image, respond with: {"japanese_found": false}
- If Japanese text IS found, respond ONLY with valid JSON in this EXACT format:

{
  "japanese_found": true,
  "extractions": [
    {
      "japanese_text": "<original Japanese text>",
      "english_translation": "<English translation>",
      "bounding_box": {
        "x": <normalized x coordinate 0.0-1.0>,
        "y": <normalized y coordinate 0.0-1.0>,
        "width": <normalized width 0.0-1.0>,
        "height": <normalized height 0.0-1.0>
      },
      "styling": {
        "bold": <true or false>,
        "italic": <true or false>
      }
    }
  ]
}

BOUNDING BOX FORMAT:
- Use normalized coordinates (0.0 to 1.0) where:
  - (x, y) = top-left corner of the text region
  - width, height = size of the text region
  - Example: x=0.5 means 50% from the left edge of the image
- The bounding box should tightly contain the text with minimal padding

STYLING DETECTION:
- Set "bold": true if the text appears in bold/heavy weight
- Set "italic": true if the text appears slanted/italicized
- If unsure, default to false

OUTPUT REQUIREMENTS:
- Do NOT include any text outside the JSON object
- Do NOT wrap the JSON in markdown code blocks or backticks
- Each distinct block or segment of Japanese text should be a separate entry
- Be thorough: include all Japanese text, even small labels or watermarks
"""


class OCRClient:
    """Wrapper around OpenAI client for vision-based OCR + translation."""

    def __init__(self) -> None:
        if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file."
            )
        self._client = OpenAI(api_key=OPENAI_API_KEY)

    def extract_japanese(self, image: Image.Image, label: str = "") -> Dict:
        """
        Send image to GPT-4o and return parsed extraction dict.

        Parameters
        ----------
        image : PIL.Image.Image
            The page image to analyse.
        label : str, optional
            Human-readable label for logging (e.g. "doc.pdf p3/12").

        Returns
        -------
        dict
            Parsed JSON from the model. Always contains "japanese_found" (bool).
            On success also contains "extractions" list.
            On failure contains "error" key.
        """
        b64 = self._encode(image)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"  [{label}] API call... (attempt {attempt}/{MAX_RETRIES})")
                response = self._client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64}",
                                        "detail": "high",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Extract and translate all Japanese text in this image, including bounding boxes and styling.",
                                },
                            ],
                        },
                    ],
                    max_tokens=2000,
                    temperature=0,
                )

                raw = response.choices[0].message.content.strip()
                return self._parse(raw, label)

            except json.JSONDecodeError:
                log.warning(f"  [{label}] JSON parse error on attempt {attempt}")
                if attempt == MAX_RETRIES:
                    return {
                        "japanese_found": False,
                        "error": "JSON parse failed after all retries"
                    }

            except Exception as exc:
                log.warning(f"  [{label}] API error on attempt {attempt}: {exc}")
                if attempt == MAX_RETRIES:
                    return {"japanese_found": False, "error": str(exc)}

            time.sleep(RETRY_DELAY_SECONDS)

        return {"japanese_found": False, "error": "Max retries exhausted"}

    @staticmethod
    def _encode(image: Image.Image) -> str:
        """Convert PIL Image to base64 PNG string."""
        buf = BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    @staticmethod
    def _parse(raw: str, label: str) -> Dict:
        """Strip markdown fences and parse JSON."""
        cleaned = raw.strip().strip("```").strip("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            log.error(f"  [{label}] Unparseable response: {cleaned[:200]}")
            raise