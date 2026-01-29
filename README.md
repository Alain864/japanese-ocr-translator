# Japanese OCR Translator

A containerized solution for extracting Japanese text from PDF images and translating it to English using Tesseract OCR and OpenAI API.

## Features

- Extract images from PDF files
- OCR Japanese text using Tesseract with Japanese language support
- Translate extracted text to English using OpenAI GPT-4
- Batch processing with progress tracking
- Structured JSON output with results
- Dockerized for easy deployment

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd japanese-ocr-translator
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Build and Run with Docker

```bash
docker-compose build
docker-compose run --rm app python src/main.py data/input/your_file.pdf
```

## Project Structure

```
japanese-ocr-translator/
├── src/
│   ├── config.py           # Configuration management
│   ├── main.py             # Entry point
│   ├── pdf_processor.py    # PDF to image extraction
│   ├── ocr_engine.py       # Tesseract OCR wrapper
│   └── translator.py       # OpenAI translation
├── tests/
├── data/
│   ├── input/              # Place PDF files here
│   └── output/             # Results saved here
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Output Format

```json
{
  "source_pdf": "example.pdf",
  "processed_at": "2026-01-28T10:30:00",
  "total_images": 5,
  "results": [
    {
      "page_number": 1,
      "japanese_text": "こんにちは世界",
      "english_translation": "Hello world",
      "ocr_confidence": 0.95
    }
  ]
}
```

## Requirements

- Docker and Docker Compose
- OpenAI API key

## License

MIT
