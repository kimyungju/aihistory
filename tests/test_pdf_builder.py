import pytest
from pathlib import Path
from pypdf import PdfWriter
from src.pdf_builder import merge_pdfs


def _create_test_pdf(path: Path, num_pages: int = 1) -> None:
    """Helper: create a small test PDF with the given number of pages."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


def test_merge_pdfs(tmp_path):
    """Multiple PDFs are merged into one with correct total page count."""
    pdf_dir = tmp_path / "documents"
    pdf_dir.mkdir()

    # Create 3 test PDFs with different page counts
    _create_test_pdf(pdf_dir / "doc_001.pdf", num_pages=2)
    _create_test_pdf(pdf_dir / "doc_002.pdf", num_pages=3)
    _create_test_pdf(pdf_dir / "doc_003.pdf", num_pages=1)

    output_pdf = tmp_path / "merged.pdf"
    total = merge_pdfs(pdf_dir, output_pdf)

    assert output_pdf.exists()
    assert total == 6  # 2 + 3 + 1


def test_merge_pdfs_empty_dir(tmp_path):
    """Merging from directory with no PDFs raises FileNotFoundError."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        merge_pdfs(empty_dir, tmp_path / "output.pdf")
