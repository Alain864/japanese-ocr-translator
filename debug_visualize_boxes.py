"""
debug_visualize_boxes.py
─────────────────────────────────────────────
Visualizes bounding boxes and bubble boxes from extractions.json
to debug coordinate accuracy from GPT-4o Vision.

Usage:
    python debug_visualize_boxes.py

Output:
    Creates debug_output/ folder with annotated images showing:
    - RED: bounding_box (tight text box)
    - BLUE: bubble_box (speech bubble area)
    - GREEN: background coverage area (bubble_box + padding)
"""

import json
from pathlib import Path
from PIL import Image, ImageDraw

from app.pdf_converter import pdf_to_images
from config.settings import INPUT_FOLDER, OUTPUT_FOLDER

# Debug output folder
DEBUG_OUTPUT = Path(__file__).parent / "debug_output"
DEBUG_OUTPUT.mkdir(exist_ok=True)

# Colors for visualization
COLOR_BOUNDING_BOX = (255, 0, 0, 200)      # Red - tight text box
COLOR_BUBBLE_BOX = (0, 0, 255, 200)        # Blue - speech bubble
COLOR_BACKGROUND = (0, 255, 0, 100)        # Green - what we actually cover

# Padding values from image_replacer.py
BG_PADDING_WITH_BUBBLE = 18
BG_PADDING_WITHOUT_BUBBLE = 30
TEXT_PADDING = 3


def normalize_to_pixels(bbox_norm, img_width, img_height, padding=0):
    """Convert normalized coordinates to pixels with padding."""
    x = float(bbox_norm.get("x", 0))
    y = float(bbox_norm.get("y", 0))
    w = float(bbox_norm.get("width", 0))
    h = float(bbox_norm.get("height", 0))

    x1 = int(x * img_width)
    y1 = int(y * img_height)
    x2 = int((x + w) * img_width)
    y2 = int((y + h) * img_height)

    # Add padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img_width, x2 + padding)
    y2 = min(img_height, y2 + padding)

    return (x1, y1, x2, y2)


def draw_box(draw, bbox, color, width=3, label=None):
    """Draw a rectangle with optional label."""
    draw.rectangle(bbox, outline=color, width=width)

    if label:
        # Draw label background
        text_bbox = draw.textbbox((bbox[0], bbox[1] - 20), label)
        draw.rectangle(text_bbox, fill=color)
        draw.text((bbox[0], bbox[1] - 20), label, fill=(255, 255, 255))


def main():
    print("=" * 70)
    print("DEBUG: Visualizing Bounding Boxes from GPT-4o Vision")
    print("=" * 70)
    print()

    # Load extractions
    extractions_file = OUTPUT_FOLDER / "extractions.json"
    if not extractions_file.exists():
        print(f"❌ Error: {extractions_file} not found")
        print("   Run: python main.py --stage ocr first")
        return

    with open(extractions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Process each PDF
    for file_data in data.get("files", []):
        pdf_name = file_data.get("file")
        pdf_path = INPUT_FOLDER / pdf_name

        if not pdf_path.exists():
            print(f"⚠️  Skipping {pdf_name} (not found)")
            continue

        print(f"📄 Processing: {pdf_name}")

        # Convert PDF to images
        images = pdf_to_images(pdf_path)

        # Process each page
        for page_data in file_data.get("pages", []):
            page_num = page_data.get("page_number")
            extractions = page_data.get("extractions", [])

            if not extractions:
                continue

            print(f"   Page {page_num}: {len(extractions)} extraction(s)")

            # Get the image for this page
            img = images[page_num - 1].copy()
            img_width, img_height = img.size

            # Create a semi-transparent overlay for filled rectangles
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            draw = ImageDraw.Draw(img)

            # Draw each extraction
            for i, extraction in enumerate(extractions, 1):
                bbox_norm = extraction.get("bounding_box", {})
                bubble_box_norm = extraction.get("bubble_box", {})
                english = extraction.get("english_translation", "")

                if not bbox_norm:
                    continue

                has_bubble = bool(bubble_box_norm)

                # 1. Draw bounding_box (RED) - tight text box
                bbox_px = normalize_to_pixels(bbox_norm, img_width, img_height, padding=0)
                draw_box(draw, bbox_px, COLOR_BOUNDING_BOX, width=2,
                        label=f"#{i} bbox")

                # 2. Draw bubble_box (BLUE) if available
                if has_bubble:
                    bubble_px = normalize_to_pixels(bubble_box_norm, img_width, img_height, padding=0)
                    draw_box(draw, bubble_px, COLOR_BUBBLE_BOX, width=2,
                            label=f"#{i} bubble")

                    # 3. Draw background coverage (GREEN) - what we actually paint white
                    bg_px = normalize_to_pixels(bubble_box_norm, img_width, img_height,
                                               padding=BG_PADDING_WITH_BUBBLE)
                    draw_overlay.rectangle(bg_px, fill=COLOR_BACKGROUND)
                else:
                    # No bubble_box - use padded bounding_box for background
                    bg_px = normalize_to_pixels(bbox_norm, img_width, img_height,
                                               padding=BG_PADDING_WITHOUT_BUBBLE)
                    draw_overlay.rectangle(bg_px, fill=COLOR_BACKGROUND)

                # Draw text placement box (where English actually goes)
                text_px = normalize_to_pixels(bbox_norm, img_width, img_height,
                                             padding=TEXT_PADDING)
                draw_box(draw, text_px, (255, 255, 0), width=1)  # Yellow - text area

            # Composite the overlay onto the image
            img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay)
            img = img.convert('RGB')

            # Save debug image
            pdf_stem = Path(pdf_name).stem
            output_file = DEBUG_OUTPUT / f"{pdf_stem}_page_{page_num:03d}_debug.png"
            img.save(output_file)
            print(f"      → Saved: {output_file}")

    print()
    print("=" * 70)
    print("✅ Debug visualization complete!")
    print(f"📂 Check output in: {DEBUG_OUTPUT}")
    print()
    print("Legend:")
    print("  🔴 RED boxes    = bounding_box (tight text area from GPT-4o)")
    print("  🔵 BLUE boxes   = bubble_box (speech bubble area from GPT-4o)")
    print("  🟢 GREEN fill   = background coverage (what gets painted white)")
    print("  🟡 YELLOW boxes = text placement area (where English goes)")
    print("=" * 70)


if __name__ == "__main__":
    main()
