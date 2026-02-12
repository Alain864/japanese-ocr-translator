# Japanese OCR Translator — AI Coding Agent Guide

## Project Overview

**Purpose**: Unified pipeline that extracts Japanese text from PDFs using Google Cloud Vision API (pixel-perfect accuracy), translates it using GPT-4o text API, and optionally replaces Japanese text in images with English translations.

**Architecture**: Single-entry Python script orchestrates three sequential processing stages across separate modules, with results saved as JSON and PNG files.

---

## Critical Architecture & Data Flow

### Pipeline Stages

1. **PDF → Images** (`pdf_converter.py`)
   - Converts PDF pages to PIL Images at configurable DPI (default 200)
   - Uses `pdf2image` with Poppler backend
   - Returns ordered list of PIL Image objects per PDF

2. **Text Detection** (`text_detector.py`)
   - Uses **Google Cloud Vision API** for pixel-perfect Japanese text detection
   - `DOCUMENT_TEXT_DETECTION` mode for dense, complex text layouts
   - Returns: Japanese text, precise bounding box (0-1 normalized), confidence scores
   - Handles complex text rotations and layouts automatically

3. **Translation** (`translator.py`)
   - Uses **GPT-4o text API** (not Vision API) for batch translation
   - Groups detected Japanese texts and translates in bulk (more cost-efficient)
   - Handles retries with exponential backoff (max 3 retries, 2s delay)
   - Returns list of English translations in same order as input

4. **Text Replacement** (`image_replacer.py`)
   - Optional stage (controlled by `ENABLE_TEXT_REPLACEMENT` setting)
   - Erases original Japanese text with intelligent white-out (detects text via threshold)
   - Detects speech bubbles with Hough circle detection (`BUBBLE_DETECT_THRESHOLD`)
   - Renders English translation with font matching attempt (Arial preferred, DejaVuSans fallback)
   - Auto-shrinks font if English text exceeds bounding box width
   - Minimum font size: configurable (default 8px)

### Data Flow Structure

```
PDF (input/) 
  → Process each page:
    - PIL.Image (HxW)
    - → [TextDetector] Google Cloud Vision detections:
        [
          {
            "japanese_text": str,
            "bounding_box": {"x": 0-1, "y": 0-1, "width": 0-1, "height": 0-1},
            "confidence": float
          }
        ]
    - → [Translator] Batch translation to English:
        ["translated text 1", "translated text 2", ...]
    - → (optional) [ImageReplacer] Modified PIL.Image
  → JSON export (output/extractions.json)
  → PNG images (output/images/*.png)
  → Report (output/processing_report.json)
```

---

## Configuration Model (Single Source of Truth)

**File**: [config/settings.py](config/settings.py)

- Reads `.env` at project root (via `python-dotenv`)
- All runtime config in one module — import from here, never hardcode
- Four config categories:
  - **Google Cloud Vision**: API key for text detection
  - **OpenAI**: API key, model for translation
  - **Stage 1 (Text Detection)**: DPI for PDF conversion
  - **Stage 2 (Replacement)**: Font paths, text erasing thresholds, bubble detection, padding, min font size, background color

**Key pattern**: Path variables use `Path(__file__).resolve().parent.parent` for relative resolution.

**Environment Variables**:
```
GOOGLE_CLOUD_API_KEY=your-google-cloud-api-key
OPENAI_API_KEY=your-openai-api-key
MODEL=gpt-4o
DPI=200
ENABLE_TEXT_REPLACEMENT=true
TEXT_ERASE_PADDING=6
TEXT_ERASE_THRESHOLD=190
BUBBLE_DETECT_THRESHOLD=200
BUBBLE_MIN_AREA=800
MIN_FONT_SIZE=8
```

---

## Module Responsibilities

| Module | Role | Key Types |
|--------|------|-----------|
| `main.py` | Entry point, validation, stage orchestration (ocr/replace/all) | — |
| `processor.py` | Coordinates pipeline for each PDF, aggregates results | `process_pdf_accurate(pdf_path, text_detector, translator, image_replacer)` |
| `text_detector.py` | Google Cloud Vision API calls, JSON parsing | `TextDetector.detect_text(image, label) → List[Dict]` |
| `translator.py` | Batch translation via GPT-4o text API, retry logic | `Translator.translate_batch(japanese_texts, label) → List[str]` |
| `pdf_converter.py` | PDF rasterization | `pdf_to_images(pdf_path) → List[Image]` |
| `image_replacer.py` | Text overlay, font sizing, bbox conversion | `ImageReplacer.replace_text(image, extractions, page_label) → (Image, success_count, fail_count)` |
| `logger.py` | Dual-sink logging (console + timestamped file) | `get_logger(name)` |
| `ocr_client.py` | ⚠️ **DEPRECATED**: Legacy OpenAI Vision API (fallback only) | `OCRClient.extract_japanese(image, label)` |

