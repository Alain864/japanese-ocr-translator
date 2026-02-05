"""
image_replacer.py
─────────────────────────────────────────────
Replaces Japanese text with English translations in images.
Uses bounding box coordinates and styling info from OCR results.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

from config.settings import (
    BACKGROUND_FILL_COLOR,
    BBOX_PADDING,
    MIN_FONT_SIZE,
    ENGLISH_FONT,
    FALLBACK_FONT,
)
from app.logger import get_logger

log = get_logger("image_replacer")


class ImageReplacer:
    """Handles text replacement in images."""

    def __init__(self):
        """Initialize with font loading."""
        self._primary_font_path = self._find_font(ENGLISH_FONT)
        self._fallback_font_path = self._find_font(FALLBACK_FONT)
        
        if not self._primary_font_path and not self._fallback_font_path:
            log.warning("No fonts found - will use PIL default font")

    def replace_text(
        self,
        image: Image.Image,
        extractions: List[Dict],
        page_label: str = ""
    ) -> Tuple[Image.Image, int, int]:
        """
        Replace Japanese text with English in an image.

        Parameters
        ----------
        image : PIL.Image.Image
            Original image with Japanese text.
        extractions : list[dict]
            List of extraction dicts from OCR, each containing:
              - japanese_text
              - english_translation
              - bounding_box: {x, y, width, height} (normalized 0-1)
              - styling: {bold, italic}
        page_label : str
            Label for logging.

        Returns
        -------
        tuple[PIL.Image.Image, int, int]
            (modified_image, successful_replacements, failed_replacements)
        """
        if not extractions:
            log.info(f"  [{page_label}] No extractions to process")
            return image.copy(), 0, 0

        # Work on a copy
        img = image.copy()
        draw = ImageDraw.Draw(img)
        img_width, img_height = img.size

        success_count = 0
        fail_count = 0

        for i, extraction in enumerate(extractions, 1):
            try:
                # Extract data
                japanese = extraction.get("japanese_text", "")
                english = extraction.get("english_translation", "")
                bbox_norm = extraction.get("bounding_box", {})
                styling = extraction.get("styling", {})

                if not bbox_norm or not english:
                    log.warning(
                        f"  [{page_label}] Extraction {i}: missing bbox or translation, skipping"
                    )
                    fail_count += 1
                    continue

                # Convert normalized coords to pixels
                bbox_px = self._normalize_to_pixels(bbox_norm, img_width, img_height)
                if not bbox_px:
                    log.warning(
                        f"  [{page_label}] Extraction {i}: invalid bounding box, skipping"
                    )
                    fail_count += 1
                    continue

                # Draw background rectangle
                self._draw_background(draw, bbox_px)

                # Render English text
                success = self._render_text(
                    draw, english, bbox_px, styling, page_label, i
                )

                if success:
                    success_count += 1
                    log.debug(
                        f"  [{page_label}] Extraction {i}: '{japanese}' → '{english}'"
                    )
                else:
                    fail_count += 1

            except Exception as exc:
                log.error(
                    f"  [{page_label}] Extraction {i}: error during replacement: {exc}"
                )
                fail_count += 1

        log.info(
            f"  [{page_label}] Replacements: {success_count} successful, "
            f"{fail_count} failed"
        )
        return img, success_count, fail_count

    def _normalize_to_pixels(
        self, bbox_norm: Dict, img_width: int, img_height: int
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Convert normalized bounding box (0-1) to pixel coordinates.

        Returns
        -------
        tuple[int, int, int, int] or None
            (x1, y1, x2, y2) pixel coordinates, or None if invalid.
        """
        try:
            x = float(bbox_norm.get("x", 0))
            y = float(bbox_norm.get("y", 0))
            w = float(bbox_norm.get("width", 0))
            h = float(bbox_norm.get("height", 0))

            # Validate range
            if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                return None

            # Convert to pixels
            x1 = int(x * img_width)
            y1 = int(y * img_height)
            x2 = int((x + w) * img_width)
            y2 = int((y + h) * img_height)

            # Add padding
            x1 = max(0, x1 - BBOX_PADDING)
            y1 = max(0, y1 - BBOX_PADDING)
            x2 = min(img_width, x2 + BBOX_PADDING)
            y2 = min(img_height, y2 + BBOX_PADDING)

            return (x1, y1, x2, y2)

        except (ValueError, TypeError):
            return None

    def _draw_background(self, draw: ImageDraw.Draw, bbox: Tuple[int, int, int, int]):
        """Draw a filled rectangle to cover original text."""
        draw.rectangle(bbox, fill=BACKGROUND_FILL_COLOR)

    def _render_text(
        self,
        draw: ImageDraw.Draw,
        text: str,
        bbox: Tuple[int, int, int, int],
        styling: Dict,
        page_label: str,
        extraction_num: int,
    ) -> bool:
        """
        Render English text in the bounding box with appropriate styling.
        Uses multi-line wrapping if text is too long.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        x1, y1, x2, y2 = bbox
        box_width = x2 - x1
        box_height = y2 - y1

        if box_width <= 0 or box_height <= 0:
            return False

        # Determine if text should be bold/italic
        is_bold = styling.get("bold", False)
        is_italic = styling.get("italic", False)

        # Calculate initial font size based on box height
        # Start with 80% of box height as a reasonable default for single line
        initial_size = int(box_height * 0.8)
        font_size = max(initial_size, MIN_FONT_SIZE)

        # Try to load font with styling
        font = self._load_font(font_size, is_bold, is_italic)

        # Wrap text to fit in box width
        wrapped_lines = self._wrap_text(text, font, box_width, draw)
        
        # Calculate total height needed for all lines
        line_height = self._get_line_height(font, draw)
        total_text_height = len(wrapped_lines) * line_height
        
        # If wrapped text is too tall, reduce font size and re-wrap
        while total_text_height > box_height and font_size > MIN_FONT_SIZE:
            font_size -= 2  # Reduce by 2 for faster convergence
            font = self._load_font(font_size, is_bold, is_italic)
            wrapped_lines = self._wrap_text(text, font, box_width, draw)
            line_height = self._get_line_height(font, draw)
            total_text_height = len(wrapped_lines) * line_height

        if total_text_height > box_height:
            log.warning(
                f"  [{page_label}] Extraction {extraction_num}: "
                f"text still too tall after wrapping (may be truncated visually)"
            )

        # Calculate starting Y position to center the text block vertically
        y_start = y1 + (box_height - total_text_height) // 2

        # Draw each line centered horizontally
        try:
            current_y = y_start
            for line in wrapped_lines:
                # Get line width for centering
                bbox_result = draw.textbbox((0, 0), line, font=font)
                line_width = bbox_result[2] - bbox_result[0]
                
                # Center horizontally
                x_pos = x1 + (box_width - line_width) // 2
                
                # Draw the line
                draw.text((x_pos, current_y), line, fill=(0, 0, 0), font=font)
                current_y += line_height
            
            return True
        except Exception as exc:
            log.error(
                f"  [{page_label}] Extraction {extraction_num}: "
                f"failed to draw text: {exc}"
            )
            return False

    def _wrap_text(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw
    ) -> List[str]:
        """
        Wrap text to fit within max_width, breaking at word boundaries.

        Parameters
        ----------
        text : str
            The text to wrap.
        font : ImageFont.FreeTypeFont
            Font to use for measuring text width.
        max_width : int
            Maximum width in pixels.
        draw : ImageDraw.Draw
            Draw object for text measurement.

        Returns
        -------
        list[str]
            List of text lines that fit within max_width.
        """
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            # Try adding this word to the current line
            test_line = " ".join(current_line + [word])
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                width = bbox[2] - bbox[0]
            except Exception:
                # If measurement fails, estimate based on character count
                width = len(test_line) * (max_width // 20)  # rough estimate

            if width <= max_width:
                current_line.append(word)
            else:
                # Current line is full, start a new line
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                
                # Check if single word is wider than max_width
                try:
                    bbox = draw.textbbox((0, 0), word, font=font)
                    word_width = bbox[2] - bbox[0]
                except Exception:
                    word_width = len(word) * (max_width // 20)
                
                if word_width > max_width:
                    # Word is too long, will overflow but include it anyway
                    log.debug(f"Single word '{word}' exceeds max width")

        # Add the last line
        if current_line:
            lines.append(" ".join(current_line))

        # If no wrapping occurred (single line fits), return as-is
        if not lines:
            lines = [text]

        return lines

    def _get_line_height(self, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw) -> int:
        """
        Calculate the height needed for one line of text.

        Parameters
        ----------
        font : ImageFont.FreeTypeFont
            Font to measure.
        draw : ImageDraw.Draw
            Draw object for text measurement.

        Returns
        -------
        int
            Line height in pixels.
        """
        try:
            # Measure a sample text with ascenders and descenders
            bbox = draw.textbbox((0, 0), "Ayg", font=font)
            return bbox[3] - bbox[1]
        except Exception:
            # Fallback: estimate based on font size
            try:
                return font.size
            except Exception:
                return 12  # Default fallback

    def _load_font(self, size: int, bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
        """
        Load a font with the specified size and styling.

        Parameters
        ----------
        size : int
            Font size in points.
        bold : bool
            Whether to try loading bold variant.
        italic : bool
            Whether to try loading italic variant.

        Returns
        -------
        ImageFont.FreeTypeFont
            Loaded font, or PIL default if loading fails.
        """
        # For simplicity, we'll ignore bold/italic font file variants
        # and just note them in the logs. PIL doesn't easily support
        # font file variant selection (Arial-Bold.ttf vs Arial.ttf).
        # Most system fonts don't expose styled variants as separate files.
        
        # Try primary font
        if self._primary_font_path:
            try:
                return ImageFont.truetype(str(self._primary_font_path), size)
            except Exception:
                pass

        # Try fallback
        if self._fallback_font_path:
            try:
                return ImageFont.truetype(str(self._fallback_font_path), size)
            except Exception:
                pass

        # Use PIL default
        return ImageFont.load_default()

    @staticmethod
    def _find_font(font_name: str) -> Optional[Path]:
        """
        Search for a font file in common system locations.

        Parameters
        ----------
        font_name : str
            Font filename (e.g., 'Arial.ttf').

        Returns
        -------
        Path or None
            Path to font file if found, else None.
        """
        # Common font directories
        search_paths = [
            Path("/usr/share/fonts"),
            Path("/System/Library/Fonts"),  # macOS
            Path("/Library/Fonts"),  # macOS
            Path.home() / "Library/Fonts",  # macOS user
            Path("C:/Windows/Fonts"),  # Windows
        ]

        for base_path in search_paths:
            if not base_path.exists():
                continue
            # Recursively search
            for font_file in base_path.rglob(font_name):
                if font_file.is_file():
                    log.debug(f"Found font: {font_file}")
                    return font_file

        log.debug(f"Font '{font_name}' not found in system paths")
        return None