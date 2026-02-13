"""
settings.py
─────────────────────────────────────────────
Single source of truth for all runtime configuration.
Reads from .env file (or environment variables).
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from project root
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

# ── Google Cloud Vision (OCR) ───────────────
GOOGLE_CLOUD_API_KEY: str = os.environ.get("GOOGLE_CLOUD_API_KEY", "")

# ── OpenAI (Translation) ────────────────────
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

# ── Stage 1: OCR + Translation ───────────────
MODEL:                str = os.environ.get("MODEL",                "gpt-4o")
DPI:                  int = int(os.environ.get("DPI",              "200"))
MAX_RETRIES:          int = int(os.environ.get("MAX_RETRIES",      "3"))
RETRY_DELAY_SECONDS:  int = int(os.environ.get("RETRY_DELAY_SECONDS", "2"))

# ── Stage 2: Text Replacement ────────────────
ENABLE_TEXT_REPLACEMENT: bool = os.environ.get("ENABLE_TEXT_REPLACEMENT", "true").lower() == "true"
ENGLISH_FONT:            str  = os.environ.get("ENGLISH_FONT",            "Arial.ttf")
FALLBACK_FONT:           str  = os.environ.get("FALLBACK_FONT",           "DejaVuSans.ttf")
BBOX_PADDING:            int  = int(os.environ.get("BBOX_PADDING",        "5"))
RENDER_BOX_PADDING_PCT:  float = float(os.environ.get("RENDER_BOX_PADDING_PCT", "0.35"))
MIN_FONT_SIZE:           int  = int(os.environ.get("MIN_FONT_SIZE",       "8"))
MAX_FONT_SIZE:           int  = int(os.environ.get("MAX_FONT_SIZE",       "66"))
TEXT_PADDING:            int  = int(os.environ.get("TEXT_PADDING",        "0"))
TEXT_INSET:              int  = int(os.environ.get("TEXT_INSET",          "0"))
LINE_SPACING:            float = float(os.environ.get("LINE_SPACING",     "1.1"))
TEXT_ERASE_PADDING:      int  = int(os.environ.get("TEXT_ERASE_PADDING",  "6"))
TEXT_ERASE_THRESHOLD:    int  = int(os.environ.get("TEXT_ERASE_THRESHOLD","190"))
TEXT_ERASE_DILATE:       int  = int(os.environ.get("TEXT_ERASE_DILATE",   "3"))
BUBBLE_DETECT_THRESHOLD: int  = int(os.environ.get("BUBBLE_DETECT_THRESHOLD", "200"))
BUBBLE_PADDING:          int  = int(os.environ.get("BUBBLE_PADDING",          "4"))
BUBBLE_MIN_AREA:         int  = int(os.environ.get("BUBBLE_MIN_AREA",         "800"))

# Parse background fill color (RGB tuple)
_bg_color_str = os.environ.get("BACKGROUND_FILL_COLOR", "255,255,255")
BACKGROUND_FILL_COLOR: tuple = tuple(int(x.strip()) for x in _bg_color_str.split(","))

# ── Paths ────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FOLDER:  Path = (_PROJECT_ROOT / os.environ.get("INPUT_FOLDER",  "input")).resolve()
OUTPUT_FOLDER: Path = (_PROJECT_ROOT / os.environ.get("OUTPUT_FOLDER", "output")).resolve()
LOG_FOLDER:    Path = (_PROJECT_ROOT / os.environ.get("LOG_FOLDER",    "logs")).resolve()

# ── Output structure ─────────────────────────
EXTRACTIONS_FILENAME: str  = "extractions.json"
REPORT_FILENAME:      str  = "processing_report.json"
IMAGES_SUBFOLDER:     str  = "images"
