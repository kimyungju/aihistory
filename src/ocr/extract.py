# src/ocr/extract.py
"""Extract page images from document PDFs.

Reads multi-page document PDFs (from Phase 1) and extracts each page
as a JPEG image. Supports continuous page numbering across documents.
"""
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from src.ocr.config import IMAGE_FORMAT, IMAGE_QUALITY


def extract_pages_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    start_page_num: int = 1,
) -> int:
    """Extract all pages from a PDF as JPEG images.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save extracted images.
        start_page_num: Starting page number for filenames.

    Returns:
        Number of pages extracted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    num_pages = len(reader.pages)

    for i, page in enumerate(reader.pages):
        page_num = start_page_num + i

        # Extract page as image via rendering
        # pypdf doesn't render pages directly; convert page to image via
        # extracting embedded images or using pdf2image-style approach.
        # For PDFs with embedded images (like scanned docs), extract the image.
        images = page.images
        if images:
            # Use the first (usually only) image on the page
            img_data = images[0].data
            img_path = output_dir / f"page_{page_num:04d}.jpg"
            with open(img_path, "wb") as f:
                f.write(img_data)
        else:
            # Blank or text-only page — create a placeholder image
            img = Image.new("RGB", (612, 792), color=(255, 255, 255))
            img_path = output_dir / f"page_{page_num:04d}.jpg"
            img.save(str(img_path), IMAGE_FORMAT, quality=IMAGE_QUALITY)

    return num_pages


def extract_volume_pages(
    docs_dir: Path,
    images_dir: Path,
) -> dict:
    """Extract pages from all document PDFs in a volume.

    Processes PDFs in sorted filename order with continuous page numbering.

    Args:
        docs_dir: Directory containing document PDFs.
        images_dir: Directory to save extracted images.

    Returns:
        Dict with total_pages and doc_page_map (doc_id -> [start, end] pages).
    """
    pdf_files = sorted(f for f in docs_dir.iterdir() if f.suffix.lower() == ".pdf")

    if not pdf_files:
        return {"total_pages": 0, "doc_page_map": {}}

    current_page = 1
    doc_page_map = {}

    for pdf_path in pdf_files:
        doc_id = pdf_path.stem  # e.g., "GALE_AAA111"
        num_pages = extract_pages_from_pdf(pdf_path, images_dir, current_page)

        doc_page_map[doc_id] = {
            "start_page": current_page,
            "end_page": current_page + num_pages - 1,
            "num_pages": num_pages,
        }

        current_page += num_pages

    total_pages = current_page - 1
    return {"total_pages": total_pages, "doc_page_map": doc_page_map}
