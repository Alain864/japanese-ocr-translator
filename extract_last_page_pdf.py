"""
Extract the last page from a PDF in ./input and write it as a new PDF in ./output.

Usage:
  python extract_last_page_pdf.py
  python extract_last_page_pdf.py --input input/your.pdf --output output/last_page.pdf

Notes:
- Prefers pypdf/PyPDF2 to preserve vector content if installed.
- Falls back to pdf2image + Pillow if pypdf isn't available.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def pick_pdf(path: Path) -> Path:
    if path.is_file():
        return path
    if not path.is_dir():
        raise FileNotFoundError(f"Input path not found: {path}")

    pdfs = sorted(path.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in: {path}")
    if len(pdfs) > 1:
        names = ", ".join(p.name for p in pdfs)
        raise SystemExit(
            "Multiple PDFs found. Please specify one with --input. "
            f"Found: {names}"
        )
    return pdfs[0]


def extract_last_page_with_pypdf(input_pdf: Path, output_pdf: Path) -> bool:
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader, PdfWriter  # type: ignore
        except Exception:
            return False

    reader = PdfReader(str(input_pdf))
    if not reader.pages:
        raise SystemExit("Input PDF has no pages")

    writer = PdfWriter()
    writer.add_page(reader.pages[-1])

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)
    return True


def extract_last_page_with_pdf2image(input_pdf: Path, output_pdf: Path) -> None:
    from pdf2image import convert_from_path, pdfinfo_from_path
    from PIL import Image

    info = pdfinfo_from_path(str(input_pdf))
    total_pages = int(info.get("Pages", 0))
    if total_pages < 1:
        raise SystemExit("Input PDF has no pages")

    last_page = total_pages
    images = convert_from_path(
        str(input_pdf),
        first_page=last_page,
        last_page=last_page,
        dpi=300,
    )
    if not images:
        raise SystemExit("Failed to render last page")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    img: Image.Image = images[0]
    img.save(str(output_pdf), "PDF")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the last page from a PDF in ./input and write it to ./output"
    )
    parser.add_argument(
        "--input",
        default="input",
        help="Path to a PDF file or a directory containing one PDF (default: ./input)",
    )
    parser.add_argument(
        "--output",
        default="output/last_page.pdf",
        help="Path to write the extracted last-page PDF (default: ./output/last_page.pdf)",
    )
    args = parser.parse_args()

    input_path = pick_pdf(Path(args.input))
    output_path = Path(args.output)

    if extract_last_page_with_pypdf(input_path, output_path):
        print(f"Saved last page (vector-preserving) to {output_path}")
        return

    extract_last_page_with_pdf2image(input_path, output_path)
    print(f"Saved last page (rasterized) to {output_path}")


if __name__ == "__main__":
    main()
