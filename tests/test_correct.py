# tests/test_correct.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.ocr.correct import correct_single_page, CORRECTION_PROMPT


def test_correction_prompt_exists():
    """Correction prompt is defined."""
    assert isinstance(CORRECTION_PROMPT, str)
    assert len(CORRECTION_PROMPT) > 50


@pytest.mark.asyncio
async def test_correct_single_page(tmp_path):
    """Correction pass reads OCR text and writes corrected version."""
    ocr_dir = tmp_path / "ocr" / "GALE_AAA111"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "page_0001.txt").write_text(
        "Tle Governor of tbe Straits Settlements", encoding="utf-8"
    )

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "The Governor of the Straits Settlements"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await correct_single_page(
        model=mock_model,
        page_txt_path=ocr_dir / "page_0001.txt",
    )
    assert result is True

    corrected = (ocr_dir / "page_0001.txt").read_text(encoding="utf-8")
    assert corrected == "The Governor of the Straits Settlements"

    # Original preserved as backup
    assert (ocr_dir / "page_0001.raw.txt").exists()


@pytest.mark.asyncio
async def test_correct_single_page_skips_if_corrected(tmp_path):
    """Skips correction if .raw.txt backup already exists."""
    ocr_dir = tmp_path / "ocr"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "page_0001.txt").write_text("corrected text", encoding="utf-8")
    (ocr_dir / "page_0001.raw.txt").write_text("raw text", encoding="utf-8")

    mock_model = MagicMock()
    result = await correct_single_page(
        model=mock_model,
        page_txt_path=ocr_dir / "page_0001.txt",
    )
    assert result is True
    # Model should not have been called
    mock_model.generate_content_async.assert_not_called()
