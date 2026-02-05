"""
processor.py
─────────────────────────────────────────────
Orchestrates the full pipeline:
  1. PDF → images (pdf_converter)
  2. OCR + translation + bounding boxes (ocr_client)
  3. Image replacement (image_replacer) - optional
Returns structured results and optionally modified images.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from app.pdf_converter import pdf_to_images
from app.ocr_client import OCRClient
from app.image_replacer import ImageReplacer
from app.logger import get_logger

log = get_logger("processor")


def process_pdf(
    pdf_path: Path,
    ocr_client: OCRClient,
    image_replacer: Optional[ImageReplacer] = None,
) -> Tuple[Dict, List[Tuple[Image.Image, str]]]:
    """
    Full pipeline for a single PDF.

    Parameters
    ----------
    pdf_path : Path
        Path to PDF file.
    ocr_client : OCRClient
        Initialized OCR client.
    image_replacer : ImageReplacer, optional
        If provided, will replace text in images.

    Returns
    -------
    tuple[dict, list[tuple]]
        - Extraction data dict: {file, total_pages, pages_with_japanese, pages: [...]}
        - List of (modified_image, filename) tuples for saving
    """
    log.info(f"\n📄 Processing: {pdf_path.name}")

    # ── Step 1: PDF → images ───────────────────
    try:
        images = pdf_to_images(pdf_path)
    except (FileNotFoundError, RuntimeError) as exc:
        log.error(f"  ❌ {exc}")
        return {
            "file": pdf_path.name,
            "error": str(exc),
            "pages": []
        }, []

    total_pages = len(images)
    log.info(f"  📑 {total_pages} page(s) to process")

    # ── Step 2: OCR each page ──────────────────
    pages_results: List[Dict] = []
    japanese_page_count = 0
    modified_images: List[Tuple[Image.Image, str]] = []

    for i, img in enumerate(images, start=1):
        page_label = f"{pdf_path.name} p{i}/{total_pages}"

        # Run OCR
        result = ocr_client.extract_japanese(img, label=page_label)

        page_entry: Dict = {
            "page_number": i,
            "japanese_found": result.get("japanese_found", False),
            "extractions": [],
            "replacement_stats": None,
        }

        if result.get("japanese_found"):
            extractions = result.get("extractions", [])
            page_entry["extractions"] = extractions
            japanese_page_count += 1
            log.info(
                f"  ✅ [{page_label}] "
                f"{len(extractions)} segment(s) found"
            )

            # ── Step 3: Replace text (if enabled) ──
            if image_replacer:
                modified_img, success, fail = image_replacer.replace_text(
                    img, extractions, page_label
                )
                page_entry["replacement_stats"] = {
                    "successful": success,
                    "failed": fail,
                }
                # Save modified image
                img_filename = f"{pdf_path.stem}_page_{i:03d}.png"
                modified_images.append((modified_img, img_filename))
            else:
                # No replacement - save original image
                img_filename = f"{pdf_path.stem}_page_{i:03d}.png"
                modified_images.append((img, img_filename))

        else:
            # No Japanese found
            if "error" in result:
                page_entry["error"] = result["error"]
                log.warning(f"  ⚠️  [{page_label}] {result['error']}")
            else:
                log.info(f"  ○  [{page_label}] No Japanese text")

            # Save original image
            img_filename = f"{pdf_path.stem}_page_{i:03d}.png"
            modified_images.append((img, img_filename))

        pages_results.append(page_entry)

    # ── Summary ────────────────────────────────
    log.info(
        f"  📊 {japanese_page_count}/{total_pages} pages "
        f"contained Japanese text"
    )

    return {
        "file": pdf_path.name,
        "total_pages": total_pages,
        "pages_with_japanese": japanese_page_count,
        "pages": pages_results,
    }, modified_images


def process_all(
    input_folder: Path,
    ocr_client: OCRClient,
    image_replacer: Optional[ImageReplacer] = None,
) -> Tuple[List[Dict], List[Tuple[Image.Image, str]]]:
    """
    Process all PDFs in input folder.

    Returns
    -------
    tuple[list[dict], list[tuple]]
        - List of per-file extraction dicts
        - List of all (image, filename) tuples to save
    """
    pdf_files = sorted(input_folder.glob("*.pdf"))
    if not pdf_files:
        log.warning(f"No PDF files found in {input_folder}")
        return [], []

    log.info(f"Found {len(pdf_files)} PDF(s) in {input_folder}")

    all_results = []
    all_images = []

    for pdf_path in pdf_files:
        file_result, file_images = process_pdf(pdf_path, ocr_client, image_replacer)
        all_results.append(file_result)
        all_images.extend(file_images)

    return all_results, all_images