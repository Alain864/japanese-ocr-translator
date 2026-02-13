# japanese-ocr-translator

**Unified pipeline** that extracts Japanese text from image-based PDFs with pixel-perfect accuracy, translates it to English, and optionally replaces the original Japanese text with English translations directly in the images.

---

## What It Does

### Stage 1: Accurate Text Detection (Google Cloud Vision)
- Converts PDF pages to high-resolution images
- Uses **Google Cloud Vision API** for pixel-perfect Japanese text detection
- Extracts: Japanese text + precise bounding box coordinates
- Handles rotated text and complex layouts automatically
- Highly accurate OCR with excellent Japanese language support

### Stage 2: Translation (GPT-4o Text API)
- Takes detected Japanese text and translates to English
- Uses GPT-4o text API (faster & cheaper than Vision API)
- Batch processing for efficiency
- Includes retry logic with exponential backoff

### Stage 3: Text Replacement (Optional)
- Uses bounding box coordinates from Google Cloud Vision to locate Japanese text
- Covers original text with white rectangle
- Renders English translation in the same location
- Auto-shrinks font size if English text exceeds bounding box
- Maximum precision text overlay

### Flexible Execution
- Run **full pipeline** (detection + translation + replacement)
- Run **OCR only** (extract text and coordinates without translation)
- Run **translation + replacement only** (use existing detections)

### Output
- **JSON file** with all extraction data (text, translations, precise coordinates)
- **Modified images** with English text replacing Japanese
- **Processing report** with success/failure statistics and API costs

---

## Project Structure

