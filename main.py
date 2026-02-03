"""
main.py
─────────────────────────────────────────────
Entry point for the Japanese OCR & Translation pipeline.

    python main.py

It validates the environment, runs the pipeline via processor.py,
and writes the final JSON output.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from config.settings import (
    INPUT_FOLDER,
    OUTPUT_FOLDER,
    OUTPUT_FILENAME,
    OPENAI_API_KEY,
    MODEL,
    DPI,
)
from app.logger import get_logger
from app.ocr_client import OCRClient
from app.processor import process_all

log = get_logger("main")


def _validate() -> None:
    """Fail fast with clear messages before any work begins."""
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
        raise SystemExit(
            "❌ OPENAI_API_KEY is not set.\n"
            "   Copy .env.example → .env and paste your key."
        )
    if not INPUT_FOLDER.is_dir():
        raise SystemExit(
            f"❌ INPUT_FOLDER does not exist: {INPUT_FOLDER}\n"
            "   Create the directory or update INPUT_FOLDER in .env"
        )
    if not any(INPUT_FOLDER.glob("*.pdf")):
        raise SystemExit(
            f"❌ No .pdf files found in {INPUT_FOLDER}\n"
            "   Drop your PDFs in there and try again."
        )


def main() -> None:
    _validate()

    # Ensure output folder exists
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    # ── banner ──────────────────────────────────
    log.info("=" * 58)
    log.info("  Japanese OCR & Translation Pipeline")
    log.info("=" * 58)
    log.info(f"  Input   : {INPUT_FOLDER}")
    log.info(f"  Output  : {OUTPUT_FOLDER}")
    log.info(f"  Model   : {MODEL}")
    log.info(f"  DPI     : {DPI}")
    log.info("=" * 58)

    # ── run ─────────────────────────────────────
    start = time.time()
    client = OCRClient()
    results = process_all(INPUT_FOLDER, client)
    elapsed = round(time.time() - start, 2)

    # ── assemble final JSON ─────────────────────
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline": "japanese_ocr_pipeline",
            "model": MODEL,
            "dpi": DPI,
            "total_files_processed": len(results),
            "total_elapsed_seconds": elapsed,
        },
        "files": results,
    }

    # ── write ───────────────────────────────────
    output_path: Path = OUTPUT_FOLDER / OUTPUT_FILENAME
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    # ── summary ─────────────────────────────────
    total_japanese_pages = sum(f.get("pages_with_japanese", 0) for f in results)
    total_pages          = sum(f.get("total_pages", 0)          for f in results)

    log.info("")
    log.info("=" * 58)
    log.info(f"  ✅ Finished in {elapsed}s")
    log.info(f"  📂 Output  → {output_path}")
    log.info(f"  📄 Pages processed          : {total_pages}")
    log.info(f"  🇯🇵 Pages with Japanese text : {total_japanese_pages}")
    log.info("=" * 58)


if __name__ == "__main__":
    main()