# src/ocr/gemini_ocr.py
"""Send page images to Gemini Vision for OCR transcription."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from src.ocr.config import OCR_PROMPTS, OCR_PROMPT, GEMINI_MODEL


def build_page_metadata(
    page_num: int,
    volume_id: str,
    source_document: str,
    text: str,
    model: str,
) -> dict:
    """Build metadata dict for an OCR'd page."""
    illegible_count = len(re.findall(r"\[illegible\]", text, re.IGNORECASE))
    return {
        "page_num": page_num,
        "volume_id": volume_id,
        "source_document": source_document,
        "model": model,
        "text": text,
        "illegible_count": illegible_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def ocr_single_page(
    model,
    image_path: Path,
    page_num: int,
    volume_id: str,
    source_document: str,
    output_dir: Path,
    prompt_key: str = "general",
) -> bool:
    """Run Gemini Vision OCR on a single page image.

    Args:
        model: Gemini GenerativeModel instance.
        image_path: Path to the page JPEG image.
        page_num: Page number for filenames and metadata.
        volume_id: Volume identifier (e.g., "CO273_534").
        source_document: Source document ID (e.g., "GALE_AAA111").
        output_dir: Directory to save .txt and .json output.
        prompt_key: Which prompt variant to use (general/tabular/handwritten).

    Returns:
        True on success, False on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        prompt = OCR_PROMPTS.get(prompt_key, OCR_PROMPT)
        img = Image.open(image_path)
        response = await model.generate_content_async([prompt, img])
        text = response.text

        # Save plain text
        txt_path = output_dir / f"page_{page_num:04d}.txt"
        txt_path.write_text(text, encoding="utf-8")

        # Save metadata JSON
        metadata = build_page_metadata(
            page_num=page_num,
            volume_id=volume_id,
            source_document=source_document,
            text=text,
            model=GEMINI_MODEL,
        )
        metadata["prompt_key"] = prompt_key
        json_path = output_dir / f"page_{page_num:04d}.json"
        json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return True

    except Exception as e:
        print(f"  OCR failed for page {page_num}: {e}")
        return False