```
japanese-ocr-translator/
├── app/
│   ├── __init__.py
│   ├── logger.py              # Logging (console + file)
│   ├── pdf_converter.py       # PDF → images
│   ├── text_detector.py       # Google Cloud Vision - accurate Japanese text detection
│   ├── translator.py          # GPT-4o text API - Japanese to English
│   ├── ocr_client.py          # OpenAI Vision API (legacy, for fallback)
│   ├── image_replacer.py      # Text replacement logic
│   └── processor.py           # Pipeline orchestration
├── config/
│   ├── __init__.py
│   └── settings.py            # Configuration from .env
├── input/                     # Drop PDFs here
├── output/
│   ├── extractions.json       # Full OCR data with precise bounding boxes
│   ├── processing_report.json # Summary statistics
│   └── images/                # Modified images (English text)
│       ├── file1_page_001.png
│       ├── file1_page_002.png
│       └── ...
├── logs/                      # One log file per run
├── .env.example               # Configuration template
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── main.py                    # Entry point
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Environment Configuration

```bash
cp .env.example .env
```

Open `.env` and set your OpenAI API key:
```env
OPENAI_API_KEY=sk-your-actual-key-here
```

All other settings have sensible defaults, but you can customize:
- `ENABLE_TEXT_REPLACEMENT=true` - Set to `false` to skip text replacement (OCR + translation only)
- `DPI=200` - Image resolution for PDF conversion (higher = more detail, slower)
- `MODEL=gpt-4o` - OpenAI model to use (for translation)
- `MAX_RETRIES=3` - Number of retries for API calls
- `RETRY_DELAY_SECONDS=2` - Delay between retries
- See `.env.example` for all options

Note: **Google Cloud Vision** requires an API key. Set `GOOGLE_CLOUD_API_KEY` in your `.env` file.

### 2a. Run with Docker (Recommended)

**Build the image:**
```bash
docker compose build
```

**Run the pipeline:**
```bash
docker compose up
```

Or use `docker compose run --rm japanese-ocr` for auto-cleanup.

### 2b. Run Locally (Without Docker)

**Prerequisites:**
- Python 3.10+
- **Poppler** (for PDF conversion)
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`
  - Windows: Download from [Poppler releases](https://github.com/osdev/poppler/releases) and add to PATH

**Install and run:**
```bash
pip install -r requirements.txt
python main.py
```

---

## Command-Line Usage

```bash
python main.py [--stage {ocr,replace,all}]
```

### Stages

- **`all`** (default) - Full pipeline: detect text → translate → replace in images
- **`ocr`** - Detection only: extract Japanese text and bounding boxes (no translation or replacement)
- **`replace`** - Translation + replacement only: translate detected text and replace in images (requires existing extraction data)

### Examples

```bash
# Full pipeline (recommended)
python main.py --stage all

# OCR detection only (extract text and coordinates)
python main.py --stage ocr

# Use existing OCR data to translate and replace text
python main.py --stage replace
```

---

## Output Format

### extractions.json

The file contains complete OCR extraction data with precise bounding boxes from Google Cloud Vision:

```json
{
  "metadata": {
    "generated_at": "2026-02-11T10:30:00.123456",
    "pipeline_version": "efficient-v1",
    "detection_method": "Google Cloud Vision",
    "translation_model": "gpt-4o",
    "dpi": 200,
    "text_replacement_enabled": true,
    "total_files_processed": 1,
    "total_elapsed_seconds": 45.2
  },
  "files": [
    {
      "file": "document.pdf",
      "total_pages": 5,
      "pages_with_japanese": 2,
      "pages": [
        {
          "page_number": 1,
          "japanese_found": false,
          "extractions": []
        },
        {
          "page_number": 2,
          "japanese_found": true,
          "extractions": [
            {
              "japanese_text": "東京タワー",
              "english_translation": "Tokyo Tower",
              "bounding_box": {
                "x": 0.45,
                "y": 0.12,
                "width": 0.18,
                "height": 0.04
              }
            }
          ],
          "replacement_stats": {
            "successful": 1,
            "failed": 0
          }
        }
      ]
    }
  ]
}
```

### Bounding Box Coordinates

Coordinates are **normalized** (0.0 to 1.0), derived from Google Cloud Vision:
- `x`, `y` = top-left corner position (fraction of image width/height)
- `width`, `height` = size of the text region
- Example: `x=0.5` means 50% from the left edge
- **Pixel-perfect accuracy** - Google Cloud Vision detects exact text location

The pipeline converts these to pixel coordinates based on actual image dimensions for text replacement.

### processing_report.json

```json
{
  "summary": {
    "total_files": 1,
    "total_pages": 5,
    "pages_with_japanese": 2,
    "total_replacements_successful": 3,
    "total_replacements_failed": 0,
    "elapsed_seconds": 45.2
  },
  "files": [
    {
      "file": "document.pdf",
      "pages": 5,
      "japanese_pages": 2
    }
  ]
}
```

---

## Architecture

### Three-Stage Pipeline

1. **Text Detection** (`text_detector.py` - Google Cloud Vision)
   - Converts PDF pages to images at configurable DPI
   - Uses Google Cloud Vision API for Japanese text detection
   - Returns pixel-perfect bounding box coordinates
   - **High accuracy OCR** - excellent Japanese language support

2. **Translation** (`translator.py` - GPT-4o Text API)
   - Takes detected Japanese text
   - Translates via GPT-4o text API (faster & cheaper than Vision)
   - Batch processing for efficiency
   - Includes retry logic with exponential backoff

3. **Text Replacement** (`image_replacer.py`)
   - Uses precise bounding boxes from Google Cloud Vision
   - Draws white rectangle over original text
   - Renders English translation with auto-font-sizing
   - Minimum font size: 8px, shrinks until text fits

### Why This Approach?

- **Accuracy**: Google Cloud Vision provides highly accurate OCR with excellent Japanese language support
- **Cost**: Google Cloud Vision is cost-effective for OCR, combined with GPT-4o for translation
- **Speed**: Cloud-based OCR with fast processing times
- **Flexibility**: Run detection alone, or translation+replacement separately
- **Quality**: Specialized models for each task vs. one generalist Vision model

---

## Configuration Reference

All settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| **OpenAI (Translation only)** |
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `MODEL` | `gpt-4o` | OpenAI model for translation |
| `MAX_RETRIES` | `3` | API retries on failure |
| `RETRY_DELAY_SECONDS` | `2` | Delay between retries |
| **PDF Processing** |
| `DPI` | `200` | PDF conversion resolution (higher = sharper) |
| **Text Replacement** |
| `ENABLE_TEXT_REPLACEMENT` | `true` | Enable/disable image modification |
| `ENGLISH_FONT` | `Arial.ttf` | Font for English text |
| `FALLBACK_FONT` | `DejaVuSans.ttf` | Fallback if primary not found |
| `BACKGROUND_FILL_COLOR` | `255,255,255` | RGB color (white) |
| `BBOX_PADDING` | `5` | Pixels of padding around text |
| `RENDER_BOX_PADDING_PCT` | `0.35` | Extra expansion for render box (percentage of text/bubble size) |
| `MIN_FONT_SIZE` | `8` | Minimum font size when auto-shrinking |
| **Paths** |
| `INPUT_FOLDER` | `./input` | Where to read PDFs |
| `OUTPUT_FOLDER` | `./output` | Where to write results |
| `LOG_FOLDER` | `./logs` | Where to write logs |

---

## Error Handling

### Detection Failures (Google Cloud Vision)
- Cloud-based API with high reliability
- If detection fails → page marked "no Japanese found"
- Failures don't block processing of other pages

### Translation Failures
- If API call fails after retries → text extracted but not translated
- Page still processed, failure logged

### Replacement Failures
- Invalid bounding box → skip that extraction, log warning
- English text too long → auto-shrink to `MIN_FONT_SIZE`
- Font loading fails → use PIL default font

### Partial Processing
- Pipeline never crashes on single-page failures
- Each page is independent
- Final report shows success/failure breakdown

---

## Docker Commands Quick Reference

```bash
# Build image (only needed once or after code changes)
docker compose build

# Run pipeline (processes all PDFs in input/)
docker compose up

# Run and auto-remove container when done
docker compose run --rm japanese-ocr

# Clean up containers
docker compose down

# Full cleanup (containers + image)
docker compose down --rmi all

# View running containers
docker ps

# View logs from last run
docker compose logs
```

---

## Troubleshooting

### "No API key found"
- Make sure you copied `.env.example` to `.env`
- Open `.env` and paste your actual OpenAI key
- Key should start with `sk-`

### "No PDF files found"
- Make sure PDFs are in the `input/` folder
- Check file extensions are `.pdf` (lowercase)

### "Font not found" warnings
- The pipeline will use PIL default font if system fonts aren't found
- This is normal and doesn't affect functionality
- Text will still be rendered, just in default font

### Text replacement not happening
- Check `ENABLE_TEXT_REPLACEMENT=true` in `.env`
- Verify bounding box data is present in `extractions.json`
- Check logs for specific errors

### Poor text detection quality
- Increase `DPI` in `.env` (try 300 for higher quality detection)
- Check input PDF image quality
- Verify Japanese text is clear and readable in the original
- Google Cloud Vision works best with clear, digital text

---

## Notes

- **API Costs**: Google Cloud Vision OCR (~$1.50 per 1000 images) + Translation API usage. Typical combined cost is ~$0.002-0.01 per page
- **Processing Speed**: ~2-5 seconds per page (cloud-based detection + translation)
- **Image Format**: Output images are PNG (lossless, preserves quality)
- **API Keys Required**: Google Cloud Vision API key for OCR, OpenAI API key for translation
- **No PDF Output**: This version only outputs images. If you need PDFs, use a separate tool to combine the images.

---

## Examples

**Input PDF:**
```
input/
└── report.pdf  (10 pages, pages 3-5 have Japanese text)
```

**After running the pipeline:**
```
output/
├── extractions.json              # All OCR data with coordinates
├── processing_report.json        # Summary & statistics
└── images/
    ├── report_page_001.png       # Original (no Japanese)
    ├── report_page_002.png       # Original (no Japanese)
    ├── report_page_003.png       # Modified (English text)
    ├── report_page_004.png       # Modified (English text)
    ├── report_page_005.png       # Modified (English text)
    ├── report_page_006.png       # Original
    └── ...
```

**Processing report shows:**
- 10 total pages processed
- 3 pages with Japanese text detected
- 8 successful text replacements
- 0 failures

---

## Dependencies

- **Google Cloud Vision** - Cloud-based OCR for text detection (requires API key)
- **OpenAI API** - Translation (requires API key)
- **pdf2image** - PDF conversion (requires system Poppler)
- **Pillow** - Image manipulation
- **python-dotenv** - Configuration
or explicitly:
docker compose run --rm japanese-ocr --stage all
# OCR only
docker compose run --rm japanese-ocr --stage ocr
# Text Replacement Only
docker compose run --rm japanese-ocr --stage replace

# Locally. (without Docker)
python main.py --stage ocr
python main.py --stage replace
python main.py --stage all
