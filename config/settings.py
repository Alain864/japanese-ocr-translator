
"""
settings.py
─────────────────────────────────────────────
Single source of truth for every runtime value.
Reads from the .env file (or real environment variables).
Every other module in the project imports what it needs from here.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from the project root (one level up from config/)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

# ── OpenAI ──────────────────────────────────
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

# ── Model / behaviour ────────────────────────
MODEL:                str = os.environ.get("MODEL",                "gpt-4o")
DPI:                  int = int(os.environ.get("DPI",              "200"))
MAX_RETRIES:          int = int(os.environ.get("MAX_RETRIES",      "3"))
RETRY_DELAY_SECONDS:  int = int(os.environ.get("RETRY_DELAY_SECONDS", "2"))

# ── Paths (resolved relative to project root) ─
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FOLDER:  Path = (_PROJECT_ROOT / os.environ.get("INPUT_FOLDER",  "input")).resolve()
OUTPUT_FOLDER: Path = (_PROJECT_ROOT / os.environ.get("OUTPUT_FOLDER", "output")).resolve()
LOG_FOLDER:    Path = (_PROJECT_ROOT / os.environ.get("LOG_FOLDER",    "logs")).resolve()

# ── Output file name ──────────────────────────
OUTPUT_FILENAME: str = "japanese_extraction_results.json"