"""Main entry point for the Japanese OCR Translator application."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

from src.config import Config
from src.pdf_processor import PDFProcessor
from src.ocr_engine import OCREngine
from src.translator import Translator


logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


class OCRTranslatorPipeline:
    """Main pipeline for OCR and translation processing."""
    
    def __init__(self):
        """Initialize the pipeline."""
        self.ocr_engine = OCREngine()
        self.translator = Translator()
        self.results: List[Dict] = []
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Process a single PDF file."""
        logger.info(f"Starting processing of: {pdf_path}")
        
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        results = {
            'source_pdf': pdf_path_obj.name,
            'processed_at': datetime.now().isoformat(),
            'total_images': 0,
            'results': []
        }
        
        with PDFProcessor(pdf_path) as processor:
            images = processor.extract_images()
            results['total_images'] = len(images)
            
            logger.info(f"Extracted {len(images)} images from PDF")
            
            for page_num, image in tqdm(images, desc="Processing pages", unit="page"):
                logger.info(f"Processing page {page_num}")
                
                ocr_result = self.ocr_engine.extract_text(image)
                
                page_result = {
                    'page_number': page_num,
                    'image_name': f"{processor.pdf_name}_page_{page_num}.png",
                    'japanese_text': ocr_result['text'],
                    'ocr_confidence': round(ocr_result['confidence'], 3),
                    'has_text': ocr_result['has_text']
                }
                
                if ocr_result['has_text'] and ocr_result['text']:
                    translation_result = self.translator.translate(ocr_result['text'])
                    
                    page_result.update({
                        'english_translation': translation_result.get('translation', ''),
                        'translation_success': translation_result.get('success', False),
                        'translation_error': translation_result.get('error')
                    })
                    
                    if translation_result.get('usage'):
                        page_result['tokens_used'] = translation_result['usage']['total_tokens']
                else:
                    page_result.update({
                        'english_translation': '',
                        'translation_success': False,
                        'translation_error': 'No text detected or confidence too low'
                    })
                
                results['results'].append(page_result)
        
        self.results = results
        return results
    
    def save_results(self, output_path: Path = None) -> Path:
        """Save processing results to JSON file."""
        if not self.results:
            raise ValueError("No results to save. Run process_pdf first.")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.results['source_pdf'].replace('.pdf', '')}_{timestamp}_results.json"
            output_path = Config.OUTPUT_DIR / filename
        
        Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to: {output_path}")
        return output_path
    
    def print_summary(self):
        """Print a summary of processing results."""
        if not self.results:
            logger.warning("No results to summarize")
            return
        
        total_pages = self.results['total_images']
        pages_with_text = sum(1 for r in self.results['results'] if r['has_text'])
        successful_translations = sum(
            1 for r in self.results['results'] if r.get('translation_success', False)
        )
        
        total_tokens = sum(
            r.get('tokens_used', 0) for r in self.results['results']
        )
        
        print("\n" + "="*60)
        print("PROCESSING SUMMARY")
        print("="*60)
        print(f"PDF File: {self.results['source_pdf']}")
        print(f"Total Pages: {total_pages}")
        print(f"Pages with Text: {pages_with_text}")
        print(f"Successful Translations: {successful_translations}")
        print(f"Total Tokens Used: {total_tokens}")
        print("="*60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract and translate Japanese text from PDF files"
    )
    parser.add_argument(
        'pdf_path',
        type=str,
        help='Path to the PDF file to process'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output path for results JSON file (optional)'
    )
    
    args = parser.parse_args()
    
    try:
        pipeline = OCRTranslatorPipeline()
        
        logger.info("="*60)
        logger.info("Japanese OCR Translator Pipeline")
        logger.info("="*60)
        
        results = pipeline.process_pdf(args.pdf_path)
        
        output_path = Path(args.output) if args.output else None
        saved_path = pipeline.save_results(output_path)
        
        pipeline.print_summary()
        
        logger.info(f"✓ Processing complete! Results saved to: {saved_path}")
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())