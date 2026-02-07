# japanese-ocr-translator

**Unified pipeline** that extracts Japanese text from image-based PDFs, translates it to English, and replaces the original Japanese text with English translations directly in the images.

---

## What It Does

### Stage 1: OCR + Translation + Localization
- Converts PDF pages to high-resolution images
- Sends each image to **GPT-4o Vision API**
- Extracts: Japanese text + English translation + bounding box coordinates + font styling (bold/italic)
- One API call per page - everything in a single request

### Stage 2: Text Replacement (Optional)
- Uses bounding box coordinates to locate Japanese text
- Covers original text with white rectangle
- Renders English translation in the same location
- Attempts to match original font characteristics (bold/italic)
- Auto-shrinks font size if English text is too long

### Output
- **JSON file** with all extraction data (text, translations, coordinates)
- **Modified images** with English text replacing Japanese
- **Processing report** with success/failure statistics

---

## Project Structure

```
japanese-ocr-translator/
├── app/
│   ├── __init__.py
│   ├── logger.py           # Logging (console + file)
│   ├── pdf_converter.py    # PDF → images
│   ├── ocr_client.py       # OpenAI Vision API calls
│   ├── image_replacer.py   # Text replacement logic
│   └── processor.py        # Pipeline orchestration
├── config/
│   ├── __init__.py
│   └── settings.py         # Configuration from .env
├── input/                  # Drop PDFs here
├── output/
│   ├── extractions.json    # Full OCR data with bounding boxes
│   ├── processing_report.json
│   └── images/             # Modified images (English text)
│       ├── file1_page_001.png
│       ├── file1_page_002.png
│       └── ...
├── logs/                   # One log file per run
├── .env.example            # Configuration template
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── main.py                 # Entry point
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
- `ENABLE_TEXT_REPLACEMENT=true` - Set to `false` to only extract text (no image modification)
- `DPI=200` - Image resolution (higher = more detail, slower, more API tokens)
- `MODEL=gpt-4o` - OpenAI model to use
- See `.env.example` for all options

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

## Usage

1. **Add PDFs** to the `input/` folder
2. **Run the pipeline** (see Setup above)
3. **Check output:**
   - `output/extractions.json` - All OCR data
   - `output/images/` - Modified images with English text
   - `output/processing_report.json` - Summary statistics
   - `logs/` - Detailed processing logs

---

## Output Format

### extractions.json

```json
{
  "metadata": {
    "generated_at": "2025-02-04T03:45:00.000000",
    "pipeline_version": "unified-v1",
    "model": "gpt-4o",
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
              },
              "styling": {
                "bold": true,
                "italic": false
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

Coordinates are **normalized** (0.0 to 1.0):
- `x`, `y` = top-left corner position
- `width`, `height` = size of the text region
- Example: `x=0.5` means 50% from the left edge

The pipeline converts these to pixel coordinates based on actual image dimensions.

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

## Configuration Reference

All settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| **OpenAI** |
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `MODEL` | `gpt-4o` | Model for OCR + translation |
| `MAX_RETRIES` | `3` | API retries per page on failure |
| `RETRY_DELAY_SECONDS` | `2` | Delay between retries |
| **PDF Processing** |
| `DPI` | `200` | Image resolution (higher = sharper) |
| **Text Replacement** |
| `ENABLE_TEXT_REPLACEMENT` | `true` | Enable/disable image modification |
| `ENGLISH_FONT` | `Arial.ttf` | Font for English text |
| `FALLBACK_FONT` | `DejaVuSans.ttf` | Fallback if primary not found |
| `BACKGROUND_FILL_COLOR` | `255,255,255` | RGB color (white) |
| `BBOX_PADDING` | `5` | Pixels of padding around text |
| `MIN_FONT_SIZE` | `8` | Minimum font size when auto-shrinking |
| **Paths** |
| `INPUT_FOLDER` | `./input` | Where to read PDFs |
| `OUTPUT_FOLDER` | `./output` | Where to write results |
| `LOG_FOLDER` | `./logs` | Where to write logs |

---

## How It Works

### Unified API Call

Instead of separate calls for OCR and localization, the pipeline uses **one API call per page** that returns everything:

**Prompt sent to GPT-4o Vision:**
```
"For each Japanese text segment in this image, return:
 - The original Japanese text
 - English translation  
 - Bounding box (normalized x, y, width, height)
 - Font styling (bold, italic)"
```

**Response format:**
```json
{
  "japanese_found": true,
  "extractions": [
    {
      "japanese_text": "営業時間",
      "english_translation": "Business Hours",
      "bounding_box": {"x": 0.1, "y": 0.5, "width": 0.2, "height": 0.04},
      "styling": {"bold": false, "italic": false}
    }
  ]
}
```

### Text Replacement Logic

For each extraction with a bounding box:

1. **Convert coordinates**: Normalized (0-1) → pixel coordinates
2. **Add padding**: Expand bounding box by `BBOX_PADDING` pixels
3. **Draw background**: White rectangle covering original text
4. **Calculate font size**: Start at 80% of box height
5. **Auto-shrink**: Reduce font size until English fits (min: `MIN_FONT_SIZE`)
6. **Center text**: Position English translation in the middle of the box
7. **Render**: Draw black text on white background

---

## Error Handling

### OCR Failures
- If API call fails after all retries → page marked with error, processing continues
- If bounding box data is missing → text extracted but not replaced

### Replacement Failures
- Invalid bounding box → skip that extraction, log warning
- English text too long → shrink to `MIN_FONT_SIZE`, then render anyway
- Font loading fails → use PIL default font
- All failures are logged and counted in the processing report

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

### Poor OCR quality
- Increase `DPI` in `.env` (try 300)
- Check input PDF image quality
- Verify Japanese text is clear and readable in the original

---

## Notes

- **API Costs**: One API call per page. At 200 DPI, typical cost is $0.01-0.03 per page.
- **Processing Speed**: ~5-10 seconds per page (depends on API latency and image complexity)
- **Image Format**: Output images are PNG (lossless, preserves quality)
- **Font Styling**: Bold/italic detection works best on clear, standard fonts
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
├── extractions.json              # All OCR data
├── processing_report.json        # Summary
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
- 3 pages with Japanese text
- 8 successful text replacements
- 0 failures

---

## License

This project uses:
- OpenAI GPT-4o API (requires API key)
- pdf2image / Poppler (Apache/GPL)
- Pillow (PIL Fork)
- python-dotenv (BSD)