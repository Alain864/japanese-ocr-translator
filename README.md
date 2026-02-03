# japanese-ocr-pipeline

Extracts Japanese text from image-based PDFs and translates it to English using **GPT-4o Vision**.

---

## How it works

1. Every `.pdf` file in `input/` is rasterised page-by-page (via Poppler).
2. Each page image is sent to GPT-4o with a structured prompt that extracts Japanese text and translates it in a single API call.
3. Results are written to a single JSON file in `output/`.

---

## Project layout

```
japanese-ocr-pipeline/
├── app/
│   ├── __init__.py
│   ├── logger.py          # Centralised logging (console + file)
│   ├── ocr_client.py      # All OpenAI Vision API calls + retry logic
│   ├── pdf_converter.py   # PDF → PIL Image conversion (Poppler)
│   └── processor.py       # Orchestrator: wires converter → OCR → result dict
├── config/
│   ├── __init__.py
│   └── settings.py        # Single source of truth for env vars / paths
├── input/                 # Drop your PDFs here
├── output/                # JSON results are written here
├── logs/                  # One log file per run
├── .env.example           # Template — copy to .env and fill in your key
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── main.py                # Entry point
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Environment

```bash
cp .env.example .env
```

Open `.env` and replace `your-openai-api-key-here` with your actual OpenAI key. That is the only required change; everything else has sensible defaults.

### 2a. Run with Docker (recommended)

```bash
# Build the image
docker build -t japanese-ocr .

# Run (drop PDFs into input/ first)
docker run --env-file .env \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  japanese-ocr
```

Or, if you have Docker Compose:

```bash
docker compose up --build
```

### 2b. Run locally (without Docker)

Prerequisites: **Python 3.10+** and **Poppler** installed on your system.

- macOS: `brew install poppler`
- Ubuntu/Debian: `sudo apt install poppler-utils`
- Windows: download from the [Poppler releases page](https://github.com/osdev/poppler/releases) and add to PATH.

```bash
pip install -r requirements.txt
python main.py
```

---

## Output

A single JSON file (`output/japanese_extraction_results.json`) with this structure:

```json
{
  "metadata": {
    "generated_at": "2025-02-02T14:30:00.000000",
    "pipeline": "japanese_ocr_pipeline",
    "model": "gpt-4o",
    "dpi": 200,
    "total_files_processed": 2,
    "total_elapsed_seconds": 45.12
  },
  "files": [
    {
      "file": "sample.pdf",
      "total_pages": 10,
      "pages_with_japanese": 3,
      "pages": [
        {
          "page_number": 2,
          "japanese_found": true,
          "extractions": [
            {
              "japanese_text": "東京タワー",
              "english_translation": "Tokyo Tower",
              "location_description": "top-right corner"
            }
          ]
        },
        {
          "page_number": 5,
          "japanese_found": false,
          "extractions": []
        }
      ]
    }
  ]
}
```

Each extraction records the original Japanese, its English translation, and a plain-language description of where on the page it appeared.

---

## Configuration reference

All values are set in `.env`. Defaults are shown.

| Variable               | Default   | Description                                          |
|------------------------|-----------|------------------------------------------------------|
| `OPENAI_API_KEY`       | —         | **Required.** Your OpenAI secret key.                |
| `MODEL`                | `gpt-4o`  | Model used for vision OCR + translation.             |
| `DPI`                  | `200`     | Resolution when rasterising PDF pages.               |
| `MAX_RETRIES`          | `3`       | API call retries per page before marking as failed.  |
| `RETRY_DELAY_SECONDS`  | `2`       | Seconds between retries.                             |
| `INPUT_FOLDER`         | `./input` | Folder to read PDFs from.                            |
| `OUTPUT_FOLDER`        | `./output`| Folder where the JSON result is written.             |
| `LOG_FOLDER`           | `./logs`  | Folder for log files.                                |

---

## Notes

- Pages with no Japanese text are still recorded in the output (with `japanese_found: false`) so you have a complete audit trail.
- If an API call fails after all retries, the page is recorded with an `error` field instead of crashing the whole run.
- The `.env` file is in `.gitignore` — it will never be committed.