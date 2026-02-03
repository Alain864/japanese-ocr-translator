"""
pdf_converter.py
─────────────────────────────────────────────
Responsible for one thing: convert a PDF file into a list of PIL Images.
Uses pdf2image (backed by Poppler's pdftoppm).
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
    Rasterise every page of *pdf_path* at the configured DPI.

    Returns
    -------
    list[PIL.Image.Image]
        One image per page, in page order.

    Raises
    ------
    FileNotFoundError
        If *pdf_path* does not exist.
    RuntimeError
        If Poppler / pdftoppm fails for any reason.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    log.info(f"Converting '{pdf_path.name}' → images at {DPI} DPI …")

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