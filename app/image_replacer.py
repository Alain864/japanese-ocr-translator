"""
image_replacer.py
─────────────────────────────────────────────
Replaces Japanese text with English translations in images.
Uses bounding box coordinates and styling info from OCR results.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config.settings import (
    BACKGROUND_FILL_COLOR,
    BBOX_PADDING,
    MIN_FONT_SIZE,
    MAX_FONT_SIZE,
    TEXT_INSET,
    LINE_SPACING,
    TEXT_ERASE_PADDING,
    TEXT_ERASE_THRESHOLD,
    TEXT_ERASE_DILATE,
    BUBBLE_DETECT_THRESHOLD,
    BUBBLE_PADDING,
    BUBBLE_MIN_AREA,
    RENDER_BOX_PADDING_PCT,
    ENGLISH_FONT,
    FALLBACK_FONT,
    TEXT_PADDING,
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
                bubble_norm = extraction.get("bubble_box") or extraction.get("speech_bubble_box")
                styling = extraction.get("styling", {})

                if not bbox_norm or not english:
                    log.warning(
                        f"  [{page_label}] Extraction {i}: missing bbox or translation, skipping"
                    )
                    fail_count += 1
                    continue

                # Convert normalized coords to pixels
                text_bbox_px = self._normalize_to_pixels(
                    bbox_norm, img_width, img_height, pad=True, pad_px=TEXT_ERASE_PADDING
                )
                if not text_bbox_px:
                    log.warning(
                        f"  [{page_label}] Extraction {i}: invalid bounding box, skipping"
                    )
                    fail_count += 1
                    continue

                # Use bubble box for rendering when available (larger area -> bigger text)
                render_bbox_px = text_bbox_px
                if bubble_norm:
                    bubble_bbox_px = self._normalize_to_pixels(
                        bubble_norm, img_width, img_height, pad=True, pad_px=BBOX_PADDING
                    )
                    if bubble_bbox_px:
                        # Expand slightly to allow larger text inside the bubble
                        expanded_bubble = self._expand_bbox(
                            bubble_bbox_px, img_width, img_height, RENDER_BOX_PADDING_PCT, BBOX_PADDING
                        )
                        text_area = (text_bbox_px[2] - text_bbox_px[0]) * (text_bbox_px[3] - text_bbox_px[1])
                        bubble_area = (expanded_bubble[2] - expanded_bubble[0]) * (expanded_bubble[3] - expanded_bubble[1])
                        if bubble_area >= int(text_area * 1.1):
                            render_bbox_px = expanded_bubble
                else:
                    # No bubble box: expand render area more aggressively
                    render_bbox_px = self._expand_bbox(
                        text_bbox_px, img_width, img_height, RENDER_BOX_PADDING_PCT, BBOX_PADDING
                    )
                # SIMPLE APPROACH: Just paint white rectangle over the original text
                self._erase_text_simple(draw, text_bbox_px)

                # Render English text in the same bbox
                success = self._render_text(
                    draw, english, text_bbox_px, styling, page_label, i
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
        self,
        bbox_norm: Dict,
        img_width: int,
        img_height: int,
        pad: bool = True,
        pad_px: Optional[int] = None,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Convert normalized bounding box (0-1) to pixel coordinates.

        Parameters
        ----------
        bbox_norm : dict
            Bounding box with normalized coordinates (0-1).
        img_width : int
            Image width in pixels.
        img_height : int
            Image height in pixels.
        pad : bool
            Whether to add padding around the box.
        pad_px : int, optional
            Padding in pixels. If None and pad=True, uses TEXT_ERASE_PADDING from settings.

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

            if pad:
                # Use either explicit padding or TEXT_ERASE_PADDING
                if pad_px is not None:
                    pad_val = max(0, int(pad_px))
                else:
                    # More generous padding: use explicit TEXT_ERASE_PADDING
                    pad_val = TEXT_ERASE_PADDING
                    
                x1 = max(0, x1 - pad_val)
                y1 = max(0, y1 - pad_val)
                x2 = min(img_width, x2 + pad_val)
                y2 = min(img_height, y2 + pad_val)

            return (x1, y1, x2, y2)

        except (ValueError, TypeError):
            return None

    @staticmethod
    def _expand_bbox(
        bbox: Tuple[int, int, int, int],
        img_width: int,
        img_height: int,
        pct: float,
        min_pad: int,
    ) -> Tuple[int, int, int, int]:
        """
        Expand a pixel bbox by a percentage of its size.
        """
        x1, y1, x2, y2 = bbox
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        pad_x = max(min_pad, int(w * pct))
        pad_y = max(min_pad, int(h * pct))

        nx1 = max(0, x1 - pad_x)
        ny1 = max(0, y1 - pad_y)
        nx2 = min(img_width, x2 + pad_x)
        ny2 = min(img_height, y2 + pad_y)

        if nx2 <= nx1 or ny2 <= ny1:
            return bbox
        return (nx1, ny1, nx2, ny2)

    def _erase_text_simple(self, draw: ImageDraw.Draw, bbox: Tuple[int, int, int, int]):
        """
        Simple approach: fill the bounding box with white background color.
        This reliably hides the original Japanese text without complex pixel analysis.
        """
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            return
        
        # Draw filled white rectangle over the bounding box
        draw.rectangle([x1, y1, x2, y2], fill=BACKGROUND_FILL_COLOR)

    def _detect_bubble_region(
        self, img: Image.Image, text_bbox: Tuple[int, int, int, int]
    ) -> Optional[Tuple[Tuple[int, int, int, int], Image.Image, Tuple[int, int, int, int]]]:
        """
        Detect the speech bubble interior by flood-filling white regions.
        More robust handling with fallback for detection failures.
        
        Returns (bubble_bbox, bubble_mask, bubble_crop_box) or None.
        """
        x1, y1, x2, y2 = text_bbox
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            return None

        # Expand search area around the text - more aggressive
        pad = int(max(w, h) * 1.2)
        crop_x1 = max(0, x1 - pad)
        crop_y1 = max(0, y1 - pad)
        crop_x2 = min(img.width, x2 + pad)
        crop_y2 = min(img.height, y2 + pad)
        crop_box = (crop_x1, crop_y1, crop_x2, crop_y2)

        crop = img.crop(crop_box)
        gray = crop.convert("L")

        # Threshold to isolate white/light bubble interiors
        thresh = max(0, min(255, BUBBLE_DETECT_THRESHOLD))
        binary = gray.point(lambda p: 255 if p >= thresh else 0)

        # Seed point: center of the text box within the crop
        seed_x = max(0, min(crop.width - 1, x1 - crop_x1 + w // 2))
        seed_y = max(0, min(crop.height - 1, y1 - crop_y1 + h // 2))

        # If seed isn't in white area, try a wider search
        if binary.getpixel((seed_x, seed_y)) == 0:
            found = False
            # Try multiple offset directions with larger offsets
            offsets = [(-5, 0), (5, 0), (0, -5), (0, 5), (-8, -8), (8, 8), 
                      (-10, 0), (10, 0), (0, -10), (0, 10), (-3, -3), (3, 3)]
            for dx, dy in offsets:
                sx = max(0, min(crop.width - 1, seed_x + dx))
                sy = max(0, min(crop.height - 1, seed_y + dy))
                if binary.getpixel((sx, sy)) == 255:
                    seed_x, seed_y = sx, sy
                    found = True
                    break
            if not found:
                # If no white region found, bubble detection failed
                # Return None - will fall back to regular text erasing
                return None

        # Flood fill the white region
        fill_value = 128
        try:
            ImageDraw.floodfill(binary, (seed_x, seed_y), fill_value, thresh=0)
        except Exception:
            # Flood fill can fail in some cases, return None
            return None

        # Mask of filled region
        mask = binary.point(lambda p: 255 if p == fill_value else 0)
        bbox = mask.getbbox()
        if not bbox:
            return None

        mx1, my1, mx2, my2 = bbox
        bubble_area = (mx2 - mx1) * (my2 - my1)
        if bubble_area < BUBBLE_MIN_AREA:
            # Bubble too small, ignore
            return None

        # Add small padding inside the bubble bounds
        pad_in = max(0, BUBBLE_PADDING)
        mx1 = max(0, mx1 + pad_in)
        my1 = max(0, my1 + pad_in)
        mx2 = min(crop.width, mx2 - pad_in)
        my2 = min(crop.height, my2 - pad_in)

        # Validate the padded bubble still has area
        if mx2 <= mx1 or my2 <= my1:
            return None

        bubble_bbox = (
            crop_x1 + mx1,
            crop_y1 + my1,
            crop_x1 + mx2,
            crop_y1 + my2,
        )
        
        try:
            bubble_mask = mask.crop((mx1, my1, mx2, my2))
        except Exception:
            return None
            
        bubble_crop_box = (crop_x1 + mx1, crop_y1 + my1, crop_x1 + mx2, crop_y1 + my2)

        log.debug(
            f"Detected bubble: area={bubble_area}px, "
            f"bbox=({bubble_bbox[0]}, {bubble_bbox[1]}, {bubble_bbox[2]}, {bubble_bbox[3]})"
        )
        return bubble_bbox, bubble_mask, bubble_crop_box

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
        if not text or not bbox:
            return False
            
        x1, y1, x2, y2 = bbox

        # Apply internal text padding for better spacing
        x1 += TEXT_PADDING
        y1 += TEXT_PADDING
        x2 -= TEXT_PADDING
        y2 -= TEXT_PADDING

        box_width = x2 - x1
        box_height = y2 - y1

        if box_width <= 0 or box_height <= 0:
            log.debug(f"  [{page_label}] Extraction {extraction_num}: box too small after padding")
            return False

        # Determine if text should be bold/italic
        is_bold = styling.get("bold", False)
        is_italic = styling.get("italic", False)

        # Apply inset to keep text off the edges
        inset = max(0, TEXT_INSET)
        x1_in = min(x2, x1 + inset)
        y1_in = min(y2, y1 + inset)
        x2_in = max(x1_in, x2 - inset)
        y2_in = max(y1_in, y2 - inset)
        inner_width = max(1, x2_in - x1_in)
        inner_height = max(1, y2_in - y1_in)

        # Find the largest font size that fits both width and height
        font_size, font, wrapped_lines, line_height, total_text_height = self._fit_text(
            text, inner_width, inner_height, draw, is_bold, is_italic
        )

        if font is None:
            log.warning(f"  [{page_label}] Extraction {extraction_num}: could not load font")
            return False

        # Line spacing between lines (in addition to font line height)
        line_spacing = LINE_SPACING

        if total_text_height > inner_height:
            log.debug(
                f"  [{page_label}] Extraction {extraction_num}: "
                f"text height {total_text_height}px exceeds box height {box_height}px (font size: {font_size}px)"
            )

        # Calculate starting Y position to center the text block vertically
        y_start = y1_in + max(0, (inner_height - total_text_height) // 2)

        # Draw each line centered horizontally
        try:
            current_y = y_start
            for idx, line in enumerate(wrapped_lines):
                if not line.strip():
                    # Skip empty lines
                    current_y += line_height
                    continue
                    
                # Get line width for centering
                try:
                    bbox_result = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox_result[2] - bbox_result[0]
                except Exception:
                    line_width = inner_width  # Fallback

                # Center horizontally, but clamp to box boundaries
                x_pos = max(x1_in, x1_in + (inner_width - line_width) // 2)
                x_pos = min(x_pos, x2_in - line_width)
                
                # Draw the line
                draw.text((x_pos, current_y), line, fill=(0, 0, 0), font=font)

                # Add line spacing (except after last line)
                if idx < len(wrapped_lines) - 1:
                    current_y += int(line_height * line_spacing)
                else:
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
            ascent, descent = font.getmetrics()
            return int((ascent + descent) * LINE_SPACING)
        except Exception:
            # Fallback: estimate based on font size
            try:
                return int(font.size * LINE_SPACING)
            except Exception:
                return 12  # Default fallback

    def _fit_text(
        self,
        text: str,
        max_width: int,
        max_height: int,
        draw: ImageDraw.Draw,
        bold: bool,
        italic: bool,
    ) -> Tuple[int, ImageFont.FreeTypeFont, List[str], int, int]:
        """
        Find an appropriate font size that fits within max_width/max_height.
        
        AGGRESSIVE APPROACH: Prioritizes large readable font over strict height fitting.
        - Max font size capped at MAX_FONT_SIZE (default 66px)
        - Allows text to wrap and use more height if needed
        - Focuses on width constraint (text must fit horizontally)
        
        Returns font size, font, wrapped lines, line height, total text height.
        """
        # Start at maximum and work down if needed
        # This is the opposite of before - tries big fonts first
        
        low = MIN_FONT_SIZE
        high = MAX_FONT_SIZE

        best_size = MIN_FONT_SIZE
        best_font = self._load_font(best_size, bold, italic)
        best_lines = self._wrap_text(text, best_font, max_width, draw)
        best_line_height = self._get_line_height(best_font, draw)
        best_total_height = len(best_lines) * best_line_height

        while low <= high:
            mid = (low + high) // 2
            font = self._load_font(mid, bold, italic)
            lines = self._wrap_text(text, font, max_width, draw)
            line_height = self._get_line_height(font, draw)
            total_height = len(lines) * line_height

            # PRIMARY CONSTRAINT: Check width (text must fit horizontally)
            fits_width = True
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                if (bbox[2] - bbox[0]) > max_width:
                    fits_width = False
                    break

            # SECONDARY CONSTRAINT: Height (allow some overflow for readability)
            # Allow height up to 120% of available for better typography
            fits_height = total_height <= int(max_height * 1.2)
            
            # Accept if width fits and height is reasonable
            if fits_width and fits_height:
                best_size = mid
                best_font = font
                best_lines = lines
                best_line_height = line_height
                best_total_height = total_height
                low = mid + 1  # Try larger - aggressive search
            else:
                high = mid - 1  # Too big or doesn't fit width, try smaller

        return best_size, best_font, best_lines, best_line_height, best_total_height

    def _load_font(self, size: int, bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
        """
        Load a font with the specified size and styling.

        Parameters
        ----------
        size : int
            Font size in pixels.
        bold : bool
            Whether to try loading bold variant.
        italic : bool
            Whether to try loading italic variant.

        Returns
        -------
        ImageFont.FreeTypeFont
            Loaded font, or PIL default if loading fails.
        """
        # Ensure size is within valid range
        size = max(MIN_FONT_SIZE, int(size))
        
        # For simplicity, we'll ignore bold/italic font file variants
        # and just note them in the logs. PIL doesn't easily support
        # font file variant selection (Arial-Bold.ttf vs Arial.ttf).
        # Most system fonts don't expose styled variants as separate files.
        
        # Try primary font
        if self._primary_font_path:
            try:
                font = ImageFont.truetype(str(self._primary_font_path), size)
                if font is not None:
                    return font
            except Exception as e:
                log.debug(f"Failed to load primary font {self._primary_font_path}: {e}")

        # Try fallback
        if self._fallback_font_path:
            try:
                font = ImageFont.truetype(str(self._fallback_font_path), size)
                if font is not None:
                    return font
            except Exception as e:
                log.debug(f"Failed to load fallback font {self._fallback_font_path}: {e}")

        # Use PIL default with better handling
        try:
            # PIL default font (doesn't support size parameter)
            default_font = ImageFont.load_default()
            log.warning(f"Using PIL default font (size not controllable, requested {size}px)")
            return default_font
        except Exception:
            # Last resort fallback
            log.error("Could not load any font, rendering may fail")
            return None

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
