"""
pdf_converter.py
─────────────────────────────────────────────
Converts PDF files to PIL Images using pdf2image (Poppler).
"""

from pathlib import Path
from typing import List

from PIL import Image
from pdf2image import convert_from_path

from config.settings import DPI
from app.logger import get_logger

log = get_logger("pdf_converter")


def pdf_to_images(pdf_path: Path) -> List[Image.Image]:
    """
    Rasterise every page of a PDF at the configured DPI.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.

    Returns
    -------
    list[PIL.Image.Image]
        One image per page, in order.

    Raises
    ------
    FileNotFoundError
        If PDF doesn't exist.
    RuntimeError
        If conversion fails.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    log.info(f"Converting '{pdf_path.name}' to images at {DPI} DPI...")

    try:
        images: List[Image.Image] = convert_from_path(
            str(pdf_path),
            dpi=DPI,
        )
    except Exception as exc:
        raise RuntimeError(
            f"pdf2image failed on '{pdf_path.name}': {exc}"
        ) from exc

    log.info(f"  → {len(images)} page(s) extracted")
    return images