---

## Key Developer Workflows

### Local Development

```bash
# Setup
cp .env.example .env
# Edit .env with GOOGLE_CLOUD_API_KEY and OPENAI_API_KEY

# Install dependencies
pip install -r requirements.txt

# Run full pipeline (all stages)
python main.py --stage all

# Run OCR only (text detection + translation, no image replacement)
python main.py --stage ocr

# Run replacement only (uses existing extractions.json)
python main.py --stage replace
```

### Docker Workflow

```bash
# Build
docker compose build

# Run (mounts input/, output/, logs/ as volumes)
docker compose up

# Run with auto-cleanup
docker compose run --rm japanese-ocr
```

### Logging

- **Console**: INFO level with timestamp
- **File**: DEBUG level, per-run timestamped file in `logs/` folder
- All loggers use `get_logger(name)` factory, rooted under "japanese_ocr"

---

## Project-Specific Patterns & Conventions

### 1. **Error Handling: Fail Fast with Context**
   - Validation at start of `main.py` with clear error messages
   - OCR failures logged but don't halt pipeline (per-page granularity)
   - Image replacement failures tracked in stats, not exceptions

### 2. **Normalized Bounding Boxes**
   - All bbox coordinates are **0-1 normalized** (not pixel coords)
   - Conversion in `image_replacer.py`: `x_px = x_norm * img_width`
   - Includes `TEXT_ERASE_PADDING` (default 6px) for white rectangle expansion

### 3. **API Cost Optimization**
   - **Separation of concerns**: Detection (Google Cloud Vision) and translation (GPT-4o text API) are separate
   - Google Cloud Vision: Per-page cost, handles complex layouts with DOCUMENT_TEXT_DETECTION mode
   - GPT-4o text API: Batch processing per page (all texts in one API call), much cheaper than Vision API
   - Single batch call per page dramatically reduces translation costs

### 4. **Font Fallback Chain**
   - Primary: `ENGLISH_FONT` (Arial.ttf)
   - Secondary: `FALLBACK_FONT` (DejaVuSans.ttf)
   - Tertiary: PIL default (if no TTF found)
   - Font path discovery searches system font paths via `_find_font()`

### 5. **Text Erasing & Replacement**
   - **Threshold-based detection**: `TEXT_ERASE_THRESHOLD` distinguishes text from background
   - **Dilation**: `TEXT_ERASE_DILATE` (default 3px) ensures complete coverage of erased text
   - **Bubble detection**: Hough circle detection identifies speech bubbles for special handling
   - **Line spacing**: `LINE_SPACING` (default 1.1x) for multi-line text rendering

### 6. **Output Structure**
   - `extractions.json`: Full per-page OCR results with bounding boxes and detections
   - `processing_report.json`: Aggregate stats (files processed, pages with Japanese, API usage)
   - `images/`: Modified PNGs named `{pdf_stem}_page_{number:03d}.png`

---

## External Dependencies & Integration Points

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `google-cloud-vision` | Google Cloud Vision API for text detection | Requires `GOOGLE_CLOUD_API_KEY` env var |
| `openai` | GPT-4o text API for translation | Requires `OPENAI_API_KEY` env var |
| `pdf2image` | PDF → PIL Images | Requires system Poppler (included in Docker) |
| `Pillow` | Image manipulation | Drawing, font rendering, format conversion |
| `python-dotenv` | Environment config | Reads `.env` file at startup |

---

## Common Modification Points

**Adjusting text detection**: Tune `DPI` in `.env` for better/faster detection quality.

**Adjusting translation**: Modify `MODEL` in `.env` (e.g., "gpt-4-turbo") or adjust temperature/max_tokens in `translator.py` system prompt.

**Adjusting text replacement**: Modify `TEXT_ERASE_THRESHOLD`, `TEXT_ERASE_PADDING`, `BUBBLE_DETECT_THRESHOLD`, `MIN_FONT_SIZE` in `.env`, or tune font lookup in `image_replacer.py`.

**Disabling text replacement**: Set `ENABLE_TEXT_REPLACEMENT=false` in `.env`.

---

## Notes for AI Agents

- Always check `.env.example` for all configurable parameters before hardcoding values
- Path resolution always uses `.resolve()` to ensure absolute paths
- Bounding box coordinates are **always normalized (0-1)** — never assume pixel space
- Each PDF is processed independently; failures don't block other files
- OCR results are deterministic JSON — prefer parsing over regex or heuristics
