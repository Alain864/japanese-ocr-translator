"""
ocr_client.py
─────────────────────────────────────────────
All OpenAI Vision API interactions live here.
  • Encodes a PIL Image → base64.
  • Sends it to GPT-4o with the extraction + translation prompt.
  • Parses the JSON response (with retries).
  • Returns a clean dict — knows nothing about PDFs or files.
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

# ── Prompt sent as the system message ────────
_SYSTEM_PROMPT = """You are a specialist OCR and translation assistant focused on Japanese text.

Your task for each image:
1. Carefully scan the ENTIRE image for any Japanese text (kanji, hiragana, katakana, or a mix).
2. Extract every piece of Japanese text exactly as it appears, preserving the original characters.
3. Translate each extracted piece into English.

IMPORTANT RULES:
- If there is NO Japanese text in the image, respond with exactly: {"japanese_found": false}
- If Japanese text IS found, respond ONLY with valid JSON in this exact format:

{
  "japanese_found": true,
  "extractions": [
    {
      "japanese_text": "<original Japanese text exactly as it appears>",
      "english_translation": "<English translation>",
      "location_description": "<brief description of where in the image this text appears>"
    }
  ]
}

- Do NOT include any text outside the JSON object.
- Do NOT wrap the JSON in markdown code blocks.
- Each distinct block or segment of Japanese text should be its own entry in the array.
- Be thorough: do not skip small labels, watermarks, or partial text.
"""


class OCRClient:
    """Thin wrapper around the OpenAI client scoped to our vision task."""

    def __init__(self) -> None:
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file or environment."
            )
        self._client = OpenAI(api_key=OPENAI_API_KEY)

    # ── public ──────────────────────────────────
    def extract_japanese(self, image: Image.Image, label: str = "") -> Dict:
        """
        Send *image* to GPT-4o and return the parsed extraction dict.

        Parameters
        ----------
        image : PIL.Image.Image
            The page image to analyse.
        label : str, optional
            Human-readable label used in log messages (e.g. "doc.pdf p3/12").

        Returns
        -------
        dict
            Parsed JSON from the model.  Always contains at least
            ``japanese_found`` (bool).  On hard failure an ``error`` key is
            added instead.
        """
        b64 = self._encode(image)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"  [{label}] API call … (attempt {attempt}/{MAX_RETRIES})")
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
                                    "text": "Extract and translate any Japanese text in this image.",
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
                    return {"japanese_found": False, "error": "JSON parse failed after all retries"}

            except Exception as exc:
                log.warning(f"  [{label}] API error on attempt {attempt}: {exc}")
                if attempt == MAX_RETRIES:
                    return {"japanese_found": False, "error": str(exc)}

            time.sleep(RETRY_DELAY_SECONDS)

        # Should not reach here, but safety net
        return {"japanese_found": False, "error": "Max retries exhausted"}

    # ── private ─────────────────────────────────
    @staticmethod
    def _encode(image: Image.Image) -> str:
        """PIL Image → base64 PNG string."""
        buf = BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    @staticmethod
    def _parse(raw: str, label: str) -> Dict:
        """Strip any accidental markdown fences and parse JSON."""
        cleaned = raw.strip().strip("```").strip("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            log.error(f"  [{label}] Unparseable response: {cleaned[:200]}")
            raise