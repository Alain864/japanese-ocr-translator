"""
logger.py
─────────────────────────────────────────────
Centralised logging configuration.
  • Console  → INFO and above
  • File     → DEBUG and above, timestamped
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from config.settings import LOG_FOLDER

_CONSOLE_FMT = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
_FILE_FMT    = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
_DATE_FMT    = "%H:%M:%S"

_root_configured = False


def _configure_root() -> None:
    global _root_configured
    if _root_configured:
        return

    LOG_FOLDER.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("japanese_ocr")
    root.setLevel(logging.DEBUG)
    root.propagate = False

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt=_DATE_FMT))
    root.addHandler(ch)

    # File
    log_file = LOG_FOLDER / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FILE_FMT, datefmt=_DATE_FMT))
    root.addHandler(fh)

    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under 'japanese_ocr' namespace."""
    _configure_root()
    return logging.getLogger(f"japanese_ocr.{name}")