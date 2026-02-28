# src/pdf_builder.py
"""
Combine downloaded page images into a single PDF per volume.
"""
from pathlib import Path
from PIL import Image


def build_pdf_from_images(pages_dir: Path, output_path: Path) -> None:
    """
    Combine all page images in a directory into a single PDF.

    Images are sorted by filename to preserve page order.
    Supports .jpg, .jpeg, .png, .tiff files.
    """
    image_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}
    image_files = sorted(
        f for f in pages_dir.iterdir()
        if f.suffix.lower() in image_extensions
    )

    if not image_files:
        print(f"No images found in {pages_dir}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert all images to RGB (required for PDF)
    images = []
    for img_path in image_files:
        img = Image.open(img_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)

    # Save first image as PDF, append the rest
    first_image = images[0]
    remaining = images[1:]

    first_image.save(
        str(output_path),
        "PDF",
        save_all=True,
        append_images=remaining,
        resolution=150.0,
    )

    print(f"Built PDF: {output_path} ({len(images)} pages)")
