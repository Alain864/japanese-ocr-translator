"""
main.py
─────────────────────────────────────────────
Entry point for the unified Japanese OCR & Translation pipeline.

    python main.py

Pipeline:
  1. Extract Japanese text + bounding boxes + translations (OCR)
  2. Replace Japanese text with English in images (optional)
  3. Save extraction JSON and modified images
"""

import json
import time
from datetime import datetime
from pathlib import Path

from config.settings import (
    INPUT_FOLDER,
    OUTPUT_FOLDER,
    EXTRACTIONS_FILENAME,
    REPORT_FILENAME,
    IMAGES_SUBFOLDER,
    OPENAI_API_KEY,
    MODEL,
    DPI,
    ENABLE_TEXT_REPLACEMENT,
)
from app.logger import get_logger
from app.ocr_client import OCRClient
from app.image_replacer import ImageReplacer
from app.processor import process_all

log = get_logger("main")


def _validate() -> None:
    """Fail fast with clear error messages."""
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
        raise SystemExit(
            "❌ OPENAI_API_KEY is not set.\n"
            "   Copy .env.example → .env and add your API key."
        )
    if not INPUT_FOLDER.is_dir():
        raise SystemExit(
            f"❌ INPUT_FOLDER does not exist: {INPUT_FOLDER}\n"
            "   Create the directory or update INPUT_FOLDER in .env"
        )
    if not any(INPUT_FOLDER.glob("*.pdf")):
        raise SystemExit(
            f"❌ No .pdf files found in {INPUT_FOLDER}\n"
            "   Add PDFs to the input folder and try again."
        )


def main() -> None:
    _validate()

    # Ensure output folders exist
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    images_folder = OUTPUT_FOLDER / IMAGES_SUBFOLDER
    images_folder.mkdir(parents=True, exist_ok=True)

    # ── Banner ──────────────────────────────────
    log.info("=" * 68)
    log.info("  Japanese OCR & Translation Pipeline (Unified)")
    log.info("=" * 68)
    log.info(f"  Input              : {INPUT_FOLDER}")
    log.info(f"  Output             : {OUTPUT_FOLDER}")
    log.info(f"  Model              : {MODEL}")
    log.info(f"  DPI                : {DPI}")
    log.info(f"  Text Replacement   : {'Enabled' if ENABLE_TEXT_REPLACEMENT else 'Disabled'}")
    log.info("=" * 68)

    # ── Initialize services ─────────────────────
    start = time.time()
    ocr_client = OCRClient()
    image_replacer = ImageReplacer() if ENABLE_TEXT_REPLACEMENT else None

    # ── Run pipeline ────────────────────────────
    results, images = process_all(INPUT_FOLDER, ocr_client, image_replacer)
    elapsed = round(time.time() - start, 2)

    # ── Save extraction JSON ────────────────────
    extraction_output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline_version": "unified-v1",
            "model": MODEL,
            "dpi": DPI,
            "text_replacement_enabled": ENABLE_TEXT_REPLACEMENT,
            "total_files_processed": len(results),
            "total_elapsed_seconds": elapsed,
        },
        "files": results,
    }

    extractions_path = OUTPUT_FOLDER / EXTRACTIONS_FILENAME
    with open(extractions_path, "w", encoding="utf-8") as fh:
        json.dump(extraction_output, fh, ensure_ascii=False, indent=2)

    # ── Save images ─────────────────────────────
    log.info(f"\n💾 Saving {len(images)} image(s)...")
    for img, filename in images:
        img_path = images_folder / filename
        img.save(img_path, "PNG")
        log.debug(f"  Saved: {img_path.name}")

    # ── Generate processing report ──────────────
    total_pages = sum(f.get("total_pages", 0) for f in results)
    total_japanese_pages = sum(f.get("pages_with_japanese", 0) for f in results)
    
    total_replacements = 0
    total_failures = 0
    for file_result in results:
        for page in file_result.get("pages", []):
            stats = page.get("replacement_stats")
            if stats:
                total_replacements += stats.get("successful", 0)
                total_failures += stats.get("failed", 0)

    report = {
        "summary": {
            "total_files": len(results),
            "total_pages": total_pages,
            "pages_with_japanese": total_japanese_pages,
            "total_replacements_successful": total_replacements,
            "total_replacements_failed": total_failures,
            "elapsed_seconds": elapsed,
        },
        "files": [
            {
                "file": f.get("file"),
                "pages": f.get("total_pages"),
                "japanese_pages": f.get("pages_with_japanese"),
            }
            for f in results
        ],
    }

    report_path = OUTPUT_FOLDER / REPORT_FILENAME
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # ── Final summary ───────────────────────────
    log.info("")
    log.info("=" * 68)
    log.info(f"  ✅ Pipeline completed in {elapsed}s")
    log.info(f"  📂 Extraction data  → {extractions_path}")
    log.info(f"  📂 Processing report→ {report_path}")
    log.info(f"  🖼️  Images saved     → {images_folder} ({len(images)} files)")
    log.info(f"  📄 Pages processed  : {total_pages}")
    log.info(f"  🇯🇵 Pages with Japanese: {total_japanese_pages}")
    if ENABLE_TEXT_REPLACEMENT:
        log.info(f"  ✏️  Text replacements : {total_replacements} successful, {total_failures} failed")
    log.info("=" * 68)


if __name__ == "__main__":
    main()