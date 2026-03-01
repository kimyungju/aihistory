# tests/test_pipeline.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from PIL import Image
from pypdf import PdfWriter

from src.ocr.pipeline import run_ocr_pipeline


def _create_test_pdf(path: Path, num_pages: int = 2) -> None:
    """Create a minimal PDF with blank pages."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        writer.write(f)


def _create_test_images(images_dir: Path, count: int = 3) -> None:
    """Create test JPEG images."""
    images_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        img = Image.new("RGB", (100, 100), color=(i * 50, i * 50, i * 50))
        img.save(images_dir / f"page_{i:04d}.jpg")


def _create_doc_images(images_dir: Path, doc_id: str, count: int) -> None:
    """Create test images in a per-document subdirectory."""
    doc_dir = images_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        img = Image.new("RGB", (100, 100), color=(i * 30, i * 30, i * 30))
        img.save(doc_dir / f"page_{i:04d}.jpg")


@pytest.mark.asyncio
async def test_run_ocr_pipeline(tmp_path):
    """Pipeline extracts pages and runs OCR on all images."""
    volume_dir = tmp_path / "CO273_534"

    # Create test images (simulating already-extracted pages)
    images_dir = volume_dir / "images"
    _create_test_images(images_dir, count=3)

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Transcribed text"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("src.ocr.pipeline.get_gemini_model", return_value=mock_model):
        result = await run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id="CO273_534",
            concurrency=2,
        )

    assert result["total_pages"] == 3
    assert len(result["completed_pages"]) == 3

    # Check output files exist
    ocr_dir = volume_dir / "ocr"
    assert (ocr_dir / "page_0001.txt").exists()
    assert (ocr_dir / "page_0001.json").exists()
    assert (ocr_dir / "page_0003.txt").exists()


@pytest.mark.asyncio
async def test_run_ocr_pipeline_resumes(tmp_path):
    """Pipeline skips already-completed pages on resume."""
    volume_dir = tmp_path / "CO273_534"
    images_dir = volume_dir / "images"
    _create_test_images(images_dir, count=3)

    # Pre-populate manifest with page 1 already done
    manifest_path = volume_dir / "ocr_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "volume_id": "CO273_534",
        "total_pages": 3,
        "completed_pages": ["1"],
        "failed_pages": [],
        "doc_page_map": {},
    }))

    # Also create the existing output for page 1
    ocr_dir = volume_dir / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    (ocr_dir / "page_0001.txt").write_text("Already done")

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "New transcription"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("src.ocr.pipeline.get_gemini_model", return_value=mock_model):
        result = await run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id="CO273_534",
            concurrency=2,
        )

    # Only pages 2 and 3 should have been OCR'd
    assert mock_model.generate_content_async.call_count == 2
    assert len(result["completed_pages"]) == 3  # 1 (resumed) + 2 (new)


@pytest.mark.asyncio
async def test_run_ocr_pipeline_per_doc_subdirs(tmp_path):
    """Pipeline traverses per-document subdirectories under images/."""
    volume_dir = tmp_path / "CO273_534"
    images_dir = volume_dir / "images"

    _create_doc_images(images_dir, "GALE_AAA111", count=2)
    _create_doc_images(images_dir, "GALE_BBB222", count=3)

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Transcribed text"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("src.ocr.pipeline.get_gemini_model", return_value=mock_model):
        result = await run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id="CO273_534",
            concurrency=2,
        )

    # 5 total pages across 2 documents
    assert len(result["completed_pages"]) == 5

    # OCR output mirrors per-document structure
    ocr_dir = volume_dir / "ocr"
    assert (ocr_dir / "GALE_AAA111" / "page_0001.txt").exists()
    assert (ocr_dir / "GALE_BBB222" / "page_0003.txt").exists()

    # Metadata includes source_document
    meta = json.loads((ocr_dir / "GALE_AAA111" / "page_0001.json").read_text())
    assert meta["source_document"] == "GALE_AAA111"
