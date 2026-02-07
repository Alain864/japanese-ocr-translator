# Japanese OCR Translator — AI Coding Agent Guide

## Project Overview

**Purpose**: Unified pipeline that extracts Japanese text from PDFs using GPT-4o Vision, translates it to English, and optionally replaces Japanese text in images with English translations.

**Architecture**: Single-entry Python script orchestrates three sequential processing stages across separate modules, with results saved as JSON and PNG files.

---

## Critical Architecture & Data Flow

### Pipeline Stages

1. **PDF → Images** (`pdf_converter.py`)
   - Converts PDF pages to PIL Images at configurable DPI (default 200)
   - Uses `pdf2image` with Poppler backend
   - Returns ordered list of PIL Image objects per PDF

2. **OCR + Translation** (`ocr_client.py`)
   - Per-page OpenAI Vision API calls (GPT-4o by default)
   - **One API call per page** — single request extracts everything in JSON format
   - Returns: Japanese text, English translation, normalized bounding box (0-1), font styling (bold/italic)
   - Handles retries with exponential backoff (max 3 retries, 2s delay)

3. **Text Replacement** (`image_replacer.py`)
   - Optional stage (controlled by `ENABLE_TEXT_REPLACEMENT` setting)
   - Draws white rectangle over original text using bounding box
   - Renders English translation with font matching attempt (Arial preferred, DejaVuSans fallback)
   - Auto-shrinks font if English text exceeds bounding box width
   - Minimum font size: 8px

### Data Flow Structure

```
PDF (input/) 
  → Process each page:
    - PIL.Image (HxW)
    - → OCR result dict:
        {
          "japanese_found": bool,
          "extractions": [
            {
              "japanese_text": str,
              "english_translation": str,
              "bounding_box": {"x": 0-1, "y": 0-1, "width": 0-1, "height": 0-1},
              "styling": {"bold": bool, "italic": bool}
            }
          ]
        }
    - → (optional) Modified PIL.Image
  → JSON export (output/extractions.json)
  → PNG images (output/images/*.png)
  → Report (output/processing_report.json)
```

---

## Configuration Model (Single Source of Truth)

**File**: [config/settings.py](config/settings.py)

- Reads `.env` at project root (via `python-dotenv`)
- All runtime config in one module — import from here, never hardcode
- Three config categories:
  - **OpenAI**: API key, model, retries
  - **Stage 1 (OCR)**: DPI, model selection
  - **Stage 2 (Replacement)**: Font paths, bbox padding, min font size, background color

**Key pattern**: Path variables use `Path(__file__).resolve().parent.parent` for relative resolution.

---

## Module Responsibilities

| Module | Role | Key Types |
|--------|------|-----------|
| `main.py` | Entry point, validation, orchestration | — |
| `processor.py` | Coordinates pipeline for each PDF, aggregates results | `process_pdf(pdf_path, ocr_client, image_replacer)` |
| `ocr_client.py` | OpenAI API calls, retry logic, JSON parsing | `OCRClient.extract_japanese(image, label)` |
| `pdf_converter.py` | PDF rasterization | `pdf_to_images(pdf_path) → List[Image]` |
| `image_replacer.py` | Text overlay, font sizing, bbox conversion | `ImageReplacer.replace_text(image, extractions, page_label) → (Image, success_count, fail_count)` |
| `logger.py` | Dual-sink logging (console + timestamped file) | `get_logger(name)` |

---

## Key Developer Workflows

### Local Development

```bash
# Setup
cp .env.example .env
# Edit .env with OPENAI_API_KEY

# Install dependencies
pip install -r requirements.txt

# Run pipeline
python main.py
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
   - Includes `BBOX_PADDING` (default 5px) for white rectangle expansion

### 3. **API Cost Optimization**
   - Single GPT-4o call per page (not per text segment)
   - System prompt guides unified JSON response format
   - JSON parsing validates response structure before use

### 4. **Font Fallback Chain**
   - Primary: `ENGLISH_FONT` (Arial.ttf)
   - Secondary: `FALLBACK_FONT` (DejaVuSans.ttf)
   - Tertiary: PIL default (if no TTF found)
   - Font path discovery searches system font paths via `_find_font()`

### 5. **Output Structure**
   - `extractions.json`: Full per-page OCR results with bounding boxes
   - `processing_report.json`: Aggregate stats (files processed, pages with Japanese, API usage)
   - `images/`: Modified PNGs named `{pdf_stem}_page_{number:03d}.png`

---

## External Dependencies & Integration Points

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `openai` | GPT-4o Vision API | Requires `OPENAI_API_KEY` env var |
| `pdf2image` | PDF → PIL Images | Requires system Poppler (included in Docker) |
| `Pillow` | Image manipulation | Drawing, font rendering, format conversion |
| `python-dotenv` | Environment config | Reads `.env` file at startup |

---

## Common Modification Points

**Adding OCR fields**: Update system prompt in `ocr_client.py`, then update JSON schema in parsing logic.

**Adjusting text replacement**: Modify `BBOX_PADDING`, `MIN_FONT_SIZE`, `BACKGROUND_FILL_COLOR` in `.env`, or tune font lookup in `image_replacer.py`.

**Changing API model**: Update `MODEL` in `.env` (e.g., "gpt-4-turbo") — no code changes needed.

**Disabling text replacement**: Set `ENABLE_TEXT_REPLACEMENT=false` in `.env`.

---

## Notes for AI Agents

- Always check `.env.example` for all configurable parameters before hardcoding values
- Path resolution always uses `.resolve()` to ensure absolute paths
- Bounding box coordinates are **always normalized (0-1)** — never assume pixel space
- Each PDF is processed independently; failures don't block other files
- OCR results are deterministic JSON — prefer parsing over regex or heuristics
