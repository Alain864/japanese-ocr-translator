"""PDF processing module for extracting images from PDF files."""

import logging
from pathlib import Path
from typing import List, Tuple
import fitz  # PyMuPDF
from PIL import Image
import io

from .config import Config

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Process PDF files and extract images."""
    
    def __init__(self, pdf_path: str):
        """Initialize PDF processor."""
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.doc = None
        self.images: List[Tuple[int, Image.Image]] = []
        
    def __enter__(self):
        """Context manager entry."""
        self.doc = fitz.open(self.pdf_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.doc:
            self.doc.close()
    
    def extract_images(self) -> List[Tuple[int, Image.Image]]:
        """Extract all images from the PDF."""
        if not self.doc:
            raise RuntimeError("PDF document not opened. Use context manager.")
        
        images = []
        
        for page_num in range(len(self.doc)):
            logger.info(f"Processing page {page_num + 1}/{len(self.doc)}")
            page = self.doc[page_num]
            
            # Render page to image at specified DPI
            mat = fitz.Matrix(Config.DPI / 72, Config.DPI / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Resize if image is too large
            if max(img.size) > Config.MAX_IMAGE_SIZE:
                logger.info(f"Resizing image from {img.size}")
                img.thumbnail((Config.MAX_IMAGE_SIZE, Config.MAX_IMAGE_SIZE), Image.LANCZOS)
            
            images.append((page_num + 1, img))
            logger.info(f"Extracted image from page {page_num + 1}: {img.size}")
        
        self.images = images
        return images
    
    @property
    def page_count(self) -> int:
        """Get the number of pages in the PDF."""
        if not self.doc:
            raise RuntimeError("PDF document not opened.")
        return len(self.doc)
    
    @property
    def pdf_name(self) -> str:
        """Get the PDF filename without extension."""
        return self.pdf_path.stem
