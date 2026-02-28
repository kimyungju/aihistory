# tests/test_extract.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from pypdf import PdfWriter

from src.ocr.extract import extract_pages_from_pdf, extract_volume_pages


def _create_test_pdf(path: Path, num_pages: int = 3) -> None:
    """Create a minimal PDF with blank pages for testing."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)  # Letter size
    with open(path, "wb") as f:
        writer.write(f)


def test_extract_pages_from_pdf(tmp_path):
    """Pages are extracted as JPEG images from a PDF."""
    pdf_path = tmp_path / "test.pdf"
    output_dir = tmp_path / "images"
    _create_test_pdf(pdf_path, num_pages=3)

    pages = extract_pages_from_pdf(pdf_path, output_dir, start_page_num=1)

    assert pages == 3
    assert len(list(output_dir.glob("*.jpg"))) == 3
    assert (output_dir / "page_0001.jpg").exists()
    assert (output_dir / "page_0002.jpg").exists()
    assert (output_dir / "page_0003.jpg").exists()


def test_extract_pages_continuous_numbering(tmp_path):
    """Page numbering continues from start_page_num."""
    pdf_path = tmp_path / "test.pdf"
    output_dir = tmp_path / "images"
    _create_test_pdf(pdf_path, num_pages=2)

    pages = extract_pages_from_pdf(pdf_path, output_dir, start_page_num=10)

    assert (output_dir / "page_0010.jpg").exists()
    assert (output_dir / "page_0011.jpg").exists()


def test_extract_volume_pages(tmp_path):
    """All PDFs in a volume's documents/ dir are extracted with continuous numbering."""
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    images_dir = tmp_path / "images"

    _create_test_pdf(docs_dir / "GALE_AAA111.pdf", num_pages=2)
    _create_test_pdf(docs_dir / "GALE_BBB222.pdf", num_pages=3)

    result = extract_volume_pages(docs_dir, images_dir)

    assert result["total_pages"] == 5
    assert len(result["doc_page_map"]) == 2
    assert len(list(images_dir.glob("*.jpg"))) == 5
    # Continuous numbering: 1-2 from first PDF, 3-5 from second
    assert (images_dir / "page_0001.jpg").exists()
    assert (images_dir / "page_0005.jpg").exists()
