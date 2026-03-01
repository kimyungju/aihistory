# tests/test_gemini_ocr.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from src.ocr.config import OCR_PROMPTS
from src.ocr.gemini_ocr import ocr_single_page, build_page_metadata


def test_build_page_metadata():
    """Metadata JSON is built correctly from OCR result."""
    result = build_page_metadata(
        page_num=5,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        text="Some transcribed text with [illegible] parts",
        model="gemini-2.0-flash",
    )

    assert result["page_num"] == 5
    assert result["volume_id"] == "CO273_534"
    assert result["source_document"] == "GALE_AAA111"
    assert result["model"] == "gemini-2.0-flash"
    assert result["text"] == "Some transcribed text with [illegible] parts"
    assert result["illegible_count"] == 1
    assert "timestamp" in result


def test_build_page_metadata_no_illegible():
    """Illegible count is 0 when no markers present."""
    result = build_page_metadata(
        page_num=1,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        text="Clear text with no issues",
        model="gemini-2.0-flash",
    )
    assert result["illegible_count"] == 0


@pytest.mark.asyncio
async def test_ocr_single_page_success(tmp_path):
    """Successful OCR returns text and saves files."""
    # Create a fake image
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    img_path = tmp_path / "page_0001.jpg"
    img.save(str(img_path))

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Transcribed colonial text here"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await ocr_single_page(
        model=mock_model,
        image_path=img_path,
        page_num=1,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        output_dir=tmp_path / "ocr",
    )

    assert result is True
    assert (tmp_path / "ocr" / "page_0001.txt").exists()
    assert (tmp_path / "ocr" / "page_0001.json").exists()

    text = (tmp_path / "ocr" / "page_0001.txt").read_text()
    assert text == "Transcribed colonial text here"

    metadata = json.loads((tmp_path / "ocr" / "page_0001.json").read_text())
    assert metadata["page_num"] == 1
    assert metadata["volume_id"] == "CO273_534"


def test_ocr_prompts_has_variants():
    """OCR_PROMPTS dict has all 3 variant keys."""
    assert "general" in OCR_PROMPTS
    assert "tabular" in OCR_PROMPTS
    assert "handwritten" in OCR_PROMPTS
    for key, prompt in OCR_PROMPTS.items():
        assert isinstance(prompt, str)
        assert len(prompt) > 50


@pytest.mark.asyncio
async def test_ocr_single_page_uses_prompt_variant(tmp_path):
    """ocr_single_page accepts a prompt_key parameter."""
    from PIL import Image
    img = Image.new("RGB", (100, 100))
    img_path = tmp_path / "page_0001.jpg"
    img.save(str(img_path))

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Table text"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await ocr_single_page(
        model=mock_model,
        image_path=img_path,
        page_num=1,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        output_dir=tmp_path / "ocr",
        prompt_key="tabular",
    )
    assert result is True

    # Verify the tabular prompt was used (not the general one)
    call_args = mock_model.generate_content_async.call_args[0][0]
    prompt_used = call_args[0]
    assert "table" in prompt_used.lower() or "column" in prompt_used.lower()
