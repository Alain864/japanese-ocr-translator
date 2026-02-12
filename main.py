"""
main.py
─────────────────────────────────────────────
Entry point for the unified Japanese OCR & Translation pipeline.

    python main.py [--stage {ocr,replace,all}]

Stages:
  ocr      - Extract Japanese text + bounding boxes + translations (OpenAI API)
  replace  - Replace Japanese text with English in images (uses existing extractions.json)
  all      - Run full pipeline (default)

Examples:
    python main.py --stage all        # Full pipeline
    python main.py --stage ocr        # OCR only
    python main.py --stage replace    # Text replacement only (requires existing extractions.json)
"""

import argparse
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
    GOOGLE_CLOUD_API_KEY,
    OPENAI_API_KEY,
    MODEL,
    DPI,
    ENABLE_TEXT_REPLACEMENT,
)
from app.logger import get_logger
from app.text_detector import TextDetector
from app.translator import Translator
from app.image_replacer import ImageReplacer
from app.processor import process_pdf_accurate, process_replacement_only

log = get_logger("main")


def _validate(stage: str) -> None:
    """Fail fast with clear error messages."""
    if stage in ("ocr", "all"):
        if not GOOGLE_CLOUD_API_KEY or GOOGLE_CLOUD_API_KEY == "your-google-cloud-api-key-here":
            raise SystemExit(
                "❌ GOOGLE_CLOUD_API_KEY is not set.\n"
                "   Add your Google Cloud API key to the .env file."
            )
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
    
    if stage == "replace":
        extractions_path = OUTPUT_FOLDER / EXTRACTIONS_FILENAME
        if not extractions_path.exists():
            raise SystemExit(
                f"❌ Cannot run text replacement: {extractions_path} not found.\n"
                "   Run with --stage ocr first, or run --stage all for full pipeline."
            )


def main() -> None:
    # ── Parse arguments ─────────────────────────
    parser = argparse.ArgumentParser(
        description="Japanese OCR & Translation pipeline with flexible stage selection"
    )
    parser.add_argument(
        "--stage",
        choices=["ocr", "replace", "all"],
        default="all",
        help="Which stage(s) to run: ocr (extraction only), replace (text replacement only), or all (default)",
    )
    args = parser.parse_args()
    stage = args.stage

    _validate(stage)

    # Ensure output folders exist
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    images_folder = OUTPUT_FOLDER / IMAGES_SUBFOLDER
    images_folder.mkdir(parents=True, exist_ok=True)

    # ── Banner ──────────────────────────────────
    log.info("=" * 68)
    log.info("  Japanese OCR & Translation Pipeline (Efficient)")
    log.info(f"  Stage: {stage.upper()}")
    log.info("=" * 68)
    log.info(f"  Input              : {INPUT_FOLDER}")
    log.info(f"  Output             : {OUTPUT_FOLDER}")
    if stage in ("ocr", "all"):
        log.info(f"  Detection          : Google Cloud Vision API")
        log.info(f"  Translation Model  : {MODEL}")
        log.info(f"  DPI                : {DPI}")
    if stage in ("replace", "all"):
        log.info(f"  Text Replacement   : {'Enabled' if ENABLE_TEXT_REPLACEMENT else 'Disabled'}")
    log.info("=" * 68)

    start = time.time()

    # ── Handle replacement-only mode ───────────
    if stage == "replace":
        log.info("\n🔄 Text Replacement Mode (using existing extractions)")
        _run_replacement_only(images_folder)
        elapsed = round(time.time() - start, 2)
        log.info(f"✅ Replacement completed in {elapsed}s")
        return

    # ── Initialize services (Google Cloud Vision + GPT-4o Translation) ──────────
    log.info("\n🚀 Initializing pipeline (Google Cloud Vision detection + GPT-4o translation)...")
    text_detector = TextDetector()
    translator = Translator()
    image_replacer = ImageReplacer() if ENABLE_TEXT_REPLACEMENT and stage in ("replace", "all") else None

    # ── Run pipeline (Detection + Translation) ──────────────────
    # Process each PDF
    pdf_files = list(INPUT_FOLDER.glob("*.pdf"))
    log.info(f"Found {len(pdf_files)} PDF(s) in {INPUT_FOLDER}")

    results = []
    images = []

    for pdf_path in pdf_files:
        file_result, file_images = process_pdf_accurate(
            pdf_path, text_detector, translator, image_replacer
        )
        results.append(file_result)
        images.extend(file_images)

    elapsed = round(time.time() - start, 2)

    # ── Save extraction JSON ────────────────────
    extraction_output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline_version": "efficient-v1",
            "detection_method": "Google Cloud Vision",
            "translation_model": MODEL,
            "dpi": DPI,
            "text_replacement_enabled": ENABLE_TEXT_REPLACEMENT and stage in ("replace", "all"),
            "total_files_processed": len(results),
            "total_elapsed_seconds": elapsed,
        },
        "files": results,
    }

    extractions_path = OUTPUT_FOLDER / EXTRACTIONS_FILENAME
    with open(extractions_path, "w", encoding="utf-8") as fh:
        json.dump(extraction_output, fh, ensure_ascii=False, indent=2)

    # ── Save images ─────────────────────────────
    if stage in ("all", "replace"):
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
    if stage in ("all", "replace"):
        log.info(f"  🖼️  Images saved     → {images_folder} ({len(images)} files)")
    log.info(f"  📄 Pages processed  : {total_pages}")
    log.info(f"  🇯🇵 Pages with Japanese: {total_japanese_pages}")
    if ENABLE_TEXT_REPLACEMENT and stage in ("all", "replace"):
        log.info(f"  ✏️  Text replacements : {total_replacements} successful, {total_failures} failed")
    log.info(f"  🚀 Architecture     : Google Cloud Vision + {MODEL} (batch translation)")
    log.info("=" * 68)


def _run_replacement_only(images_folder: Path) -> None:
    """Run text replacement using existing extractions.json."""
    extractions_path = OUTPUT_FOLDER / EXTRACTIONS_FILENAME
    
    with open(extractions_path, "r", encoding="utf-8") as fh:
        extraction_data = json.load(fh)
    
    image_replacer = ImageReplacer()
    results, images = process_replacement_only(
        extraction_data, INPUT_FOLDER, image_replacer
    )
    
    log.info(f"\n💾 Saving {len(images)} image(s)...")
    for img, filename in images:
        img_path = images_folder / filename
        img.save(img_path, "PNG")
        log.debug(f"  Saved: {img_path.name}")


if __name__ == "__main__":
    main()