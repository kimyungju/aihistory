import pytest
from pathlib import Path
from PIL import Image
from src.pdf_builder import build_volume_pdf


def _create_test_jpg(path: Path, width: int = 100, height: int = 100) -> None:
    """Helper: create a small test JPG image."""
    img = Image.new("RGB", (width, height), color="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG")
    img.close()


def test_build_volume_pdf(tmp_path):
    """Page images across documents are combined into a single PDF."""
    images_dir = tmp_path / "images"

    # Create 2 document subdirectories with page images
    doc1 = images_dir / "GALE_DOC001"
    _create_test_jpg(doc1 / "page_0001.jpg")
    _create_test_jpg(doc1 / "page_0002.jpg")

    doc2 = images_dir / "GALE_DOC002"
    _create_test_jpg(doc2 / "page_0001.jpg")
    _create_test_jpg(doc2 / "page_0002.jpg")
    _create_test_jpg(doc2 / "page_0003.jpg")

    output_pdf = tmp_path / "volume.pdf"
    total = build_volume_pdf(images_dir, output_pdf)

    assert output_pdf.exists()
    assert total == 5  # 2 + 3
    assert output_pdf.stat().st_size > 0


def test_build_volume_pdf_empty_dir(tmp_path):
    """Building from directory with no images raises FileNotFoundError."""
    empty_dir = tmp_path / "images"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        build_volume_pdf(empty_dir, tmp_path / "output.pdf")


def test_build_volume_pdf_missing_dir(tmp_path):
    """Building from non-existent directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        build_volume_pdf(tmp_path / "nonexistent", tmp_path / "output.pdf")
