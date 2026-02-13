# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Japanese OCR Translator: A unified pipeline that extracts Japanese text from image-based PDFs using GPT-4o Vision, translates it to English, and optionally replaces the original Japanese text with English translations directly in the images.

## Quick Start Commands

### Local Development
```bash
# Setup
cp .env.example .env
# Edit .env with OPENAI_API_KEY

# Install dependencies (requires Python 3.10+ and Poppler)
pip install -r requirements.txt

# Run full pipeline (default)
python main.py

# Run OCR only (no text replacement)
python main.py --stage ocr

# Run text replacement only (requires existing extractions.json)
python main.py --stage replace
```

### Docker
```bash
# Build
docker compose build

# Run full pipeline
docker compose up

# Run with auto-cleanup
docker compose run --rm japanese-ocr

# Override stage
docker compose run --rm japanese-ocr --stage ocr
```

## Architecture & Data Flow

### Three-Stage Pipeline

1. **PDF → Images** ([app/pdf_converter.py](app/pdf_converter.py))
   - Converts PDF pages to PIL Images at configured DPI (default 200)
   - Uses pdf2image with Poppler backend

2. **OCR + Translation** ([app/ocr_client.py](app/ocr_client.py))
   - **One OpenAI Vision API call per page** extracts everything in a single request
   - Returns: Japanese text, English translation, normalized bounding boxes (0-1), font styling
   - Includes retry logic with exponential backoff (max 3 retries)

3. **Text Replacement** ([app/image_replacer.py](app/image_replacer.py)) - Optional
   - Covers original text with white rectangle using bounding box coordinates
   - Renders English translation with font matching (Arial → DejaVuSans → PIL default)
   - Auto-shrinks font size if English text exceeds bounding box width (min 8px)

### Pipeline Orchestration

- [main.py](main.py): Entry point with validation and stage selection
- [app/processor.py](app/processor.py): Coordinates pipeline execution per PDF
- [config/settings.py](config/settings.py): Single source of truth for all configuration (reads from .env)

### Output Structure
```
output/
├── extractions.json           # Full per-page OCR results with bounding boxes
├── processing_report.json     # Aggregate statistics
└── images/
    └── {pdf_stem}_page_{num:03d}.png
```

## Critical Implementation Details

### Normalized Bounding Boxes
- **All bounding box coordinates use 0-1 normalized range, NOT pixel coordinates**
- Conversion to pixels happens in [app/image_replacer.py](app/image_replacer.py): `x_px = x_norm * img_width`
- Includes configurable `BBOX_PADDING` (default 5px) to expand rectangles before drawing

### Single API Call Strategy
- One GPT-4o Vision API call per page extracts all data (text, translation, coordinates, styling)
- System prompt guides unified JSON response format
- This minimizes API costs compared to separate OCR + localization calls

### Error Handling Philosophy
- **Fail fast on startup**: Validate API key, input folder, and required files before processing
- **Continue on per-page failures**: Individual page errors don't halt the entire pipeline
- **Track partial successes**: All failures logged and counted in processing report

### Configuration Model
- All runtime config in [config/settings.py](config/settings.py)
- Never hardcode values - always import from settings
- Check `.env.example` for all available parameters
- Path resolution uses `.resolve()` for absolute paths

## Common Development Patterns

### Adding New OCR Fields
1. Update system prompt in [app/ocr_client.py](app/ocr_client.py)
2. Update JSON schema validation in parsing logic

### Adjusting Text Replacement
- Modify `.env` settings: `BBOX_PADDING`, `MIN_FONT_SIZE`, `BACKGROUND_FILL_COLOR`
- Font fallback chain: `ENGLISH_FONT` → `FALLBACK_FONT` → PIL default

### Changing API Model
- Update `MODEL` in `.env` (e.g., "gpt-4-turbo")
- No code changes needed

### Disabling Text Replacement
- Set `ENABLE_TEXT_REPLACEMENT=false` in `.env`

## Testing & Validation

- Add test PDFs to `input/` folder
- Check logs in `logs/` directory (timestamped files with DEBUG level)
- Verify output in `output/extractions.json` and `output/processing_report.json`
- Modified images saved to `output/images/`

## Dependencies

| Package | Purpose | Notes |
|---------|---------|-------|
| openai | GPT-4o Vision API | Requires `OPENAI_API_KEY` |
| pdf2image | PDF rasterization | Requires system Poppler (included in Docker) |
| Pillow | Image manipulation | Drawing, font rendering |
| python-dotenv | Environment config | Reads `.env` at startup |

### System Requirements
- **Local**: Python 3.10+, Poppler (`brew install poppler` on macOS)
- **Docker**: No additional requirements
