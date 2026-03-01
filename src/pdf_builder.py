"""
Build per-volume PDFs from downloaded page images (JPG).

Each volume has images organized as:
    pdfs/{volume_id}/images/{doc_id}/page_NNNN.jpg

Documents are sorted by doc_id, pages within each document by filename,
producing a single continuous PDF per volume.
"""
from pathlib import Path
from PIL import Image
from pypdf import PdfWriter, PdfReader
import io


def build_volume_pdf(images_dir: Path, output_path: Path) -> int:
    """
    Build a single PDF from all page images across documents in a volume.

    Processes images one at a time to avoid memory issues with large volumes.

    Args:
        images_dir: Directory containing per-document subdirectories of JPGs
        output_path: Path for the output PDF

    Returns:
        Total number of pages in the PDF

    Raises:
        FileNotFoundError: If images_dir doesn't exist or contains no images
    """
    if not images_dir.exists():
        raise FileNotFoundError(f"Directory not found: {images_dir}")

    # Collect all JPGs across all document subdirectories, sorted by doc then page
    all_images = []
    for doc_dir in sorted(images_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        pages = sorted(doc_dir.glob("*.jpg"))
        all_images.extend(pages)

    if not all_images:
        raise FileNotFoundError(f"No JPG images found in {images_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    skipped = []

    for i, img_path in enumerate(all_images):
        try:
            img = Image.open(img_path).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "PDF")
            img.close()
            buf.seek(0)
            reader = PdfReader(buf)
            writer.add_page(reader.pages[0])
        except Exception:
            skipped.append(img_path.name)
            continue

        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(all_images)} pages processed...")

    if not writer.pages:
        raise FileNotFoundError(f"No valid images found in {images_dir}")

    if skipped:
        print(f"  WARNING: skipped {len(skipped)} corrupt images: {skipped[:10]}")

    with open(output_path, "wb") as f:
        writer.write(f)

    doc_count = sum(1 for d in images_dir.iterdir() if d.is_dir())
    total = len(writer.pages)
    print(f"Built {output_path.name}: {total} pages from {doc_count} documents")
    return total
