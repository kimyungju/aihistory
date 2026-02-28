# tests/test_pdf_builder.py
import pytest
from pathlib import Path
from PIL import Image
from src.pdf_builder import build_pdf_from_images


def test_build_pdf_from_images(tmp_path):
    """Images are combined into a single PDF in page order."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()

    # Create 3 small test images
    for i in range(1, 4):
        img = Image.new("RGB", (100, 100), color=(i * 50, i * 50, i * 50))
        img.save(pages_dir / f"page_{i:04d}.jpg")

    output_pdf = tmp_path / "output.pdf"
    build_pdf_from_images(pages_dir, output_pdf)

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0

    # Verify page count
    from pypdf import PdfReader
    reader = PdfReader(str(output_pdf))
    assert len(reader.pages) == 3
