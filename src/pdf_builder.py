"""
Merge downloaded document PDFs into a single per-volume PDF.
"""
from pathlib import Path
from pypdf import PdfWriter


def merge_pdfs(pdf_dir: Path, output_path: Path) -> int:
    """
    Merge all PDF files in a directory into a single PDF.

    PDFs are sorted by filename to maintain document order.

    Args:
        pdf_dir: Directory containing individual document PDFs
        output_path: Path for the merged output PDF

    Returns:
        Total number of pages in the merged PDF

    Raises:
        FileNotFoundError: If pdf_dir doesn't exist or contains no PDFs
    """
    if not pdf_dir.exists():
        raise FileNotFoundError(f"Directory not found: {pdf_dir}")

    pdf_files = sorted(f for f in pdf_dir.iterdir() if f.suffix.lower() == ".pdf")

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {pdf_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    for pdf_path in pdf_files:
        writer.append(str(pdf_path))

    total_pages = len(writer.pages)

    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"Merged {len(pdf_files)} PDFs into {output_path} ({total_pages} pages)")
    return total_pages
