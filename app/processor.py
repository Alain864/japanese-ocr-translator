"""
processor.py
─────────────────────────────────────────────
Orchestrator module.  For every PDF it:
  1. Converts pages to images  (pdf_converter)
  2. Runs OCR + translation on each page  (ocr_client)
  3. Assembles and returns a structured result dict.

It does NOT write files — that responsibility belongs to main.py.
"""

from pathlib import Path
from typing import Dict, List

from app.pdf_converter import pdf_to_images
from app.ocr_client import OCRClient
from app.logger import get_logger

log = get_logger("processor")


def process_pdf(pdf_path: Path, client: OCRClient) -> Dict:
    """
    Full pipeline for a single PDF.

    Parameters
    ----------
    pdf_path : Path
        Absolute path to the PDF file.
    client   : OCRClient
        Shared, already-initialised OCR client.

    Returns
    -------
    dict
        ``{file, total_pages, pages_with_japanese, pages: [...]}``.
        On conversion failure an ``error`` key is present instead of pages.
    """
    log.info(f"\n📄 Processing: {pdf_path.name}")

    # ── step 1: PDF → images ───────────────────
    try:
        images = pdf_to_images(pdf_path)
    except (FileNotFoundError, RuntimeError) as exc:
        log.error(f"  ❌ {exc}")
        return {"file": pdf_path.name, "error": str(exc), "pages": []}

    total_pages = len(images)
    log.info(f"  📑 {total_pages} page(s) to process")

    # ── step 2: OCR each page ──────────────────
    pages_results: List[Dict] = []
    japanese_page_count = 0

    for i, img in enumerate(images, start=1):
        label = f"{pdf_path.name} p{i}/{total_pages}"

        result = client.extract_japanese(img, label=label)

        page_entry: Dict = {
            "page_number": i,
            "japanese_found": result.get("japanese_found", False),
            "extractions": [],
        }

        if result.get("japanese_found"):
            page_entry["extractions"] = result.get("extractions", [])
            japanese_page_count += 1
            log.info(
                f"  ✅ [{label}] "
                f"{len(page_entry['extractions'])} segment(s) found"
            )
        else:
            if "error" in result:
                page_entry["error"] = result["error"]
                log.warning(f"  ⚠️  [{label}] {result['error']}")
            else:
                log.info(f"  ○  [{label}] No Japanese text")

        pages_results.append(page_entry)

    # ── step 3: summary ────────────────────────
    log.info(
        f"  📊 {japanese_page_count}/{total_pages} pages "
        f"contained Japanese text"
    )

    return {
        "file": pdf_path.name,
        "total_pages": total_pages,
        "pages_with_japanese": japanese_page_count,
        "pages": pages_results,
    }


def process_all(input_folder: Path, client: OCRClient) -> List[Dict]:
    """
    Discover every PDF in *input_folder* and run the full pipeline on each.

    Returns a list of per-file result dicts (same shape as ``process_pdf``).
    """
    pdf_files = sorted(input_folder.glob("*.pdf"))
    if not pdf_files:
        log.warning(f"No PDF files found in {input_folder}")
        return []

    log.info(f"Found {len(pdf_files)} PDF(s) in {input_folder}")
    return [process_pdf(p, client) for p in pdf_files]